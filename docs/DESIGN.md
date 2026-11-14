# Course Waitlist – Design Specification (v1.0)

## 1. Scope
One course offering. Operations: **enroll**, **drop** (enrolled learner), **leave waitlist**
(waitlisted learner), and automatic **FIFO waitlist promotion** when a seat opens.

No starter project was supplied, so per the assessment's fallback this is a minimal Python
service with an in-memory store plus a thin demo CLI. Out of scope: frontend, catalog,
persistence/database, identity, payments, multi-term, configurable policy engine.

## 2. Assumptions and policy decisions
| # | Topic | Decision | Source |
|---|-------|----------|--------|
| A1 | Prerequisite rule | The offering has exactly **one prerequisite course ID**. A learner is eligible iff their completed-courses record contains it. | Candidate decision |
| A2 | Ineligible at enroll | Rejected with `PREREQUISITE_NOT_MET`; **no state is recorded**; never waitlisted. The learner may retry after completing the prerequisite. | Spec: "eligible learners join the waitlist" |
| A3 | Ineligible at front of queue | **Skip and remove.** Eligibility is re-checked at promotion time. An ineligible learner is removed from the waitlist, status becomes `REMOVED`, a `RemovalRecord` is kept, and promotion continues with the next learner. | Candidate decision (vs. "skip but keep") |
| A4 | Re-enroll after removal | Treated as a duplicate: `PREVIOUSLY_REMOVED`, no state change. **Permanent** for this offering, even if the prerequisite is later completed. | Candidate decision |
| A5 | Re-enroll after drop | A learner who was **enrolled and dropped** is `DROPPED` and **may not re-enroll** (`PREVIOUSLY_DROPPED`). | Candidate decision |
| A6 | Leave waitlist | A waitlisted learner may leave voluntarily → `WITHDRAWN`. They never held a seat, so they **may enroll again**; they re-join at the **back** of the queue (or get a seat directly if one is free). No promotion runs, since no seat opened. | Candidate decision |
| A7 | Enrolled learner loses prerequisite | Keeps the seat. Eligibility is evaluated only at enroll and promotion time. | Candidate decision |
| A8 | Waitlist size | Unlimited. | Candidate decision |
| A9 | `drop` vs `leave_waitlist` | Separate operations. `drop` on a waitlisted learner returns `NOT_ENROLLED` with a hint, instead of guessing intent. | Design choice |
| A10 | Learner identity | Learner IDs must be non-empty strings known to the `LearnerDirectory`; anything else is `INVALID_REQUEST`. | Design choice |

## 3. Learner state model
Each learner holds at most one status per offering.

| From | Event | To |
|------|-------|----|
| none / WITHDRAWN | enroll, eligible, seat free | ENROLLED |
| none / WITHDRAWN | enroll, eligible, course full | WAITLISTED (back of queue) |
| none / WITHDRAWN | enroll, not eligible | unchanged (`PREREQUISITE_NOT_MET`) |
| WAITLISTED | leave_waitlist | WITHDRAWN |
| WAITLISTED | promotion, still eligible | ENROLLED |
| WAITLISTED | promotion, no longer eligible | REMOVED (terminal) |
| ENROLLED | drop | DROPPED (terminal) |

`PREREQUISITE_NOT_MET` on enroll leaves the learner in their prior state (none or WITHDRAWN).

## 4. Service boundary
| Component | Responsibility |
|-----------|----------------|
| `LearnerDirectory` (`directory.py`) | In-memory stand-in for a student-records system: learner_id → completed course IDs. Mutable, so eligibility can change while a learner waits. |
| `CourseOffering` (`offering.py`) | Owns capacity, statuses, enrolled set, waitlist, and removal audit. All business rules and locking. |
| `Result`, `Outcome`, `OfferingState`, `RemovalRecord`, `LearnerStatus` (`models.py`) | Immutable value types. |
| `cli.py` | Demo shell only; no rules. |

## 5. API
```python
offering = CourseOffering(course_id, capacity, prerequisite_course_id, directory)
offering.enroll(learner_id)         -> Result
offering.drop(learner_id)           -> Result   # .promoted, .removed list the promotion side effects
offering.leave_waitlist(learner_id) -> Result
offering.snapshot()                 -> OfferingState  # immutable point-in-time copy
```
Expected business outcomes are returned, not raised. `ValueError` is raised only for an invalid
offering configuration at construction time (capacity < 1, empty IDs, self-prerequisite), which
is a programming error rather than a learner request.

