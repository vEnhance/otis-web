from typing import Any

from django import forms
from django.core.validators import FileExtensionValidator
from django.forms.models import ModelChoiceField

from core.models import Unit
from dashboard.models import PSet, UploadedFile


class NewUploadForm(forms.ModelForm):
    class Meta:
        model = UploadedFile
        fields = ("category", "content", "description")
        widgets = {
            "description": forms.Textarea(attrs={"cols": 40, "rows": 2}),
        }
        help_texts = {
            "content": "",
        }


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
