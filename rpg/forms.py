from django import forms
from django.core.validators import RegexValidator

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
