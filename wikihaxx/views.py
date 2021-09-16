from django.contrib.auth.decorators import login_required
from django.http.request import HttpRequest
from django.http.response import HttpResponse, HttpResponseRedirect
from django.urls.base import reverse
from wiki.models import URLPath


@login_required
def problem(request: HttpRequest, puid: str) -> HttpResponse:
	try:
		notable_problems = URLPath.get_by_path(path='notable-problems')
	except URLPath.DoesNotExist:
		raise Exception("Notable problems article doesn't exist")

	try:
		u = URLPath.get_by_path(path=f'notable-problems/{puid}')
	except URLPath.DoesNotExist:
		content = f'[problem {puid}]' + '\n' + '[/problem]' + '\n' * 2
		content += f'This is automatically generated article for {puid}.' + '\n' * 2
		content += '## Statement' + '\n'
		content += '[statement]'
		u = URLPath.create_urlpath(
			parent=notable_problems,
			slug=puid,
			title=puid,
			request=request,
			content=content,
		)
		return HttpResponseRedirect(reverse('wiki:edit', kwargs={'path': u.path}))
	else:
		return HttpResponseRedirect(u.get_absolute_url())
