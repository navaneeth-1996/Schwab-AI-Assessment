"""T5–T7, T10, T12: drop, FIFO promotion, skip-and-retain (DESIGN.md §8, §13)."""

from course_registration import LearnerStatus, Outcome
from tests.conftest import PREREQ, assert_invariants, assert_order_preserved, fill


# T5 ---------------------------------------------------------------- FIFO promotion (AC 3)
def test_drop_with_empty_waitlist_opens_seat(make_offering, directory):
    o = make_offering(capacity=2, eligible=["a"])
    fill(o, "a")
    r = o.drop("a")
    assert r.outcome is Outcome.DROPPED and r.promoted == () and r.skipped == ()
    s = o.snapshot()
    assert s.enrolled == () and s.seats_available == 2
    assert s.statuses["a"] is LearnerStatus.DROPPED
    assert_invariants(o, directory)


def test_successive_drops_promote_in_fifo_order(make_offering, directory):
    o = make_offering(capacity=1, eligible=["a", "b", "c", "d"])
    fill(o, "a", "b", "c", "d")
    assert o.drop("a").promoted == ("b",)
    assert o.snapshot().waitlist == ("c", "d")
    assert o.drop("b").promoted == ("c",)
    assert o.drop("c").promoted == ("d",)
    s = o.snapshot()
    assert s.enrolled == ("d",) and s.waitlist == ()
    assert_invariants(o, directory)


# T6 ---------------------------------------------------------------- skip and retain (AC 3, 4; A3)
def test_ineligible_head_is_skipped_and_retained_at_position_one(make_offering, directory):
    """The DESIGN.md §8.1 example: [A, B, C, D], A ineligible -> B promoted, [A, C, D]."""
    o = make_offering(capacity=1, eligible=["x", "A", "B", "C", "D"])
    fill(o, "x", "A", "B", "C", "D")
    directory.revoke_completion("A", PREREQ)
    before = o.snapshot()

    r = o.drop("x")
    assert r.promoted == ("B",) and r.skipped == ("A",)
    s = o.snapshot()
    assert s.enrolled == ("B",)
    assert s.waitlist == ("A", "C", "D")
    assert s.statuses["A"] is LearnerStatus.WAITLISTED
    assert_order_preserved(before, s)
    assert_invariants(o, directory)


def test_multiple_ineligible_learners_skipped_in_one_pass(make_offering, directory):
    o = make_offering(capacity=1, eligible=["x", "a", "b", "c"])
    fill(o, "x", "a", "b", "c")
    directory.revoke_completion("a", PREREQ)
    directory.revoke_completion("b", PREREQ)
    r = o.drop("x")
    assert r.promoted == ("c",) and r.skipped == ("a", "b")
    assert o.snapshot().waitlist == ("a", "b")
    assert_invariants(o, directory)


def test_all_waitlisted_ineligible_leaves_seat_vacant_and_queue_intact(make_offering, directory):
    o = make_offering(capacity=1, eligible=["x", "a", "b"])
    fill(o, "x", "a", "b")
    directory.revoke_completion("a", PREREQ)
    directory.revoke_completion("b", PREREQ)
    r = o.drop("x")
    assert r.promoted == () and r.skipped == ("a", "b")
    s = o.snapshot()
    assert s.enrolled == () and s.waitlist == ("a", "b") and s.seats_available == 1
    assert_invariants(o, directory)


def test_skipped_learner_rechecked_at_every_promotion(make_offering, directory):
    o = make_offering(capacity=1, eligible=["x", "A", "B", "C"])
    fill(o, "x", "A", "B", "C")
    directory.revoke_completion("A", PREREQ)
    assert o.drop("x").skipped == ("A",)          # B promoted
    r = o.drop("B")
    assert r.skipped == ("A",) and r.promoted == ("C",)
    assert o.snapshot().waitlist == ("A",)


def test_promotion_stops_scanning_once_seats_full(make_offering, directory):
    o = make_offering(capacity=1, eligible=["x", "a", "b"])
    fill(o, "x", "a", "b")
    directory.revoke_completion("b", PREREQ)
    r = o.drop("x")
    assert r.promoted == ("a",) and r.skipped == ()   # b never examined


