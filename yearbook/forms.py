from typing import Any

from django import forms
from django.db.models.query import QuerySet
from django.forms.boundfield import BoundField

from .models import YearbookEntry

# Rendered full width, since these are the page itself rather than metadata
PAGE_FIELDS = ("avatar", "tagline", "bio", "is_draft")

# Rendered as a label/input table, keeping their help text
BIOGRAPHICAL_FIELDS = ("country", "graduation_year", "university", "imo_id")

# Also a label/input table, but these labels say it all, so the help text is
# dropped to keep each account on a single line
CONTACT_FIELDS = {
    "email": "Email",
    "discord_username": "Discord",
    "github_username": "GitHub",
    "aops_username": "AoPS",
    "instagram_username": "Instagram",
    "website": "Website",
}


class YearbookEntryForm(forms.ModelForm):
    class Meta:
        model = YearbookEntry
        fields = PAGE_FIELDS + BIOGRAPHICAL_FIELDS + tuple(CONTACT_FIELDS)

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        for name in BIOGRAPHICAL_FIELDS:
            self._style_for_table(self.fields[name])
        for name, label in CONTACT_FIELDS.items():
            field = self.fields[name]
            field.label = label
            field.help_text = ""
            self._style_for_table(field)

    @staticmethod
    def _style_for_table(field: forms.Field) -> None:
        """Crispy adds these classes itself, but the table rows are rendered by
        hand, so the widgets need dressing here instead."""
        base = (
            "form-select" if isinstance(field.widget, forms.Select) else "form-control"
        )
        field.widget.attrs.setdefault("class", f"{base} {base}-sm")

    @property
    def biographical_fields(self) -> list[BoundField]:
        return [self[name] for name in BIOGRAPHICAL_FIELDS]

    @property
    def contact_fields(self) -> list[BoundField]:
        return [self[name] for name in CONTACT_FIELDS]


class YearbookEntryChoiceField(forms.ModelChoiceField):
    """Labels the picker's options the way the cards read.

    The label is also what the search box matches against, so it has to be the
    person's name rather than `str(entry)`."""

    def label_from_instance(self, obj: Any) -> str:
        assert isinstance(obj, YearbookEntry)
        return obj.name


class YearbookEntrySelectForm(forms.Form):
    """The index's jump-to-an-entry picker.

    The choices are per-viewer, since a draft is only in the yearbook for its
    author and for staff; picking one that isn't yours to see is the same
    non-answer as picking nobody."""

    entry = YearbookEntryChoiceField(
        queryset=YearbookEntry.objects.none(),
        label="Entry",
        empty_label="Search for a name...",
    )

    def __init__(self, queryset: QuerySet[YearbookEntry], *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        field = self.fields["entry"]
        assert isinstance(field, YearbookEntryChoiceField)
        field.queryset = queryset
