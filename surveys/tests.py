import datetime

import pytest
from django.contrib.messages import constants as message_levels
from freezegun.api import freeze_time

from core.factories import SemesterFactory, UserFactory
from roster.factories import AssistantFactory, StudentFactory
from rpg.factories import AchievementFactory, AchievementUnlockFactory
from rpg.models import AchievementUnlock

from .factories import (
    GMFeedbackFactory,
    InstructorCommentFactory,
    SurveyCompletionFactory,
    SurveyFactory,
)
from .models import GMFeedback, InstructorComment, SurveyCompletion

UTC = datetime.UTC


def _response(**overrides: str) -> dict[str, str]:
    data = {
        "essay": "Units are fun",
        "satisfaction": "6",
        "anything_else": "",
        "gm_signed": "signed",
        "instructor_comments": "",
        "instructor_signed": "",
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_submit_signed(otis):
    assistant = AssistantFactory.create()
    alice = StudentFactory.create(assistant=assistant)
    achievement = AchievementFactory.create()
    survey = SurveyFactory.create(semester=alice.semester, achievement=achievement)
    otis.login(alice)

    resp = otis.post_redirects(
        otis.url("survey-detail", survey.pk),
        "survey-submit",
        survey.pk,
        data=_response(
            anything_else="Hi Evan",
            instructor_comments="Thanks!",
            instructor_signed="signed",
        ),
        follow=True,
    )
    assert any(m.level == message_levels.SUCCESS for m in resp.context["messages"])

    assert SurveyCompletion.objects.filter(survey=survey, student=alice).exists()
    feedback = GMFeedback.objects.get(survey=survey)
    assert feedback.student == alice
    assert feedback.essay == "Units are fun"
    assert feedback.satisfaction == 6
    assert feedback.anything_else == "Hi Evan"
    comment = InstructorComment.objects.get(survey=survey)
    assert comment.student == alice
    assert comment.assistant == assistant
    assert comment.comments == "Thanks!"
    assert AchievementUnlock.objects.filter(
        user=alice.user, achievement=achievement
    ).exists()

    resp = otis.get_ok("survey-detail", survey.pk)
    assert resp.context["gm_feedback"] == feedback
    assert resp.context["instructor_comment"] == comment
    assert "form" not in resp.context
    otis.assert_testid(resp, "survey-signed-response")


@pytest.mark.django_db
def test_submit_anonymous(otis):
    alice = StudentFactory.create(assistant=AssistantFactory.create())
    survey = SurveyFactory.create(semester=alice.semester)
    otis.login(alice)

    otis.post_redirects(
        otis.url("survey-detail", survey.pk),
        "survey-submit",
        survey.pk,
        data=_response(
            gm_signed="anonymous",
            instructor_comments="Thanks!",
            instructor_signed="anonymous",
        ),
    )

    assert SurveyCompletion.objects.filter(survey=survey, student=alice).exists()
    assert GMFeedback.objects.get(survey=survey).student is None
    assert InstructorComment.objects.get(survey=survey).student is None

    resp = otis.get_ok("survey-detail", survey.pk)
    assert resp.context["gm_feedback"] is None
    assert resp.context["instructor_comment"] is None
    otis.assert_testid(resp, "survey-anonymous-response")


@pytest.mark.django_db
def test_signing_is_independent(otis):
    alice = StudentFactory.create(assistant=AssistantFactory.create())
    survey = SurveyFactory.create(semester=alice.semester)
    otis.login(alice)

    otis.post_30x(
        "survey-submit",
        survey.pk,
        data=_response(
            gm_signed="anonymous",
            instructor_comments="Thanks!",
            instructor_signed="signed",
        ),
    )
    assert GMFeedback.objects.get(survey=survey).student is None
    assert InstructorComment.objects.get(survey=survey).student == alice


@pytest.mark.django_db
def test_optional_fields_can_be_skipped(otis):
    alice = StudentFactory.create(assistant=AssistantFactory.create())
    survey = SurveyFactory.create(semester=alice.semester)
    otis.login(alice)

    otis.post_30x("survey-submit", survey.pk, data=_response(satisfaction=""))
    feedback = GMFeedback.objects.get(survey=survey)
    assert feedback.satisfaction is None
    assert feedback.anything_else == ""
    assert not InstructorComment.objects.exists()


@pytest.mark.django_db
def test_invalid_submission_keeps_input(otis):
    alice = StudentFactory.create(assistant=AssistantFactory.create())
    survey = SurveyFactory.create(semester=alice.semester)
    otis.login(alice)

    # Missing signing choices: nothing is saved and the form comes back filled in.
    resp = otis.post_ok(
        "survey-submit",
        survey.pk,
        data=_response(gm_signed="", instructor_comments="Thanks!"),
    )
    form = resp.context["form"]
    assert set(form.errors) == {"gm_signed", "instructor_signed"}
    assert form.data["essay"] == "Units are fun"
    assert not SurveyCompletion.objects.exists()
    assert not GMFeedback.objects.exists()


@pytest.mark.django_db
def test_form_drops_unasked_fields(otis):
    alice = StudentFactory.create()  # no assistant
    survey = SurveyFactory.create(
        semester=alice.semester, satisfaction_prompt="", anything_else_prompt=""
    )
    otis.login(alice)

    resp = otis.get_ok("survey-detail", survey.pk)
    assert set(resp.context["form"].fields) == {"essay", "gm_signed"}

    # Posting a field the form dropped doesn't sneak it in.
    otis.post_30x(
        "survey-submit",
        survey.pk,
        data=_response(
            satisfaction="3",
            anything_else="Sneaky",
            instructor_comments="Sneaky",
            instructor_signed="signed",
        ),
    )
    feedback = GMFeedback.objects.get(survey=survey)
    assert feedback.satisfaction is None
    assert feedback.anything_else == ""
    assert not InstructorComment.objects.exists()


@pytest.mark.django_db
def test_blank_instructor_prompt_drops_field(otis):
    bob = StudentFactory.create(assistant=AssistantFactory.create())
    survey = SurveyFactory.create(semester=bob.semester)
    otis.login(bob)
    resp = otis.get_ok("survey-detail", survey.pk)
    assert "instructor_comments" in resp.context["form"].fields

    survey.instructor_comments_prompt = ""
    survey.save()
    resp = otis.get_ok("survey-detail", survey.pk)
    assert "instructor_comments" not in resp.context["form"].fields


@pytest.mark.django_db
def test_cannot_submit_twice(otis):
    alice = StudentFactory.create()
    survey = SurveyFactory.create(semester=alice.semester)
    otis.login(alice)

    otis.post_30x("survey-submit", survey.pk, data=_response())
    resp = otis.post_redirects(
        otis.url("survey-detail", survey.pk),
        "survey-submit",
        survey.pk,
        data=_response(essay="Second try"),
        follow=True,
    )
    assert any(m.level == message_levels.ERROR for m in resp.context["messages"])
    assert list(GMFeedback.objects.values_list("essay", flat=True)) == ["Units are fun"]


@pytest.mark.django_db
def test_cannot_submit_when_closed(otis):
    alice = StudentFactory.create()
    survey = SurveyFactory.create(
        semester=alice.semester,
        opens_at=datetime.datetime(2021, 9, 1, tzinfo=UTC),
        closes_at=datetime.datetime(2021, 10, 1, tzinfo=UTC),
    )
    otis.login(alice)

    for now in ("2021-08-31", "2021-10-02"):
        with freeze_time(now, tz_offset=0):
            resp = otis.get_ok("survey-detail", survey.pk)
            assert "form" not in resp.context
            otis.assert_testid(resp, "survey-not-open")
            otis.post_redirects(
                otis.url("survey-detail", survey.pk),
                "survey-submit",
                survey.pk,
                data=_response(),
            )
    assert not SurveyCompletion.objects.exists()
    assert not GMFeedback.objects.exists()

    with freeze_time("2021-09-15", tz_offset=0):
        otis.post_30x("survey-submit", survey.pk, data=_response())
    assert SurveyCompletion.objects.filter(survey=survey, student=alice).exists()


@pytest.mark.django_db
def test_other_semester_cannot_submit(otis):
    survey = SurveyFactory.create()
    old = StudentFactory.create(semester=SemesterFactory.create(end_year=2020))
    otis.login(old)

    otis.get_denied("survey-detail", survey.pk)
    otis.post_denied("survey-submit", survey.pk, data=_response())
    assert not GMFeedback.objects.exists()


@pytest.mark.django_db
def test_staff_cannot_submit_for_student(otis):
    assistant = AssistantFactory.create()
    alice = StudentFactory.create(assistant=assistant)
    survey = SurveyFactory.create(semester=alice.semester)
    otis.login(assistant)

    otis.get_denied("survey-detail", survey.pk)
    otis.post_denied("survey-submit", survey.pk, data=_response())
    assert not GMFeedback.objects.exists()


@pytest.mark.django_db
def test_superuser_preview(otis):
    survey = SurveyFactory.create()
    admin = UserFactory.create(is_staff=True, is_superuser=True)
    otis.login(admin)

    resp = otis.get_ok("survey-detail", survey.pk)
    assert resp.context["preview"]
    assert "instructor_comments" in resp.context["form"].fields
    otis.assert_testid(resp, "survey-preview")
    otis.post_denied("survey-submit", survey.pk, data=_response())


@pytest.mark.django_db
def test_existing_achievement_is_kept(otis):
    alice = StudentFactory.create()
    achievement = AchievementFactory.create()
    unlock = AchievementUnlockFactory.create(user=alice.user, achievement=achievement)
    survey = SurveyFactory.create(semester=alice.semester, achievement=achievement)
    otis.login(alice)

    otis.post_30x("survey-submit", survey.pk, data=_response())
    assert list(AchievementUnlock.objects.filter(user=alice.user)) == [unlock]


@pytest.mark.django_db
def test_signed_response_shows_reply(otis):
    alice = StudentFactory.create()
    survey = SurveyFactory.create(semester=alice.semester)
    SurveyCompletionFactory.create(survey=survey, student=alice)
    GMFeedbackFactory.create(survey=survey, student=alice, reply="Glad to hear it")
    otis.login(alice)

    resp = otis.get_ok("survey-detail", survey.pk)
    otis.assert_testid(resp, "survey-reply")


@pytest.mark.django_db
def test_survey_list(otis):
    alice = StudentFactory.create(semester=SemesterFactory.create(end_year=2021))
    StudentFactory.create(
        user=alice.user, semester=SemesterFactory.create(end_year=2020)
    )
    at = datetime.datetime

    old_done = SurveyFactory.create(
        semester=alice.user.student_set.get(semester__end_year=2020).semester,
        opens_at=at(2019, 9, 1, tzinfo=UTC),
        closes_at=at(2019, 10, 1, tzinfo=UTC),
    )
    SurveyCompletionFactory.create(
        survey=old_done,
        student=alice.user.student_set.get(semester__end_year=2020),
    )
    current = SurveyFactory.create(
        semester=alice.semester,
        opens_at=at(2020, 9, 1, tzinfo=UTC),
        closes_at=at(2020, 10, 1, tzinfo=UTC),
    )
    upcoming = SurveyFactory.create(
        semester=alice.semester,
        opens_at=at(2021, 1, 1, tzinfo=UTC),
        closes_at=at(2021, 2, 1, tzinfo=UTC),
    )
    other_semester = SurveyFactory.create(
        opens_at=at(2020, 9, 1, tzinfo=UTC),
        closes_at=at(2020, 10, 1, tzinfo=UTC),
    )

    otis.login(alice)
    with freeze_time("2020-09-15", tz_offset=0):
        resp = otis.get_ok("survey-list")
    assert [(r["survey"], r["completed"]) for r in resp.context["rows"]] == [
        (current, False),
        (old_done, True),
    ]

    admin = UserFactory.create(is_staff=True, is_superuser=True)
    otis.login(admin)
    with freeze_time("2020-09-15", tz_offset=0):
        resp = otis.get_ok("survey-list")
    assert {r["survey"] for r in resp.context["rows"]} == {
        old_done,
        current,
        upcoming,
        other_semester,
    }


@pytest.mark.django_db
def test_admin_pages(otis):
    alice = StudentFactory.create(assistant=AssistantFactory.create())
    survey = SurveyFactory.create(semester=alice.semester)
    SurveyCompletionFactory.create(survey=survey, student=alice)
    GMFeedbackFactory.create(survey=survey, student=alice)
    GMFeedbackFactory.create(survey=survey)
    InstructorCommentFactory.create(survey=survey, assistant=alice.assistant)
    admin = UserFactory.create(is_staff=True, is_superuser=True)
    otis.login(admin)

    resp = otis.get_ok("admin:surveys_survey_changelist")
    assert resp.context["cl"].result_list[0].completion_count == 1
    otis.get_ok("admin:surveys_survey_change", survey.pk)
    otis.get_ok("admin:surveys_surveycompletion_changelist")
    resp = otis.get_ok(
        "admin:surveys_gmfeedback_changelist", data={"student__isempty": "1"}
    )
    assert resp.context["cl"].result_count == 1
    otis.get_ok("admin:surveys_instructorcomment_changelist")
