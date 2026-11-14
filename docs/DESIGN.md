# Course Waitlist – Design Specification (v1.9)

> **Status: v1.9 – under review; not yet implemented** (the code still implements v1.0).
> Revision history (v1.0 → v1.9) and the reasoning behind each decision will be recorded in
> `docs/AI_USAGE.md` during implementation; until then, see the git history of this file.

## 1. Scope
One course offering. Operations: **enroll**, **drop** (enrolled learner), **leave waitlist**
(waitlisted learner), and automatic **FIFO waitlist promotion** when a seat opens, or before a
newcomer is seated (§8.2).

No starter project was supplied, so per the assessment's fallback this is a minimal Python
service with an in-memory store plus a thin demo CLI. Out of scope: frontend, catalog,
persistence/database, identity, payments, multi-term, configurable policy engine.

## 2. Assumptions and policy decisions
| # | Topic | Decision | Source |
|---|-------|----------|--------|
| A1 | Prerequisite rule | The offering has exactly **one prerequisite course ID**. A learner is eligible iff their completed-courses record contains it. | Candidate decision |
| A2 | Ineligible at enroll | **Rejected.** Returns outcome `REJECTED` with a message naming the missing prerequisite. **Nothing is stored:** the learner's status (none, `DROPPED` or `WITHDRAWN`), seats and waitlist are unchanged. The learner may try again at any time; eligibility is re-checked on every attempt. | Candidate decision (v1.7) |
| A3 | Ineligible when reached during promotion | **Skip and retain.** The learner is not promoted (AC 4), keeps their exact FIFO position, and is re-checked at every later promotion. Once eligible, they are first in line for the next seat. | Candidate decision (v1.2) |
| A4 | ~~Re-enroll after removal~~ | **No longer applies.** The system never removes learners from the waitlist. | Removed in v1.2 |
| A5 | Re-enroll after drop | A `DROPPED` learner **may enroll again** through the normal flow (§2.2). | Candidate decision (v1.1) |
| A6 | Leave waitlist | A waitlisted learner (eligible or not) may leave voluntarily → `WITHDRAWN`, and **may enroll again** through the normal flow, re-joining at the **back** of the queue (or getting a seat if one is free). | Candidate decision |
| A7 | Enrolled learner loses prerequisite | **Eligibility is never checked for already-enrolled learners.** An enrolled learner keeps their seat whatever happens to their records later. Eligibility is evaluated only at the three check points in §2.2 (new enrollment, moving to the waitlist, promotion). | Candidate decision (confirmed v1.9) |
| A8 | Waitlist size | Unlimited. | Candidate decision |
| A9 | `drop` vs `leave_waitlist` | Separate operations. `drop` on a waitlisted learner returns `NOT_ENROLLED` with a hint, instead of guessing intent. | Design choice |
| A10 | Learner identity | Learner IDs must be non-empty strings known to the `LearnerDirectory`; anything else is `INVALID_REQUEST`, and no status is recorded. | Design choice |
| A11 | Prerequisite data stability | Learners' completed-course records are assumed **stable during normal operation**. The service does not watch for record changes. Eligibility is evaluated only at the check points in §2.2, and the promotion-time check (C3) is a **safeguard** for the rare case where a record changed while the learner waited. | Candidate decision (v1.6) |

### 2.1 Interpretation of "a learner may enroll only once" (decided)
The statement prohibits **duplicate records**, not re-enrollment.

| Rule | Meaning |
|------|---------|
| R1 | A learner who is `ENROLLED` is never also `WAITLISTED`. |
| R2 | A learner who is `WAITLISTED` is never also `ENROLLED`. |
| R3 | While a learner is `ENROLLED` or `WAITLISTED` (active), any new enroll request is rejected as a duplicate (`ALREADY_ENROLLED` / `ALREADY_WAITLISTED`) and changes nothing. This duplicate check runs **before** the prerequisite check, so an active learner always gets the duplicate result, never `REJECTED`. |
| R4 | A learner who is `DROPPED` or `WITHDRAWN` is inactive, and **may enroll again** through the same flow as a first-time learner (§2.2). A learner whose request was `REJECTED` simply has no new record, and may also try again. |

