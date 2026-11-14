import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from course_registration import CourseOffering, LearnerDirectory, Outcome
from tests.conftest import COURSE, PREREQ, assert_invariants


class SlowDirectory(LearnerDirectory):
    """Yields inside directory reads to widen the read-then-write windows in the service.

    Without this, CPython's GIL makes races rare enough that a missing lock can pass these
    tests. Verified by deliberately deleting the lock: first from enroll/drop (they passed until
    `has_completed` was slowed), then from leave_waitlist (it passed until `exists`, which every
    operation calls during validation, was slowed too).
    """

    def has_completed(self, learner_id, course_id):
        time.sleep(0.001)
        return super().has_completed(learner_id, course_id)

    def exists(self, learner_id):
        time.sleep(0.0005)
        return super().exists(learner_id)


@pytest.fixture
def slow_directory():
    return SlowDirectory()


@pytest.fixture
def make_offering(slow_directory):
    def _make(capacity=2, eligible=(), ineligible=()):
        for lid in eligible:
            slow_directory.register(lid, {PREREQ})
        for lid in ineligible:
            slow_directory.register(lid, set())
        return CourseOffering(COURSE, capacity, PREREQ, slow_directory)

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


# ---------------------------------------------------------------- v1.9 behaviour under concurrency


def test_concurrent_drop_and_leave_waitlist_resolve_to_exactly_one_outcome(make_offering):
    """A drop promoting B races B leaving the waitlist: B ends up enrolled XOR withdrawn.

    The withdrawal is delayed slightly so that, without the lock, it lands while the drop's
    promotion is checking B's eligibility (inside SlowDirectory.has_completed). That is the
    window where an unlocked implementation would delete B from the waitlist under promotion.
    """

    def late_leave(o, lid):
        time.sleep(0.0007)
        return o.leave_waitlist(lid)

    for i in range(40):
        o = make_offering(capacity=1, eligible=[f"a{i}", f"b{i}"])
        o.enroll(f"a{i}"); o.enroll(f"b{i}")
        drop_r, leave_r = _run_concurrently([lambda: o.drop(f"a{i}"), lambda: late_leave(o, f"b{i}")])
        promoted = f"b{i}" in drop_r.promoted
        withdrawn = leave_r.outcome is Outcome.WITHDRAWN
        assert promoted != withdrawn, (drop_r, leave_r)
        s = o.snapshot()
        assert s.waitlist == ()
        assert s.enrolled == ((f"b{i}",) if promoted else ())
        assert_invariants(o)


def test_concurrent_drops_and_newcomers_respect_skip_retain_and_sp1(make_offering, slow_directory):
    """Retained A stays first; eligible waitlisted B and C beat every concurrent newcomer (SP1)."""
    seated = ["s0", "s1", "s2"]
    newcomers = [f"N{i}" for i in range(8)]
    o = make_offering(capacity=3, eligible=seated + ["A", "B", "C"] + newcomers)
    for lid in seated + ["A", "B", "C"]:
        o.enroll(lid)
    slow_directory.revoke_completion("A", PREREQ)      # A will be skipped and retained

    fns = [lambda: o.drop("s0"), lambda: o.drop("s1")] + [lambda n=n: o.enroll(n) for n in newcomers]
    _run_concurrently(fns, workers=len(fns))

    s = o.snapshot()
    assert set(s.enrolled) == {"s2", "B", "C"}          # the two freed seats went to the waitlist
    assert s.waitlist[0] == "A"                         # retained at the front
    assert set(s.waitlist[1:]) == set(newcomers)        # every newcomer queued behind A
    assert_invariants(o, slow_directory)


def test_concurrent_withdraw_and_rejoin_of_same_learner_never_duplicates(make_offering):
    o = make_offering(capacity=1, eligible=["a", "b", "c"])
    o.enroll("a"); o.enroll("b"); o.enroll("c")
    fns = [(lambda: o.leave_waitlist("b")) if i % 2 == 0 else (lambda: o.enroll("b")) for i in range(30)]
    _run_concurrently(fns, workers=30)
    s = o.snapshot()
    assert s.waitlist.count("b") <= 1
    assert s.enrolled == ("a",)
    assert_invariants(o)

