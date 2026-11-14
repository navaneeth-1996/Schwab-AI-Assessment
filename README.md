# Course Waitlist – Enrollment, Drop and FIFO Promotion

A bounded service for **one course offering**:
- enroll with a prerequisite check;
- drop;
- leave the waitlist;
- automatic first-in-first-out promotion from the waitlist.

In-memory, Python standard library only; pytest for tests. Implements
[`docs/DESIGN.md`](docs/DESIGN.md) **v2.0**.

| Doc | Contents |
|-----|----------|
| [`docs/DESIGN.md`](docs/DESIGN.md) | Assumptions, eligibility check points and use cases, state model, API, invariants, promotion and seat-priority rules, concurrency, tradeoffs, AC traceability, test plan, limitations |
| [`docs/AI_USAGE.md`](docs/AI_USAGE.md) | AI prompts, responses, accept/edit/reject decisions, verification evidence |
| [`docs/DESIGN_REVIEW_CHECKLIST.md`](docs/DESIGN_REVIEW_CHECKLIST.md) | Decision checklist used during design review |

## Deliverables
| Assessment deliverable | Where |
|------------------------|-------|
| Runnable code for the scoped feature | [`course_registration/`](course_registration/) (logic in `offering.py`) |
| Focused automated tests | [`tests/`](tests/): 114 tests ([test commands](#run-the-tests)) |
| Design specification | [`docs/DESIGN.md`](docs/DESIGN.md) |
| AI prompt and use record, with verification evidence | [`docs/AI_USAGE.md`](docs/AI_USAGE.md) |
| Setup and run instructions | [Setup](#setup), [Run the tests](#run-the-tests), [Run the demo](#run-the-demo) below |
| Limitations and follow-up risks | [Limitations](#limitations-and-follow-up-risks) below; full list in DESIGN.md §14 |

## Policy in brief
- **Eligibility:** the learner must have completed the course's single prerequisite. It is
  checked **only** at new enrollment, when moving to the waitlist, and at promotion. It is never
  re-checked for an already-enrolled learner.
- **Rejected:** a learner without the prerequisite gets `REJECTED`. Nothing is stored, and they
  can try again at any time.
- **Enroll only once:** a learner never has duplicate records, and may hold a seat only once.
  - Duplicate requests get `ALREADY_ENROLLED` / `ALREADY_WAITLISTED`.
  - A learner who **dropped** an enrolled seat gets `PREVIOUSLY_DROPPED`, with no eligibility check.
  - A learner who **left the waitlist** never held a seat, so they may enroll again through the
    normal flow.
- **Promotion:** runs after every drop, and before a newcomer is seated.
  - It scans the waitlist from the front and seats the first eligible learners.
  - A learner who has become ineligible while waiting is **skipped and keeps their position**,
    and is checked again at the next promotion.
- **Seat priority:** eligible waitlisted learners always come before new requests. Ineligible
  waiting learners never block an eligible newcomer from a vacant seat.

## Setup
Requires Python 3.10+ (tested on 3.11, 3.12 and 3.13).
```bash
git clone -b main https://github.com/navaneeth-1996/Schwab-AI-Assessment.git
```
```bash
cd Schwab-AI-Assessment
```
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
Expected: `114 passed`.

## Run the demo
```bash
python -m course_registration.cli --capacity 1 < examples/demo.txt
```
The demo shows:
- a rejection;
- waitlisting and a duplicate request;
- a learner whose record is revoked while waiting being skipped but keeping position 1;
- that learner getting the next seat once their record is corrected;
- a dropped learner refused with `PREVIOUSLY_DROPPED`;
- a withdrawn learner re-joining at the back of the waitlist.

Interactive: `python -m course_registration.cli --capacity 2`, then type commands such as
`learner amy CS101`, `enroll amy`, `drop amy`, `leave amy`, `revoke amy CS101`,
`complete amy CS101`, `show`.

## Library usage
```python
from course_registration import CourseOffering, LearnerDirectory, Outcome

d = LearnerDirectory()
d.register("amy", {"CS101"})
o = CourseOffering("CS201", capacity=30, prerequisite_course_id="CS101", directory=d)
r = o.enroll("amy")          # Result(outcome=Outcome.ENROLLED, ...)
r = o.drop("amy")            # r.promoted / r.skipped describe what promotion did
```

## Layout
```
course_registration/
  models.py      Outcome, LearnerStatus, Result, OfferingState
  directory.py   LearnerDirectory (stand-in for a student-records system; queried only)
  offering.py    CourseOffering – all rules, promotion and locking
  cli.py         demo shell
tests/
  conftest.py                    fixtures, assert_invariants(), assert_order_preserved()
  test_enrollment.py             T1–T4: free seat, full course, duplicates, rejection, A7
  test_promotion.py              T5–T7, T10, T12: FIFO, skip-and-retain, drops, non-triggers
  test_seat_priority.py          T8, T8b: SP1 / SP2
  test_reenrollment.py           T9: dropped learners blocked; withdrawn learners may re-join
  test_invalid_requests.py       T11: malformed or unknown IDs, bad configuration
  test_concurrency.py            T13: parallel enroll/drop/leave_waitlist with widened race windows
  test_randomized_invariants.py  T13: 30 seeded random sequences, invariants after every step
  test_cli.py                    demo script smoke test
```

## Acceptance-criteria traceability
| AC | Covered by |
|----|------------|
| 1 Enroll with capacity + prerequisite | `test_enrollment.py` (T1), `test_seat_priority.py` (SP2) |
| 2 Waitlist once; no duplicates | `test_enrollment.py` (T2, T3), `test_reenrollment.py` (cycles), `test_concurrency.py` |
| 3 Drop promotes earliest eligible | `test_promotion.py` (T5–T7) |
| 4 Ineligible never enrolled or promoted; policy consistent | `test_enrollment.py` (T4), `test_promotion.py` (T6, T7), `test_seat_priority.py`, random test |
| 5 Invalid and duplicate drops are safe | `test_promotion.py` (T10, T12), `test_invalid_requests.py` (T11) |
| 6 Test coverage + concurrency | All of the above + `test_concurrency.py`, `test_randomized_invariants.py` |
| 7 AI use record | `docs/AI_USAGE.md` |

Full mapping: DESIGN.md §11 (criteria) and §13 (tests).

## Limitations and follow-up risks
See DESIGN.md §14. In short:
- **Storage:** in-memory, single process.
- **Retained learners:** ineligible learners can wait indefinitely.
- **Corrected records:** if a skipped learner's record is corrected while a seat is vacant, the
  seat is filled only at the next drop or eligible enroll (stable-data assumption).
- **A drop is final:** a learner who drops can't re-enroll in this offering
  (`PREVIOUSLY_DROPPED`); no admin override in scope.
- **History:** only the current status is kept.
- **Notifications and admin:** none (no learner notifications, no admin operations).
- **Concurrency tests:** probabilistic.
