from typing import Any

from django import forms

from .models import OIMEComment, OIMEContributor, OIMEProposal


class OIMEContributorForm(forms.ModelForm[OIMEContributor]):
    class Meta:
        model = OIMEContributor
        fields = [
            "display_name",
            "hide_from_leaderboards",
            "hide_from_acknowledgments",
        ]


class OIMEProposalForm(forms.ModelForm[OIMEProposal]):
    subject = forms.ChoiceField(
        choices=OIMEProposal.SUBJECT_CHOICES,
        widget=forms.RadioSelect,
    )
    difficulty = forms.TypedChoiceField(
        choices=OIMEProposal.DIFFICULTY_CHOICES,
        coerce=int,
        widget=forms.RadioSelect,
    )

    class Meta:
        model = OIMEProposal
        fields = [
            "title",
            "credit",
            "statement",
            "answer",
            "solution",
            "subject",
            "difficulty",
        ]
        widgets = {
            "statement": forms.Textarea(attrs={"rows": 6}),
            "solution": forms.Textarea(attrs={"rows": 10}),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Difficulty is fixed once the problem is submitted: its time limit and any
        # recorded fights depend on it, so it can only be chosen at creation.
        if self.instance.pk is not None:
            self.fields.pop("difficulty", None)


class OIMEAnswerForm(forms.Form):
    answer = forms.IntegerField(
        min_value=0,
        max_value=999,
        widget=forms.NumberInput(
            attrs={"class": "form-control", "placeholder": "0-999"}
        ),
    )


class OIMECommentForm(forms.ModelForm[OIMEComment]):
    class Meta:
        model = OIMEComment
        fields = ["content"]
        widgets = {
            "content": forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
        }
