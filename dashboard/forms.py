from typing import Any

from django import forms
from django.core.validators import FileExtensionValidator
from django.forms.models import ModelChoiceField

from core.models import Unit
from dashboard.models import PSet

pset_file_validator = FileExtensionValidator(
    allowed_extensions=["pdf", "txt", "tex", "png", "jpg"]
)


class PSetSubmitForm(forms.ModelForm):
    content = forms.FileField(
        help_text="The file itself",
        validators=[
            pset_file_validator,
        ],
    )

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.fields["unit"].empty_label = "Search for a unit..."  # type: ignore
        self.fields["next_unit_to_unlock"].empty_label = "Search for a unit..."  # type: ignore

    class Meta:
        model = PSet
        fields = (
            "unit",
            "clubs",
            "hours",
            "feedback",
            "special_notes",
            "next_unit_to_unlock",
        )


class PSetResubmitForm(forms.ModelForm):
    content = forms.FileField(
        help_text="The file itself",
        validators=[
            pset_file_validator,
        ],
        required=False,
    )

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.fields["next_unit_to_unlock"].empty_label = "Search for a unit..."  # type: ignore

    class Meta:
        model = PSet
        fields = (
            "clubs",
            "hours",
            "feedback",
            "special_notes",
            "next_unit_to_unlock",
        )


class BonusRequestForm(forms.Form):
    def __init__(self, *args: Any, **kwargs: Any):
        level: int = kwargs.pop("level")
        super().__init__(*args, **kwargs)
        queryset = Unit.objects.filter(group__bonuslevel__level__lte=level)
        self.fields["unit"] = ModelChoiceField(queryset)
