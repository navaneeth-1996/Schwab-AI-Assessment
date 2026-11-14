# Course Waitlist – Design Specification (v1.2)

> **Status: v1.2 DRAFT – under review, not yet implemented.** The code still implements v1.0.
>
> Changes from v1.0:
> - **v1.1 – A5:** dropped learners may re-enroll through the normal flow (was: blocked). New
>   §2.1 defines "enroll only once" as at most one active record.
> - **v1.2 – A3:** an ineligible learner reached during promotion is **skipped and retained**:
>   they keep their waitlist position (was: skip and remove).
>   - The `REMOVED` state, `PREVIOUSLY_REMOVED` outcome and `RemovalRecord` are deleted.
>     A4 no longer applies.
>   - Promotion now scans the waitlist in order for the first eligible learner (§8).
>   - New trigger rules: promotion also runs before a newcomer is seated, and on demand (§8.2).
>   - Invariant 3 now reads "no free seat while an **eligible** learner waits" (§7).

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
| A3 | Ineligible when reached during promotion | **Skip and retain.** Eligibility is re-checked at promotion time (required by AC 3 and AC 4). An ineligible learner is **not promoted**, but **keeps their exact waitlist position**. Promotion moves on to the next learner in order. Once they are eligible again, they are first in line for the next seat. | Candidate decision (changed in v1.2; was "skip and remove") |
| A4 | ~~Re-enroll after removal~~ | **No longer applies.** Learners are never removed from the waitlist by the system. | Removed in v1.2 |
| A5 | Re-enroll after drop | A learner who was **enrolled and dropped** (`DROPPED`) **may enroll again** as a fresh request: prerequisite check → seat if free → otherwise back of the waitlist → otherwise rejected (`PREREQUISITE_NOT_MET`). | Candidate decision (changed in v1.1; was "blocked") |
| A6 | Leave waitlist | A waitlisted learner (eligible or not) may leave voluntarily → `WITHDRAWN`. They **may enroll again** through the normal flow, re-joining at the **back** of the queue (or getting a seat directly if one is free). | Candidate decision |
| A7 | Enrolled learner loses prerequisite | Keeps the seat. Eligibility is evaluated only at enroll and promotion time. | Candidate decision |
| A8 | Waitlist size | Unlimited. | Candidate decision |
| A9 | `drop` vs `leave_waitlist` | Separate operations. `drop` on a waitlisted learner returns `NOT_ENROLLED` with a hint, instead of guessing intent. | Design choice |
| A10 | Learner identity | Learner IDs must be non-empty strings known to the `LearnerDirectory`; anything else is `INVALID_REQUEST`. | Design choice |

### 2.1 Interpretation of "a learner may enroll only once"
A learner has **at most one active record** (`ENROLLED` or `WAITLISTED`) at any time. A second
enroll while active returns `ALREADY_ENROLLED` / `ALREADY_WAITLISTED` and changes nothing.
Once a learner is no longer active (`DROPPED` or `WITHDRAWN`), they may enroll again through
the same flow as a first-time learner. No state permanently blocks re-enrollment.

The prerequisite is checked at every point where a learner gains a place:
1. enroll, when a seat is free → `ENROLLED`;
2. enroll, when the course is full → `WAITLISTED`;
3. promotion from the waitlist → `ENROLLED` if eligible; otherwise **skipped, position kept**.

## 3. Learner state model
Each learner holds at most one status per offering. There are four statuses: `ENROLLED`,
`WAITLISTED`, `DROPPED`, `WITHDRAWN`. None is terminal.

| From | Event | To |
|------|-------|----|
| none / DROPPED / WITHDRAWN | enroll, eligible, seat free after promotion (§8.2) | ENROLLED |
| none / DROPPED / WITHDRAWN | enroll, eligible, course full | WAITLISTED (back of queue) |
| none / DROPPED / WITHDRAWN | enroll, not eligible | unchanged (`PREREQUISITE_NOT_MET`) |
| WAITLISTED | leave_waitlist | WITHDRAWN |
| WAITLISTED | promotion, eligible, seat free | ENROLLED |
| WAITLISTED | promotion, not eligible | WAITLISTED (unchanged, same position; reported as skipped) |
| ENROLLED | drop | DROPPED |

