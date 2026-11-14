import pytest

from course_registration import CourseOffering, LearnerDirectory, LearnerStatus

COURSE = "CS201"
PREREQ = "CS101"


def assert_invariants(offering: CourseOffering) -> None:
    """Invariants from docs/DESIGN.md §6, checked against a snapshot."""
    s = offering.snapshot()
    enrolled, waitlist = set(s.enrolled), set(s.waitlist)
    removed = {r.learner_id for r in s.removals}

    assert len(s.enrolled) <= s.capacity, "over capacity"
    assert len(enrolled) == len(s.enrolled), "duplicate enrolled record"
    assert len(waitlist) == len(s.waitlist), "duplicate waitlist record"
    assert enrolled.isdisjoint(waitlist), "learner both enrolled and waitlisted"
    if s.waitlist:
        assert len(s.enrolled) == s.capacity, "open seat while learners are waiting"
    # status map agrees with the collections
    assert enrolled == {k for k, v in s.statuses.items() if v is LearnerStatus.ENROLLED}
    assert waitlist == {k for k, v in s.statuses.items() if v is LearnerStatus.WAITLISTED}
    assert removed == {k for k, v in s.statuses.items() if v is LearnerStatus.REMOVED}
    assert len(removed) == len(s.removals), "duplicate removal record"


@pytest.fixture
def directory():
    return LearnerDirectory()


@pytest.fixture
def make_offering(directory):
    """make_offering(capacity, eligible=[...], ineligible=[...]) -> CourseOffering"""

    def _make(capacity=2, eligible=(), ineligible=()):
        for lid in eligible:
            directory.register(lid, {PREREQ})
        for lid in ineligible:
            directory.register(lid, set())
        return CourseOffering(COURSE, capacity, PREREQ, directory)

    return _make
