"""Structural tests that permission checks live in the right place.

Three separate vulnerabilities (JobUpdate, ProblemSuggestionUpdate, DeleteFile) all
had the same shape: the object-level permission check existed, but sat in a method
that ran too late (after the write) or on only one HTTP verb (so GET leaked the
form, or POST skipped the check entirely). These tests encode the invariants that
would have caught each of them, so the mistake can't come back quietly.

Nothing here hits the database or the network; it is a static read of the URL conf
and of the view source.
"""

import ast
import pathlib
from typing import Any

import pytest
from django.urls import get_resolver
from django.urls.resolvers import URLPattern, URLResolver

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

PROJECT_APPS = (
    "aincrad",
    "arch",
    "core",
    "dashboard",
    "exams",
    "hanabi",
    "markets",
    "opal",
    "otisweb",
    "payments",
    "roster",
    "rpg",
    "suggestions",
    "tubes",
    "yearbook",
)

# Names that, appearing on a view's decorators or in its MRO, mean the view has
# decided who may reach it.
GUARD_NAMES = (
    "login_required",
    "verified_required",
    "staff_required",
    "admin_required",
    "LoginRequired",
    "StaffRequired",
    "AdminRequired",
    "VerifiedRequired",
    "Contributor",
    "Superuser",
    "Staffuser",
    "GroupRequired",
)

# Methods that run before any write and on every HTTP verb. An object-level
# permission check belongs in one of these.
SAFE_CHECK_METHODS = frozenset({"get_object", "get_queryset", "dispatch", "setup"})

# Views deliberately reachable without logging in. Each entry is a
# (url name, why) pair; adding to this list should be a conscious decision.
PUBLIC_VIEWS: dict[str | None, str] = {
    "api": "aincrad API; authenticated by a hashed token in the POST body",
    "certify": "capability URL; the checksum is verified before anything renders",
    "hanabi-contests": "public list of Hanabi contests",
    "hanabi-replays": "public results, gated on the contest being over",
    "hint-list-deprecated": "pure redirect to the guarded hint list",
    "opal-hunt-list": "public list of OPAL hunts",
    "github-landing": "public landing page",
    "oime-landing": "public landing page",
    "payments-cancelled": "static 'payment cancelled' page",
    "payments-checkout": "capability URL; checksum verified before Stripe is touched",
    "payments-config": "returns only the Stripe publishable key",
    "payments-invoice": "capability URL; checksum verified before anything renders",
    "payments-success": "static 'payment succeeded' page",
    "payments-webhook": "Stripe webhook; authenticated by signature verification",
    None: "unnamed routes are redirect shims onto named, guarded views",
}


def _iter_routes(resolver: Any, prefix: str = ""):
    for pattern in resolver.url_patterns:
        if isinstance(pattern, URLResolver):
            yield from _iter_routes(pattern, prefix + str(pattern.pattern))
        elif isinstance(pattern, URLPattern):
            yield prefix + str(pattern.pattern), pattern.callback, pattern.name


def _project_routes():
    for route, callback, name in _iter_routes(get_resolver()):
        if (getattr(callback, "__module__", "") or "").startswith(PROJECT_APPS):
            yield route, callback, name