# T7 ---------------------------------------------------------------- record corrected (safeguard path)
def test_corrected_learner_promoted_at_next_drop_ahead_of_later_joiners(make_offering, directory):
    o = make_offering(capacity=1, eligible=["x", "A", "B", "C"])
    fill(o, "x", "A", "B", "C")
    directory.revoke_completion("A", PREREQ)
    o.drop("x")                                    # A skipped, B promoted -> [A, C]
    directory.add_completion("A", PREREQ)          # record corrected while course is full
    assert o.snapshot().waitlist == ("A", "C")     # nothing happens yet (A11)
    r = o.drop("B")
    assert r.promoted == ("A",) and r.skipped == ()
    assert o.snapshot().waitlist == ("C",)


def test_correction_while_seat_vacant_is_not_acted_on_until_next_trigger(make_offering, directory):
    o = make_offering(capacity=1, eligible=["x", "A"])
    fill(o, "x", "A")
    directory.revoke_completion("A", PREREQ)
    o.drop("x")                                    # A skipped; seat vacant
    directory.add_completion("A", PREREQ)
    s = o.snapshot()
    assert s.enrolled == () and s.waitlist == ("A",)   # not promoted immediately (A11)


# T10 ---------------------------------------------------------------- repeated / invalid drops (AC 5)
def test_repeated_drop_returns_already_dropped_and_promotes_nothing(make_offering):
    o = make_offering(capacity=1, eligible=["a", "b", "c"])
    fill(o, "a", "b", "c")
    o.drop("a")                                    # promotes b
    before = o.snapshot()
    r = o.drop("a")
    assert r.outcome is Outcome.ALREADY_DROPPED and r.promoted == ()
    assert o.snapshot() == before


def test_drop_of_never_enrolled_learner(make_offering):
    o = make_offering(capacity=1, eligible=["a", "b"])
    fill(o, "a")
    before = o.snapshot()
    assert o.drop("b").outcome is Outcome.NOT_ENROLLED
    assert o.snapshot() == before


def test_drop_of_waitlisted_learner_is_rejected_with_hint(make_offering):
    o = make_offering(capacity=1, eligible=["a", "b"])
    fill(o, "a", "b")
    before = o.snapshot()
    r = o.drop("b")
    assert r.outcome is Outcome.NOT_ENROLLED and "leave_waitlist" in r.message
    assert o.snapshot() == before


def test_drop_of_withdrawn_learner(make_offering):
    o = make_offering(capacity=1, eligible=["a", "b"])
    fill(o, "a", "b")
    o.leave_waitlist("b")
    before = o.snapshot()
    assert o.drop("b").outcome is Outcome.NOT_ENROLLED
    assert o.snapshot() == before


# T12 ---------------------------------------------------------------- what does NOT trigger promotion
def test_leave_waitlist_triggers_no_promotion(make_offering, directory):
    o = make_offering(capacity=1, eligible=["x", "A", "B"])
    fill(o, "x", "A", "B")
    directory.revoke_completion("A", PREREQ)
    directory.revoke_completion("B", PREREQ)
    o.drop("x")                                    # A and B skipped; seat vacant
    directory.add_completion("B", PREREQ)          # B now eligible, but nothing triggers (A11)
    r = o.leave_waitlist("A")
    assert r.outcome is Outcome.WITHDRAWN and r.promoted == ()
    s = o.snapshot()
    assert s.enrolled == () and s.waitlist == ("B",)   # B NOT promoted by a withdrawal


def test_rejected_enroll_never_triggers_promotion(make_offering, directory):
    o = make_offering(capacity=1, eligible=["x", "A"], ineligible=["n"])
    fill(o, "x", "A")
    directory.revoke_completion("A", PREREQ)
    o.drop("x")                                    # seat vacant, A retained
    directory.add_completion("A", PREREQ)          # A now eligible, but nothing triggers
    before = o.snapshot()
    r = o.enroll("n")                              # ineligible newcomer
    assert r.outcome is Outcome.REJECTED and r.promoted == ()
    assert o.snapshot() == before                  # invariant 5: pure no-op
