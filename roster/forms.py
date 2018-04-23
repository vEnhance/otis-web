from django import forms
import itertools

import roster

class UnitChoiceBoundField(forms.BoundField):
	@property
	def subject(self):
		return self.field.choices[1][1][1] # terrible hack, but oh well

class UnitChoiceField(forms.TypedChoiceField):
	def get_bound_field(self, form, field_name):
		return UnitChoiceBoundField(form, self, field_name)

class CurriculumForm(forms.Form):
	"""A form which takes a list of units
	and puts together a form letting you pick a curriculum.
	
	units: the list of units
	original: a list of unit ID's
	"""

	def __init__(self, *args, **kwargs):
		units = kwargs.pop('units')
		original = kwargs.pop('original', [])
		enabled = kwargs.pop('enabled', False)

		super(CurriculumForm, self).__init__(*args, **kwargs)
		
		n = 0
		for name, group in itertools.groupby(units, lambda u : u.group.name):
			group = list(group)
			field_name = 'group-' + str(n)

			form_kwargs = {}
			form_kwargs['label'] = name
			form_kwargs['choices'] = ((None, "---"),) \
					+ tuple((unit.id, unit.code) for unit in group)

			for unit in group:
				if unit.id in original:
					form_kwargs['initial'] = unit.id
					break
			else:
				form_kwargs['initial'] = None

			form_kwargs['help_text'] = ' '.join([unit.code for unit in group])
			form_kwargs['required'] = False
			form_kwargs['label_suffix'] = 'aoeu' # wait why is this here again
			form_kwargs['coerce'] = int
			form_kwargs['empty_value'] = None
			form_kwargs['disabled'] = not enabled

			self.fields[field_name] = UnitChoiceField(**form_kwargs)
			n += 1


class AdvanceForm(forms.ModelForm):
	class Meta:
		model = roster.models.Student
		fields = ('current_unit_index',)
