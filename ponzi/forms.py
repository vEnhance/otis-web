from django import forms

from .models import MAX_INVESTMENT


class InvestmentForm(forms.Form):
    amount = forms.IntegerField(
        min_value=1,
        max_value=MAX_INVESTMENT,
        help_text=f"Whole number of spades, at most {MAX_INVESTMENT}",
    )