R1–R3 are guaranteed by storing exactly one status per learner (§6), and are asserted by
invariants 2 and 6. No state permanently blocks re-enrollment.

### 2.2 Eligibility (prerequisite) check points
The prerequisite is checked at **every** point where a learner gains a place:

| # | Check point | If eligible | If not eligible |
|---|-------------|-------------|-----------------|
| C1 | `enroll`, seat free | `ENROLLED` | `REJECTED` outcome; no state change |
| C2 | `enroll`, course full (moving to the waitlist) | `WAITLISTED`, back of queue | `REJECTED` outcome; no state change |
| C3 | Promotion, waitlist → enrolled | `ENROLLED` | **Skipped and retained**: stays `WAITLISTED` at the same position; re-checked at the next promotion |

C1 and C2 are one check, made in `enroll` *before* the seat-or-waitlist decision. So no
ineligible learner ever enters the waitlist.

These are the **only** places eligibility is evaluated. It is **never** evaluated for an
already-enrolled learner (A7), on a duplicate request, on `drop`, or on `leave_waitlist`. The
service does not react to record changes between check points (A11).

**Why C3 exists (safeguard).** Every waitlisted learner passed C2 when they joined, and
prerequisite data is stable during normal operation (A11), so under normal conditions C3 always passes. C3 only fails if the learner's records change while they
wait (a completion is revoked, corrected, or was posted in error). AC 4 requires that such a
learner is not promoted. Skip and retain means that a records change can block a promotion,
but **never costs the learner their position**.

### 2.3 Eligibility decision use cases
| # | Use case | Eligibility checked? | Outcome |
|---|----------|----------------------|---------|
| UC1 | New learner, prerequisite met, seat free | ✅ C1 | `ENROLLED` |
| UC2 | New learner, prerequisite met, course full | ✅ C2 | `WAITLISTED` at the back |
| UC3 | New learner, prerequisite not met (seat free or course full) | ✅ C1/C2 | `REJECTED`; nothing stored |
| UC4 | Enrolled learner's prerequisite record is later revoked | ❌ never (A7) | Keeps the seat; nothing happens |
| UC5 | Enrolled learner sends another enroll request | ❌ duplicate check only (R3) | `ALREADY_ENROLLED`; no change |
| UC6 | Enrolled learner drops (eligible or not) | ❌ | `DROPPED`; the seat opens, and promotion (P1) checks the waitlisted learners |
| UC7 | Waitlisted learner sends another enroll request | ❌ duplicate check only (R3) | `ALREADY_WAITLISTED` with position; no change |
| UC8 | Waitlisted learner leaves the waitlist | ❌ | `WITHDRAWN`; no promotion |
| UC9 | Seat opens; the learner at the front is eligible | ✅ C3 | Promoted to `ENROLLED` |
| UC10 | Seat opens; the learner at the front has had their record revoked since joining | ✅ C3 (safeguard) | Skipped and retained at the same position; the next eligible learner is promoted |
| UC11 | A skipped learner's record is corrected; the next seat opens | ✅ C3 | Promoted ahead of everyone who joined after them |
| UC12 | Dropped or withdrawn learner enrolls again | ✅ C1/C2 (treated as new) | `ENROLLED`, `WAITLISTED` or `REJECTED`, exactly as UC1–UC3 |
| UC13 | Eligible newcomer arrives while a seat is vacant and only ineligible learners wait | ✅ C1 for the newcomer, C3 for the waiting learners (P2) | Waiting learners are skipped and retained; the newcomer takes the seat (SP2) |

## 3. Learner state model
Four statuses: `ENROLLED`, `WAITLISTED` (active); `DROPPED`, `WITHDRAWN` (inactive).
None is terminal.

