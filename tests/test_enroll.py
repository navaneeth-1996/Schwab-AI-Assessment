from course_registration import LearnerStatus, Outcome
from tests.conftest import assert_invariants


def test_enroll_succeeds_when_capacity_remains_and_prereq_met(make_offering):
    o = make_offering(capacity=2, eligible=["a"])
    r = o.enroll("a")
    assert r.outcome is Outcome.ENROLLED and r.ok
    s = o.snapshot()
    assert s.enrolled == ("a",) and s.waitlist == () and s.seats_available == 1
    assert_invariants(o)


def test_enroll_fills_to_exact_capacity(make_offering):
    o = make_offering(capacity=3, eligible=["a", "b", "c"])
    assert [o.enroll(x).outcome for x in "abc"] == [Outcome.ENROLLED] * 3
    assert o.snapshot().seats_available == 0
    assert_invariants(o)


def test_full_course_puts_eligible_learner_on_waitlist(make_offering):
    o = make_offering(capacity=1, eligible=["a", "b", "c"])
    o.enroll("a")
    assert o.enroll("b").outcome is Outcome.WAITLISTED
    assert o.enroll("c").outcome is Outcome.WAITLISTED
    s = o.snapshot()
    assert s.enrolled == ("a",) and s.waitlist == ("b", "c")
    assert_invariants(o)


def test_prerequisite_failure_rejected_with_capacity_available(make_offering):
    o = make_offering(capacity=2, ineligible=["x"])
    before = o.snapshot()
    r = o.enroll("x")
    assert r.outcome is Outcome.PREREQUISITE_NOT_MET and not r.ok
    assert o.snapshot() == before


def test_prerequisite_failure_rejected_when_full_not_waitlisted(make_offering):
    o = make_offering(capacity=1, eligible=["a"], ineligible=["x"])
    o.enroll("a")
    assert o.enroll("x").outcome is Outcome.PREREQUISITE_NOT_MET
    assert o.snapshot().waitlist == ()
    assert "x" not in o.snapshot().statuses


def test_duplicate_enroll_when_enrolled(make_offering):
    o = make_offering(capacity=2, eligible=["a"])
    o.enroll("a")
    before = o.snapshot()
    assert o.enroll("a").outcome is Outcome.ALREADY_ENROLLED
    assert o.enroll("a").outcome is Outcome.ALREADY_ENROLLED
    assert o.snapshot() == before


def test_duplicate_enroll_when_waitlisted_keeps_single_record_and_position(make_offering):
    o = make_offering(capacity=1, eligible=["a", "b", "c"])
    o.enroll("a"); o.enroll("b"); o.enroll("c")
    before = o.snapshot()
    r = o.enroll("b")
    assert r.outcome is Outcome.ALREADY_WAITLISTED and "position 1" in r.message
    assert o.snapshot() == before
    assert_invariants(o)


def test_enrolled_learner_keeps_seat_if_prereq_later_revoked(make_offering, directory):
    o = make_offering(capacity=1, eligible=["a"])
    o.enroll("a")
    directory.revoke_completion("a", "CS101")
    assert o.snapshot().statuses["a"] is LearnerStatus.ENROLLED
    assert o.enroll("a").outcome is Outcome.ALREADY_ENROLLED
