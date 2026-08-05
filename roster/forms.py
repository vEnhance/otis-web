import itertools
from typing import Any, Optional

from django import forms
from django.contrib.auth.models import User
from django.db.models.query_utils import Q
from django.forms.forms import BaseForm

from core.models import EMAIL_PREFERENCE_FIELDS, Semester, Unit
from dashboard.models import PSet
from roster.models import Student, StudentRegistration, UnitInquiry


class UnitChoiceBoundField(forms.BoundField):
    @property
    def subject(self) -> str:
        first_unit_pair = self.field.choices[0]  # type: ignore
        first_unit_code = first_unit_pair[1]
        return first_unit_code[1]


class UnitChoiceField(forms.TypedMultipleChoiceField):
    def get_bound_field(self, form: BaseForm, field_name: str):
        return UnitChoiceBoundField(form, self, field_name)


class CurriculumForm(forms.Form):
    """A form which takes a list of units
    and puts together a form letting you pick a curriculum.

    units: the list of units
    original: a list of unit PK's
    """

    def __init__(self, *args: Any, **kwargs: Any):
        units = kwargs.pop("units")
        original = kwargs.pop("original", [])
        enabled = kwargs.pop("enabled", False)

        super().__init__(*args, **kwargs)

        for n, (name, group_iter) in enumerate(
            itertools.groupby(units, lambda u: u.group.name)
        ):
            group = list(group_iter)
            field_name = f"group-{str(n)}"
            chosen_units = [unit for unit in group if unit.pk in original]

            form_kwargs = {
                "label": name,
                "choices": tuple(((unit.pk, unit.code) for unit in group)),
                "help_text": " ".join([unit.code for unit in group]),
                "required": False,
                "label_suffix": "aoeu",
                "coerce": int,
                "empty_value": None,
                "disabled": not enabled,
                "initial": [unit.pk for unit in chosen_units],
            }
            self.fields[field_name] = UnitChoiceField(**form_kwargs)


class AdvanceUnitChoiceField(forms.ModelMultipleChoiceField):
    def __init__(self, *args: Any, **kwargs: Any):
        widget = kwargs.pop(
            "widget", forms.SelectMultiple(attrs={"class": "chosen-select"})
        )
        required = kwargs.pop("required", False)
        super().__init__(*args, widget=widget, required=required, **kwargs)


class AdvanceForm(forms.Form):
    def __init__(self, *args: Any, **kwargs: Any):
        student = kwargs.pop("student")
        super().__init__(*args, **kwargs)

        self.fields["units_to_unlock"] = AdvanceUnitChoiceField(
            label="Unlock",
            queryset=(
                student.curriculum.exclude(
                    pk__in=student.unlocked_units.values_list("pk")
                ).exclude(
                    pk__in=PSet.objects.filter(student=student).values_list("unit__pk"),
                )
                if not args
                else Unit.objects.all()
            ),
            help_text="Units to unlock, already in curriculum.",
        )
        self.fields["units_to_open"] = AdvanceUnitChoiceField(
            label="Open",
            queryset=(
                Unit.objects.exclude(pk__in=student.unlocked_units.values_list("pk"))
                if not args
                else Unit.objects.all()
            ),
            help_text="Units to open (add and unlock).",
        )
        self.fields["units_to_add"] = AdvanceUnitChoiceField(
            label="Add",
            queryset=(
                Unit.objects.exclude(pk__in=student.curriculum.values_list("pk"))
                if not args
                else Unit.objects.all()
            ),
            help_text="Units to add without unlocking.",
        )
        self.fields["units_to_lock"] = AdvanceUnitChoiceField(
            label="Lock",
            queryset=student.unlocked_units.all() if not args else Unit.objects.all(),
            help_text="Units to remove from unlocked set.",
        )
        self.fields["units_to_drop"] = AdvanceUnitChoiceField(
            label="Drop",
            queryset=student.curriculum.all() if not args else Unit.objects.all(),
            help_text="Units to remove altogether.",
        )


