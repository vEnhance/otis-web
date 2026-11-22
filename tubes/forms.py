from typing import Any, ClassVar

from django import forms
from django.db.models import Count, Q, QuerySet

from .models import (
    OIMEComment,
    OIMEContributor,
    OIMEProposal,
    OIMESelection,
    OIMEYear,
)


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

    breaking_change = forms.BooleanField(required=False, label="Breaking change")

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if self.instance.pk is None:
            # Nothing to break yet.
            self.fields.pop("breaking_change")
            return
        # TODO(cj): help text for changing difficulty on an existing problem.
        self.fields["difficulty"].help_text = "TODO: difficulty changes are breaking."
        # TODO(cj): help text for the breaking-change checkbox.
        help_text = "TODO: what a breaking change does (stats reset)."
        if self.instance.archived:
            # TODO(cj): extra line for an archived problem.
            help_text += " TODO: this also unarchives the problem."
        self.fields["breaking_change"].help_text = help_text

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean() or {}
        # A new difficulty means a new time limit, so earlier solve times no
        # longer compare: changing it is always a breaking change.
        if (
            self.instance.pk is not None
            and "difficulty" in self.changed_data
            and not cleaned.get("breaking_change")
        ):
            # TODO(cj): error shown when difficulty changes without the box ticked.
            self.add_error("breaking_change", "TODO: difficulty change needs this.")
        return cleaned


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

    def __init__(
        self,
        *args: Any,
        editors: QuerySet[OIMEContributor] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        field = self.fields["editor"]
        field.queryset = (  # type: ignore[attr-defined]
            editors if editors is not None else editor_choices(self.instance.year)
        )
        field.label_from_instance = lambda c: f"{c} ({c.load})"  # type: ignore[attr-defined]


def editor_choices(year: OIMEYear) -> QuerySet[OIMEContributor]:
    """The year's editor pool, plus anyone already editing for it.

    Each carries ``load``, the number of the year's chosen problems they edit, so
    the dropdown can be balanced at a glance.
    """
    pks = set(year.editors.values_list("pk", flat=True)) | set(
        year.selections.filter(editor__isnull=False).values_list("editor_id", flat=True)
    )
    contributors = OIMEContributor.objects.filter(pk__in=pks)
    return contributors.annotate(
        load=Count(
            "editing",
            filter=Q(editing__year=year) & ~Q(editing__status="SEL_DEFERRED"),
        )
    ).order_by("display_name")


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
