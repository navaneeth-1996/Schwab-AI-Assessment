import pytest

from course_registration import CourseOffering, LearnerDirectory, LearnerStatus, OfferingState

COURSE = "CS201"
PREREQ = "CS101"


def assert_invariants(offering: CourseOffering, directory: LearnerDirectory | None = None) -> None:
    """Structural invariants from DESIGN.md §7 (1, 2, 4).

    Pass ``directory`` to also check invariant 3 / SP1 ("no vacant seat while an eligible learner
    waits"). Only do that straight after a drop or a successful enroll: by design (A11) the
    invariant is restored at those triggers, not when a record changes.
    """
    s = offering.snapshot()
    enrolled, waitlist = set(s.enrolled), set(s.waitlist)

    assert len(s.enrolled) <= s.capacity, "inv 1: over capacity"
    assert len(enrolled) == len(s.enrolled), "inv 2: duplicate enrolled record"
    assert len(waitlist) == len(s.waitlist), "inv 2: duplicate waitlist record"
    assert enrolled.isdisjoint(waitlist), "inv 2: learner both enrolled and waitlisted"
    assert enrolled == {k for k, v in s.statuses.items() if v is LearnerStatus.ENROLLED}, "inv 4"
    assert waitlist == {k for k, v in s.statuses.items() if v is LearnerStatus.WAITLISTED}, "inv 4"

    if directory is not None and s.seats_available > 0:
        eligible_waiting = [l for l in s.waitlist if directory.has_completed(l, s.prerequisite_course_id)]
        assert not eligible_waiting, f"inv 3: vacant seat while eligible learners wait: {eligible_waiting}"


def assert_order_preserved(before: OfferingState, after: OfferingState) -> None:
    """Invariant 7: learners who remain waiting keep their relative order; new ones join at the back."""
    remaining = [l for l in before.waitlist if l in set(after.waitlist)]
    assert list(after.waitlist[: len(remaining)]) == remaining, "inv 7: waitlist reordered"


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


def fill(offering, *learners):
    """Enroll learners in order (helper for building a starting state)."""
    for lid in learners:
        offering.enroll(lid)
