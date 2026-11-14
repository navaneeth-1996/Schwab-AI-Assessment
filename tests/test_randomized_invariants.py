"""Seeded random operation sequences (T13); invariants 1–8 checked after every step."""

import random

import pytest

from course_registration import LearnerStatus, Outcome
from tests.conftest import PREREQ, assert_invariants, assert_order_preserved

ACTIVE = (LearnerStatus.ENROLLED, LearnerStatus.WAITLISTED)


@pytest.mark.parametrize("seed", range(30))
def test_random_operation_sequences_preserve_invariants(make_offering, directory, seed):
    rng = random.Random(seed)
    ids = [f"L{i}" for i in range(12)]
    eligible = [i for i in ids if rng.random() < 0.8]
    o = make_offering(capacity=rng.randint(1, 4), eligible=eligible,
                      ineligible=[i for i in ids if i not in eligible])

    for _ in range(250):
        lid = rng.choice(ids + ["ghost", ""])
        op = rng.choice(["enroll", "enroll", "drop", "leave_waitlist", "toggle_prereq"])
        before = o.snapshot()
        if op == "toggle_prereq":                  # simulate a record revoked / corrected
            if directory.exists(lid):
                (directory.revoke_completion if directory.has_completed(lid, PREREQ)
                 else directory.add_completion)(lid, PREREQ)
            assert o.snapshot() == before          # record changes never trigger anything (A11)
            continue

        r = getattr(o, op)(lid)
        after = o.snapshot()

        # inv 5: not-accepted outcomes are pure no-ops
        if not r.ok:
            assert after == before, (op, lid, r)
        # inv 6 / R3: enroll on an active learner never changes state, and is never REJECTED
        if op == "enroll" and before.statuses.get(lid) in ACTIVE:
            assert r.outcome in (Outcome.ALREADY_ENROLLED, Outcome.ALREADY_WAITLISTED)
        # A2: REJECTED only when the learner really is ineligible
        if r.outcome is Outcome.REJECTED:
            assert not directory.has_completed(lid, PREREQ)
        # AC 4: nobody is newly seated unless eligible at that moment
        newly_seated = set(after.enrolled) - set(before.enrolled)
        assert all(directory.has_completed(l, PREREQ) for l in newly_seated)
        # inv 7: promotion never reorders the waitlist
        assert_order_preserved(before, after)
        # inv 1, 2, 4 always; inv 3 / 8 right after a drop or a successful enroll
        triggered = (op == "drop" and r.ok) or (op == "enroll" and r.ok)
        assert_invariants(o, directory if triggered else None)
