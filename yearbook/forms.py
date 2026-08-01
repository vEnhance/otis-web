from typing import Any

from django import forms
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
