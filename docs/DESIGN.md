# Course Waitlist – Design Specification (v1.4)

> **Status: v1.4 DRAFT – under review, not yet implemented.** The code still implements v1.0.
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
> - **v1.3:** documentation only, no policy change.
>   - §2.1 now spells out the three eligibility check points, and why the promotion re-check
>     is a safeguard.
>   - Added acceptance-criteria traceability (§11), scope compliance (§12), test plan (§13)
>     and limitations (§14).
> - **v1.4:** O2 resolved. "Enroll only once" = no duplicate active records (candidate decision);
>   §2.1 rewritten as explicit rules; the rejected "once ever" reading added to §10.

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

### 2.1 Interpretation of "a learner may enroll only once" (decided)
The statement prohibits **duplicate records**, not re-enrollment. Concretely:

| Rule | Meaning |
|------|---------|
| R1 | A learner who is `ENROLLED` is never also `WAITLISTED`. |
| R2 | A learner who is `WAITLISTED` is never also `ENROLLED`. |
| R3 | While a learner is `ENROLLED` or `WAITLISTED` (active), any new enroll request is rejected (`ALREADY_ENROLLED` / `ALREADY_WAITLISTED`) and changes nothing. |
| R4 | A learner who **dropped** an enrolled seat (`DROPPED`) or **withdrew** from the waitlist (`WITHDRAWN`) is no longer active, and **may enroll again** through the same flow as a first-time learner (§2.2). |

R1–R3 are guaranteed by storing exactly one status per learner (§6), and are asserted by
invariants 2 and 6. No state permanently blocks re-enrollment.

### 2.2 Eligibility (prerequisite) check points
The prerequisite is checked at **every** point where a learner gains a place:

| # | Check point | If eligible | If not eligible |
|---|-------------|-------------|-----------------|
| C1 | `enroll`, seat free | `ENROLLED` | Rejected: `PREREQUISITE_NOT_MET`, no state change |
| C2 | `enroll`, course full (moving to the waitlist) | `WAITLISTED`, back of queue | Rejected: `PREREQUISITE_NOT_MET`, no state change |
| C3 | Promotion, waitlist → enrolled | `ENROLLED` | **Skipped and retained**: stays `WAITLISTED` at the same position |

C1 and C2 are one check, made in `enroll` *before* the seat-or-waitlist decision. So no
ineligible learner ever enters the waitlist.

**Why C3 exists (safeguard).** Every waitlisted learner passed C2 when they joined, so under
normal conditions C3 always passes. C3 only fails if the learner's records change while they
wait: for example, a prerequisite completion is revoked, corrected, or was posted in error.
AC 4 requires that such a learner is not promoted. Skip and retain (A3) means that a records
change can block a promotion, but **never costs the learner their position**. When their
records are fixed, they are next in line.

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
| "Enroll only once" = no duplicate active records; re-enroll after drop/withdraw allowed | "Once ever": block any learner who has ever enrolled | AC 2 makes the requirement testable as "duplicate enrollment requests do not create duplicate records", and no AC forbids re-enrolling after a drop. Re-enrollment can't jump the queue: a dropped seat is offered to the waitlist first, and a re-enrolling learner joins the back if the course is full. **Cost:** a reviewer may hold the stricter reading; this is mitigated by documenting the rules explicitly (§2.1). |
| Return result values | Raise exceptions | Duplicate and invalid requests are expected traffic; callers branch on an enum. |
| Coarse per-offering lock | Fine-grained or optimistic locking | One offering, small critical sections; correctness first. |

## 11. Acceptance-criteria traceability
| AC | Requirement (from the assessment) | How the design satisfies it | Section |
|----|-----------------------------------|------------------------------|---------|
| 1 | Enrollment succeeds when capacity remains and the prerequisite is met | Check C1; seat assigned only if `len(enrolled) < capacity` after any pending promotion | §2.2, §8.2 |
| 2 | When full, an eligible learner joins the waitlist **once**; duplicate requests create no duplicate records | Check C2; one status per learner; enroll on an active learner returns `ALREADY_*` with no change | §2.1, §3, inv. 2, 6 |
| 3 | Drop opens a seat and promotes the earliest **eligible** waitlisted learner per the documented policy | Promotion trigger 1 after every successful drop; ordered scan promotes the first eligible learner(s) | §8.1, §8.2 |
| 4 | An ineligible learner is not enrolled or promoted; the skip/retain policy is applied **consistently** | C1/C2 reject; C3 skips and retains. One promotion routine is used by all three triggers, so the policy is identical everywhere | §2.2, A3, §8 |
| 5 | Invalid requests and duplicate drops return clear results without corrupting enrollment, capacity or waitlist | `INVALID_REQUEST`, `ALREADY_DROPPED`, `NOT_ENROLLED`, `NOT_WAITLISTED`; every rejection leaves state identical | §5, inv. 5 |
| 6 | Tests for capacity available/full, duplicates, FIFO promotion, prerequisite failure, invalid/repeated drops; concurrency test where practical | Test plan T1–T12, including concurrency with a widened race window | §13 |
| 7 | Record AI prompts, responses, accept/edit/reject decisions, verification | `docs/AI_USAGE.md` (to be updated with the v1.1–v1.3 design decisions during development) | — |

Problem-statement checks:

| Statement | Design |
|-----------|--------|
| "A learner may enroll only once." | No duplicate active records: rules R1–R4 (§2.1). Consistent with AC 2 ("duplicate enrollment requests do not create duplicate records"). The stricter "once ever" reading was considered and rejected (§10). |
| "When the course is full, eligible learners join the waitlist." | C2 |
| "If a seat opens, promote the earliest eligible learner." | §8.1, word for word |
| "Define whether an ineligible learner is skipped or remains waiting, and apply that policy consistently." | A3: skipped *and* remains waiting at the same position; one routine (§8) |

## 12. Scope and deliverable compliance
| Assessment boundary / expectation | Status |
|-----------------------------------|--------|
| One offering's enroll, drop and waitlist-promotion slice only | ✅ Single `CourseOffering`. `leave_waitlist` and `promote_waitlist` serve the waitlist slice; no other features. |
| No frontend, catalog, payments, identity, multi-term, deployment, new database | ✅ In-memory store; a demo CLI only (the assessment's "command-line prototype" fallback) |
| No separate greenfield/brownfield/ambiguous variants | ✅ One implementation |
| State assumptions; **no configurable policy engine** | ✅ Fixed rules A1–A10; no policy flags or plug-ins |
| No starter supplied → minimal service or CLI with in-memory store | ✅ |
| State what happens when an ineligible learner reaches the front | ✅ A3, §2.2 C3 |
| Prioritise correct capacity/queue behaviour over feature count | ✅ Invariants 1–7 asserted in every test; ⚠ `promote_waitlist()` is a small addition needed for the retain policy (O3) |
| No credentials or sensitive data in prompts/records | ✅ Fictional learner IDs only |
| Design spec covers boundary, data/API, invariants, promotion rule, concurrency/persistence, assumptions/tradeoffs | ✅ §2–§10 |
| Runnable code, focused tests, setup/run instructions, limitations summary | ⏳ Code and README to be updated to v1.3 after design sign-off; limitations in §14 |

## 13. Test plan (to implement after sign-off)
| # | Scenario | AC |
|---|----------|----|
| T1 | Enroll with a free seat and the prerequisite met → `ENROLLED`; fill to exact capacity | 1 |
| T2 | Course full → `WAITLISTED` in arrival order | 2 |
| T3 | Duplicate enroll while enrolled / waitlisted / just promoted → `ALREADY_*`, no change; 40 concurrent duplicate enrolls → one record | 2, 6 |
| T4 | Prerequisite not met at C1 and at C2 → rejected, never waitlisted, no state recorded | 4 |
| T5 | Drop promotes the earliest eligible learner; successive drops follow FIFO | 3 |
| T6 | **Skip and retain:** an ineligible head is skipped, the next eligible learner is promoted, and the skipped learner keeps position 1 | 3, 4 |
| T7 | A retained learner regains eligibility → gets the next seat ahead of later joiners, via a drop, via an enroll trigger, or via `promote_waitlist()` | 3, 4 |
| T8 | Only ineligible learners waiting → seat stays free; an eligible newcomer gets it directly | 1, 4 |
| T9 | Re-enroll after drop and after withdraw: seat if free, back of queue if full, rejected if no longer eligible; repeated cycles never duplicate | 2 |
| T10 | Repeated drop → `ALREADY_DROPPED`; drop of a waitlisted, withdrawn or never-enrolled learner → `NOT_ENROLLED`; no extra promotion | 5 |
| T11 | Malformed or unknown learner IDs on every operation → `INVALID_REQUEST`, state unchanged; invalid construction raises `ValueError` | 5 |
| T12 | Concurrency: parallel enrolls never exceed capacity; parallel repeated drops promote once; mixed drops/enrolls keep invariants; seeded random sequences check invariants 1–7 after each step | 6 |

## 14. Limitations and follow-up risks
- **In-memory, single process.** State is lost on restart, and the lock doesn't protect multiple
  processes. A real store needs drop → promote in one transaction, with row locks or version
  checks, and a unique constraint on (offering, learner).
- **Retained ineligible learners can wait indefinitely** (O4). The waitlist length overstates
  real demand, and each promotion scans past them.
- **An idle seat until the next trigger.** If a retained learner regains eligibility while a seat
  is free, the seat stays empty until the next drop, the next eligible enroll, or a
  `promote_waitlist()` call. Nothing calls it automatically when records change.
- **No history.** Only the current status is stored, so after drop → re-enroll there's no record
  of the earlier enrollment, and skips are reported in the `Result` but not stored.
- **"Enroll only once" interpretation.** The decided reading (§2.1) allows re-enrollment after a drop or withdrawal; a reviewer holding the "once ever" reading would see this differently (§10).
- **No notifications** to promoted or skipped learners, and **no admin operations** (capacity
  change, force-enroll).
- **Concurrency tests are probabilistic.** They rely on a widened race window.
- Learner IDs are matched exactly (no case or whitespace normalisation).

## 15. Open items (to settle before implementation)
| # | Question | Proposed |
|---|----------|----------|
| O1 | Should a failed prerequisite check at enroll be **stored** as a `REJECTED` state (audit), or only returned as `PREREQUISITE_NOT_MET`? | Return only (current A2) |
| O2 | ~~Interpretation of "enroll only once"~~ | **Resolved (v1.4):** no duplicate active records, R1–R4 in §2.1; "once ever" recorded as the rejected alternative in §10; the no-history limitation is in §14. |
| O3 | Keep `promote_waitlist()` as a public operation? | Yes |
| O4 | Should retained ineligible learners ever expire from the waitlist (e.g. after being skipped N times)? | No; document as a limitation |