def _decorators_by_function() -> dict[str, dict[str, list[str]]]:
    """module dotted path -> {function name: [decorator source, ...]}.

    Read from source rather than from the callable, because Django's decorators
    use functools.wraps and so leave no trace on the wrapped function.
    """
    out: dict[str, dict[str, list[str]]] = {}
    for path in REPO_ROOT.rglob("*.py"):
        text = str(path)
        if any(skip in text for skip in ("/.venv/", "/migrations/", "/site-packages/")):
            continue
        try:
            tree = ast.parse(path.read_text())
        except (SyntaxError, UnicodeDecodeError):
            continue
        module = str(path.relative_to(REPO_ROOT)).removesuffix(".py").replace("/", ".")
        out[module] = {
            node.name: [ast.unparse(d) for d in node.decorator_list]
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
    return out


def _view_classes():
    """Yield (relative path, ClassDef) for every view class defined in the project."""
    for path in sorted(REPO_ROOT.rglob("*.py")):
        text = str(path)
        if any(
            skip in text
            for skip in ("/.venv/", "/migrations/", "/site-packages/", "tests.py")
        ):
            continue
        try:
            tree = ast.parse(path.read_text())
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            bases = " ".join(ast.unparse(b) for b in node.bases)
            if "View" in bases:
                yield str(path.relative_to(REPO_ROOT)), node


def test_every_route_has_an_auth_guard():
    """Every routed view carries a guard, or is a knowing exception."""
    decorators = _decorators_by_function()
    unguarded: list[str] = []

    for route, callback, name in _project_routes():
        view_class = getattr(callback, "view_class", None)
        if view_class is not None:
            blob = " ".join(klass.__name__ for klass in view_class.__mro__)
        else:
            module = getattr(callback, "__module__", "")
            func = getattr(callback, "__name__", "")
            blob = " ".join(decorators.get(module, {}).get(func, []))
        if any(guard in blob for guard in GUARD_NAMES):
            continue
        if name in PUBLIC_VIEWS:
            continue
        unguarded.append(f"{name} (/{route}) in {callback.__module__}")

    assert not unguarded, (
        "These routes have no login/staff/admin/verified guard and are not listed "
        "in PUBLIC_VIEWS. Add the right mixin or decorator, or, if the view really "
        "is meant to be public, add it to PUBLIC_VIEWS with a reason:\n  "
        + "\n  ".join(sorted(unguarded))
    )


def _first_line_matching(fn: ast.AST, predicate) -> int | None:
    lines = [
        node.lineno
        for node in ast.walk(fn)
        if getattr(node, "lineno", None) is not None and predicate(node)
    ]
    return min(lines) if lines else None


def _denies_at(fn: ast.AST) -> int | None:
    return _first_line_matching(
        fn, lambda n: isinstance(n, ast.Raise) and "PermissionDenied" in ast.unparse(n)
    )


def _acts_at(fn: ast.AST) -> int | None:
    """First line that hands off to the parent view or writes to the database."""
    writes = (
        ".save(",
        ".delete(",
        ".create(",
        ".add(",
        ".remove(",
        ".set(",
        ".update(",
        ".get_or_create(",
        ".bulk_create(",
    )

    def is_action(node: ast.AST) -> bool:
        if not isinstance(node, ast.Call):
            return False
        src = ast.unparse(node)
        return src.startswith("super(") or any(w in src for w in writes)

    return _first_line_matching(fn, is_action)


def test_single_object_views_check_permissions_in_a_safe_method():
    """Detail/Update/Delete views must scope the object itself, not just one verb.

    This is the JobUpdate and ProblemSuggestionUpdate shape. These views render the
    object on GET, so a check that lives only in post() or form_valid() hands the
    object's contents to anyone who asks for the form. The check has to sit
    somewhere that runs for every verb, before the object is handed out.
    """
    offenders: list[str] = []

    for rel_path, cls in _view_classes():
        bases = " ".join(ast.unparse(b) for b in cls.bases)
        if not any(
            kind in bases for kind in ("DetailView", "UpdateView", "DeleteView")
        ):
            continue
        methods = {
            node.name: node
            for node in cls.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        denying = {
            name
            for name, node in methods.items()
            if "PermissionDenied" in ast.unparse(node)
        }
        if not denying or denying & SAFE_CHECK_METHODS:
            continue
        offenders.append(
            f"{rel_path}:{cls.lineno} {cls.name} denies only in {sorted(denying)}; "
            f"move the check into one of {sorted(SAFE_CHECK_METHODS)} so that GET "
            f"is covered too"
        )

    assert not offenders, (
        "These single-object views leak on GET or check too late:\n  "
        + "\n  ".join(offenders)
    )


def test_verb_specific_checks_run_before_the_view_acts():
    """A check inside post()/form_valid() must precede the write it is guarding.

    Escalating on a single verb is fine — StudentAssistantList reads as staff but
    writes as superuser. What is never fine is JobUpdate's original shape, where the
    check came after super().post() had already saved the form.
    """
    guarded_methods = ("post", "put", "patch", "delete", "form_valid")
    offenders: list[str] = []

    for rel_path, cls in _view_classes():
        for node in cls.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name not in guarded_methods:
                continue
            denies_at = _denies_at(node)
            acts_at = _acts_at(node)
            if denies_at is None or acts_at is None:
                continue
            if denies_at > acts_at:
                offenders.append(
                    f"{rel_path}:{node.lineno} {cls.name}.{node.name}() writes on "
                    f"line {acts_at} but only raises PermissionDenied on line "
                    f"{denies_at}"
                )

    assert not offenders, (
        "These views act before they check, so the write lands even when the "
        "request should have been denied:\n  " + "\n  ".join(offenders)
    )


def test_no_view_skips_ancestors_with_a_targeted_super_dispatch():
    """`super(SomeView, self).dispatch(...)` silently skips the access mixins.

    This is the PSetDetail bug: the two-argument form started the MRO walk *after*
    DetailView, which sits below LoginRequiredMixin, so the login check never ran.
    Plain `super()` is what you want.
    """
    offenders: list[str] = []

    for rel_path, cls in _view_classes():
        for node in ast.walk(cls):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (isinstance(func, ast.Attribute) and func.attr == "dispatch"):
                continue
            inner = func.value
            if (
                isinstance(inner, ast.Call)
                and isinstance(inner.func, ast.Name)
                and inner.func.id == "super"
                and inner.args
            ):
                offenders.append(
                    f"{rel_path}:{node.lineno} {cls.name} calls "
                    f"{ast.unparse(inner)}.dispatch(...)"
                )

    assert not offenders, (
        "These views call super() with explicit arguments before dispatch, which "
        "skips part of the MRO and can bypass the access mixins. Use a bare "
        "super().dispatch(...), or move the check into get_object():\n  "
        + "\n  ".join(offenders)
    )


@pytest.mark.parametrize("url_name", sorted(PUBLIC_VIEWS, key=str))
def test_public_view_allowlist_has_no_stale_entries(url_name: str | None):
    """Keep PUBLIC_VIEWS honest: every exemption must still name a real route."""
    assert any(name == url_name for _, _, name in _project_routes()), (
        f"PUBLIC_VIEWS lists {url_name!r}, which no longer matches any route. "
        "Remove the entry."
    )
