"""T9: re-enrollment after drop or withdrawal; "enroll only once" = one active record (§2.1)."""

from course_registration import LearnerStatus, Outcome
from tests.conftest import PREREQ, assert_invariants, fill


# after drop (A5) --------------------------------------------------------------------------------
def test_dropped_learner_reenrolls_directly_when_seat_free(make_offering, directory):
    o = make_offering(capacity=2, eligible=["a"])
    fill(o, "a"); o.drop("a")
    assert o.enroll("a").outcome is Outcome.ENROLLED
    assert o.snapshot().enrolled == ("a",)
    assert_invariants(o, directory)


def test_dropped_learner_reenroll_goes_to_back_of_waitlist_when_full(make_offering, directory):
    o = make_offering(capacity=1, eligible=["a", "b", "c"])
    fill(o, "a", "b", "c")
    o.drop("a")                                    # b promoted into a's seat
    assert o.enroll("a").outcome is Outcome.WAITLISTED
    s = o.snapshot()
    assert s.enrolled == ("b",) and s.waitlist == ("c", "a")
    assert_invariants(o, directory)


def test_dropped_learner_reenroll_rechecks_prereq_and_stores_nothing(make_offering, directory):
    o = make_offering(capacity=2, eligible=["a"])
    fill(o, "a"); o.drop("a")
    directory.revoke_completion("a", PREREQ)
    before = o.snapshot()
    assert o.enroll("a").outcome is Outcome.REJECTED
    assert o.snapshot() == before
    assert o.snapshot().statuses["a"] is LearnerStatus.DROPPED


def test_drop_and_reenroll_cycles_never_duplicate(make_offering, directory):
    o = make_offering(capacity=2, eligible=["a", "b"])
    fill(o, "a", "b")
    for _ in range(5):
        assert o.drop("a").outcome is Outcome.DROPPED
        assert o.enroll("a").outcome is Outcome.ENROLLED
        assert_invariants(o, directory)
    assert o.snapshot().enrolled.count("a") == 1


def test_reenrolled_learner_can_drop_again(make_offering):
    o = make_offering(capacity=1, eligible=["a"])
    fill(o, "a"); o.drop("a"); o.enroll("a")
    assert o.drop("a").outcome is Outcome.DROPPED
    assert o.drop("a").outcome is Outcome.ALREADY_DROPPED


# after withdraw (A6) ----------------------------------------------------------------------------
def _full(make_offering):
    o = make_offering(capacity=1, eligible=["a", "b", "c", "d"])
    fill(o, "a", "b", "c", "d")
    return o


def test_leave_waitlist_marks_withdrawn_and_preserves_order(make_offering):
    o = _full(make_offering)
    r = o.leave_waitlist("c")
    assert r.outcome is Outcome.WITHDRAWN and r.ok
    s = o.snapshot()
    assert s.waitlist == ("b", "d") and s.statuses["c"] is LearnerStatus.WITHDRAWN
    assert_invariants(o)


def test_withdrawn_learner_is_not_promoted(make_offering):
    o = _full(make_offering)
    o.leave_waitlist("b")
    assert o.drop("a").promoted == ("c",)


def test_withdrawn_learner_reenrolls_at_back_of_queue(make_offering):
    o = _full(make_offering)
    o.leave_waitlist("b")
    assert o.enroll("b").outcome is Outcome.WAITLISTED
    assert o.snapshot().waitlist == ("c", "d", "b")


def test_withdrawn_learner_reenrolls_directly_when_seat_free(make_offering, directory):
    o = make_offering(capacity=1, eligible=["a", "b"])
    fill(o, "a", "b")
    o.leave_waitlist("b"); o.drop("a")
    assert o.enroll("b").outcome is Outcome.ENROLLED
    assert_invariants(o, directory)


def test_withdrawn_learner_reenroll_rechecks_prereq(make_offering, directory):
    o = _full(make_offering)
    o.leave_waitlist("b")
    directory.revoke_completion("b", PREREQ)
    before = o.snapshot()
    assert o.enroll("b").outcome is Outcome.REJECTED
    assert o.snapshot() == before


def test_retained_ineligible_learner_may_withdraw(make_offering, directory):
    o = make_offering(capacity=1, eligible=["x", "A", "B"])
    fill(o, "x", "A", "B")
    directory.revoke_completion("A", PREREQ)
    o.drop("x")                                    # A skipped and retained
    assert o.leave_waitlist("A").outcome is Outcome.WITHDRAWN
    assert o.snapshot().waitlist == ()


def test_leave_waitlist_twice_and_by_non_waitlisted(make_offering, directory):
    o = _full(make_offering)
    directory.register("z", {PREREQ})
    o.leave_waitlist("b")
    before = o.snapshot()
    assert o.leave_waitlist("b").outcome is Outcome.NOT_WAITLISTED
    assert o.leave_waitlist("a").outcome is Outcome.NOT_WAITLISTED   # enrolled
    assert o.leave_waitlist("z").outcome is Outcome.NOT_WAITLISTED   # never interacted
    assert o.snapshot() == before


def test_withdraw_and_rejoin_cycles_never_duplicate(make_offering):
    o = _full(make_offering)
    for _ in range(5):
        assert o.leave_waitlist("b").outcome is Outcome.WITHDRAWN
        assert o.enroll("b").outcome is Outcome.WAITLISTED
        assert_invariants(o)
    assert o.snapshot().waitlist == ("c", "d", "b")