| From | Event | To |
|------|-------|----|
| none / DROPPED / WITHDRAWN | enroll, eligible, seat free | ENROLLED |
| none / DROPPED / WITHDRAWN | enroll, eligible, course full | WAITLISTED (back of queue) |
| none / DROPPED / WITHDRAWN | enroll, not eligible | unchanged (`REJECTED` outcome) |
| ENROLLED / WAITLISTED | enroll (any eligibility) | unchanged (`ALREADY_*`) |
| WAITLISTED | leave_waitlist | WITHDRAWN |
| WAITLISTED | promotion, eligible, seat free | ENROLLED |
| WAITLISTED | promotion, not eligible | WAITLISTED (same position; reported as skipped) |
| ENROLLED | drop | DROPPED |

## 4. Service boundary
| Component | Responsibility |
|-----------|----------------|
| `LearnerDirectory` (`directory.py`) | In-memory stand-in for a student-records system: learner_id → completed course IDs. Read-only from the offering's point of view: the offering only *queries* it at the check points in §2.2. (Tests may change records to exercise the C3 safeguard.) |
| `CourseOffering` (`offering.py`) | Owns capacity, statuses, enrolled set and waitlist. All business rules, promotion and locking. |
| `Result`, `Outcome`, `OfferingState`, `LearnerStatus` (`models.py`) | Immutable value types. |
| `cli.py` | Demo shell only; no rules. |

## 5. API
```python
offering = CourseOffering(course_id, capacity, prerequisite_course_id, directory)
offering.enroll(learner_id)          -> Result
offering.drop(learner_id)            -> Result
offering.leave_waitlist(learner_id)  -> Result
offering.snapshot()                  -> OfferingState  # immutable point-in-time copy
```
Promotion has no public method; it is triggered automatically (§8.2).

`Result` fields: `outcome`, `learner_id`, `message`, `promoted: tuple[str, ...]` (moved waitlist →
enrolled by this call), and `skipped: tuple[str, ...]` (ineligible learners passed over and
retained by this call).

Expected business outcomes are returned, not raised. `ValueError` is raised only for an invalid
offering configuration at construction time (capacity < 1, empty IDs, self-prerequisite), which
is a programming error rather than a learner request.

| Operation | Success (`ok=True`) | Not accepted (`ok=False`, state unchanged) |
|-----------|---------------------|---------------------------|
| enroll | `ENROLLED`, `WAITLISTED` | `REJECTED`, `ALREADY_ENROLLED`, `ALREADY_WAITLISTED`, `INVALID_REQUEST` |
| drop | `DROPPED` | `ALREADY_DROPPED`, `NOT_ENROLLED`, `INVALID_REQUEST` |
| leave_waitlist | `WITHDRAWN` | `NOT_WAITLISTED`, `INVALID_REQUEST` |

Messages: `REJECTED` → "Rejected: prerequisite CS101 not completed." `ALREADY_WAITLISTED`
includes the learner's current waitlist position. (It doesn't report eligibility: a duplicate
request is not an eligibility check point, §2.2.)

## 6. Data model
| Field | Type | Notes |
|-------|------|-------|
| `_status` | `dict[str, LearnerStatus]` | Authoritative current state per learner (active and inactive), used for duplicate detection. |
| `_enrolled` | `dict[str, None]` | Insertion-ordered set. |
| `_waitlist` | `OrderedDict[str, int]` | learner → join sequence number. Ordered scan for promotion; O(1) removal. Skipped learners are never moved, so FIFO position is preserved. |
| `_seq` | `int` | Monotonic counter for join order; deterministic, no wall clock. |

## 7. Invariants
1. `len(enrolled) <= capacity`.
2. Enrolled and waitlisted sets are disjoint; neither contains duplicates (R1, R2).
3. **No free seat while an eligible learner waits**, evaluated at the moment each `drop` or
   successful `enroll` completes. A seat may be free while the waitlist holds only learners who
   were ineligible at the last promotion. If one of them later becomes eligible, the seat is
   filled at the next trigger (§8.2), not immediately (A11).
4. The status map agrees exactly with the enrolled and waitlisted collections.
5. **Every not-accepted outcome** (`REJECTED`, `ALREADY_*`, `NOT_*`, `INVALID_REQUEST`) leaves the
   snapshot identical to before the call.
