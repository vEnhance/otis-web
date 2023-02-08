from django import forms

from .models import Market


class MarketCreateForm(forms.ModelForm):
    prompt_plain = forms.CharField(widget=forms.Textarea)
    solution_plain = forms.CharField(widget=forms.Textarea, required=False)

    class Meta:
        model = Market
        fields = (
            "slug",
            "title",
            "answer",
            "show_answer",
        )
