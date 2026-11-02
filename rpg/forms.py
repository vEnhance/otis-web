from typing import Any

from django import forms
from django.core.validators import RegexValidator

from .levelsys import SUITS

CODE_REGEX = r"\A[a-fA-F0-9]{24,26}\Z"


class DiamondsForm(forms.Form):
    """Form for entering a diamond code.

    The code is validated on the server only, deliberately: a guess that isn't
    shaped like a code at all should still be recorded (see
    AchievementCodeGuess.is_well_formed), so the field carries none of the
    HTML5 attributes (pattern, minlength, maxlength) that would make the
    browser refuse to submit it.
    """

    code = forms.CharField(
        label="Enter a hex code of length 24-26 here.",
        required=True,
        validators=[
            RegexValidator(
                regex=CODE_REGEX, message="This doesn't appear to be a hex code."
            )
        ],
    )


class PrestigeContractForm(forms.Form):
    """Takes the square roots of the four deductions."""

    clubs = forms.IntegerField(min_value=0, label="♣ Dexterity")
    hearts = forms.IntegerField(min_value=0, label="♥ Wisdom")
    spades = forms.IntegerField(min_value=0, label="♠ Strength")
    diamonds = forms.IntegerField(min_value=0, label="♦ Charisma")

    def __init__(
        self, *args: Any, totals: dict[str, float], max_level: int, **kwargs: Any
    ):
        """`totals` must be unrounded, so a deduction can't leave a stat negative."""
        super().__init__(*args, **kwargs)
        self.totals = totals
        self.max_level = max_level
        for suit, field in self.fields.items():
            field.help_text = f"Current total: {round(totals[suit], 2)}"

    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean() or {}
        roots = {suit: cleaned_data.get(suit) for suit in SUITS}
        if any(root is None for root in roots.values()):
            return cleaned_data
        if sum(roots.values()) != self.max_level:  # type: ignore
            raise forms.ValidationError(
                f"The four numbers must add up to exactly {self.max_level}."
            )
        for suit, root in roots.items():
            assert root is not None
            value = self.totals[suit]
            if value < 0:
                if root != 0:
                    self.add_error(suit, "This statistic is negative, so pick 0.")
            elif root * root > value:
                self.add_error(suit, f"You only have {round(value, 2)} to give up.")
        return cleaned_data
