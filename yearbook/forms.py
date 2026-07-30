from django import forms

from .models import YearbookEntry

YEARBOOK_FIELDS = (
    "tagline",
    "country",
    "graduation_year",
    "avatar",
    "email",
    "discord_username",
    "github_username",
    "aops_username",
    "instagram_username",
    "imo_years",
    "university",
    "bio",
)


class YearbookEntryForm(forms.ModelForm):
    class Meta:
        model = YearbookEntry
        fields = YEARBOOK_FIELDS


class YearbookEntryCreateForm(YearbookEntryForm):
    acknowledge = forms.BooleanField(
        required=True,
        label="I understand the yearbook policy",
        help_text="Your real name and the years you were in OTIS will be shown "
        "on your yearbook page, along with everything you fill in above. "
        "Anyone in the Verified group can read it.",
    )
