"""Structural tests that permission checks live in the right place.

Three separate vulnerabilities (JobUpdate, ProblemSuggestionUpdate, DeleteFile) all
had the same shape: the object-level permission check existed, but sat in a method
that ran too late (after the write) or on only one HTTP verb (so GET leaked the
form, or POST skipped the check entirely). These tests encode the invariants that
would have caught each of them, so the mistake can't come back quietly.

Views are always enumerated from the URL conf and inspected via the runtime class,
never by matching names in source text. A view that Django routes to is a view these
tests see, whatever it inherits from and whatever the file is called. Nothing here
touches the database or the network.
"""

import ast
import functools
import inspect
import pathlib
import textwrap
from typing import Any, NamedTuple

import pytest
from django.urls import get_resolver
from django.urls.resolvers import URLPattern, URLResolver
from django.views.generic.detail import SingleObjectMixin

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

# Methods that only run once the request is already committed to changing something.
WRITE_METHODS = frozenset({"post", "put", "patch", "delete", "form_valid"})

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


class ViewSource(NamedTuple):
    """A view class we route to, paired with its own parsed source."""

    cls: type
    node: ast.ClassDef
    first_line: int

    def where(self, node: ast.AST | None = None) -> str:
        module = self.cls.__module__.replace(".", "/")
        return f"{module}.py:{self.line_of(node)} {self.cls.__name__}"

    def line_of(self, node: ast.AST | None = None) -> int:
        """Translate a line inside the parsed class back to a line in the file."""
        if node is None:
            return self.first_line
        return self.first_line + getattr(node, "lineno", 1) - 1

    def methods(self) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
        return {
            child.name: child
            for child in self.node.body
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
        }


@functools.cache
def _read_class(cls: type) -> ViewSource | None:
    try:
        lines, first_line = inspect.getsourcelines(cls)
    except (OSError, TypeError):  # pragma: no cover - only for synthesised classes
        return None
    node = ast.parse(textwrap.dedent("".join(lines))).body[0]
    if not isinstance(node, ast.ClassDef):  # pragma: no cover - defensive
        return None
    return ViewSource(cls=cls, node=node, first_line=first_line)


def _routed_view_classes() -> list[type]:
    """Every class-based view Django actually routes to, deduplicated."""
    seen: dict[str, type] = {}
    for _route, callback, _name in _project_routes():
        cls = getattr(callback, "view_class", None)
        if cls is not None:
            seen[f"{cls.__module__}.{cls.__name__}"] = cls
    return [seen[key] for key in sorted(seen)]


def _own_sources(cls: type) -> list[ViewSource]:
    """The view's own source plus that of the project classes it inherits from.

    A view can perfectly well inherit its get_object() from a project mixin, so
    looking only at the class body would report false failures.
    """
    out = []
    for ancestor in cls.__mro__:
        if not (getattr(ancestor, "__module__", "") or "").startswith(PROJECT_APPS):
            continue
        source = _read_class(ancestor)
        if source is not None:
            out.append(source)
    return out


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


def test_single_object_views_check_permissions_in_a_safe_method():
    """Detail/Update/Delete views must scope the object, not just one verb.

    This is the JobUpdate and ProblemSuggestionUpdate shape. These views render the
    object on GET, so a check that lives only in post() or form_valid() hands its
    contents to anyone who asks for the form. Views that scope the object by
    request.user instead of raising are fine, and land here with nothing to report.
    """
    offenders: list[str] = []

    for cls in _routed_view_classes():
        if not issubclass(cls, SingleObjectMixin):
            continue
        denying: set[str] = set()
        for source in _own_sources(cls):
            for name, method in source.methods().items():
                if "PermissionDenied" in ast.unparse(method):
                    denying.add(name)
        if denying and not (denying & SAFE_CHECK_METHODS):
            offenders.append(
                f"{cls.__module__}.{cls.__name__} denies only in {sorted(denying)}; "
                f"move the check into one of {sorted(SAFE_CHECK_METHODS)} so that "
                f"GET is covered too"
            )

    assert not offenders, (
        "These single-object views leak on GET or check too late:\n  "
        + "\n  ".join(offenders)
    )


def _first_matching(method: ast.AST, predicate) -> ast.AST | None:
    """The earliest node in the method satisfying predicate, by line number."""
    found = [
        node
        for node in ast.walk(method)
        if getattr(node, "lineno", None) is not None and predicate(node)
    ]
    return min(found, key=lambda n: n.lineno) if found else None  # type: ignore[attr-defined]


def _denies_in(method: ast.AST) -> ast.AST | None:
    return _first_matching(
        method,
        lambda n: isinstance(n, ast.Raise) and "PermissionDenied" in ast.unparse(n),
    )


def _hands_off_in(method: ast.AST) -> ast.AST | None:
    """Where the method delegates to the parent view, which is where writes happen.

    Deliberately keys on super() alone. Trying to also spot ORM writes by method
    name is what made an earlier version of this file flag `context.update(...)`
    as a database write and fail correct code.
    """
    return _first_matching(
        method,
        lambda n: isinstance(n, ast.Call) and ast.unparse(n).startswith("super("),
    )


def test_verb_specific_checks_run_before_the_view_acts():
    """A check inside post()/form_valid() must precede the super() call it guards.

    Escalating on a single verb is fine — StudentAssistantList reads as staff but
    writes as superuser. What is never fine is JobUpdate's original shape, where the
    check came after super().post() had already saved the form.
    """
    offenders: list[str] = []

    for cls in _routed_view_classes():
        for source in _own_sources(cls):
            for name, method in source.methods().items():
                if name not in WRITE_METHODS:
                    continue
                denies = _denies_in(method)
                hands_off = _hands_off_in(method)
                if denies is None or hands_off is None:
                    continue
                if denies.lineno > hands_off.lineno:  # type: ignore[attr-defined]
                    offenders.append(
                        f"{source.where(method)}.{name}() calls super() on line "
                        f"{source.line_of(hands_off)} but only raises "
                        f"PermissionDenied on line {source.line_of(denies)}"
                    )

    assert not offenders, (
        "These views act before they check, so the write lands even when the "
        "request should have been denied:\n  " + "\n  ".join(sorted(set(offenders)))
    )


def test_no_view_skips_ancestors_with_a_targeted_super_dispatch():
    """`super(SomeView, self).dispatch(...)` silently skips the access mixins.

    This is the PSetDetail bug: the two-argument form started the MRO walk *after*
    DetailView, which sits below LoginRequiredMixin, so the login check never ran.
    Plain `super()` is what you want.
    """
    offenders: list[str] = []

    for cls in _routed_view_classes():
        for source in _own_sources(cls):
            for node in ast.walk(source.node):
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
                        f"{source.where(node)} calls {ast.unparse(inner)}.dispatch(...)"
                    )

    assert not offenders, (
        "These views call super() with explicit arguments before dispatch, which "
        "skips part of the MRO and can bypass the access mixins. Use a bare "
        "super().dispatch(...), or move the check into get_object():\n  "
        + "\n  ".join(sorted(set(offenders)))
    )


@pytest.mark.parametrize("url_name", sorted(PUBLIC_VIEWS, key=str))
def test_public_view_allowlist_has_no_stale_entries(url_name: str | None):
    """Keep PUBLIC_VIEWS honest: every exemption must still name a real route."""
    assert any(name == url_name for _, _, name in _project_routes()), (
        f"PUBLIC_VIEWS lists {url_name!r}, which no longer matches any route. "
        "Remove the entry."
    )
