from django.shortcuts import render
from hanabi.models import HanabiContest


# Create your views here.
class HanabiContestList(LoginRequiredMixin, ListView[HanabiContestList]):
    model = HanabiContest
    context_object_name = "contests"
