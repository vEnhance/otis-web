from dashboard.models import QuestComplete
from django.contrib.auth.decorators import login_required, user_passes_test  # NOQA
from django.http.request import HttpRequest
from django.http.response import HttpResponse
from django.shortcuts import render
from roster.models import Student

from .forms import ScoreForm

# Create your views here.


@login_required
@user_passes_test(lambda u: u.is_superuser)
def usemo_score(request: HttpRequest) -> HttpResponse:
	if request.method == 'POST':
		form = ScoreForm(request.POST)
		if form.is_valid():
			students = Student.objects.filter(semester__active=True)
			qcs = []
			for s in students:
				for line in form.text.split('\n'):
					name = line[:line.index('\t')].strip()
					spades = int(line[line.rindex('\t') + 1:].strip())
					if s.user.get_full_name.lower() == name:
						qcs.append(
							QuestComplete(student=s, title="USEMO Points", category="US", spades=spades)
						)
			QuestComplete.objects.bulk_create(qcs)
	else:
		form = ScoreForm()

	context = {
		'title': 'USEMO Score Upload',
		'form': form,
	}
	return render(request, "mouse/scores.html", context)
