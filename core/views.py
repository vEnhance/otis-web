from django.shortcuts import render

from django.views.generic.list import ListView
from .models import UnitGroup

# Create your views here.

class UnitGroupListView(ListView):
	model = UnitGroup
	queryset = UnitGroup.objects.all().order_by('subject', 'name')\
			.prefetch_related('unit_set')
