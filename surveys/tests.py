import datetime
import uuid

import pytest
from django.contrib.auth.models import Group
from django.contrib.messages import constants as message_levels
from freezegun.api import freeze_time

from core.factories import SemesterFactory, UserFactory
from roster.factories import AssistantFactory, StudentFactory
from roster.models import Student
from rpg.factories import AchievementFactory, AchievementUnlockFactory
from rpg.models import AchievementUnlock

from .factories import (
    GMFeedbackFactory,
    InstructorCommentFactory,
    SurveyCompletionFactory,
    SurveyFactory,
)
from .models import GMFeedback, InstructorComment, SurveyCompletion
from .views import RESPONSES_PER_PAGE

UTC = datetime.UTC


def verified_student(**kwargs) -> Student:
    group, _ = Group.objects.get_or_create(name="Verified")
    return StudentFactory.create(user__groups=(group,), **kwargs)


def _response(**overrides: str) -> dict[str, str]:
    data = {
        "essay": "Units are fun",
        "satisfaction": "6",
        "anything_else": "",
        "gm_identity": "signed",
        "instructor_comments": "",
        "instructor_signed": "",
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_submit_signed(otis):
    assistant = AssistantFactory.create()
    alice = verified_student(assistant=assistant)
    achievement = AchievementFactory.create()
    survey = SurveyFactory.create(semester=alice.semester, achievement=achievement)
    otis.login(alice)

    otis.post_redirects(
        otis.url("survey-detail", survey.pk),
        "survey-submit",
        survey.pk,
        data=_response(
            anything_else="Hi Evan",
            instructor_comments="Thanks!",
            instructor_signed="signed",
        ),
    )

    assert SurveyCompletion.objects.filter(survey=survey, student=alice).exists()
    feedback = GMFeedback.objects.get(survey=survey)
    assert feedback.student == alice
    assert feedback.token is None
    assert feedback.essay == "Units are fun"
    assert feedback.satisfaction == 6
    assert feedback.anything_else == "Hi Evan"
    comment = InstructorComment.objects.get(survey=survey)
    assert comment.student == alice
    assert comment.assistant == assistant
    assert comment.comments == "Thanks!"
    # The achievement waits for the survey to close; see Survey.grant_achievements.
    assert not AchievementUnlock.objects.filter(achievement=achievement).exists()

    resp = otis.get_ok("survey-detail", survey.pk)
    assert resp.context["gm_feedback"] == feedback
    assert resp.context["instructor_comment"] == comment
    assert "form" not in resp.context
    otis.assert_testid(resp, "survey-signed-response")


@pytest.mark.django_db
def test_submit_anonymous(otis):
    alice = verified_student(assistant=AssistantFactory.create())
    survey = SurveyFactory.create(semester=alice.semester)
    otis.login(alice)

    otis.post_redirects(
        otis.url("survey-detail", survey.pk),
        "survey-submit",
        survey.pk,
        data=_response(
            gm_identity="anonymous",
            instructor_comments="Thanks!",
            instructor_signed="anonymous",
        ),
    )

    assert SurveyCompletion.objects.filter(survey=survey, student=alice).exists()
    feedback = GMFeedback.objects.get(survey=survey)
    assert feedback.student is None
    assert feedback.token is None
    assert InstructorComment.objects.get(survey=survey).student is None

    resp = otis.get_ok("survey-detail", survey.pk)
    assert resp.context["gm_feedback"] is None
    assert resp.context["instructor_comment"] is None
    otis.assert_testid(resp, "survey-anonymous-response")


@pytest.mark.django_db
def test_submit_anonymous_with_link(otis):
    alice = verified_student()
    survey = SurveyFactory.create(semester=alice.semester)
    otis.login(alice)

    resp = otis.post_30x(
        "survey-submit", survey.pk, data=_response(gm_identity="anonymous_link")
    )

    feedback = GMFeedback.objects.get(survey=survey)
    assert feedback.student is None
    assert feedback.token is not None
    # Submitting lands on the private link, since nothing else leads back to it.
    link = otis.url("survey-gm-feedback", survey.pk, feedback.token)
    otis.assert_redirects(resp, link)

    # The survey page can't link back, but says what the link looks like.
    resp = otis.get_ok("survey-detail", survey.pk)
    prefix = resp.context["private_link_prefix"]
    assert f"http://testserver{link}" == f"{prefix}{feedback.token}/"


@pytest.mark.django_db
def test_signing_is_independent(otis):
    alice = verified_student(assistant=AssistantFactory.create())
    survey = SurveyFactory.create(semester=alice.semester)
    otis.login(alice)

    otis.post_30x(
        "survey-submit",
        survey.pk,
        data=_response(
            gm_identity="anonymous",
            instructor_comments="Thanks!",
            instructor_signed="signed",
        ),
    )
    assert GMFeedback.objects.get(survey=survey).student is None
    assert InstructorComment.objects.get(survey=survey).student == alice


@pytest.mark.django_db
def test_optional_fields_can_be_skipped(otis):
    alice = verified_student(assistant=AssistantFactory.create())
    survey = SurveyFactory.create(semester=alice.semester)
    otis.login(alice)

    otis.post_30x("survey-submit", survey.pk, data=_response(satisfaction=""))
    feedback = GMFeedback.objects.get(survey=survey)
    assert feedback.satisfaction is None
    assert feedback.anything_else == ""
    assert not InstructorComment.objects.exists()


@pytest.mark.django_db
def test_invalid_submission_keeps_input(otis):
    alice = verified_student(assistant=AssistantFactory.create())
    survey = SurveyFactory.create(semester=alice.semester)
    otis.login(alice)

    # Missing signing choices: nothing is saved and the form comes back filled in.
    resp = otis.post_ok(
        "survey-submit",
        survey.pk,
        data=_response(gm_identity="", instructor_comments="Thanks!"),
    )
    form = resp.context["form"]
    assert set(form.errors) == {"gm_identity", "instructor_signed"}
    assert form.data["essay"] == "Units are fun"
    assert not SurveyCompletion.objects.exists()
    assert not GMFeedback.objects.exists()


@pytest.mark.django_db
def test_form_drops_unasked_fields(otis):
    alice = verified_student()  # no assistant
    survey = SurveyFactory.create(
        semester=alice.semester, satisfaction_prompt="", anything_else_prompt=""
    )
    otis.login(alice)

    resp = otis.get_ok("survey-detail", survey.pk)
    assert set(resp.context["form"].fields) == {"essay", "gm_identity"}

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
    bob = verified_student(assistant=AssistantFactory.create())
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
    alice = verified_student()
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
    alice = verified_student()
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
    old = verified_student(semester=SemesterFactory.create(end_year=2020))
    otis.login(old)

    otis.get_denied("survey-detail", survey.pk)
    otis.post_denied("survey-submit", survey.pk, data=_response())
    assert not GMFeedback.objects.exists()


@pytest.mark.django_db
def test_unverified_student_denied(otis):
    alice = StudentFactory.create()
    survey = SurveyFactory.create(semester=alice.semester)
    otis.login(alice)

    otis.get_denied("survey-list")
    otis.get_denied("survey-detail", survey.pk)
    otis.post_denied("survey-submit", survey.pk, data=_response())
    assert not SurveyCompletion.objects.exists()


@pytest.mark.django_db
def test_instructor_preview(otis):
    assistant = AssistantFactory.create()
    alice = StudentFactory.create(assistant=assistant)
    survey = SurveyFactory.create(semester=alice.semester)
    otis.login(assistant)

    resp = otis.get_ok("survey-detail", survey.pk)
    assert resp.context["preview"]
    otis.post_denied("survey-submit", survey.pk, data=_response())
    assert not GMFeedback.objects.exists()

    # Instructing in another semester doesn't count.
    otis.login(AssistantFactory.create())
    otis.get_denied("survey-detail", survey.pk)


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
def test_grant_achievements_action(otis):
    achievement = AchievementFactory.create()
    closed = SurveyFactory.create(
        achievement=achievement,
        opens_at=datetime.datetime(2021, 9, 1, tzinfo=UTC),
        closes_at=datetime.datetime(2021, 10, 1, tzinfo=UTC),
    )
    still_open = SurveyFactory.create(achievement=AchievementFactory.create())
    alice, bob, carol = (
        SurveyCompletionFactory.create(survey=closed).student for _ in range(3)
    )
    unlock = AchievementUnlockFactory.create(user=alice.user, achievement=achievement)
    SurveyCompletionFactory.create(survey=still_open)
    otis.login(UserFactory.create(is_staff=True, is_superuser=True))

    for _ in range(2):  # granting again changes nothing
        otis.post_ok(
            "admin:surveys_survey_changelist",
            data={
                "action": "grant_achievements",
                "_selected_action": [closed.pk, still_open.pk],
            },
            follow=True,
        )
        assert set(AchievementUnlock.objects.values_list("user", "achievement")) == {
            (alice.user.pk, achievement.pk),
            (bob.user.pk, achievement.pk),
            (carol.user.pk, achievement.pk),
        }
    assert AchievementUnlock.objects.get(user=alice.user) == unlock


@pytest.mark.django_db
def test_signed_response_shows_reply(otis):
    alice = verified_student()
    survey = SurveyFactory.create(semester=alice.semester)
    SurveyCompletionFactory.create(survey=survey, student=alice)
    GMFeedbackFactory.create(survey=survey, student=alice, reply="Glad to hear it")
    otis.login(alice)

    resp = otis.get_ok("survey-detail", survey.pk)
    otis.assert_testid(resp, "survey-reply")


@pytest.mark.django_db
def test_private_link(otis):
    survey = SurveyFactory.create()
    feedback = GMFeedbackFactory.create(survey=survey, token=uuid.uuid4())
    # Anyone with the link can see the feedback, since nothing ties it to a student.
    otis.login(verified_student())

    resp = otis.get_ok("survey-gm-feedback", survey.pk, feedback.token)
    assert resp.context["gm_feedback"] == feedback
    otis.assert_testid(resp, "survey-private-link")
    otis.assert_no_testid(resp, "survey-reply")
    otis.assert_no_testid(resp, "survey-read")

    feedback.is_read = True
    feedback.save()
    resp = otis.get_ok("survey-gm-feedback", survey.pk, feedback.token)
    otis.assert_testid(resp, "survey-read")

    feedback.reply = "Glad to hear it"
    feedback.save()
    resp = otis.get_ok("survey-gm-feedback", survey.pk, feedback.token)
    otis.assert_testid(resp, "survey-reply")

    otis.get_not_found("survey-gm-feedback", survey.pk, uuid.uuid4())
    # The token only works under its own survey.
    other = SurveyFactory.create()
    otis.get_not_found("survey-gm-feedback", other.pk, feedback.token)


@pytest.mark.django_db
def test_private_link_requires_login(otis):
    feedback = GMFeedbackFactory.create(token=uuid.uuid4())
    otis.get_login_redirect("survey-gm-feedback", feedback.survey.pk, feedback.token)


@pytest.mark.django_db
def test_survey_list(otis):
    alice = verified_student(semester=SemesterFactory.create(end_year=2021))
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


@pytest.mark.django_db
def test_survey_list_instructor(otis):
    assistant = AssistantFactory.create()
    alice = StudentFactory.create(assistant=assistant)
    at = datetime.datetime
    upcoming = SurveyFactory.create(
        semester=alice.semester,
        opens_at=at(2021, 1, 1, tzinfo=UTC),
        closes_at=at(2021, 2, 1, tzinfo=UTC),
    )
    SurveyFactory.create()  # another semester
    InstructorCommentFactory.create(survey=upcoming, assistant=assistant)
    InstructorCommentFactory.create(survey=upcoming, assistant=assistant, is_read=True)
    InstructorCommentFactory.create(survey=upcoming)  # someone else's
    otis.login(assistant)

    with freeze_time("2020-09-15", tz_offset=0):
        resp = otis.get_ok("survey-list")
    (row,) = resp.context["rows"]
    assert row["survey"] == upcoming
    assert row["status"] == "upcoming"
    assert row["is_instructor"]
    assert not row["is_student"]
    assert row["survey"].num_unread_comments == 1
    otis.assert_testid(resp, f"survey-preview-{upcoming.pk}")
    otis.assert_testid(resp, f"survey-comments-{upcoming.pk}")
    otis.assert_no_testid(resp, f"survey-inbox-{upcoming.pk}")
    otis.assert_no_testid(resp, f"survey-edit-{upcoming.pk}")


@pytest.mark.django_db
def test_survey_list_superuser_buttons(otis):
    survey = SurveyFactory.create()
    SurveyCompletionFactory.create(survey=survey)
    GMFeedbackFactory.create(survey=survey)
    GMFeedbackFactory.create(survey=survey, is_read=True)
    otis.login(UserFactory.create(is_staff=True, is_superuser=True))

    resp = otis.get_ok("survey-list")
    (row,) = resp.context["rows"]
    assert row["survey"].num_completions == 1
    assert row["survey"].num_unread_feedback == 1
    for button in ("preview", "edit", "inbox"):
        otis.assert_testid(resp, f"survey-{button}-{survey.pk}")
    otis.assert_no_testid(resp, f"survey-comments-{survey.pk}")


@pytest.mark.django_db
def test_gm_feedback_inbox(otis):
    survey = SurveyFactory.create()
    unread = GMFeedbackFactory.create(survey=survey)
    read = GMFeedbackFactory.create(survey=survey, is_read=True)
    later = GMFeedbackFactory.create(survey=survey)
    GMFeedbackFactory.create()  # another survey
    otis.login(UserFactory.create(is_staff=True, is_superuser=True))

    replied = GMFeedbackFactory.create(survey=survey, is_read=True, reply="Hi")

    def shown(**data: str) -> list[GMFeedback]:
        resp = otis.get_ok("survey-gm-feedback-inbox", survey.pk, data=data)
        return list(resp.context["page_obj"])

    # Unread by default, which is what there is to do something about.
    assert shown() == [unread, later]
    assert shown(status="unread") == [unread, later]
    assert shown(status="all") == [unread, read, later, replied]
    assert shown(status="read") == [read, replied]
    assert shown(status="replied") == [replied]
    assert shown(status="unreplied") == [unread, read, later]
    # A bad filter falls back to unread, and a page past the end to the last one.
    assert shown(status="x", page="9") == [unread, later]


@pytest.mark.django_db
def test_gm_feedback_inbox_is_superuser_only(otis):
    alice = StudentFactory.create(assistant=AssistantFactory.create())
    survey = SurveyFactory.create(semester=alice.semester)
    feedback = GMFeedbackFactory.create(survey=survey, student=alice)
    for user in (alice.user, alice.assistant.user):
        otis.login(user)
        otis.get_denied("survey-gm-feedback-inbox", survey.pk)
        otis.post_denied(
            "survey-gm-feedback-respond",
            survey.pk,
            feedback.pk,
            data={"action": "reply", "reply": "Hi"},
        )
    feedback.refresh_from_db()
    assert not feedback.is_read
    assert feedback.reply == ""


@pytest.mark.django_db
def test_gm_feedback_respond(otis):
    survey = SurveyFactory.create()
    feedback = GMFeedbackFactory.create(survey=survey, student=StudentFactory.create())
    otis.login(UserFactory.create(is_staff=True, is_superuser=True))

    def respond(**data: str):
        return otis.post_30x(
            "survey-gm-feedback-respond", survey.pk, feedback.pk, data=data
        )

    # Viewing the inbox doesn't mark anything read.
    otis.get_ok("survey-gm-feedback-inbox", survey.pk)
    feedback.refresh_from_db()
    assert not feedback.is_read

    respond(action="read")
    feedback.refresh_from_db()
    assert feedback.is_read
    respond(action="unread")
    feedback.refresh_from_db()
    assert not feedback.is_read

    with freeze_time("2021-09-15", tz_offset=0):
        resp = respond(action="reply", reply="  Thanks!  ", back_status="all")
    assert resp["Location"] == otis.url("survey-gm-feedback-inbox", survey.pk) + (
        "?status=all"
    )
    feedback.refresh_from_db()
    assert feedback.is_read
    assert feedback.reply == "Thanks!"
    assert feedback.replied_at == datetime.datetime(2021, 9, 15, tzinfo=UTC)

    # Resubmitting the same reply, as after marking unread, keeps its time.
    respond(action="unread")
    with freeze_time("2021-09-20", tz_offset=0):
        respond(action="reply", reply="Thanks!")
    feedback.refresh_from_db()
    assert feedback.is_read
    assert feedback.replied_at == datetime.datetime(2021, 9, 15, tzinfo=UTC)

    respond(action="reply", reply="")
    feedback.refresh_from_db()
    assert feedback.reply == ""
    assert feedback.replied_at is None

    # The feedback only answers to its own survey.
    otis.post_not_found(
        "survey-gm-feedback-respond",
        SurveyFactory.create().pk,
        feedback.pk,
        data={"action": "read"},
    )
    assert (
        otis.get("survey-gm-feedback-respond", survey.pk, feedback.pk).status_code
        == 405
    )


@pytest.mark.django_db
def test_gm_feedback_respond_returns_to_page(otis):
    survey = SurveyFactory.create()
    feedbacks = GMFeedbackFactory.create_batch(RESPONSES_PER_PAGE + 1, survey=survey)
    otis.login(UserFactory.create(is_staff=True, is_superuser=True))
    inbox = otis.url("survey-gm-feedback-inbox", survey.pk)

    otis.post_redirects(
        f"{inbox}?page=2",
        "survey-gm-feedback-respond",
        survey.pk,
        feedbacks[-1].pk,
        data={"action": "read", "back_status": "unread", "back_page": "2"},
    )
    # Page 2 is now empty under the unread filter, so it shows page 1.
    resp = otis.get_ok(
        "survey-gm-feedback-inbox", survey.pk, data={"status": "unread", "page": "2"}
    )
    assert resp.context["page_obj"].number == 1
    # A forged return page can't point anywhere but the inbox.
    otis.post_redirects(
        inbox,
        "survey-gm-feedback-respond",
        survey.pk,
        feedbacks[0].pk,
        data={"action": "read", "back_status": "evil", "back_page": "x"},
    )


@pytest.mark.django_db
def test_cannot_reply_to_unreachable_feedback(otis):
    survey = SurveyFactory.create()
    feedback = GMFeedbackFactory.create(survey=survey)  # anonymous, no link
    otis.login(UserFactory.create(is_staff=True, is_superuser=True))

    resp = otis.post_ok(
        "survey-gm-feedback-respond",
        survey.pk,
        feedback.pk,
        data={"action": "reply", "reply": "Hello?"},
        follow=True,
    )
    assert any(m.level == message_levels.ERROR for m in resp.context["messages"])
    feedback.refresh_from_db()
    assert feedback.reply == ""
    assert not feedback.is_read


@pytest.mark.django_db
def test_instructor_comment_inbox(otis):
    assistant = AssistantFactory.create()
    survey = SurveyFactory.create()
    alice = verified_student(semester=survey.semester, assistant=assistant)
    mine = InstructorCommentFactory.create(
        survey=survey, assistant=assistant, student=alice
    )
    theirs = InstructorCommentFactory.create(survey=survey)
    otis.login(assistant)

    resp = otis.get_ok("survey-instructor-comment-inbox", survey.pk)
    assert list(resp.context["page_obj"]) == [mine]

    otis.post_redirects(
        otis.url("survey-instructor-comment-inbox", survey.pk),
        "survey-instructor-comment-mark",
        survey.pk,
        mine.pk,
        data={"action": "read"},
    )
    mine.refresh_from_db()
    assert mine.is_read

    # Someone else's comments can't be touched.
    otis.post_not_found(
        "survey-instructor-comment-mark",
        survey.pk,
        theirs.pk,
        data={"action": "read"},
    )
    theirs.refresh_from_db()
    assert not theirs.is_read

    # The student sees it was read.
    SurveyCompletionFactory.create(survey=survey, student=alice)
    otis.login(alice)
    resp = otis.get_ok("survey-detail", survey.pk)
    otis.assert_testid(resp, "survey-instructor-read")

    # Students can't see the inbox at all.
    otis.get_denied("survey-instructor-comment-inbox", survey.pk)


def test_satisfaction_emoji():
    emoji = [GMFeedback(satisfaction=n).satisfaction_emoji for n in range(8)]
    assert emoji == ["😢"] * 3 + ["😐"] * 3 + ["🤩"] * 2
    assert GMFeedback(satisfaction=None).satisfaction_emoji == ""
