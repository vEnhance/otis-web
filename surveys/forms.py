from typing import Any

from django import forms
from django.forms import BoundField
from django.forms.widgets import ChoiceWidget
from markdownify.templatetags.markdownify import markdownify

from roster.models import Assistant, Student
from surveys.models import Survey

SIGNED = "signed"
ANONYMOUS = "anonymous"
ANONYMOUS_LINK = "anonymous_link"


class SatisfactionScale(ChoiceWidget):
    """Radio buttons laid out horizontally between two sets of emoji.

    This deliberately isn't a RadioSelect, since crispy renders those
    with its own template and would ignore this one.
    """

    input_type = "radio"
    template_name = "surveys/widgets/satisfaction_scale.html"
    use_fieldset = True


def instructor_field_name(assistant: Assistant) -> str:
    return f"instructor_comments_{assistant.pk}"


class SurveyForm(forms.Form):
    essay = forms.CharField(
        label="Free comments (read only by Evan)",
        widget=forms.Textarea(attrs={"rows": 12}),
    )
    satisfaction = forms.TypedChoiceField(
        choices=[(n, str(n)) for n in range(8)],
        coerce=int,
        empty_value=None,
        required=False,
        widget=SatisfactionScale,
    )
    anything_else = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    identity = forms.ChoiceField(
        label="Sign your comments?",
        choices=(
            (
                SIGNED,
                "Sign with my name. Any reply from Evan will show up on this page.",
            ),
            (
                ANONYMOUS_LINK,
                "Submit anonymously, but get a private link to see any replies. I'll need to save this link myself.",
            ),
            (ANONYMOUS, "Submit anonymously, with no way to see any replies."),
        ),
        widget=forms.RadioSelect,
    )

    def __init__(
        self, *args: Any, survey: Survey, student: Student | None, **kwargs: Any
    ) -> None:
        super().__init__(*args, **kwargs)
        self.fields["essay"].help_text = markdownify(survey.essay_prompt)
        if survey.satisfaction_prompt:
            self.fields["satisfaction"].label = survey.satisfaction_prompt
        else:
            del self.fields["satisfaction"]
        if survey.anything_else_prompt:
            self.fields["anything_else"].label = survey.anything_else_prompt
        else:
            del self.fields["anything_else"]
        # Field names of the instructor section, which the template renders
        # under its own heading, and which assistant each one goes to.
        self.instructor_field_names: list[str] = []
        self.instructor_fields: dict[str, Assistant] = {}
        if survey.instructor_comments_prompt and student is None:
            self._add_instructor_field("instructor_comments", "Your instructor")
        elif survey.instructor_comments_prompt and student is not None:
            for assistant in student.assistants.select_related("user"):
                name = instructor_field_name(assistant)
                self.instructor_fields[name] = assistant
                self._add_instructor_field(name, assistant.name)
        if self.instructor_field_names:
            self.fields[
                "identity"
            ].help_text = "This also applies to your comments to your instructors."
        # The signing choice comes last, after the instructor section.
        self.fields["identity"] = self.fields.pop("identity")

    def _add_instructor_field(self, name: str, label: str) -> None:
        self.instructor_field_names.append(name)
        self.fields[name] = forms.CharField(
            label=label,
            required=False,
            widget=forms.Textarea(attrs={"rows": 6, "class": "form-control mb-3"}),
        )

    def main_fields(self) -> list[BoundField]:
        return [
            self[name]
            for name in self.fields
            if name != "identity" and name not in self.instructor_field_names
        ]

    def instructor_section(self) -> list[BoundField]:
        return [self[name] for name in self.instructor_field_names]