| Operation | Success (`ok=True`, state changes) | Rejection (`ok=False`, state unchanged) |
|-----------|------------------------------------|-----------------------------------------|
| enroll | `ENROLLED`, `WAITLISTED` | `ALREADY_ENROLLED`, `ALREADY_WAITLISTED`, `PREVIOUSLY_DROPPED`, `PREVIOUSLY_REMOVED`, `PREREQUISITE_NOT_MET`, `INVALID_REQUEST` |
| drop | `DROPPED` | `ALREADY_DROPPED`, `NOT_ENROLLED`, `INVALID_REQUEST` |
| leave_waitlist | `WITHDRAWN` | `NOT_WAITLISTED`, `INVALID_REQUEST` |

## 6. Data model
| Field | Type | Notes |
|-------|------|-------|
| `_status` | `dict[str, LearnerStatus]` | Authoritative per-learner state, including terminal states (DROPPED, REMOVED, WITHDRAWN) needed for duplicate detection. |
| `_enrolled` | `dict[str, None]` | Insertion-ordered set. |
| `_waitlist` | `OrderedDict[str, int]` | learner → join sequence number. O(1) FIFO pop and O(1) removal for `leave_waitlist`. |
| `_removals` | `list[RemovalRecord]` | Audit of skip-and-remove decisions (learner, reason, sequence). |
| `_seq` | `int` | Monotonic event counter; gives deterministic ordering without a wall clock. |

## 7. Invariants
Checked by `tests/conftest.py::assert_invariants` after operations in every test module, and
after each step of 25 seeded random 200-step sequences.
1. `len(enrolled) <= capacity`.
2. Enrolled and waitlisted sets are disjoint; neither contains duplicates.
3. **No idle seat while learners wait:** if the waitlist is non-empty, the course is full.
4. The status map agrees exactly with the enrolled, waitlisted, and removed collections.
5. Every rejection outcome leaves the snapshot identical to before the call.
6. `DROPPED` and `REMOVED` are terminal: enroll always returns `PREVIOUSLY_*`.

## 8. Promotion rule
Runs after a successful `drop`, inside the same critical section:
```
while len(enrolled) < capacity and waitlist:
    learner = waitlist.pop_front()
    if eligible(learner):  status ENROLLED, add to enrolled, report as promoted
    else:                  status REMOVED, append RemovalRecord, report as removed; continue
```
The loop (rather than one step) ensures that removing ineligible learners never leaves a seat
open while an eligible learner is still waiting. Only the head of the queue is evaluated; an
ineligible learner further back is untouched until they reach the front, so regaining the
prerequisite in the meantime is honoured.

## 9. Concurrency and persistence
- **Persistence:** in-memory only (per scope). State is lost on restart.
- **Concurrency:** one `threading.Lock` per `CourseOffering`. Every public method, including
  validation, runs entirely under it, so check-then-act sequences (duplicate check → capacity
  check → insert) and drop → promote are atomic. `snapshot()` also takes the lock, so readers
  never see a half-applied promotion.
- Lock ordering: offering lock → directory lock. The directory never calls the offering, so
  deadlock is impossible.
- Concurrency tests use a `SlowDirectory` that sleeps inside the eligibility check to widen the
  race window. Without it, deleting the lock still passed the tests under CPython's GIL (found
  by deliberately breaking the code; see `docs/AI_USAGE.md`).

## 10. Tradeoffs
| Choice | Alternative | Why |
|--------|-------------|-----|
| Skip and remove | Skip but keep place | The queue can't block; promotion is O(k) in removed learners; behaviour is simple to explain. Cost: a learner whose eligibility lapses briefly loses their place permanently. |
| Return result values | Raise exceptions | Duplicate and invalid requests are expected traffic; callers branch on an enum. |
| Coarse per-offering lock | Fine-grained or optimistic locking | One offering, small critical sections; correctness first. |
| Eligibility re-checked only at the head | Re-check the whole queue on every change | Matches "promote the earliest eligible learner"; avoids scanning or evicting learners who may regain eligibility before their turn. |
