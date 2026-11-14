from course_registration import LearnerStatus, Outcome
from tests.conftest import assert_invariants


def test_drop_opens_seat_when_waitlist_empty(make_offering):
    o = make_offering(capacity=2, eligible=["a"])
    o.enroll("a")
    r = o.drop("a")
    assert r.outcome is Outcome.DROPPED and r.promoted == () and r.removed == ()
    s = o.snapshot()
    assert s.enrolled == () and s.seats_available == 2
    assert s.statuses["a"] is LearnerStatus.DROPPED
    assert_invariants(o)


def test_drop_promotes_earliest_waitlisted_learner_fifo(make_offering):
    o = make_offering(capacity=1, eligible=["a", "b", "c", "d"])
    for x in "abcd":
        o.enroll(x)
    assert o.drop("a").promoted == ("b",)
    assert o.snapshot().waitlist == ("c", "d")
    assert o.drop("b").promoted == ("c",)
    assert o.drop("c").promoted == ("d",)
    s = o.snapshot()
    assert s.enrolled == ("d",) and s.waitlist == ()
    assert_invariants(o)


def test_ineligible_head_is_skipped_and_removed_then_next_promoted(make_offering, directory):
    o = make_offering(capacity=1, eligible=["a", "b", "c"])
    for x in "abc":
        o.enroll(x)
    directory.revoke_completion("b", "CS101")      # b becomes ineligible while waiting

    r = o.drop("a")
    assert r.promoted == ("c",)
    assert [rec.learner_id for rec in r.removed] == ["b"]
    assert r.removed[0].reason is Outcome.PREREQUISITE_NOT_MET
    s = o.snapshot()
    assert s.enrolled == ("c",) and s.waitlist == ()
    assert s.statuses["b"] is LearnerStatus.REMOVED
    assert [rec.learner_id for rec in s.removals] == ["b"]
    assert_invariants(o)


def test_multiple_ineligible_learners_removed_in_one_promotion(make_offering, directory):
    o = make_offering(capacity=1, eligible=["a", "b", "c", "d"])
    for x in "abcd":
        o.enroll(x)
    directory.revoke_completion("b", "CS101")
    directory.revoke_completion("c", "CS101")
    r = o.drop("a")
    assert r.promoted == ("d",)
    assert [rec.learner_id for rec in r.removed] == ["b", "c"]
    assert_invariants(o)


def test_all_waitlisted_ineligible_leaves_seat_open_and_waitlist_empty(make_offering, directory):
    o = make_offering(capacity=1, eligible=["a", "b"])
    o.enroll("a"); o.enroll("b")
    directory.revoke_completion("b", "CS101")
    r = o.drop("a")
    assert r.promoted == () and [x.learner_id for x in r.removed] == ["b"]
    s = o.snapshot()
    assert s.enrolled == () and s.waitlist == () and s.seats_available == 1
    assert_invariants(o)


def test_removal_policy_applied_consistently_to_non_head_learners(make_offering, directory):
    """An ineligible learner behind the head is untouched until they reach the front."""
    o = make_offering(capacity=1, eligible=["a", "b", "c", "d"])
    for x in "abcd":
        o.enroll(x)
    directory.revoke_completion("c", "CS101")
    assert o.drop("a").promoted == ("b",)
    assert o.snapshot().waitlist == ("c", "d")         # c still waiting; not yet at front
    r = o.drop("b")
    assert r.promoted == ("d",) and [x.learner_id for x in r.removed] == ["c"]
    assert_invariants(o)


def test_learner_who_regains_prereq_before_reaching_front_is_promoted(make_offering, directory):
    o = make_offering(capacity=1, eligible=["a", "b"])
    o.enroll("a"); o.enroll("b")
    directory.revoke_completion("b", "CS101")
    directory.add_completion("b", "CS101")
    assert o.drop("a").promoted == ("b",)


def test_removed_learner_cannot_reenroll_even_after_regaining_prereq(make_offering, directory):
    o = make_offering(capacity=1, eligible=["a", "b"])
    o.enroll("a"); o.enroll("b")
    directory.revoke_completion("b", "CS101")
    o.drop("a")
    directory.add_completion("b", "CS101")
    before = o.snapshot()
    assert o.enroll("b").outcome is Outcome.PREVIOUSLY_REMOVED
    assert o.snapshot() == before


def test_dropped_learner_cannot_reenroll(make_offering):
    o = make_offering(capacity=2, eligible=["a"])
    o.enroll("a"); o.drop("a")
    before = o.snapshot()
    assert o.enroll("a").outcome is Outcome.PREVIOUSLY_DROPPED
    assert o.snapshot() == before


def test_repeated_drop_returns_already_dropped_and_does_not_change_state(make_offering):
    o = make_offering(capacity=1, eligible=["a", "b", "c"])
    for x in "abc":
        o.enroll(x)
    o.drop("a")                                      # promotes b
    before = o.snapshot()
    r = o.drop("a")
    assert r.outcome is Outcome.ALREADY_DROPPED and r.promoted == ()
    assert o.snapshot() == before                    # c NOT promoted, b still enrolled
    assert_invariants(o)


def test_drop_of_never_enrolled_learner(make_offering):
    o = make_offering(capacity=1, eligible=["a", "b"])
    o.enroll("a")
    before = o.snapshot()
    assert o.drop("b").outcome is Outcome.NOT_ENROLLED
    assert o.snapshot() == before


def test_drop_of_waitlisted_learner_is_rejected_with_hint(make_offering):
    o = make_offering(capacity=1, eligible=["a", "b"])
    o.enroll("a"); o.enroll("b")
    before = o.snapshot()
    r = o.drop("b")
    assert r.outcome is Outcome.NOT_ENROLLED and "leave_waitlist" in r.message
    assert o.snapshot() == before


def test_drop_of_withdrawn_or_removed_learner_is_not_enrolled(make_offering, directory):
    o = make_offering(capacity=1, eligible=["a", "b", "c"])
    for x in "abc":
        o.enroll(x)
    o.leave_waitlist("c")
    directory.revoke_completion("b", "CS101")
    o.drop("a")                                      # removes b
    before = o.snapshot()
    assert o.drop("b").outcome is Outcome.NOT_ENROLLED
    assert o.drop("c").outcome is Outcome.NOT_ENROLLED
    assert o.snapshot() == before