class InquiryForm(forms.ModelForm):
    def __init__(self, *args: Any, **kwargs: Any):
        student: Student = kwargs.pop("student")
        super().__init__(*args, **kwargs)
        # TODO this breaks ordering, might want to fix
        curriculum_pks = student.curriculum.all().values_list("pk", flat=True)
        queryset = Unit.objects.filter(
            Q(group__hidden=False) | Q(pk__in=curriculum_pks)
        )
        self.fields["unit"].queryset = queryset  # type: ignore

    class Meta:
        model = UnitInquiry
        fields = ("unit", "action_type", "explanation")
        widgets = {
            "explanation": forms.Textarea(attrs={"cols": 40, "rows": 3}),
        }


class DecisionForm(forms.ModelForm):
    given_name = forms.CharField(
        label="First name (given name)",
        max_length=128,
        help_text="Your given (first) name, can be more than one. Please use a real name.",
    )
    surname = forms.CharField(
        label="Last name (surname)",
        max_length=128,
        help_text="Your family (last) name. Please use a real name.",
    )
    email_address = forms.EmailField(
        label="Your email address (one you check)",
        help_text="The email you want Evan to contact you with",
    )
    passcode = forms.CharField(
        max_length=128,
        label="Invitation passcode",
        help_text="This is provided in your acceptance letter and registration instructions on apply.evanchen.cc.",
    )
    gender = forms.ChoiceField(
        choices=StudentRegistration.GENDER_CHOICES,
        widget=forms.RadioSelect(),
    )

    email_on_announcement = forms.BooleanField(
        label="Receive emails for announcements",
        help_text="Receive all-student announcements. If this is set to False, announcements will only appear on OTIS-WEB.",
        required=False,
    )
    email_on_inquiry_complete = forms.BooleanField(
        label="Receive email on petition processed",
        help_text="Receive an email when your petition has been processed.",
        required=False,
    )
    email_on_pset_complete = forms.BooleanField(
        label="Receive email on completed problem set",
        help_text="Receive an email when your problem sets are checked off.",
        required=False,
    )
    email_on_suggestion_processed = forms.BooleanField(
        label="Receive email on suggestion processed",
        help_text="Receive an email when your problem suggestion status is updated.",
        required=False,
    )

    class Meta:
        model = StudentRegistration
        fields = (
            "given_name",
            "surname",
            "email_address",
            "gender",
            "graduation_year",
            "school_name",
            "country",
            "aops_username",
            "agreement_form",
            "passcode",
            "parent_email",
        ) + EMAIL_PREFERENCE_FIELDS


class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")


class LinkAssistantForm(forms.Form):
    student = forms.ModelChoiceField(
        queryset=Student.objects.filter(
            semester__active=True,
            assistant__isnull=True,
        ),
        label="Student to claim",
    )


class UserLookupForm(forms.Form):
    query = forms.CharField(
        label="Search query",
        help_text="Email, Django username, social account username, or real name.",
    )


class UserMergeForm(forms.Form):
    """Folds a duplicate account X into the account Y which is kept."""

    old_user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        widget=forms.NumberInput,
        label="Duplicate user PK (X)",
        help_text="This account is deactivated and emptied out.",
    )
    new_user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        widget=forms.NumberInput,
        label="Surviving user PK (Y)",
        help_text="Students and social accounts of X are moved here.",
    )

    def clean(self) -> dict[str, Any]:
        cleaned_data: dict[str, Any] = super().clean() or {}
        old_user: Optional[User] = cleaned_data.get("old_user")
        new_user: Optional[User] = cleaned_data.get("new_user")
        if old_user is None or new_user is None:
            return cleaned_data
        if old_user == new_user:
            raise forms.ValidationError("The two accounts need to be distinct.")
        if old_user.is_superuser or old_user.is_staff:
            raise forms.ValidationError(
                f"Refusing to deactivate {old_user.username}, who is staff. "
                "Merge this one by hand."
            )
        # Student has unique_together (user, semester), so a shared semester
        # would make the move blow up; bail out rather than merge halfway.
        clashes = Semester.objects.filter(student__user=old_user).filter(
            student__user=new_user
        )
        if clashes.exists():
            names = ", ".join(str(semester) for semester in clashes)
            raise forms.ValidationError(
                f"Both accounts have a student for {names}. "
                "Delete the redundant student(s) first."
            )
        return cleaned_data
