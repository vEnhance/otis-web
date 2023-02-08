from django.contrib.auth.decorators import login_required
from django.http.request import HttpRequest
from django.http.response import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls.base import reverse
from django.utils.text import slugify
from wiki.models import URLPath

from core.models import UnitGroup

WIKI_SUBJECT_CHART = {
    "A": "algebra",
    "F": "algebra",
    "C": "combinatorics",
    "G": "geometry",
    "N": "number-theory",
    "M": "miscellaneous",
    "K": "secret",
}


def edit_redirect(u: URLPath) -> HttpResponseRedirect:
    return HttpResponseRedirect(reverse("wiki:edit", kwargs={"path": u.path}))


def view_redirect(u: URLPath) -> HttpResponseRedirect:
    return HttpResponseRedirect(u.get_absolute_url())


def wiki_redirect(u: URLPath) -> HttpResponseRedirect:
    return view_redirect(u)


@login_required
def unitgroup(request: HttpRequest, pk: int) -> HttpResponse:
    group = get_object_or_404(UnitGroup, pk=pk)

    subject_name = WIKI_SUBJECT_CHART[group.subject]
    slug = slugify(group.name)
    try:
        u = URLPath.get_by_path(path=f"/units/list-of-{subject_name}-units/{slug}")
    except URLPath.DoesNotExist:
        parent = URLPath.get_by_path(path=f"/units/list-of-{subject_name}-units/")
        content = (
            f"[unit {group.slug}]\n[/unit]\n\n"
            f"(This is an automatically generated article for {group.name}. "
            "Please add some content!)\n\n"
        )
        u = URLPath.create_urlpath(
            parent=parent,
            slug=slug,
            title=group.name,
            request=request,
            content=content,
        )
    return wiki_redirect(u)
