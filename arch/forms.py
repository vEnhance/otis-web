from typing import Any

from django import forms

from .models import Hint, Problem


class HintUpdateFormWithReason(forms.ModelForm):
    reason = forms.CharField(
        max_length=255, help_text="Reason for editing.", required=False
    )

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.fields["problem"].empty_label = "Search for a problem..."  # type: ignore

    class Meta:
        model = Hint
        fields = (
            "problem",
            "number",
            "keywords",
            "content",
            "reason",
        )


class ProblemSelectForm(forms.Form):
    problem = forms.ModelChoiceField(
        queryset=Problem.objects.all(), empty_label="Search for a problem..."
    )
