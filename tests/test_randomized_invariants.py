"""Seeded random operation sequences; invariants must hold after every step."""

import random

import pytest

from course_registration import LearnerStatus, Outcome
from tests.conftest import PREREQ, assert_invariants


@pytest.mark.parametrize("seed", range(25))
def test_random_operation_sequences_preserve_invariants(make_offering, directory, seed):
    rng = random.Random(seed)
    ids = [f"L{i}" for i in range(12)]
    eligible = [i for i in ids if rng.random() < 0.8]
    o = make_offering(capacity=rng.randint(1, 4), eligible=eligible,
                      ineligible=[i for i in ids if i not in eligible])

    for _ in range(200):
        lid = rng.choice(ids + ["ghost", ""])
        op = rng.choice(["enroll", "enroll", "drop", "leave_waitlist", "toggle_prereq"])
        before = o.snapshot()
        if op == "toggle_prereq":
            if directory.exists(lid):
                (directory.revoke_completion if directory.has_completed(lid, PREREQ)
                 else directory.add_completion)(lid, PREREQ)
            continue
        r = getattr(o, op)(lid)
        if not r.ok:
            assert o.snapshot() == before, (op, lid, r)
        # terminal states are sticky
        if before.statuses.get(lid) in (LearnerStatus.DROPPED, LearnerStatus.REMOVED) and op == "enroll":
            assert r.outcome in (Outcome.PREVIOUSLY_DROPPED, Outcome.PREVIOUSLY_REMOVED)
        assert_invariants(o)
