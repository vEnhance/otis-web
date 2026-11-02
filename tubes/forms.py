from typing import Any, ClassVar

from django import forms

from .models import OIMEComment, OIMEContributor, OIMEProposal, OIMESelection


class OIMEContributorForm(forms.ModelForm[OIMEContributor]):
    class Meta:
        model = OIMEContributor
        fields = (
            "display_name",
            "hide_from_leaderboards",
            "hide_from_acknowledgments",
        )


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
        fields = (
            "title",
            "credit",
            "statement",
            "answer",
            "solution",
            "subject",
            "difficulty",
            "is_draft",
        )
        widgets: ClassVar[dict[str, forms.Widget]] = {
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
        fields = ("content",)
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "content": forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
        }


class OIMESelectionForm(forms.ModelForm[OIMESelection]):
    """The editor-in-chief's controls on one selected problem, other than status."""

    class Meta:
        model = OIMESelection
        fields = ("editor", "description", "notes")
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "editor": forms.Select(attrs={"class": "otis-select"}),
            "description": forms.TextInput(attrs={"class": "form-control"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["editor"].queryset = OIMEContributor.objects.order_by(  # type: ignore[attr-defined]
            "display_name"
        )


class OIMEBulkEditForm(OIMESelectionForm):
    """One row of the bulk page: who edits a chosen problem and its description."""

    class Meta(OIMESelectionForm.Meta):
        fields = ("editor", "description")

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["description"].widget.attrs["placeholder"] = "Description"


OIMEBulkEditFormSet = forms.modelformset_factory(
    OIMESelection, form=OIMEBulkEditForm, extra=0
)


class OIMEReleaseForm(forms.Form):
    """The one input on the release interstitial: when the contest goes public."""

    release_at = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
        ),
        help_text="Selected problems are retired from testsolving at this moment.",
    )
