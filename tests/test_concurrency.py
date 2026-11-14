import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from course_registration import CourseOffering, LearnerDirectory, Outcome
from tests.conftest import COURSE, PREREQ, assert_invariants


class SlowDirectory(LearnerDirectory):
    """Yields inside the eligibility check to widen the read-then-write window.

    Without this, CPython's GIL makes races rare enough that a missing lock in the
    service can pass these tests (verified by deleting the lock: tests still passed).
    """

    def has_completed(self, learner_id, course_id):
        time.sleep(0.001)
        return super().has_completed(learner_id, course_id)


@pytest.fixture
def make_offering():
    directory = SlowDirectory()

    def _make(capacity=2, eligible=()):
        for lid in eligible:
            directory.register(lid, {PREREQ})
        return CourseOffering(COURSE, capacity, PREREQ, directory)

    return _make


def _run_concurrently(fns, workers=32):
    barrier = threading.Barrier(len(fns))

    def wrap(fn):
        barrier.wait()   # maximise overlap
        return fn()

    with ThreadPoolExecutor(max_workers=min(workers, len(fns))) as pool:
        return list(pool.map(wrap, fns))


def test_concurrent_enrolls_never_exceed_capacity(make_offering):
    ids = [f"L{i}" for i in range(60)]
    o = make_offering(capacity=5, eligible=ids)
    results = _run_concurrently([lambda i=i: o.enroll(i) for i in ids], workers=60)
    outcomes = [r.outcome for r in results]
    assert outcomes.count(Outcome.ENROLLED) == 5
    assert outcomes.count(Outcome.WAITLISTED) == 55
    assert len(o.snapshot().waitlist) == 55
    assert_invariants(o)


def test_concurrent_duplicate_enrolls_create_one_record(make_offering):
    o = make_offering(capacity=3, eligible=["a"])
    results = _run_concurrently([lambda: o.enroll("a") for _ in range(40)], workers=40)
    outcomes = [r.outcome for r in results]
    assert outcomes.count(Outcome.ENROLLED) == 1
    assert outcomes.count(Outcome.ALREADY_ENROLLED) == 39
    assert o.snapshot().enrolled == ("a",)


def test_concurrent_repeated_drops_promote_exactly_once(make_offering):
    o = make_offering(capacity=1, eligible=["a", "b", "c"])
    for x in "abc":
        o.enroll(x)
    results = _run_concurrently([lambda: o.drop("a") for _ in range(30)], workers=30)
    outcomes = [r.outcome for r in results]
    assert outcomes.count(Outcome.DROPPED) == 1
    assert outcomes.count(Outcome.ALREADY_DROPPED) == 29
    assert sum(len(r.promoted) for r in results) == 1
    s = o.snapshot()
    assert s.enrolled == ("b",) and s.waitlist == ("c",)
    assert_invariants(o)


def test_mixed_concurrent_drops_and_enrolls_preserve_invariants(make_offering):
    seated = [f"S{i}" for i in range(10)]
    newcomers = [f"N{i}" for i in range(30)]
    o = make_offering(capacity=10, eligible=seated + newcomers)
    for s in seated:
        o.enroll(s)
    fns = [lambda s=s: o.drop(s) for s in seated] + [lambda n=n: o.enroll(n) for n in newcomers]
    _run_concurrently(fns, workers=40)
    snap = o.snapshot()
    assert len(snap.enrolled) == 10
    assert set(snap.enrolled) <= set(newcomers)
    assert len(snap.waitlist) == 20
    assert_invariants(o)
