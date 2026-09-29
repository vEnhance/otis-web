from typing import Any

from django import forms
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
    gm_identity = forms.ChoiceField(
        label="Sign your comments to Evan?",
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
    instructor = forms.ModelChoiceField(
        queryset=Assistant.objects.none(),
        label="Which instructor are these comments for?",
        required=False,
    )
    instructor_comments = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 6}),
    )
    instructor_signed = forms.ChoiceField(
        label="Sign your comments to your instructor?",
        choices=(
            (SIGNED, "Sign with my name."),
            (ANONYMOUS, "Submit anonymously."),
        ),
        required=False,
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
        instructors = [] if student is None else list(student.assistants.all())
        self.sole_instructor = instructors[0] if len(instructors) == 1 else None
        if survey.instructor_comments_prompt and (student is None or instructors):
            self.fields["instructor_comments"].label = survey.instructor_comments_prompt
        else:
            del self.fields["instructor_comments"]
            del self.fields["instructor_signed"]
        if len(instructors) > 1 and "instructor_comments" in self.fields:
            instructor_field = self.fields["instructor"]
            assert isinstance(instructor_field, forms.ModelChoiceField)
            instructor_field.queryset = Assistant.objects.filter(
                pk__in=[a.pk for a in instructors]
            )
        else:
            del self.fields["instructor"]

    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean() or {}
        if cleaned_data.get("instructor_comments") and not cleaned_data.get(
            "instructor_signed"
        ):
            self.add_error(
                "instructor_signed",
                "Choose whether to sign your comments to your instructor.",
            )
        if cleaned_data.get("instructor_comments"):
            if self.sole_instructor is not None:
                cleaned_data["instructor"] = self.sole_instructor
            elif not cleaned_data.get("instructor"):
                self.add_error(
                    "instructor", "Choose which instructor to send your comments to."
                )
        return cleaned_data
