import pytest
from django.contrib.messages import constants as message_levels

from core.factories import SemesterFactory, UnitFactory, UserFactory, UserProfileFactory
from roster.factories import InvoiceFactory, StudentFactory, StudentRegistrationFactory
from roster.models import ENABLED_STANDINGS, LEGIT_STANDINGS, Student, StudentStanding


@pytest.mark.django_db
def test_student_unit_counts() -> None:
    alice = StudentFactory.create()
    units = UnitFactory.create_batch(10)
    alice.curriculum.set(units[:7])
    alice.unlocked_units.set(units[2:5])
    assert alice.curriculum_length == 7
    assert alice.num_unlocked == 3


@pytest.mark.parametrize(
    ("standing", "legit", "newborn", "enabled"),
    [
        (StudentStanding.GOOD, True, False, True),
        (StudentStanding.NEWBORN, True, True, True),
        (StudentStanding.PROBATION, True, False, True),
        (StudentStanding.SUSPENDED, True, False, False),
        (StudentStanding.FAKE, False, False, True),
        (StudentStanding.DROPPED, True, False, False),
    ],
)
def test_standing_booleans(
    standing: StudentStanding, legit: bool, newborn: bool, enabled: bool
) -> None:
    student = Student(standing=standing)
    assert student.legit is legit
    assert student.newborn is newborn
    assert student.enabled is enabled


@pytest.mark.django_db
def test_standing_filters_agree_with_booleans() -> None:
    for standing in StudentStanding:
        StudentFactory.create(standing=standing)
    students = list(Student.objects.all())
    assert set(Student.objects.filter(standing__in=LEGIT_STANDINGS)) == {
        student for student in students if student.legit
    }
    assert set(Student.objects.filter(standing__in=ENABLED_STANDINGS)) == {
        student for student in students if student.enabled
    }


@pytest.mark.django_db
def test_master_schedule(otis) -> None:
    alice = StudentFactory.create(user__first_name="Ada", user__last_name="Adalhaidis")
    alice.curriculum.set(UnitFactory.create_batch(10)[:8])
    otis.login(UserFactory.create(is_staff=True, is_superuser=True))
    resp = otis.get("master-schedule")
    otis.assert_has(resp, text='title="Ada Adalhaidis"', count=8)


@pytest.fixture
def giga_chart_students() -> list[Student]:
    semester = SemesterFactory.create(show_invoices=True)
    students = [
        StudentFactory.create(
            semester=semester, reg=StudentRegistrationFactory.create()
        )
        for _ in range(5)
    ]
    for student in students:
        InvoiceFactory.create(student=student)
        UserProfileFactory.create(user=student.user)
    return students


@pytest.mark.django_db
def test_giga_chart_csv(otis, giga_chart_students) -> None:
    otis.login(UserFactory.create(is_staff=True, is_superuser=True))
    otis.get_20x("giga-chart", "csv", follow=True)


@pytest.mark.django_db
def test_giga_chart_html_lists_contacts(otis, giga_chart_students) -> None:
    otis.login(UserFactory.create(is_staff=True, is_superuser=True))
    # an export: its rendered text is the product
    resp = otis.get_20x("giga-chart", "html", follow=True)
    for student in giga_chart_students:
        otis.assert_has(resp, student.name)
        otis.assert_has(resp, student.user.email)
        otis.assert_has(resp, student.reg.parent_email)


@pytest.mark.django_db
def test_giga_chart_requires_superuser(otis) -> None:
    otis.login(UserFactory.create(is_staff=True))
    otis.get_denied("giga-chart", "csv")


@pytest.mark.django_db
def test_suspend_student(otis) -> None:
    alice = StudentFactory.create()
    otis.login(UserFactory.create(is_staff=True, is_superuser=True))

    resp = otis.post("toggle-suspension", alice.pk, follow=True)
    alice.refresh_from_db()
    assert alice.standing == StudentStanding.SUSPENDED
    assert alice.user.is_active is False
    assert any(m.level == message_levels.SUCCESS for m in resp.context["messages"])


@pytest.mark.django_db
def test_unsuspend_student_puts_them_on_probation(otis) -> None:
    alice = StudentFactory.create(
        standing=StudentStanding.SUSPENDED, user__is_active=False
    )
    otis.login(UserFactory.create(is_staff=True, is_superuser=True))

    otis.post("toggle-suspension", alice.pk)
    alice.refresh_from_db()
    assert alice.standing == StudentStanding.PROBATION
    assert alice.user.is_active is True


@pytest.mark.django_db
def test_toggle_suspension_rejects_get(otis) -> None:
    alice = StudentFactory.create()
    otis.login(UserFactory.create(is_staff=True, is_superuser=True))
    otis.get_40x("toggle-suspension", alice.pk)
    alice.refresh_from_db()
    assert alice.standing == StudentStanding.GOOD


@pytest.mark.django_db
def test_toggle_suspension_requires_superuser(otis) -> None:
    alice = StudentFactory.create()
    otis.login(UserFactory.create(is_staff=True))
    otis.post_denied("toggle-suspension", alice.pk)
    otis.login(alice)
    otis.post_denied("toggle-suspension", alice.pk)
    alice.refresh_from_db()
    assert alice.standing == StudentStanding.GOOD


@pytest.mark.django_db
def test_suspension_link_is_admin_only(otis) -> None:
    alice = StudentFactory.create()
    otis.login(UserFactory.create(is_staff=True, is_superuser=True))
    otis.assert_testid(otis.get_ok("portal", alice.pk), "toggle-suspension")
    otis.login(alice)
    otis.assert_no_testid(otis.get_ok("portal", alice.pk), "toggle-suspension")
