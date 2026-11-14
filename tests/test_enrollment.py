"""T1–T4: enrollment, waitlisting, duplicates, prerequisite failure (DESIGN.md §2, §13)."""

from course_registration import LearnerStatus, Outcome
from tests.conftest import PREREQ, assert_invariants, fill


# T1 ---------------------------------------------------------------- capacity available (AC 1)
def test_enroll_succeeds_when_capacity_remains_and_prereq_met(make_offering, directory):
    o = make_offering(capacity=2, eligible=["a"])
    r = o.enroll("a")
    assert r.outcome is Outcome.ENROLLED and r.ok
    s = o.snapshot()
    assert s.enrolled == ("a",) and s.waitlist == () and s.seats_available == 1
    assert_invariants(o, directory)


def test_enroll_fills_to_exact_capacity(make_offering, directory):
    o = make_offering(capacity=3, eligible=["a", "b", "c"])
    assert [o.enroll(x).outcome for x in "abc"] == [Outcome.ENROLLED] * 3
    assert o.snapshot().seats_available == 0
    assert_invariants(o, directory)


# T2 ---------------------------------------------------------------- full capacity (AC 2)
def test_full_course_waitlists_eligible_learners_in_arrival_order(make_offering, directory):
    o = make_offering(capacity=1, eligible=["a", "b", "c"])
    fill(o, "a")
    r_b, r_c = o.enroll("b"), o.enroll("c")
    assert (r_b.outcome, r_c.outcome) == (Outcome.WAITLISTED, Outcome.WAITLISTED)
    assert "position 1" in r_b.message and "position 2" in r_c.message
    s = o.snapshot()
    assert s.enrolled == ("a",) and s.waitlist == ("b", "c")
    assert_invariants(o, directory)


# T3 ---------------------------------------------------------------- duplicates (AC 2, R1–R3)
def test_duplicate_enroll_when_enrolled(make_offering):
    o = make_offering(capacity=2, eligible=["a"])
    fill(o, "a")
    before = o.snapshot()
    assert o.enroll("a").outcome is Outcome.ALREADY_ENROLLED
    assert o.enroll("a").outcome is Outcome.ALREADY_ENROLLED
    assert o.snapshot() == before


def test_duplicate_enroll_when_waitlisted_reports_position_and_keeps_single_record(make_offering):
    o = make_offering(capacity=1, eligible=["a", "b", "c"])
    fill(o, "a", "b", "c")
    before = o.snapshot()
    r = o.enroll("c")
    assert r.outcome is Outcome.ALREADY_WAITLISTED and "position 2" in r.message
    assert o.snapshot() == before


def test_promoted_learner_enrolling_again_is_duplicate(make_offering):
    o = make_offering(capacity=1, eligible=["a", "b"])
    fill(o, "a", "b")
    assert o.drop("a").promoted == ("b",)
    before = o.snapshot()
    assert o.enroll("b").outcome is Outcome.ALREADY_ENROLLED
    assert o.snapshot() == before


def test_duplicate_check_precedes_prereq_check_for_active_learners(make_offering, directory):
    """R3 / UC5 / UC7: an active learner whose record is revoked gets ALREADY_*, never REJECTED."""
    o = make_offering(capacity=1, eligible=["a", "b"])
    fill(o, "a", "b")
    directory.revoke_completion("a", PREREQ)
    directory.revoke_completion("b", PREREQ)
    before = o.snapshot()
    assert o.enroll("a").outcome is Outcome.ALREADY_ENROLLED
    assert o.enroll("b").outcome is Outcome.ALREADY_WAITLISTED
    assert o.snapshot() == before


# T4 ---------------------------------------------------------------- prerequisite failure (AC 4, A2)
def test_prereq_failure_with_seat_free_is_rejected_and_nothing_stored(make_offering):
    o = make_offering(capacity=2, ineligible=["x"])
    before = o.snapshot()
    r = o.enroll("x")
    assert r.outcome is Outcome.REJECTED and not r.ok
    assert "Rejected: prerequisite CS101 not completed." == r.message
    assert o.snapshot() == before
    assert "x" not in o.snapshot().statuses


def test_prereq_failure_when_full_is_rejected_and_never_waitlisted(make_offering):
    o = make_offering(capacity=1, eligible=["a"], ineligible=["x"])
    fill(o, "a")
    before = o.snapshot()
    assert o.enroll("x").outcome is Outcome.REJECTED
    assert o.snapshot() == before


def test_repeated_rejection_stays_stateless_then_normal_flow_once_eligible(make_offering, directory):
    o = make_offering(capacity=1, ineligible=["x"])
    assert o.enroll("x").outcome is Outcome.REJECTED
    assert o.enroll("x").outcome is Outcome.REJECTED
    assert o.snapshot().statuses == {}
    directory.add_completion("x", PREREQ)
    assert o.enroll("x").outcome is Outcome.ENROLLED


def test_enrolled_learner_is_never_rechecked(make_offering, directory):
    """A7 / UC4 / UC6: revoking an enrolled learner's record changes nothing; they can still drop."""
    o = make_offering(capacity=1, eligible=["a", "b"])
    fill(o, "a", "b")
    directory.revoke_completion("a", PREREQ)
    assert o.snapshot().statuses["a"] is LearnerStatus.ENROLLED
    r = o.drop("a")
    assert r.outcome is Outcome.DROPPED and r.promoted == ("b",)
