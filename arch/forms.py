from typing import Any, Dict, Set, Union

from django import forms
from django.shortcuts import get_object_or_404

from . import models


class HintUpdateFormWithReason(forms.ModelForm):
	reason = forms.CharField(max_length=255, help_text = "Reason for editing.", required = False)
	class Meta:
		model = models.Hint
		fields = ('number', 'keywords', 'content', 'reason',)

class ProblemUpdateFormWithReason(forms.ModelForm):
	reason = forms.CharField(max_length=255, help_text = "Reason for editing.", required = False)
	class Meta:
		model = models.Problem
		fields = ('source', 'description', 'aops_url', 'reason',)

class ProblemSelectWidget(forms.Select):
	def create_option(
			self, name: str, value: Any, label : Union[int, str], selected : Union[Set[str], bool], index : int, subindex: int = None, attrs: Dict[str, Any] = None
	):
		option = super().create_option(
			name, value, label, selected, index, subindex, attrs or {},
		)
		if value:
			problem = get_object_or_404(models.Problem, puid=value)
			option['attrs'].update({
				'data-source': problem.source or '',
				'data-description': problem.description,
				})
		return option

class ProblemSelectForm(forms.Form):
	lookup_problem = forms.ModelChoiceField(
			to_field_name='puid',
			queryset = models.Problem.objects.all(),
			widget = ProblemSelectWidget
			)