6. Enroll on an active learner never changes state (R3).
7. **Promotion never reorders the waitlist:** learners who remain waiting keep their relative
   FIFO order.
8. **Seat priority (§8.3):** a newcomer is seated only if, at that moment, no waitlisted learner
   is eligible (SP1); and a newcomer is never refused a vacant seat merely because ineligible
   learners are waiting (SP2).

## 8. Promotion

### 8.1 Rule
"Promote the earliest **eligible** learner", repeated while seats are empty:
```
for learner in waitlist, front to back (FIFO):      # iterate over a copy
    if len(enrolled) == capacity: stop
    if eligible(learner):  remove from waitlist; status ENROLLED; report as promoted
    else:                  leave in place (same FIFO slot); report as skipped
```
One ordered pass fills every empty seat. Ineligible learners are never moved or removed; each
later promotion re-checks them in FIFO order, so once eligible they are ahead of everyone who
joined after them.

**"Same waitlist position" defined.** A skipped learner keeps their place in the FIFO order:
everyone who joined before them stays ahead, and everyone who joined after them stays behind.
Their displayed position number can only go *down*, as learners ahead of them are promoted or
leave; a skip never moves them back. Learners behind a promoted learner each move up one place.

| Waitlist before a seat opens | A is ineligible → A skipped, B promoted |
|------------------------------|------------------------------------------|
| A – 1 | A – 1 (skipped; stays at the front) |
| B – 2 | B → enrolled |
| C – 3 | C – 2 (moves up one) |
| D – 4 | D – 3 (moves up one) |

At the next promotion, A is checked first again: promoted if now eligible, otherwise skipped
again and C is promoted. The only events that change a learner's place are being promoted, and
voluntarily leaving the waitlist (a later re-enroll joins at the back).

Example: waitlist `[A, B, C]`, A is currently ineligible, one seat opens.
→ A is skipped, B is promoted; the waitlist becomes `[A, C]`.
→ The next seat opens: A is re-checked first. If A's record has been corrected, A is promoted
  ahead of C; otherwise A is skipped again and C is promoted.

### 8.2 When promotion runs (automatic)
Promotion runs automatically, under the offering's lock, at exactly two points. Both are
moments when a seat is (or may be) empty.

| # | Trigger | Why |
|---|---------|-----|
| P1 | After every successful `drop` | A seat has opened. This is the main trigger. |
| P2 | Inside `enroll`, before seating an eligible newcomer into an empty seat | Safeguard. A seat can be empty because every waiting learner was ineligible at the last promotion. Running promotion first re-checks those learners (C3), so a waiting learner whose record was corrected is never overtaken by a newcomer. It runs only on the path that seats the newcomer, so rejected requests stay side-effect-free (invariant 5). |

Nothing else triggers promotion. `leave_waitlist` opens no seat, and the service does not
react to changes in learner records (A11).

### 8.3 Seat priority: waitlist vs. new enrollment requests
| Rule | Statement | Mechanism |
|------|-----------|-----------|
| SP1 | **Existing eligible waitlisted learners always have priority over new enrollment requests.** | P2: before a newcomer is seated, promotion fills every vacant seat it can from the waitlist. The newcomer gets a seat only if one is still vacant afterwards; otherwise they join the back of the waitlist. |
| SP2 | **Retained ineligible learners never block an eligible newcomer from a vacant seat.** | Promotion skips ineligible learners (C3). If seats are still vacant after the pass, the eligible newcomer takes one immediately, instead of being waitlisted behind learners who can't currently be seated. |

**Why this is FIFO.** A new enrollment request is treated as arriving at the **back** of the
queue. Filling a vacant seat is then one FIFO scan, applied the same way everywhere:

```
candidates = waitlist (front → back) + [newcomer]
seat the first eligible candidate(s), skipping (and retaining) ineligible waitlisted learners
```

