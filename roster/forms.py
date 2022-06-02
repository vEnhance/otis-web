import itertools
from typing import Any

from core.models import Unit
from django import forms
from django.contrib.auth.models import User
from django.db.models.query_utils import Q
from django.forms.forms import BaseForm

from roster.models import Student, StudentRegistration, UnitInquiry  # NOQA


class UnitChoiceBoundField(forms.BoundField):
	@property
	def subject(self) -> str:
		first_unit_pair = self.field.choices[0]  # type: ignore
		first_unit_code = first_unit_pair[1]
		first_unit_subject = first_unit_code[1]  # second letter
		return first_unit_subject


class UnitChoiceField(forms.TypedMultipleChoiceField):
	def get_bound_field(self, form: BaseForm, field_name: str):
		return UnitChoiceBoundField(form, self, field_name)


class CurriculumForm(forms.Form):
	"""A form which takes a list of units
	and puts together a form letting you pick a curriculum.

	units: the list of units
	original: a list of unit ID's
	"""
	def __init__(self, *args: Any, **kwargs: Any):
		units = kwargs.pop('units')
		original = kwargs.pop('original', [])
		enabled = kwargs.pop('enabled', False)

		super(CurriculumForm, self).__init__(*args, **kwargs)

		n = 0
		for name, group_iter in itertools.groupby(units, lambda u: u.group.name):
			group = list(group_iter)
			field_name = 'group-' + str(n)
			chosen_units = [unit for unit in group if unit.id in original]

			form_kwargs = {}
			form_kwargs['label'] = name
			form_kwargs['choices'] = tuple((unit.id, unit.code) for unit in group)
			form_kwargs['help_text'] = ' '.join([unit.code for unit in group])
			form_kwargs['required'] = False
			form_kwargs['label_suffix'] = 'aoeu'  # wait why is this here again
			form_kwargs['coerce'] = int
			form_kwargs['empty_value'] = None
			form_kwargs['disabled'] = not enabled
			form_kwargs['initial'] = [unit.id for unit in chosen_units]
			self.fields[field_name] = UnitChoiceField(**form_kwargs)
			n += 1


class AdvanceForm(forms.ModelForm):
	def __init__(self, *args: Any, **kwargs: Any):
		super(AdvanceForm, self).__init__(*args, **kwargs)
		student = kwargs['instance']
		self.fields['unlocked_units'] = forms.ModelMultipleChoiceField(
			widget=forms.SelectMultiple(attrs={'class': 'chosen-select'}),
			queryset=student.curriculum.all(),
			help_text="The set of unlocked units.",
			required=False
		)

	class Meta:
		model = Student
		fields = ('unlocked_units', )


class InquiryForm(forms.ModelForm):
	def __init__(self, *args: Any, **kwargs: Any):
		student: Student = kwargs.pop('student')
		super(InquiryForm, self).__init__(*args, **kwargs)
		# TODO this breaks ordering, might want to fix
		curriculum_pks = student.curriculum.all().values_list('pk', flat=True)
		queryset = Unit.objects.filter(Q(group__hidden=False) | Q(pk__in=curriculum_pks))
		self.fields['unit'].queryset = queryset  # type: ignore

	class Meta:
		model = UnitInquiry
		fields = ('unit', 'action_type', 'explanation')
		widgets = {
			'explanation': forms.Textarea(attrs={
				'cols': 40,
				'rows': 3
			}),
		}


class DecisionForm(forms.ModelForm):
	given_name = forms.CharField(
		max_length=128, help_text="Your given (first) name, can be more than one"
	)
	surname = forms.CharField(max_length=128, help_text="Your family (last) name")
	email_address = forms.EmailField(
		label="Your email address (one you check)",
		help_text="The email you want Evan to contact you with"
	)
	passcode = forms.CharField(
		max_length=128,
		label="Invitation passcode",
		help_text="You should have gotten the passcode in your acceptance email.",
		widget=forms.PasswordInput
	)

	class Meta:
		model = StudentRegistration
		fields = (
			'parent_email',
			'track',
			'gender',
			'graduation_year',
			'school_name',
			'country',
			'aops_username',
			'agreement_form',
		)


class UserForm(forms.ModelForm):
	class Meta:
		model = User
		fields = ('first_name', 'last_name', 'email')
