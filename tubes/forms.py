from django import forms

from .models import OIMEComment, OIMEContributor, OIMEProposal


class OIMESetupForm(forms.Form):
    display_name = forms.CharField(
        max_length=200,
        help_text="The name you want credited on problems you author or help select.",
    )
    is_serious = forms.ChoiceField(
        choices=[("serious", "Serious (timed sessions)"), ("casual", "Casual (browse freely)")],
        widget=forms.RadioSelect,
        initial="serious",
        label="Testsolving mode",
        help_text="Serious: 5n+5 minutes per difficulty-n problem, answer locked until time. "
        "You can downgrade to casual later, but not upgrade.",
    )


class OIMEContributorForm(forms.ModelForm[OIMEContributor]):
    class Meta:
        model = OIMEContributor
        fields = ["display_name"]


class OIMEProposalForm(forms.ModelForm[OIMEProposal]):
    class Meta:
        model = OIMEProposal
        fields = ["statement", "answer", "solution", "subject", "difficulty"]
        widgets = {
            "statement": forms.Textarea(attrs={"rows": 6}),
            "solution": forms.Textarea(attrs={"rows": 10}),
        }


class OIMEAnswerForm(forms.Form):
    answer = forms.IntegerField(
        min_value=0,
        max_value=999,
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "0-999"}),
    )


class OIMECommentForm(forms.ModelForm[OIMEComment]):
    class Meta:
        model = OIMEComment
        fields = ["content"]
        widgets = {
            "content": forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
        }