Eligible waitlisted learners are always ahead of the newcomer (SP1). Ineligible ones are skipped
exactly as they are on a drop (SP2). The newcomer, if not seated, takes the last FIFO slot.

Examples (capacity 2, one seat vacant). A seat can only be vacant while learners wait if every
waiting learner was ineligible at the last promotion (invariant 3). So "eligible" below means
*skipped earlier, record since corrected* (the A11 safeguard case).

| Waitlist | Newcomer N (eligible) | Result |
|----------|-----------------------|--------|
| A (skipped earlier; record since corrected, now eligible) | N enrolls | A is promoted into the vacant seat; N joins the waitlist behind everyone (SP1) |
| A (still ineligible) | N enrolls | A is skipped and keeps position 1; N takes the vacant seat (SP2) |
| A (still ineligible), B (skipped earlier; now eligible) | N enrolls | A is skipped; B is promoted; no seat left, so N is waitlisted: `[A, N]` |
| *(empty)* | N enrolls | N takes the vacant seat (the normal case) |

## 9. Concurrency and persistence
- **Persistence:** in-memory only (per scope). State is lost on restart.
- **Concurrency:** one `threading.Lock` per `CourseOffering`. Every public method, and any
  promotion it triggers, runs entirely under it. Check-then-act sequences (duplicate check →
  prerequisite check → P2 → capacity check → insert) and drop → promote are therefore atomic.
  `snapshot()` also takes the lock.
- **Lock ordering:** offering lock → directory lock only. The directory never calls the
  offering, so deadlock is impossible.
- Concurrency tests use a `SlowDirectory` that sleeps inside the eligibility check to widen the
  race window. Without it, deleting the lock still passed the tests under CPython's GIL (found
  by deliberately breaking the code; see `docs/AI_USAGE.md`).

## 10. Tradeoffs
| Choice | Alternative | Why |
|--------|-------------|-----|
| "Enroll only once" = no duplicate active records; re-enroll after drop, withdraw or reject is allowed | "Once ever": block any learner who has ever enrolled | AC 2 defines the requirement as "duplicate enrollment requests do not create duplicate records", and no AC forbids re-enrolling. Re-enrollment can't jump the queue: a dropped seat goes to the waitlist first, and a re-enrolling learner joins the back if the course is full. **Cost:** a reviewer may hold the stricter reading; mitigated by explicit rules R1–R4. |
| Skip and **retain** | Skip and remove | Fair to learners whose ineligibility is temporary; follows "earliest eligible" literally; no terminal state. **Cost:** ineligible learners can wait indefinitely (waitlist length overstates demand); each promotion scans past them (O(n)). |
| Return `REJECTED` without storing a status | Store a `REJECTED` status on the learner | Re-enrollment is allowed and eligibility is re-checked on every attempt, so a stored rejection would never change behaviour. Keeping rejections stateless means every rejection is a pure no-op (invariant 5), and the model stays at four statuses. **Cost:** there's no record of failed attempts (an audit log would be the right tool if needed). |
| Promotion on drop (P1) and before seating a newcomer (P2) only; prerequisite data assumed stable (A11) | Event-driven promotion when a learner's records change; or a public `promote_waitlist()` | Eligibility is evaluated only at the three agreed check points; there's no event plumbing between the records system and the offering; and the implementation stays small. **Cost:** if a skipped learner's record is corrected while a seat is empty, the seat stays empty until the next drop or eligible enroll. |
| Return result values | Raise exceptions | Duplicate and invalid requests are expected traffic; callers branch on an enum. |
| Coarse per-offering lock | Fine-grained or optimistic locking | One offering, small critical sections; correctness first. |