## 4. Service boundary
| Component | Responsibility |
|-----------|----------------|
| `LearnerDirectory` (`directory.py`) | In-memory stand-in for a student-records system: learner_id → completed course IDs. Mutable, so eligibility can change while a learner waits. |
| `CourseOffering` (`offering.py`) | Owns capacity, statuses, enrolled set and waitlist. All business rules and locking. |
| `Result`, `Outcome`, `OfferingState`, `LearnerStatus` (`models.py`) | Immutable value types. |
| `cli.py` | Demo shell only; no rules. |

## 5. API
```python
offering = CourseOffering(course_id, capacity, prerequisite_course_id, directory)
offering.enroll(learner_id)          -> Result
offering.drop(learner_id)            -> Result
offering.leave_waitlist(learner_id)  -> Result
offering.promote_waitlist()          -> Result   # NEW: fill free seats on demand (§8.2)
offering.snapshot()                  -> OfferingState  # immutable point-in-time copy
```
`Result` fields: `outcome`, `learner_id`, `message`, `promoted: tuple[str, ...]` (moved waitlist →
enrolled by this call), and `skipped: tuple[str, ...]` (ineligible learners passed over and
retained by this call).

Expected business outcomes are returned, not raised. `ValueError` is raised only for an invalid
offering configuration at construction time (capacity < 1, empty IDs, self-prerequisite), which
is a programming error rather than a learner request.

| Operation | Success (`ok=True`) | Rejection (`ok=False`, state unchanged) |
|-----------|---------------------|-----------------------------------------|
| enroll | `ENROLLED`, `WAITLISTED` | `ALREADY_ENROLLED`, `ALREADY_WAITLISTED`, `PREREQUISITE_NOT_MET`, `INVALID_REQUEST` |
| drop | `DROPPED` | `ALREADY_DROPPED`, `NOT_ENROLLED`, `INVALID_REQUEST` |
| leave_waitlist | `WITHDRAWN` | `NOT_WAITLISTED`, `INVALID_REQUEST` |
| promote_waitlist | `PROMOTION_RUN` (with `promoted` / `skipped`, possibly empty) | — |

`ALREADY_WAITLISTED` includes the learner's position and, if they are currently ineligible, says
that they will be skipped at promotion until the prerequisite is met.

## 6. Data model
| Field | Type | Notes |
|-------|------|-------|
| `_status` | `dict[str, LearnerStatus]` | Authoritative per-learner state, including inactive states (DROPPED, WITHDRAWN), needed for duplicate detection. |
| `_enrolled` | `dict[str, None]` | Insertion-ordered set. |
| `_waitlist` | `OrderedDict[str, int]` | learner → join sequence number. Ordered scan for promotion; O(1) removal for promotion and `leave_waitlist`. Skipped learners are never moved, so their position is preserved. |
| `_seq` | `int` | Monotonic counter for join order; deterministic, no wall clock. |

## 7. Invariants
1. `len(enrolled) <= capacity`.
2. Enrolled and waitlisted sets are disjoint; neither contains duplicates.
3. **No free seat while an eligible learner waits.** This holds immediately after every
   successful `drop`, every successful `enroll`, and every `promote_waitlist`. A seat *may* be
   free while the waitlist holds only ineligible learners. (Between operations, a directory
   change can make a waiting learner eligible; the next trigger in §8.2 restores the invariant.)
4. The status map agrees exactly with the enrolled and waitlisted collections.
5. Every rejection outcome leaves the snapshot identical to before the call.
6. Enroll on an active learner (`ENROLLED`/`WAITLISTED`) never changes state.
7. **Promotion never reorders the waitlist:** the relative order of learners who remain waiting
   is unchanged by any promotion.

