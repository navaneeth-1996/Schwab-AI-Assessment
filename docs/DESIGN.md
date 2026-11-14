# Course Waitlist – Design Specification (DRAFT v0.1)

> Status: draft for review. Items marked **[OPEN]** need confirmation before implementation.

## 1. Scope
One course offering. Operations: **enroll**, **drop** (enrolled learner), **leave waitlist** (waitlisted
learner), and automatic **FIFO waitlist promotion** when a seat opens.
No starter project was supplied, so this is a minimal Python service with an in-memory store
(per the assessment's fallback). No frontend, catalog, persistence, auth, or policy engine.

## 2. Confirmed assumptions
| # | Topic | Decision |
|---|-------|----------|
| A1 | Prerequisite rule | The offering has exactly **one prerequisite course ID**. A learner is eligible iff their completed-courses record contains that ID. |
| A2 | Ineligible at enroll time | Request is **rejected** (`PREREQUISITE_NOT_MET`). Ineligible learners never join the waitlist. |
| A3 | Ineligible at promotion time | **Skip and remove.** Eligibility is re-checked when a learner reaches the front of the queue. If no longer eligible, they are removed from the waitlist, a **removal record** is kept (learner, reason, sequence), and promotion continues with the next learner. |
| A4 | Re-enroll after removal | A learner with a removal record who calls enroll again is treated as a **duplicate**: no new record, state unchanged, result `PREVIOUSLY_REMOVED`. |
| A5 | Waitlist size | **Unlimited.** |
| A6 | Leave waitlist | A waitlisted learner may voluntarily leave the waitlist. No seat opens, so no promotion runs. |
| A7 | Stack | Python 3, pytest. |

## 3. Service boundary
```
LearnerDirectory   – in-memory learner records: learner_id -> set(completed course IDs)
                     (stand-in for an external student-records system; mutable so eligibility
                      can change while a learner waits)
CourseOffering     – owns capacity, enrolled set, waitlist, removal records; all business rules
Result / Outcome   – explicit result values returned by every operation (no exceptions for
                     expected business outcomes)
cli.py (optional)  – thin demo wrapper; no logic
```

## 4. API (draft)
```python
offering = CourseOffering(course_id, capacity, prerequisite_course_id, directory)

offering.enroll(learner_id)          -> Result
offering.drop(learner_id)            -> Result   # includes promoted / removed learner IDs
offering.leave_waitlist(learner_id)  -> Result
offering.snapshot()                  -> OfferingState   # immutable copy for inspection/tests
```

| Operation | Possible outcomes |
|-----------|-------------------|
| enroll | `ENROLLED`, `WAITLISTED`, `ALREADY_ENROLLED`, `ALREADY_WAITLISTED`, `PREVIOUSLY_REMOVED`, `PREREQUISITE_NOT_MET`, `INVALID_REQUEST` |
| drop | `DROPPED`, `NOT_ENROLLED`, `INVALID_REQUEST` |
| leave_waitlist | `LEFT_WAITLIST`, `NOT_WAITLISTED`, `INVALID_REQUEST` |

`INVALID_REQUEST`: empty / non-string learner ID, or learner unknown to the directory.

## 5. Data model
- `capacity: int` (validated > 0 at construction)
- `enrolled: set[str]`
- `waitlist: OrderedDict[str, int]` – learner_id -> join sequence number; O(1) FIFO pop and O(1) removal
- `removed: dict[str, RemovalRecord]` – audit of skip-and-remove decisions
- `_seq: int` – monotonic counter for deterministic ordering (no wall clock)

## 6. Invariants (checked in tests after every operation)
1. `len(enrolled) <= capacity`
2. `enrolled`, `waitlist`, `removed` are pairwise disjoint (a learner is in at most one state)
3. No duplicates in waitlist
4. If `len(enrolled) < capacity` then waitlist contains no learner (promotion drained it)
5. Any non-success outcome leaves state unchanged

## 7. Promotion rule
Triggered after a successful `drop`, inside the same critical section:
```
while len(enrolled) < capacity and waitlist:
    learner = pop head of waitlist
    if eligible(learner): enrolled.add(learner); record as promoted
    else:                 removed[learner] = RemovalRecord(reason=PREREQUISITE_NOT_MET); continue
```

## 8. Concurrency
Each `CourseOffering` holds a `threading.Lock`; every public method runs entirely under it, so
drop + promotion is atomic. A focused test fires many concurrent enrolls at a small capacity and
asserts the invariants.

## 9. [OPEN] Questions
- Q1 – Re-enroll after voluntary drop / voluntary leave of waitlist: allowed (back of queue) or
  treated as duplicate like A4?
- Q2 – Is A4 permanent, even if the learner later completes the prerequisite?
- Q3 – An already-enrolled learner whose prerequisite is later revoked: stays enrolled
  (proposed – eligibility is only checked at enroll and promotion time).