## 11. Acceptance-criteria traceability
| AC | Requirement (from the assessment) | How the design satisfies it | Section |
|----|-----------------------------------|------------------------------|---------|
| 1 | Enrollment succeeds when capacity remains and the prerequisite is met | Check C1; a seat is assigned if one is still vacant after P2 (SP1). Ineligible waitlisted learners never block it (SP2) | §2.2, §8.2 |
| 2 | When full, an eligible learner joins the waitlist **once**; duplicate requests create no duplicate records | Check C2; one status per learner; R1–R3; duplicate check precedes the prerequisite check | §2.1, §3, inv. 2, 6 |
| 3 | Drop opens a seat and promotes the earliest **eligible** waitlisted learner per the documented policy | P1 after every successful drop; FIFO scan promotes the first eligible learner(s) | §8 |
| 4 | An ineligible learner is not enrolled or promoted; the skip/retain policy is applied **consistently** | C1/C2 → `REJECTED`; C3 → skip and retain. A single promotion routine serves P1 and P2, so the policy is identical everywhere. AC 4 is applied at the moments a learner **gains a place** (new enrollment, moving to the waitlist, promotion). Already-enrolled learners are not re-evaluated (A7, A11; UC4) | §2.2, §2.3, A2, A3, A7, §8 |
| 5 | Invalid requests and duplicate drops return clear results without corrupting enrollment, capacity or waitlist | `INVALID_REQUEST`, `ALREADY_DROPPED`, `NOT_ENROLLED`, `NOT_WAITLISTED`; no rejection touches seats or the waitlist | §5, inv. 5 |
| 6 | Tests for capacity available/full, duplicates, FIFO promotion, prerequisite failure, invalid/repeated drops; concurrency where practical | Test plan T1–T13 | §13 |
| 7 | Record AI prompts, responses, accept/edit/reject decisions, verification | `docs/AI_USAGE.md` (to be updated with the v1.1–v1.9 design decisions during development) | — |

| Problem statement | Design |
|-------------------|--------|
| "A learner may enroll only once." | No duplicate active records: R1–R4 (§2.1); "once ever" considered and rejected (§10). |
| "When the course is full, eligible learners join the waitlist." | C2 |
| "If a seat opens, promote the earliest eligible learner." | §8.1, word for word; P1 and P2 make it automatic |
| "Define whether an ineligible learner is skipped or remains waiting, and apply that policy consistently." | A3: skipped *and* remains waiting at the same FIFO position; one routine for all triggers |

## 12. Scope and deliverable compliance
| Assessment boundary / expectation | Status |
|-----------------------------------|--------|
| One offering's enroll, drop and waitlist-promotion slice only | ✅ Single `CourseOffering`; `leave_waitlist` serves the waitlist slice |
| No frontend, catalog, payments, identity, multi-term, deployment, new database | ✅ In-memory store; demo CLI only (the "command-line prototype" fallback) |
| No separate greenfield/brownfield/ambiguous variants | ✅ One implementation |
| State assumptions; **no configurable policy engine** | ✅ Fixed rules A1–A11; no policy flags or plug-ins |
| State what happens when an ineligible learner reaches the front | ✅ A3, §2.2 C3, §8.1 example |
| Prioritise correct capacity/queue behaviour over feature count | ✅ Invariants 1–8 asserted throughout; no extra infrastructure (no event plumbing, no public promotion API) |
| No credentials or sensitive data in prompts/records | ✅ Fictional learner IDs only |
| Design spec covers boundary, data/API, invariants, promotion rule, concurrency/persistence, assumptions/tradeoffs | ✅ §2–§10 |
| Runnable code, focused tests, setup/run instructions, limitations summary | ⏳ Code and README to be updated after sign-off; limitations in §14 |

