# Design Review Checklist (final, v2.0)

This checklist was used to review each design decision with the candidate. Every item is
settled; ticked boxes show the decision implemented in v2.0. The full reasoning for each change
is in `docs/AI_USAGE.md` (Interactions 5–14 and 17).

Decision legend: `APPROVED` (kept as proposed) / `CHANGED` (candidate chose something else) /
`NOT APPLICABLE`.

---

## A. Policy decisions

### A1 – Prerequisite rule
- [x] One prerequisite course ID; the learner must have completed it
- [ ] Several prerequisite course IDs; all required
- [ ] Several course IDs; any one is enough
- Decision: CHANGED from the AI's first proposal (a set of courses) to a single course ID

### A2 – Ineligible learner at enroll time
- [x] Return `REJECTED` with a message; **nothing stored**; the learner may try again at any time
- [ ] Return `REJECTED` and store a `REJECTED` status *(tried in v1.5; removed in v1.7)*
- Decision: CHANGED (v1.7): a stored status adds nothing, because re-enrollment is allowed and eligibility is re-checked

### A3 – Learner at the front of the waitlist is not eligible when a seat opens
- [ ] Skip and **remove** *(v1.0)*
- [x] Skip and **retain**: same FIFO position, re-checked at every later promotion
- Decision: CHANGED (v1.2): losing eligibility while waiting must not cost the learner their place

### A4 – Removed learner tries to enroll again
- Decision: NOT APPLICABLE (v1.2): nobody is removed from the waitlist any more

### A5 – Enrolled learner who dropped tries to enroll again
- [x] Blocked: `PREVIOUSLY_DROPPED`, no eligibility check *(v1.0, restored in v2.0)*
- [ ] Allowed through the normal flow *(v1.1–v1.9)*
- Decision: CHANGED (v2.0): a seat may be held only once; this satisfies both the literal sentence and AC 2

### A6 – Waitlisted learner leaves the waitlist and re-enrolls
- [x] Allowed; joins the back of the queue, or gets a seat if one is free
- [ ] Original position restored
- [ ] Not allowed
- Decision: APPROVED

### A7 – Enrolled learner's prerequisite is revoked after enrolling
- [x] Keeps the seat: **eligibility is never checked for already-enrolled learners**
- [ ] Automatically dropped and the next eligible learner promoted
- Decision: APPROVED and explicitly confirmed (v1.9); AC 4 applies when a learner gains a place

### A8 – Waitlist size
- [x] Unlimited
- [ ] Fixed maximum
- Decision: APPROVED

### A9 – Drop vs. leave waitlist
- [x] Separate operations: `drop` (enrolled only) and `leave_waitlist`
- [ ] One `drop` that handles both
- Decision: APPROVED

### A10 – Invalid requests
- [x] Blank or non-string ID, or an unknown learner → `INVALID_REQUEST`; no state change
- [ ] Unknown learners auto-registered
- Decision: APPROVED

### A11 – Prerequisite data stability *(added v1.6)*
- [x] Records are assumed stable during normal operation; the promotion-time check is a safeguard; no reaction to record changes
- [ ] Event-driven promotion when records change *(tried in v1.5; removed in v1.6)*
- Decision: CHANGED (v1.6)

### R1–R5 – "A learner may enroll only once" *(added v1.4, revised v2.0)*
- [ ] No duplicate active records; re-enroll allowed after drop or withdraw *(v1.4–v1.9)*
- [x] No duplicate records, and a seat may be held only once: dropped learners blocked (R4); withdrawn learners may re-join (R5)
- [ ] "Once ever", also blocking withdrawn learners
- Decision: CHANGED (v2.0), candidate's choice (Option B)

### Eligibility check points *(added v1.3, confirmed v1.9)*
- [x] Only at new enrollment, moving to the waitlist, and promotion; never for enrolled learners, duplicates, previously dropped learners, drops or withdrawals
- Decision: APPROVED

---

## B. Design and implementation choices

### B1 – How results are reported
- [x] `Result` with an `Outcome` enum; no exceptions for business cases
- [ ] Typed exceptions
- Decision: APPROVED

### B2 – Promotion
- [ ] Only the head is checked; ineligible learners removed *(v1.0)*
- [ ] Also triggered by record changes or a public `promote_waitlist()` *(v1.2–v1.5; removed)*
- [x] One FIFO pass that seats the first eligible learners and skips (retains) ineligible ones. Triggered automatically after a drop (P1) and before seating a newcomer (P2)
- Decision: CHANGED (final form in v1.6)

### B2a – Seat priority *(added v1.8)*
- [x] SP1: eligible waitlisted learners always come before new requests
- [x] SP2: retained ineligible learners never block an eligible newcomer from a vacant seat
- Decision: APPROVED (candidate's rules)

### B3 – Concurrency
- [x] One `threading.Lock` per offering around every operation; concurrency tests with widened race windows
- [ ] No locking
- Decision: APPROVED

### B4 – Persistence
- [x] In-memory only (matches the assessment's scope)
- [ ] JSON file or SQLite
- Decision: APPROVED

### B5 – Demo CLI
- [x] Keep the small line-based CLI plus `examples/demo.txt`
- [ ] Remove it
- Decision: APPROVED

### B6 – Audit trail
- [x] No stored audit; each `Result` reports `promoted` and `skipped` learners
- [ ] Event log of every state change
- Decision: APPROVED (no history is listed as a limitation)
