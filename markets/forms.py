from django import forms

from .models import Market


class MarketCreateForm(forms.ModelForm):
    prompt_plain = forms.CharField(widget=forms.Textarea)
    solution_plain = forms.CharField(widget=forms.Textarea, required=False)

    class Meta:
        model = Market
        fields = (
            "title",
            "slug",
            "prompt_plain",
            "answer",
            "show_answer",
            "int_guesses_only",
            "solution_plain",
            "start_date",
            "end_date",
        )