## 13. Test plan (to implement after sign-off)
| # | Scenario | AC |
|---|----------|----|
| T1 | Enroll with a free seat and the prerequisite met → `ENROLLED`; fill to exact capacity | 1 |
| T2 | Course full → `WAITLISTED` in arrival order | 2 |
| T3 | Duplicate enroll while enrolled / waitlisted / just promoted → `ALREADY_*`, no change, even if the learner is currently ineligible; 40 concurrent duplicate enrolls → one record | 2, 6 |
| T4 | Prerequisite not met at C1 and at C2 → `REJECTED` outcome; snapshot identical (no status recorded, seats and waitlist unchanged); after completing the prerequisite → normal flow | 1, 4, 5 |
| T5 | Drop promotes the earliest eligible learner; successive drops follow FIFO | 3 |
| T6 | Skip and retain: an ineligible head is skipped, the next eligible learner is promoted, and the skipped learner keeps position 1 | 3, 4 |
| T7 | A retained learner's record is corrected (safeguard path): (a) while full → promoted at the next drop, ahead of later joiners; (b) while a seat is empty → **not** promoted immediately; promoted when the next eligible newcomer enrolls (P2), and the newcomer is waitlisted behind them | 3, 4 |
| T8 | **SP2:** only ineligible learners waiting → seat stays vacant after the drop; an eligible newcomer takes it directly, and the ineligible learners keep their positions | 1, 4 |
| T8b | **SP1:** a vacant seat with an eligible learner waiting (record corrected after being skipped) → a newcomer's enroll promotes the waiting learner first, and the newcomer is waitlisted at the back. Also: the mixed case `[A ineligible, B eligible]` + newcomer → B seated, waitlist `[A, N]` | 1, 3, 4 |
| T9 | Re-enroll after drop or withdraw: seat if free, back of queue if full, `REJECTED` (state unchanged) if not eligible; repeated cycles never duplicate | 2 |
| T10 | Repeated drop → `ALREADY_DROPPED`; drop of a waitlisted, withdrawn or never-enrolled learner → `NOT_ENROLLED`; no extra promotion | 5 |
| T11 | Malformed or unknown learner IDs on every operation → `INVALID_REQUEST`, no status recorded; invalid construction raises `ValueError` | 5 |
| T12 | Record changes trigger no promotion on their own; `leave_waitlist` triggers no promotion; a rejected enroll never triggers P2; an enrolled learner whose record is revoked keeps the seat and can still drop normally (UC4, UC6) | 3, 4, 5 |
| T13 | Concurrency: parallel enrolls never exceed capacity; parallel duplicate enrolls create one record; parallel repeated drops promote exactly once; mixed parallel drops and enrolls keep invariants; a widened race window proves that removing the lock makes these tests fail. Seeded random sequences check invariants 1–8 after each step | 6 |

## 14. Limitations and follow-up risks
- **In-memory, single process.** State is lost on restart, and the lock doesn't protect multiple
  processes. A real store needs drop → promote in one transaction, with row locks or version
  checks, and a unique constraint on (offering, learner).
- **Retained ineligible learners can wait indefinitely.** The waitlist length overstates real
  demand, and each promotion scans past them.
- **Prerequisite data is assumed stable (A11).** If a skipped learner's record is corrected while
  a seat is empty, the seat stays empty until the next drop or eligible enroll. If records change
  often in practice, event-driven promotion would be needed.
- **No history.** Only the current status is stored: there's no record of an earlier enrollment
  after drop → re-enroll, failed (`REJECTED`) attempts are not recorded, and skips are reported in
  the `Result` but not stored.
- **"Enroll only once" interpretation.** The decided reading allows re-enrollment; a reviewer
  holding the "once ever" reading would see this differently (§10).
- **No notifications** to promoted, skipped or rejected learners, and **no admin operations**
  (capacity change, force-enroll).
- **Concurrency tests are probabilistic.** They rely on a widened race window.
- Learner IDs are matched exactly (no case or whitespace normalisation).

## 15. Open items
| # | Question | Resolution |
|---|----------|------------|
| O1 | Store a failed prerequisite check at enroll? | **Resolved (v1.7):** no. Return the `REJECTED` outcome and message only; no status stored (A2) |
| O2 | Interpretation of "enroll only once" | **Resolved (v1.4):** no duplicate active records, R1–R4 (§2.1) |
| O3 | How promotion is triggered | **Resolved (v1.6):** automatic on drop (P1) and before seating a newcomer (P2); no reaction to record changes; no public `promote_waitlist()` |
| O4 | Should retained ineligible learners expire? | **Resolved (v1.5):** no; they keep their FIFO slot and are re-checked at every promotion |

No open items remain. Next step: candidate sign-off, then implementation per §13.
