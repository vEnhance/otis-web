from django import forms

from .models import UnitGroup


class CatalogFilterForm(forms.Form):
    difficulty = forms.MultipleChoiceField(
        choices=[("B", "B"), ("D", "D"), ("Z", "Z")],
        widget=forms.CheckboxSelectMultiple(attrs={"class": "filter-form"}),
        required=False,
    )

    category = forms.MultipleChoiceField(
        choices=UnitGroup.SUBJECT_CHOICES_SHORT,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "filter-form"}),
        required=False,
    )

    status = forms.MultipleChoiceField(
        choices=[
            ("completed", "Done (✓)"),
            ("unlocked", "Unlocked (⏲)"),
            ("locked", "Locked (⧖)"),
        ],
        widget=forms.CheckboxSelectMultiple(attrs={"class": "filter-form"}),
        required=False,
    )

    sort = forms.ChoiceField(
        choices=[
            ("", "A-Z"),
            ("-num_psets_in_group", "Number of completions (high to low)"),
            ("num_psets_in_group", "Number of completions (low to high)"),
            ("position", "Relative order (first to last)"),
            ("-position", "Relative order (last to first)"),
        ],
        required=False,
        initial="",  # Sorts by A-Z
    )

    group_by_category = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "filter-form"}),
    )
