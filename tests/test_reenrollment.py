"""T9: "enroll only once" (§2.1). Dropped learners are blocked (R4); withdrawn learners may re-join (R5)."""

from course_registration import LearnerStatus, Outcome
from tests.conftest import PREREQ, assert_invariants, fill


# after drop (A5, R4): a seat may be held only once --------------------------------------------
def test_dropped_learner_gets_previously_dropped_with_seat_free(make_offering):
    o = make_offering(capacity=2, eligible=["a"])
    fill(o, "a"); o.drop("a")
    before = o.snapshot()
    r = o.enroll("a")
    assert r.outcome is Outcome.PREVIOUSLY_DROPPED and not r.ok
    assert r.message == "Learner dropped this course and cannot enroll again."
    assert o.snapshot() == before
    assert o.snapshot().statuses["a"] is LearnerStatus.DROPPED


def test_dropped_learner_gets_previously_dropped_when_full(make_offering):
    o = make_offering(capacity=1, eligible=["a", "b", "c"])
    fill(o, "a", "b", "c")
    o.drop("a")                                    # b promoted
    before = o.snapshot()
    assert o.enroll("a").outcome is Outcome.PREVIOUSLY_DROPPED
    assert o.snapshot() == before                  # not waitlisted
    assert o.snapshot().waitlist == ("c",)


def test_promoted_then_dropped_learner_is_previously_dropped(make_offering):
    """A seat gained by promotion counts as the learner's one enrollment."""
    o = make_offering(capacity=1, eligible=["a", "b"])
    fill(o, "a", "b")
    assert o.drop("a").promoted == ("b",)
    o.drop("b")
    assert o.enroll("b").outcome is Outcome.PREVIOUSLY_DROPPED


def test_previously_dropped_runs_no_eligibility_check(make_offering, directory, monkeypatch):
    """R4 runs before the prerequisite check: no eligibility lookup, and never REJECTED."""
    o = make_offering(capacity=2, eligible=["a"])
    fill(o, "a"); o.drop("a")
    directory.revoke_completion("a", PREREQ)       # would be REJECTED if eligibility were checked
    calls = []
    original = directory.has_completed
    monkeypatch.setattr(directory, "has_completed", lambda *args: calls.append(args) or original(*args))
    assert o.enroll("a").outcome is Outcome.PREVIOUSLY_DROPPED
    assert calls == []


def test_previously_dropped_is_stable_across_repeated_requests(make_offering):
    o = make_offering(capacity=1, eligible=["a"])
    fill(o, "a"); o.drop("a")
    before = o.snapshot()
    for _ in range(3):
        assert o.enroll("a").outcome is Outcome.PREVIOUSLY_DROPPED
        assert o.drop("a").outcome is Outcome.ALREADY_DROPPED
        assert o.leave_waitlist("a").outcome is Outcome.NOT_WAITLISTED
    assert o.snapshot() == before


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
