import pytest

from course_registration import CourseOffering, LearnerDirectory, Outcome
from tests.conftest import assert_invariants

BAD_IDS = [None, "", "   ", 123, ["a"], b"a"]


@pytest.mark.parametrize("bad", BAD_IDS)
@pytest.mark.parametrize("op", ["enroll", "drop", "leave_waitlist"])
def test_malformed_learner_id_is_invalid_and_state_unchanged(make_offering, op, bad):
    o = make_offering(capacity=1, eligible=["a", "b"])
    o.enroll("a"); o.enroll("b")
    before = o.snapshot()
    r = getattr(o, op)(bad)
    assert r.outcome is Outcome.INVALID_REQUEST and not r.ok
    assert o.snapshot() == before
    assert set(o.snapshot().statuses) == {"a", "b"}   # no status recorded for the bad ID


@pytest.mark.parametrize("op", ["enroll", "drop", "leave_waitlist"])
def test_unknown_learner_is_invalid(make_offering, op):
    o = make_offering(capacity=1, eligible=["a"])
    o.enroll("a")
    before = o.snapshot()
    r = getattr(o, op)("ghost")
    assert r.outcome is Outcome.INVALID_REQUEST and "Unknown" in r.message
    assert o.snapshot() == before
    assert "ghost" not in o.snapshot().statuses
    assert_invariants(o)


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(capacity=0),
        dict(capacity=-1),
        dict(capacity=1.5),
        dict(capacity=True),
        dict(course_id=""),
        dict(prerequisite_course_id="  "),
        dict(prerequisite_course_id="CS201"),   # self-prerequisite
        dict(directory=None),
    ],
)
def test_invalid_offering_configuration_rejected(kwargs):
    args = dict(course_id="CS201", capacity=1, prerequisite_course_id="CS101", directory=LearnerDirectory())
    args.update(kwargs)
    with pytest.raises(ValueError):
        CourseOffering(**args)


def test_snapshot_is_immutable_copy(make_offering):
    o = make_offering(capacity=1, eligible=["a", "b"])
    o.enroll("a")
    s = o.snapshot()
    with pytest.raises(TypeError):
        s.statuses["b"] = "ENROLLED"  # type: ignore[index]
    o.enroll("b")
    assert s.waitlist == ()                          # earlier snapshot unaffected
