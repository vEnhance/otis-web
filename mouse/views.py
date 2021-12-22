from datetime import datetime

from dashboard.models import QuestComplete
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test  # NOQA
from django.http.request import HttpRequest
from django.http.response import HttpResponse
from django.shortcuts import render
from roster.models import Student

from .forms import GraderForm, ScoreForm

# Create your views here.

YEAR = datetime.now().year


@login_required
@user_passes_test(lambda u: u.is_superuser)
def usemo_score(request: HttpRequest) -> HttpResponse:
	if request.method == 'POST':
		form = ScoreForm(request.POST)
		if form.is_valid():
			students = Student.objects.filter(semester__active=True)
			qcs = []
			for s in students:
				for line in form.cleaned_data['text'].splitlines():
					line = line.strip()
					if not line:
						continue
					name = line[:line.index('\t')].strip()
					spades = int(line[line.rindex('\t') + 1:].strip())
					if s.user.get_full_name().lower() == name.lower():
						qcs.append(
							QuestComplete(student=s, title=f"USEMO {YEAR}", category="US", spades=spades)
						)
			QuestComplete.objects.bulk_create(qcs)
			messages.success(request, f'Built {len(qcs)} records')
	else:
		form = ScoreForm()

	context = {
		'title': 'USEMO Score Upload',
		'form': form,
	}
	return render(request, "mouse/form.html", context)


@login_required
@user_passes_test(lambda u: u.is_superuser)
def usemo_grader(request: HttpRequest) -> HttpResponse:
	if request.method == 'POST':
		form = GraderForm(request.POST)
		if form.is_valid():
			students = Student.objects.filter(semester__active=True)
			qcs = []
			for s in students:
				for line in form.cleaned_data['text'].splitlines():
					line = line.strip()
					if not line:
						continue
					name = line[:line.index('\t')].strip()
					if s.user.get_full_name().lower() == name.lower():
						qcs.append(QuestComplete(student=s, title="USEMO Points", category="UG", spades=15))
			QuestComplete.objects.bulk_create(qcs)
			messages.success(request, f'Built {len(qcs)} records')
	else:
		form = GraderForm()

	context = {
		'title': 'USEMO Grader Bounty',
		'form': form,
	}
	return render(request, "mouse/form.html", context)
