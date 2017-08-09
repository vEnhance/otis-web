from django import forms
import itertools

class CurriculumForm(forms.Form):
	"""A form which takes a list of units
	and puts together a form letting you pick a curriculum.
	
	units: the list of units
	original: list of unit ID's
	"""

	def __init__(self, *args, **kwargs):
		units = kwargs.pop('units')
		original = kwargs.pop('original', [])
		print original

		super(CurriculumForm, self).__init__(*args, **kwargs)
		
		n = 0
		for name, group in itertools.groupby(units, lambda u : u.name):
			group = list(group)
			field_name = 'group-' + str(n)
			label = name
			choices = ((None, "---"),) + tuple((unit.id, unit.code) for unit in group)

			for unit in group:
				if unit.id in original:
					initial = unit.id
					break
			else:
				initial = None

			self.fields[field_name] = forms.ChoiceField(
					label = label, choices = choices, initial = initial)
					

			n += 1
