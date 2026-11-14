# Design Review Checklist

How to use: for each item, tick **one** box (`[x]`). The current design is pre-ticked.
To propose something else, tick **Other** and describe it in the "Notes" line.
When done, tell Claude "checklist updated" and the design, code, tests and docs will be
redesigned to match.

Status legend for the Decision line: `APPROVED` / `CHANGED` / `NEEDS DISCUSSION`

---

## A. Policy decisions

### A1 – Prerequisite rule
- [x] One prerequisite course ID; the learner must have completed it *(current)*
- [ ] Several prerequisite course IDs; the learner must have completed **all** of them
- [ ] Several course IDs; completing **any one** is enough
- [ ] Other
- Notes:
- Decision:

### A2 – Ineligible learner at enroll time
- [x] Rejected (`PREREQUISITE_NOT_MET`); nothing recorded; may retry later *(current)*
- [ ] Rejected and recorded, so repeat attempts are blocked
- [ ] Other
- Notes:
- Decision:

### A3 – Learner at the front of the waitlist is no longer eligible when a seat opens
- [ ] Skip and **remove**: status `REMOVED`, audit record kept, next learner checked *(previous)*
- [x] Skip but **keep place**: stays waiting at the same position; skipped each time until eligible again *(current, v1.2)*
- [ ] Other
- Notes: Losing eligibility while waiting shouldn't cost the learner their place. Eligibility is still re-checked at promotion (AC 3 and AC 4), so they are not promoted while ineligible.
- Decision: CHANGED

### A4 – REMOVED learner tries to enroll again
- [ ] Blocked permanently (`PREVIOUSLY_REMOVED`) *(previous)*
- [ ] Allowed if now eligible; joins the back of the queue
- [ ] Other
- Notes: The REMOVED state no longer exists after A3 changed to skip and retain.
- Decision: NOT APPLICABLE (v1.2)

### A5 – Enrolled learner who DROPPED tries to enroll again
- [ ] Blocked (`PREVIOUSLY_DROPPED`) *(previous)*
- [x] Allowed; prerequisite re-checked, seat if free, otherwise back of the waitlist *(current, v1.1)*
- [ ] Other
- Notes: "Enroll only once" means one active record (enrolled or waitlisted), not once ever.
- Decision: CHANGED

### A6 – Waitlisted learner leaves the waitlist (WITHDRAWN) and re-enrolls
- [x] Allowed; joins the **back** of the queue (or gets a seat directly if one is free) *(current)*
- [ ] Allowed; **original position restored**
- [ ] Not allowed
- [ ] Other
- Notes:
- Decision:

### A7 – Enrolled learner's prerequisite is revoked after enrolling
- [x] Keeps the seat; eligibility is checked only at enroll and promotion *(current)*
- [ ] Automatically dropped, and the next eligible learner is promoted
- [ ] Other
- Notes:
- Decision:

### A8 – Waitlist size
- [x] Unlimited *(current)*
- [ ] Fixed maximum (state the number in Notes); enroll returns `WAITLIST_FULL` when reached
- [ ] Other
- Notes:
- Decision:

### A9 – Drop vs. leave waitlist
- [x] Separate operations: `drop` (enrolled only) and `leave_waitlist` *(current)*
- [ ] One `drop` operation that handles both, returning `DROPPED` or `WITHDRAWN`
- [ ] Other
- Notes:
- Decision:

### A10 – Invalid requests
- [x] Blank or non-string ID, or a learner unknown to the directory → `INVALID_REQUEST`, no state change *(current)*
- [ ] Unknown learners are auto-registered with no completed courses
- [ ] Other
- Notes:
- Decision:

---

## B. Design and implementation choices

### B1 – How results are reported
- [x] Every operation returns a `Result` with an `Outcome` enum; no exceptions for business cases *(current)*
- [ ] Raise typed exceptions for rejections (e.g. `AlreadyEnrolledError`)
- [ ] Other
- Notes:
- Decision:

### B2 – Promotion scope
- [ ] Only the learner at the front is checked; ineligible ones removed *(previous)*
- [x] Scan the waitlist in order and promote the first eligible learner(s); ineligible learners stay in place. Promotion also runs before a newcomer is seated, and via `promote_waitlist()` *(current, v1.2)*
- [ ] On each promotion, sweep the **whole** waitlist and remove every ineligible learner
- [ ] Other
- Notes:
- Decision:

### B3 – Concurrency
- [x] One lock per offering around every operation; concurrency tests with a widened race window *(current)*
- [ ] No locking (single-threaded use only); drop the concurrency tests
- [ ] Other
- Notes:
- Decision:

### B4 – Persistence
- [x] In-memory only *(current; matches the assessment's scope)*
- [ ] Add a JSON-file or SQLite store
- [ ] Other
- Notes:
- Decision:

### B5 – Demo CLI
- [x] Keep the small line-based CLI plus `examples/demo.txt` *(current)*
- [ ] Remove it; library and tests only
- [ ] Replace it with a minimal HTTP API (note: the assessment says no frontend)
- [ ] Other
- Notes:
- Decision:

### B6 – Audit trail
- [x] No stored audit; each `Result` reports `promoted` and `skipped` learners *(current, v1.2; RemovalRecord deleted)*
- [ ] Record every state change (enroll, waitlist, drop, withdraw, promote, remove) in an event log
- [ ] Other
- Notes:
- Decision:

---

## C. Anything else
Add any further changes, questions or concerns here:

-
