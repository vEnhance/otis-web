from django import forms


class DiamondsForm(forms.Form):
    code = forms.RegexField(
        label="Enter a hex code of length 24-26 here.",
        regex=r"[a-fA-F0-9]{24,26}",
        required=True,
        min_length=24,
        max_length=26,
        error_messages={"invalid": "This doesn't appear to be a hex code."},
        widget=forms.TextInput(attrs={"pattern": "[a-fA-F]+"}),
    )
