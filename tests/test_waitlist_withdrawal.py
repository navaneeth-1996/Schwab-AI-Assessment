from course_registration import LearnerStatus, Outcome
from tests.conftest import assert_invariants


def _full(make_offering):
    o = make_offering(capacity=1, eligible=["a", "b", "c", "d"])
    for x in "abcd":
        o.enroll(x)
    return o


def test_leave_waitlist_marks_withdrawn_and_preserves_order(make_offering):
    o = _full(make_offering)
    r = o.leave_waitlist("c")
    assert r.outcome is Outcome.WITHDRAWN and r.ok
    s = o.snapshot()
    assert s.waitlist == ("b", "d") and s.enrolled == ("a",)
    assert s.statuses["c"] is LearnerStatus.WITHDRAWN
    assert_invariants(o)


def test_withdrawn_learner_is_skipped_by_promotion(make_offering):
    o = _full(make_offering)
    o.leave_waitlist("b")
    assert o.drop("a").promoted == ("c",)


def test_withdrawn_learner_can_reenroll_and_goes_to_back_of_queue(make_offering):
    o = _full(make_offering)
    o.leave_waitlist("b")
    r = o.enroll("b")
    assert r.outcome is Outcome.WAITLISTED
    assert o.snapshot().waitlist == ("c", "d", "b")
    assert_invariants(o)


def test_withdrawn_learner_can_reenroll_directly_when_seat_free(make_offering, directory):
    o = make_offering(capacity=1, eligible=["a", "b"])
    o.enroll("a"); o.enroll("b")
    o.leave_waitlist("b")
    o.drop("a")
    assert o.enroll("b").outcome is Outcome.ENROLLED
    assert_invariants(o)


def test_withdrawn_learner_reenroll_still_requires_prereq(make_offering, directory):
    o = _full(make_offering)
    o.leave_waitlist("b")
    directory.revoke_completion("b", "CS101")
    before = o.snapshot()
    assert o.enroll("b").outcome is Outcome.PREREQUISITE_NOT_MET
    assert o.snapshot() == before
    assert o.snapshot().statuses["b"] is LearnerStatus.WITHDRAWN


def test_leave_waitlist_twice(make_offering):
    o = _full(make_offering)
    o.leave_waitlist("b")
    before = o.snapshot()
    assert o.leave_waitlist("b").outcome is Outcome.NOT_WAITLISTED
    assert o.snapshot() == before


def test_leave_waitlist_by_enrolled_or_unknown_status_learner(make_offering, directory):
    o = _full(make_offering)
    directory.register("z", {"CS101"})
    before = o.snapshot()
    assert o.leave_waitlist("a").outcome is Outcome.NOT_WAITLISTED   # enrolled
    assert o.leave_waitlist("z").outcome is Outcome.NOT_WAITLISTED   # never interacted
    assert o.snapshot() == before


def test_repeated_withdraw_and_rejoin_never_duplicates_records(make_offering):
    o = _full(make_offering)                      # a enrolled; b, c, d waitlisted
    for _ in range(5):
        assert o.leave_waitlist("b").outcome is Outcome.WITHDRAWN
        assert o.enroll("b").outcome is Outcome.WAITLISTED
        assert_invariants(o)
    s = o.snapshot()
    assert s.waitlist == ("c", "d", "b") and s.waitlist.count("b") == 1
