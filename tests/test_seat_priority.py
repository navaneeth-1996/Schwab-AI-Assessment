"""T8, T8b, UC13: waitlist vs. new enrollment requests (DESIGN.md §8.3, SP1/SP2, invariant 8)."""

from course_registration import Outcome
from tests.conftest import PREREQ, assert_invariants, fill


def _vacant_seat_with_retained(make_offering, directory, waiting, capacity=2):
    """Build: `capacity` seats, one vacant, `waiting` learners retained after being skipped."""
    seated = [f"s{i}" for i in range(capacity)]
    o = make_offering(capacity=capacity, eligible=seated + list(waiting) + ["N"])
    fill(o, *seated, *waiting)
    for w in waiting:
        directory.revoke_completion(w, PREREQ)
    r = o.drop(seated[0])                          # all waiting skipped -> one seat vacant
    assert r.promoted == () and r.skipped == tuple(waiting)
    return o


# T8 / SP2 ---------------------------------------------------------------------------------------
def test_sp2_ineligible_retained_learner_does_not_block_eligible_newcomer(make_offering, directory):
    o = _vacant_seat_with_retained(make_offering, directory, ["A"])
    r = o.enroll("N")
    assert r.outcome is Outcome.ENROLLED
    assert r.skipped == ("A",) and r.promoted == ()
    s = o.snapshot()
    assert "N" in s.enrolled and s.waitlist == ("A",)   # A keeps position 1
    assert_invariants(o, directory)


# T8b / SP1 --------------------------------------------------------------------------------------
def test_sp1_corrected_waitlisted_learner_beats_newcomer(make_offering, directory):
    o = _vacant_seat_with_retained(make_offering, directory, ["A"])
    directory.add_completion("A", PREREQ)          # record corrected; seat still vacant (A11)
    r = o.enroll("N")
    assert r.outcome is Outcome.WAITLISTED
    assert r.promoted == ("A",)
    s = o.snapshot()
    assert "A" in s.enrolled and s.waitlist == ("N",)
    assert_invariants(o, directory)


def test_sp1_sp2_mixed_case(make_offering, directory):
    """§8.3 example: [A ineligible, B corrected] + N -> A skipped, B seated, waitlist [A, N]."""
    o = _vacant_seat_with_retained(make_offering, directory, ["A", "B"])
    directory.add_completion("B", PREREQ)
    r = o.enroll("N")
    assert r.outcome is Outcome.WAITLISTED
    assert r.promoted == ("B",) and r.skipped == ("A",)
    assert o.snapshot().waitlist == ("A", "N")
    assert_invariants(o, directory)


def test_newcomer_with_empty_waitlist_takes_vacant_seat(make_offering, directory):
    o = make_offering(capacity=2, eligible=["a", "N"])
    fill(o, "a")
    r = o.enroll("N")
    assert r.outcome is Outcome.ENROLLED and r.promoted == () and r.skipped == ()
    assert_invariants(o, directory)


def test_course_full_newcomer_waitlisted_without_promotion_scan(make_offering, directory):
    o = make_offering(capacity=1, eligible=["a", "b", "N"])
    fill(o, "a", "b")
    r = o.enroll("N")
    assert r.outcome is Outcome.WAITLISTED and r.promoted == () and r.skipped == ()
    assert o.snapshot().waitlist == ("b", "N")


def test_multiple_vacancies_filled_waitlist_first_then_newcomer(make_offering, directory):
    """Two vacancies, one corrected waiting learner: they take one seat, the newcomer the other."""
    o = make_offering(capacity=3, eligible=["s0", "s1", "s2", "A", "N"])
    fill(o, "s0", "s1", "s2", "A")
    directory.revoke_completion("A", PREREQ)
    o.drop("s0"); o.drop("s1")                     # A skipped twice; two vacancies
    directory.add_completion("A", PREREQ)
    r = o.enroll("N")
    assert r.outcome is Outcome.ENROLLED and r.promoted == ("A",)
    s = o.snapshot()
    assert set(s.enrolled) == {"s2", "A", "N"} and s.waitlist == ()
    assert_invariants(o, directory)


def test_single_pass_fills_every_vacancy_before_newcomer(make_offering, directory):
    """Two vacancies, two corrected waiting learners: both are seated and the newcomer waits (inv 3)."""
    o = make_offering(capacity=3, eligible=["s0", "s1", "s2", "A", "B", "N"])
    fill(o, "s0", "s1", "s2", "A", "B")
    directory.revoke_completion("A", PREREQ)
    directory.revoke_completion("B", PREREQ)
    o.drop("s0"); o.drop("s1")                     # A and B skipped; two vacancies
    directory.add_completion("A", PREREQ)
    directory.add_completion("B", PREREQ)
    r = o.enroll("N")
    assert r.promoted == ("A", "B") and r.outcome is Outcome.WAITLISTED
    assert o.snapshot().waitlist == ("N",)
    assert_invariants(o, directory)
