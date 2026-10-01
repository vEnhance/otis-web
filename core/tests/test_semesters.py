import pytest

from core.factories import GroupFactory, SemesterFactory, UserFactory
from core.models import Semester


@pytest.mark.django_db
def test_semester_url():
    SemesterFactory.create_batch(5)
    for sem in Semester.objects.all():
        assert f"/dash/past/{sem.pk}/" == sem.get_absolute_url()
    assert Semester.objects.count() == 5


@pytest.mark.django_db
def test_calendar(otis):
    verified_group = GroupFactory(name="Verified")
    alice = UserFactory.create(username="alice", groups=(verified_group,))
    otis.login(alice)

    # no active semester, so this should 404
    otis.get_40x("calendar")

    # still 404's since no calendar provided
    sem = SemesterFactory.create(active=True)
    otis.get_40x("calendar")

    # add a calendar URL, now it should work
    sem.calendar_url = "https://www.example.org"
    sem.save()
    resp = otis.get_30x("calendar")
    assert resp.headers["Location"] == "https://www.example.org"
