from typing import Any

from django import forms
from django.core.validators import RegexValidator

from .levelsys import SUITS, FourMetersDict, Meter

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
    """Takes the number of levels offered from each statistic."""

    clubs = forms.IntegerField(min_value=0, label="Dexterity levels to offer")
    hearts = forms.IntegerField(min_value=0, label="Wisdom levels to offer")
    spades = forms.IntegerField(min_value=0, label="Strength levels to offer")
    diamonds = forms.IntegerField(min_value=0, label="Charisma levels to offer")

    def __init__(
        self,
        *args: Any,
        meters: FourMetersDict,
        max_level: int,
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)
        self.meters = meters
        self.max_level = max_level
        for suit, field in self.fields.items():
            meter: Meter = meters[suit]
            if meter.value < 0:
                field.help_text = f"You have a negative total of {meter.value} in this statistic. No offering is possible."
                field.initial = 0
                field.disabled = True
            else:
                field.help_text = (
                    f"You can offer up to {meter.level} levels in this statistic."
                )

    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean() or {}
        offered = {suit: cleaned_data.get(suit) for suit in SUITS}
        if any(levels is None for levels in offered.values()):
            return cleaned_data
        if (offered_sum := sum(offered.values())) != self.max_level:  # type: ignore
            raise forms.ValidationError(
                f"The total sum of the offerings must be exactly {self.max_level}. "
                f"The given values {' + '.join(str(_) for _ in offered.values())} sum to {offered_sum}."
            )
        for suit, levels in offered.items():
            assert levels is not None
            if levels > (level := self.meters[suit].level):
                self.add_error(suit, f"You only have {level} levels to offer.")
        return cleaned_data

    def deductions(self) -> dict[str, int]:
        return {
            suit: self.meters[suit].prestige_deduction(self.cleaned_data[suit])
            for suit in SUITS
        }
