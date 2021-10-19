from core.models import UnitGroup
from django.contrib.auth.decorators import login_required
from django.http.request import HttpRequest
from django.http.response import HttpResponse, HttpResponseRedirect
from django.urls.base import reverse
from django.utils.text import slugify
from wiki.models import URLPath


def edit_redirect(u: URLPath) -> HttpResponseRedirect:
	return HttpResponseRedirect(reverse('wiki:edit', kwargs={'path': u.path}))


def view_redirect(u: URLPath) -> HttpResponseRedirect:
	return HttpResponseRedirect(u.get_absolute_url())


def wiki_redirect(u: URLPath) -> HttpResponseRedirect:
	return view_redirect(u)


@login_required
def problem(request: HttpRequest, puid: str) -> HttpResponse:

	try:
		u = URLPath.get_by_path(path=f'notable-problems/{puid}')
	except URLPath.DoesNotExist:
		parent = URLPath.get_by_path(path='notable-problems')
		content = f'[problem {puid}]' + '\n' + '[/problem]' + '\n' * 2
		content += f'(This is an automatically generated article for {puid}. Please add some content!)' + '\n' * 2
		content += '## Statement' + '\n'
		content += '[statement]'
		u = URLPath.create_urlpath(
			parent=parent,
			slug=puid,
			title=puid,
			request=request,
			content=content,
		)
	return wiki_redirect(u)


@login_required
def unitgroup(request: HttpRequest, pk: int) -> HttpResponse:
	group = UnitGroup.objects.get(pk=pk)

	if group.subject == "A" or group.subject == "F":
		subject_name = 'algebra'
	elif group.subject == "C":
		subject_name = 'combinatorics'
	elif group.subject == "G":
		subject_name = 'geometry'
	elif group.subject == "N":
		subject_name = 'number-theory'
	elif group.subject == "M":
		subject_name = 'miscellaneous'
	elif group.subject == "K":
		subject_name = 'null'
	else:
		raise Exception(f"No subject for {group.name}.")

	slug = slugify(group.name)
	try:
		u = URLPath.get_by_path(path=f'/units/list-of-{subject_name}-units/{slug}')
	except URLPath.DoesNotExist:
		parent = URLPath.get_by_path(path=f'/units/list-of-{subject_name}-units/')
		content = f'[unit {group.slug}]' + '\n' + '[/unit]' + '\n' * 2
		content += f'(This is an automatically generated article for {group.name}. Please add some content!)' + '\n' * 2
		u = URLPath.create_urlpath(
			parent=parent,
			slug=slug,
			title=group.name,
			request=request,
			content=content,
		)
	return wiki_redirect(u)
