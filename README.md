# Course Waitlist – Enrollment, Drop and FIFO Promotion

A bounded service for **one course offering**:
- enroll with a prerequisite check;
- drop;
- leave the waitlist;
- automatic first-in-first-out promotion from the waitlist, which skips and removes learners who
  no longer meet the prerequisite.

In-memory, Python standard library only; pytest for tests.

| Doc | Contents |
|-----|----------|
| [`docs/DESIGN.md`](docs/DESIGN.md) | Assumptions, state model, API, invariants, promotion rule, concurrency, tradeoffs |
| [`docs/AI_USAGE.md`](docs/AI_USAGE.md) | AI prompts, responses, accept/edit/reject decisions, verification evidence |

## Policy in one paragraph
A learner is eligible if they have completed the offering's single prerequisite course.
Ineligible learners are rejected and never waitlisted. When the course is full, eligible
learners join the waitlist in arrival order. When an enrolled learner drops, seats are refilled
from the front of the waitlist. A learner at the front who is **no longer eligible is removed**,
with an audit record, and the next learner is tried. **DROPPED** and **REMOVED** learners cannot
enroll again. A learner who voluntarily **leaves the waitlist (WITHDRAWN)** can enroll again,
at the back of the queue.

## Setup
Requires Python 3.10+.
```bash
python3 -m venv .venv
```
```bash
source .venv/bin/activate
```
```bash
pip install -r requirements-dev.txt
```

## Run the tests
```bash
pytest -q
```
Expected: `88 passed`.

## Run the demo
```bash
python -m course_registration.cli --capacity 1 < examples/demo.txt
```
Or run it interactively with `python -m course_registration.cli --capacity 2`, then type
commands such as `learner amy CS101`, `enroll amy`, `drop amy`, `leave amy`,
`revoke amy CS101` and `show`.

## Library usage
```python
from course_registration import CourseOffering, LearnerDirectory, Outcome

d = LearnerDirectory()
d.register("amy", {"CS101"})
o = CourseOffering("CS201", capacity=30, prerequisite_course_id="CS101", directory=d)
r = o.enroll("amy")          # Result(outcome=Outcome.ENROLLED, ...)
r = o.drop("amy")            # r.promoted / r.removed list what promotion did
```

## Layout
```
course_registration/
  models.py      Outcome, LearnerStatus, Result, OfferingState, RemovalRecord
  directory.py   LearnerDirectory (stand-in for a student-records system)
  offering.py    CourseOffering – all rules and locking
  cli.py         demo shell
tests/
  conftest.py                  fixtures + assert_invariants()
  test_enroll.py               free seat, full course, prerequisite failure, duplicates
  test_drop_and_promotion.py   FIFO, skip-and-remove, repeated or invalid drops
  test_waitlist_withdrawal.py  WITHDRAWN state and re-enroll
  test_invalid_requests.py     malformed or unknown IDs, bad configuration
  test_concurrency.py          parallel enroll/drop with a widened race window
  test_randomized_invariants.py  seeded random sequences, invariants after every step
  test_cli.py                  demo script smoke test
```

## Acceptance-criteria traceability
| AC | Covered by |
|----|------------|
| 1 Enroll with capacity + prerequisite | `test_enroll.py::test_enroll_succeeds_*`, `test_enroll_fills_to_exact_capacity` |
| 2 Waitlist once; no duplicates | `test_full_course_*`, `test_duplicate_enroll_*`, `test_concurrent_duplicate_enrolls_*` |
| 3 Drop promotes earliest eligible | `test_drop_promotes_earliest_waitlisted_learner_fifo`, `test_ineligible_head_*` |
| 4 Ineligible never enrolled; policy consistent | `test_prerequisite_failure_*`, `test_multiple_ineligible_*`, `test_removal_policy_applied_consistently_*`, `test_removed_learner_cannot_reenroll_*` |
| 5 Invalid and duplicate drops are safe | `test_invalid_requests.py`, `test_repeated_drop_*`, `test_drop_of_*` |
| 6 Test coverage + concurrency | All of the above + `test_concurrency.py`, `test_randomized_invariants.py` |
| 7 AI use record | `docs/AI_USAGE.md` |

## Limitations and follow-up risks
- **In-memory only.** State is lost on restart. A real store would need the drop → promote step
  in one database transaction, with row locking (e.g. `SELECT … FOR UPDATE`) or a
  version-number check, and unique constraints on (offering, learner).
- **Single process.** The `threading.Lock` doesn't protect multiple processes or hosts.
- **Removal is permanent.** A learner whose prerequisite record is briefly wrong (e.g. a data
  correction in progress) at the moment they reach the front loses their place for good.
  Needs an admin override, or a "hold" state, in a real system.
- **No notifications.** Promoted or removed learners aren't told; `Result.promoted` and
  `Result.removed` are the hook for that.
- **Eligibility is checked only at the front of the queue**, so the waitlist can hold learners
  who are currently ineligible. Waitlist length overstates real demand.
- **The promotion audit lives in memory.** `RemovalRecord` has no timestamp or actor; a real
  system needs durable audit logging.
- **No admin operations.** There is no capacity change, reinstatement, or force-enroll. A
  capacity increase would also need to trigger promotion.
- **Concurrency tests** rely on a sleep-based race window. They're reliable here, but they are
  probabilistic by nature.
- Learner IDs are matched exactly: `"Amy"` and `"amy "` are different learners.
