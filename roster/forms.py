from django import forms
import itertools

import roster

class UnitChoiceBoundField(forms.BoundField):
	@property
	def subject(self):
		first_unit_pair = self.field.choices[0]
		first_unit_code = first_unit_pair[1]
		first_unit_subject = first_unit_code[1] # second letter
		return first_unit_subject

class UnitChoiceField(forms.TypedMultipleChoiceField):
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
			chosen_units = [unit for unit in group if unit.id in original]

			form_kwargs = {}
			form_kwargs['label'] = name
			form_kwargs['choices'] = tuple((unit.id, unit.code) for unit in group)
			form_kwargs['help_text'] = ' '.join([unit.code for unit in group])
			form_kwargs['required'] = False
			form_kwargs['label_suffix'] = 'aoeu' # wait why is this here again
			form_kwargs['coerce'] = int
			form_kwargs['empty_value'] = None
			form_kwargs['disabled'] = not enabled
			form_kwargs['initial'] = [unit.id for unit in chosen_units]
			self.fields[field_name] = UnitChoiceField(**form_kwargs)
			n += 1


class AdvanceForm(forms.ModelForm):
	def __init__(self, *args, **kwargs):
		super(AdvanceForm, self).__init__(*args, **kwargs)
		student = kwargs['instance']
		self.fields['pointer_current_unit'] = forms.ModelChoiceField(
				queryset = student.curriculum.all(),
				empty_label = "(none)",
				help_text = "Use this if you want to \"jump\" the counter "
				"to a certain point.",
				required = False)

	class Meta:
		model = roster.models.Student
		fields = ('num_units_done', 'pointer_current_unit', 'vision')


class InquiryForm(forms.ModelForm):
	def __init__(self, *args, **kwargs):
		super(InquiryForm, self).__init__(*args, **kwargs)
		self.fields['unit'].queryset = \
				self.fields['unit'].queryset\
				.order_by('group__name', 'code')

	class Meta:
		model = roster.models.UnitInquiry
		fields = ('unit', 'action_type', 'explanation')
		widgets = {
			'explanation': forms.Textarea(
				attrs={'cols': 60, 'rows': 3}),
			}