## 8. Promotion

### 8.1 Rule
"Promote the earliest **eligible** learner", repeated while seats are free:
```
for learner in waitlist, front to back:          # iterate over a copy
    if len(enrolled) == capacity: stop
    if eligible(learner):  remove from waitlist; status ENROLLED; report as promoted
    else:                  leave in place;        report as skipped
```
A single ordered pass fills every free seat. Ineligible learners are never moved or removed,
so when they become eligible again they are ahead of everyone who joined after them.

Example: waitlist `[A, B, C]`, A is currently ineligible, one seat opens.
→ B is promoted; the waitlist becomes `[A, C]`. If A regains eligibility, A gets the next seat
ahead of C.

### 8.2 When promotion runs
All triggers run inside the same lock as the operation that causes them.
1. **After a successful `drop`.** A seat has opened.
2. **Inside `enroll`, before seating an eligible newcomer into a seat that appears free.** A
   seat can be free while ineligible learners wait. If one of them has since regained
   eligibility, they must get the seat ahead of the newcomer. Promotion runs first; the newcomer
   is seated only if a seat is still free, and otherwise joins the back of the waitlist.
   This trigger runs only on the path that would seat the newcomer, so rejected requests remain
   no-ops (invariant 5).
3. **`promote_waitlist()` on demand.** This is the hook for an external system to call when a
   learner's records change (e.g. a prerequisite completion is posted). Without it, a free seat
   would stay empty until the next drop or enroll.

`leave_waitlist` does not trigger promotion: no seat opens.

## 9. Concurrency and persistence
- **Persistence:** in-memory only (per scope). State is lost on restart.
- **Concurrency:** one `threading.Lock` per `CourseOffering`. Every public method, including
  validation and any promotion it triggers, runs entirely under it. Check-then-act sequences
  (duplicate check → promotion → capacity check → insert) and drop → promote are therefore
  atomic. `snapshot()` also takes the lock, so readers never see a half-applied promotion.
- Lock ordering: offering lock → directory lock. The directory never calls the offering, so
  deadlock is impossible.
- Concurrency tests use a `SlowDirectory` that sleeps inside the eligibility check to widen the
  race window. Without it, deleting the lock still passed the tests under CPython's GIL (found
  by deliberately breaking the code; see `docs/AI_USAGE.md`).

## 10. Tradeoffs
| Choice | Alternative | Why |
|--------|-------------|-----|
| Skip and **retain** | Skip and remove | Fair to learners whose ineligibility is temporary (e.g. a record correction); follows the spec's "earliest eligible" wording without inventing a penalty; removes a terminal state. **Cost:** ineligible learners can wait indefinitely, so the waitlist length overstates real demand; each promotion scans past them (O(n) in waitlist length); extra trigger rules are needed (§8.2). |
| Promotion before seating a newcomer + `promote_waitlist()` | Promote only on drop | Without these, a newcomer could take a free seat ahead of a waiting learner who has regained eligibility. Remaining gap: a seat can stay empty until the next trigger, if nothing calls `promote_waitlist()`. |
| Return result values | Raise exceptions | Duplicate and invalid requests are expected traffic; callers branch on an enum. |
| Coarse per-offering lock | Fine-grained or optimistic locking | One offering, small critical sections; correctness first. |

## 11. Open items (to settle before implementation)
| # | Question | Proposed |
|---|----------|----------|
| O1 | Should a failed prerequisite check at enroll be **stored** as a `REJECTED` state (audit), or only returned as `PREREQUISITE_NOT_MET`? | Return only (current A2) |
| O2 | Add "enroll once *ever*" to §10 as the rejected alternative to §2.1, with the AC 2 reasoning; list "no history of earlier enrollments after drop → re-enroll" as a limitation. | Add both |
| O3 | Keep `promote_waitlist()` as a public operation? | Yes |
| O4 | Should retained ineligible learners ever expire from the waitlist (e.g. after being skipped N times)? | No; document as a limitation |
