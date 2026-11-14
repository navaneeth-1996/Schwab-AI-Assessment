# AI Prompt and Use Record

**Tool:** Claude Code (AI coding assistant), used in one session.
**Activities AI was used for:** requirements analysis, design options, code generation, test
generation, deliberately breaking the code to check the tests, documentation.
**Human role:** made every policy decision, reviewed the AI's proposals, accepted, edited or
rejected them (below).
No credentials, secrets or personal data were included in prompts. Learner names in tests and
the demo are fictional.

> **Candidate to complete:** sections marked _[candidate]_ are for your own review notes. The
> rubric rewards candid, independent verification, so record what *you* checked and changed.

---

## Interaction 1 – Requirements analysis
**Prompt (summary):** Shared the assessment PDF. "Go through the acceptance criteria,
prerequisites and limitations, list the points you understood, then we will confirm what we can
accept and how to design the complete code. Go through the checklist as well." The prompt also
included an initial understanding: enroll with a prerequisite check, classify learners as
enrolled or waitlisted based on capacity.

**AI response (summary):**
- Restated the problem, the 7 acceptance criteria, scope limits, deliverables and expectations.
- Noted the repo was empty, so the in-memory service/CLI fallback applies.
- Corrected the initial understanding:
  - the spec defines no prerequisite rule;
  - there is a third outcome, *rejected*;
  - drop + automatic promotion is a core operation;
  - duplicate and invalid handling must not corrupt state;
  - half the deliverables are documents.
- Flagged a subtlety: if eligibility is only checked at enroll time, nobody ineligible can ever
  be on the waitlist, so AC4 could never come up. Eligibility therefore has to be **re-checked
  at promotion time**, which needs learner records that can change.
- Proposed invariants and 6 open decisions.
- Noted that the referenced `Course-Registration-Rubric-Score.md` was not supplied.

| Suggestion | Decision |
|-----------|----------|
| Re-check eligibility at promotion time; directory must be mutable | **Accepted** |
| Prerequisite = a set of required course IDs | **Edited**: candidate chose a single prerequisite course ID |
| Option A "skip and remove" vs. B "skip but keep" (AI recommended A) | **Accepted A, edited**: candidate added that a removal record must be kept and that a removed learner who re-enrolls is treated as a duplicate |
| Waitlist unlimited | **Accepted** |
| Waitlisted learner may leave the waitlist | **Accepted** |
| Python + pytest | **Accepted** |
| Explicit result enum instead of exceptions | **Accepted** (implicitly; not objected to) |

## Interaction 2 – Design draft and follow-up questions
**Prompt (summary):** Candidate supplied the decisions above and asked the AI to proceed and
discuss again.

**AI response (summary):**
- Wrote `docs/DESIGN.md` v0.1: service boundary, API, outcome table, data model, invariants,
  promotion loop and locking approach.
- Asked 3 open questions, each with a recommendation:
  - Q1 re-enroll after a voluntary drop or leave;
  - Q2 whether the removal block is permanent;
  - Q3 whether an enrolled learner who loses the prerequisite keeps the seat.

| Suggestion | Decision |
|-----------|----------|
| Q1: allow re-enroll after any voluntary action | **Rejected in part / edited**: candidate split it into two states. `DROPPED` (was enrolled) **cannot** re-enroll; `WITHDRAWN` (left the waitlist) **can** re-enroll. |
| Q2: removal block is permanent | Not answered explicitly; AI default applied at first. **Became moot in v1.2** (skip and remove replaced by skip and retain). |
| Q3: enrolled learner keeps the seat | AI default applied at first; **explicitly confirmed by the candidate in v1.9** (no eligibility checks for enrolled learners). |

## Interaction 3 – First implementation (v1.0, superseded by v1.9)
**Prompt (summary):** The DROPPED/WITHDRAWN decision above, which implied "go ahead".

**AI output:**
- `course_registration/` package: `models.py`, `directory.py`, `offering.py`, `cli.py`.
- 88 pytest tests in 7 modules (90 after Interaction 4), including a shared invariant checker, concurrency tests and
  seeded random-sequence tests.
- `examples/demo.txt`, this record, README, and the final DESIGN.md.

**AI self-review and verification during implementation:**
1. Full suite: `88 passed`.
2. **Deliberately broke the code** (scripted, then reverted) to confirm the tests catch real
   defects:

   | Bug introduced | Caught? |
   |----------------|---------|
   | Waitlist served last-in-first-out instead of FIFO | yes |
   | Eligibility not re-checked at promotion | yes |
   | Drop does not trigger promotion | yes |
   | Capacity check off by one (`<=`) | yes |
   | DROPPED learner allowed to re-enroll | yes |
   | Promotion fills only one seat (`if` instead of `while`) | yes |
   | **Lock removed from `enroll`** | **no, survived** |

3. **Defect found in the AI's own tests:** the concurrency tests passed even with the lock
   removed. CPython's GIL makes the race window too small to hit.
   **Fix (edited):** added a `SlowDirectory` test double that sleeps inside `has_completed`,
   widening the read-then-write window. Re-ran with the lock removed from `enroll` and from
   `drop`: both now fail. Restored code: suite passes on 3 consecutive runs.
4. Ran the CLI demo by hand and checked each printed outcome against the policy table. The first
   demo script did not exercise withdraw-then-re-enroll, so it was rewritten, and a CLI smoke
   test was added.
5. Replaced an unclear ASCII state diagram in DESIGN.md with a transition table.

## Interaction 4 – "Enroll only once" review
**Prompt (summary):** Candidate asked how the "a learner may enroll only once" requirement is
handled, and which use cases were considered.

**AI response (summary):** Explained the single-status-per-learner model and listed the use
cases with their tests. While mapping cases to tests, the AI found two that had no dedicated
test: a promoted learner calling enroll again, and repeated withdraw/re-join cycles.
**Accepted:** added `test_promoted_learner_enrolling_again_is_duplicate` and
`test_repeated_withdraw_and_rejoin_never_duplicates_records`. Suite: `90 passed`. No production
code changed.

## Interactions 5–13 – Design review, v1.1 → v1.9 (design only, no code)
After the v1.0 implementation, the candidate asked to **change only the design until it was
final** ("do changes only to the DESIGN first; once we finalise DESIGN we will go ahead for
development"). Code changes the AI had already started for v1.1 were reverted before commit.
Each row below is one decision.

| Ver. | Candidate prompt (summary) | AI suggestion / response | Decision |
|------|----------------------------|--------------------------|----------|
| 1.1 | "Enroll only once" means no duplicate active records; a learner who drops should be able to re-enroll through the normal flow | Implemented the change across code and docs, then reverted the code when told "design first" | **Edited:** reverses the candidate's own v1.0 rule (DROPPED blocked); design-only |
| — | "Should a learner be allowed to re-enroll after dropping; does this comply with the ACs?" | Mapped the problem statement and ACs 2–6; no AC forbids re-enrolling; AC 2 makes "only once" testable as "no duplicate records". Flagged the risk of a "once ever" reading | **Accepted:** keep re-enrollment; document the interpretation |
| 1.2 | Asked whether to skip and retain or skip and remove; preferred retain "as eligibility is checked already" | Agreed retain is valid and fairer. **Corrected the reasoning:** the earlier check doesn't decide the question; what matters is whether lapsed eligibility should cost a learner their place. Listed the extra rules retain needs | **Accepted:** skip and retain; `REMOVED` state deleted |
| — | "An ineligibility factor at promotion shouldn't make the learner lose their position, right?" | Confirmed, with the limit that AC 3/4 still forbid *promoting* them while ineligible; worked example | **Accepted** |
| 1.3 | Listed the three eligibility check points; asked to check the design against ACs and limitations | Added check points C1–C3, AC traceability, scope compliance, test plan and limitations sections | **Accepted** |
| 1.4 | Restated "enroll only once": never enrolled *and* waitlisted, no new request while active; re-enroll after drop or withdraw | Wrote rules R1–R4; recorded "once ever" as the rejected alternative | **Accepted** |
| 1.5 | Store a REJECTED status; promote automatically whenever a seat is empty; retained learners stay in FIFO order | Implemented in design, including promotion on eligibility changes (directory notifications) | **Accepted at first, later revised** (v1.6, v1.7) |
| — | "Clarify what 'same waitlist position' means" | Defined it as relative FIFO order: the displayed number can only go down; a skip never moves anyone back | **Accepted;** candidate restated it with an A/B/C/D example, which was added to §8.1 |
| 1.6 | "Keep prerequisite data stable; promotion-time validation is a safeguard. Ignore automatic promotion on eligibility changes" | Removed directory notifications; added assumption A11; promotion only after a drop (P1) and before seating a newcomer (P2) | **Edited:** rejects the AI's v1.5 event-driven mechanism |
| 1.7 | "Storing REJECTED is not necessary, as re-enrollment is allowed and eligibility re-checked" | Removed the stored status; REJECTED is an outcome only; rejections are pure no-ops again | **Edited:** reverses v1.5 O1 |
| 1.8 | "Eligible waitlisted learners always have priority over new requests; retained ineligible learners must not block a new eligible learner" | Showed both rules were already implied (P2, T8); made them explicit as SP1/SP2 with a FIFO explanation and invariant 8 | **Accepted** |
| 1.9 | "Re-analyse the design against the document" | AI review found: a **contradiction the AI had introduced** (the `ALREADY_WAITLISTED` message would need an eligibility check outside the three agreed points); stale references; misleading examples; incomplete T13; the AC 4 vs A7 interpretation risk; and the AI record not yet updated | **Accepted** fixes; the candidate then decided AC 4 vs A7: **no eligibility checks for already-enrolled learners**. Use cases UC1–UC13 added |

## Interaction 14 – Implementation of design v1.9
**Prompt (summary):** "Go ahead and implement; commit the files as well."

**AI output:**
- `offering.py` rewritten to v1.9:
  - duplicate check before the prerequisite check;
  - stateless `REJECTED`;
  - one FIFO promotion routine with skip-and-retain;
  - promotion triggers P1 (drop) and P2 (before seating a newcomer).
- `models.py`: four statuses; `REMOVED`, `PREVIOUSLY_*` and `RemovalRecord` deleted; new
  `Result.skipped`.
- Tests reorganised by test-plan ID (T1–T13): `test_enrollment.py`, `test_promotion.py`,
  `test_seat_priority.py`, `test_reenrollment.py`. The invariant checker now also covers
  invariants 3, 7 and 8. The random-sequence test checks AC 4 directly: nobody is newly seated
  unless eligible.
- Demo script rewritten around the v1.9 story; README updated.

**Verification:**
1. `pytest -q` → **111 passed**, on 3 consecutive runs.
2. **CLI defect found by the demo smoke test:** comment lines were parsed before being skipped,
   so an apostrophe in a comment crashed the shell. **Fixed** by skipping comments before parsing.
3. **Deliberately broke the code 13 ways** (scripted, then restored; restored file verified
   byte-identical):

   | # | Bug introduced | Caught? |
   |---|----------------|---------|
   | 1 | Skip-and-**remove** instead of retain | yes |
   | 2 | No eligibility re-check at promotion | yes |
   | 3 | No P2: newcomer seated ahead of the waitlist (breaks SP1) | yes |
   | 4 | Newcomer waitlisted whenever anyone waits (breaks SP2) | yes |
   | 5 | Prerequisite check before duplicate check (breaks R3) | yes |
   | 6 | REJECTED stores a status | yes |
   | 7 | Waitlist scanned last-in-first-out | yes |
   | 8 | Promotion seats at most one learner per pass | **no, survived** → fixed |
   | 9 | Capacity check off by one | yes |
   | 10 | Promotion runs on `leave_waitlist` | **no, survived** → fixed |
   | 11 | Dropped learner blocked from re-enrolling | yes |
   | 12 | Lock removed from `enroll` | yes |
   | 13 | Lock removed from `drop` | yes |

4. **Gaps found in the AI's own tests (from the two survivors):**
   - #8: no test needed one pass to fill two vacancies. **Added**
     `test_single_pass_fills_every_vacancy_before_newcomer`.
   - #10: the leave-waitlist test had no vacant seat, so a stray promotion had no effect.
     **Rewritten** with a vacant seat and an eligible waiting learner.
   - Both survivors are now caught.
5. Demo output checked line by line against DESIGN.md §2.3 use cases (UC1–UC3, UC7, UC10, UC11,
   UC12).

## Interaction 15 – Concurrent requests with a threading lock
**Prompt (summary):** "Handle the concurrent requests using threading lock."

**AI response (summary):**
- Confirmed the lock was already in place: one `threading.Lock` per `CourseOffering`, held by
  `enroll`, `drop`, `leave_waitlist` and `snapshot`, including any promotion they trigger.
  Lock order is offering → directory only.
- Checked whether the tests actually enforce it, by deleting each lock in turn. **Finding:**
  removing the lock from `leave_waitlist` still passed all 111 tests. Nothing ran
  `leave_waitlist` concurrently, and the race-widening sleep only covered the eligibility check,
  which `leave_waitlist` never calls.
- No production change was needed; the gap was in the tests.

**Changes (tests only):**
- `SlowDirectory` also sleeps in `exists` (called by every operation during validation).
- Three new concurrency tests for v1.9 behaviour:
  - a drop racing a withdrawal of the learner it would promote (exactly one outcome);
  - concurrent drops and newcomers with a retained ineligible learner (skip-and-retain plus SP1);
  - concurrent withdraw/re-join of one learner (no duplicates).
- **Edited after the first attempt:** the drop/withdraw race test caught a missing
  `leave_waitlist` lock in only 2 of 5 runs, too timing-dependent to rely on. The withdrawal is
  now delayed to land inside the promotion's eligibility check.

**Verification:**
| Lock removed from | Caught (concurrency tests, repeated runs) |
|-------------------|-------------------------------------------|
| `enroll` | 10/10 |
| `drop` | 10/10 |
| `leave_waitlist` | 10/10 (was 0/5 before this change, then 2/5 on the first attempt) |

Real code: full suite `114 passed` in 10/10 consecutive runs; restored `offering.py` verified
byte-identical.

## Interaction 16 – Final check against the assessment document
**Prompt (summary):** "Are all the tests passing? Check against the document whether anything is
missing."

**AI checks and evidence:**
- `pytest -q` → `114 passed`, both in the working copy and in a **fresh clone** set up exactly
  as the README describes.
- Also run on **Python 3.11, 3.12 and 3.13**: 114 passed on each. (3.10 was not available.)
- Coverage (`coverage run --branch`): `offering.py` **100% lines and branches**; models and
  directory 100%; `cli.py` 79% (demo argument parsing and error paths only).
- No personal data or credentials in any committed file.
- Deliverables, ACs 1–7, scope limits and candidate expectations re-checked against the PDF.

**Found and fixed:** `DESIGN_REVIEW_CHECKLIST.md` had stopped being updated at v1.5. B2 still
mentioned the removed `promote_waitlist()`; the A7 confirmation, A11, R1–R4 and SP1/SP2 were
missing. Rewritten to the final v1.9 decisions. README now states the tested Python versions.

**Still open (outside the AI's remit):** the candidate's own review section below.

**Rubric:** the scorecard referenced by the assessment (`Course-Registration-Rubric-Score.md`)
was not accessible to the candidate. The work was therefore checked against the priorities the
assessment states itself: correct capacity and queue behaviour, focused tests, understandable
changes, evidence of independent review, and candour about AI use. No rubric-based self-score
is claimed.

## Interaction 17 – Re-examining "enroll only once" (design v2.0)
**Prompt (summary):** The candidate asked whether "a learner may enroll only once" requires a
change, given that both withdrawn and dropped learners could re-enroll. They asked to discuss
first and change nothing until a conclusion was reached.

**AI response (summary):**
- Argued that the two cases differ:
  - a **withdrawn** learner never enrolled, so re-joining doesn't break even a strict reading;
  - a **dropped** learner has already enrolled once, so re-enrolling is exactly what a literal
    reading forbids.
- **Candidly noted that the plain wording leans stricter than the v1.4–v1.9 interpretation the
  AI had helped justify.**
- Offered three options:
  - A: keep the current rule;
  - B: block dropped learners, allow withdrawn ones;
  - C: block both.
- Gave use cases and recommended **B**: it satisfies both AC 2 and the literal sentence, and
  doesn't penalise learners who never held a seat. It is also the candidate's original v1.0
  distinction.

**Candidate decision:** **Option B**, with outcome `PREVIOUSLY_DROPPED`. The previously-dropped
check runs right after the duplicate checks, with **no eligibility check**. (The AI had offered
`ALREADY_DROPPED` as an alternative; the candidate chose the distinct outcome.)

**Changes:**
- Design v2.0: A5, §2.1 rules R1–R5, use cases UC12/UC12b, state table, outcomes, invariants 5–6,
  tradeoffs, traceability, T9, limitations, O2.
- `Outcome.PREVIOUSLY_DROPPED`; one check in `enroll`.
- Five T9 tests replaced. One new test spies on the directory to prove that no eligibility lookup
  happens for a dropped learner. The random-sequence test asserts R4 on every step.
- Demo, README and checklist updated.

**Verification:**
- Before the test changes, exactly the 6 tests that encoded the old rule failed, and nothing else.
- After: `114 passed` in 5/5 runs.
- Deliberately broke the new rule 3 ways (all caught):
  - dropped learner allowed to re-enroll;
  - eligibility checked before the dropped check;
  - withdrawn learners blocked too.

## Files informed by AI
| File | AI contribution | Human decision points |
|------|-----------------|-----------------------|
| `docs/DESIGN.md` | Drafted and revised (v0.1 → v1.9) | Every policy row (A1–A11), R1–R4, SP1/SP2, check points, the stable-data assumption; the decisions to remove event-driven promotion and the stored REJECTED status |
| `docs/DESIGN_REVIEW_CHECKLIST.md` | Drafted | Ticked and changed by candidate decisions |
| `course_registration/*.py` | Generated | Behaviour fully specified by the candidate-approved design |
| `tests/*.py` | Generated | Coverage from AC 6 and test plan §13; strengthened after deliberately breaking the code |
| `README.md`, `docs/AI_USAGE.md` | Drafted | _[candidate review]_ |

## Candidate's independent review _[candidate to complete]_

### Setup (from the repository root; Python 3.10+, tested on 3.11–3.13)
```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

### Run
```bash
pytest -q                                                    # expected: 114 passed
python -m course_registration.cli --capacity 1 < examples/demo.txt
```
Optional coverage check:
```bash
pip install coverage
coverage run --branch -m pytest -q && coverage report -m --include="course_registration/*"
```

To check a test catches a bug: change one rule in `course_registration/offering.py` (for
example, replace `with self._lock:` in `drop` with `if True:`, or make `_promote` remove
ineligible learners), run `pytest -q`, confirm a failure, then undo the change with
`git checkout course_registration/offering.py`.

### Review checklist
- [ ] Read `course_registration/offering.py` end to end against DESIGN.md §2, §8 and §2.3.
- [x] Run `pytest -q` yourself and paste the output below.
- [x] Introduce at least one defect of your own and confirm a test fails.
- [x] Run the demo and check it against the use-case table (run with an injected defect; see below).
- [ ] Note anything you changed or rejected from the generated code.

`pytest -q` from `Schwab-AI-Assessment`, 14 Nov 2026:

```
............................................................................ [ 66%]
......................................                                       [100%]
114 passed in 0.77s
```

**Defect introduced and result:**
The dropped-learner check in `enroll` (R4) was disabled, and the demo was re-run:
`python -m course_registration.cli --capacity 1 < examples/demo.txt`. The output differed from
the correct run in exactly the places R4 governs; everything else (rejection, skip-and-retain,
the corrected learner's promotion, withdraw and re-join) was unchanged:

| Demo step | Expected | Observed with the defect |
|-----------|----------|--------------------------|
| `enroll amy` (amy dropped earlier) | `PREVIOUSLY_DROPPED` | `WAITLISTED: Course full; waitlisted at position 2.` |
| `drop amy` | `ALREADY_DROPPED` | `NOT_ENROLLED: Learner is not enrolled. Use leave_waitlist to leave the waitlist.` |
| Final waitlist | `['dan']` | `['amy', 'dan']` |
| amy's final status | `DROPPED` | `WAITLISTED` |

Conclusion: the defect lets a dropped learner enroll a second time, which breaks the
"enroll only once" rule (R4), and it is visible in the demo.

`pytest -q` with the defect in place: **36 failed, 78 passed**. Every failure traces to R4:

| Test file | Failed | What it caught |
|-----------|--------|----------------|
| `test_reenrollment.py` | 5 of 5 `PREVIOUSLY_DROPPED` tests | Dropped learners got `ENROLLED` / `WAITLISTED` instead of `PREVIOUSLY_DROPPED`. `test_previously_dropped_runs_no_eligibility_check` got `REJECTED`, showing the learner reached the eligibility check that R4 must skip. |
| `test_randomized_invariants.py` | 30 of 30 seeds | Every random sequence hit a dropped learner re-enrolling |
| `test_cli.py` | 1 | The demo no longer printed `PREVIOUSLY_DROPPED` |

Excerpt:
```
E   AssertionError: assert <Outcome.REJECTED: 'REJECTED'> is <Outcome.PREVIOUSLY_DROPPED: 'PREVIOUSLY_DROPPED'>
tests/test_reenrollment.py:46: AssertionError
...
36 failed, 78 passed in 0.95s
```
The 78 passing tests cover unrelated rules (capacity, FIFO, skip-and-retain, seat priority,
concurrency), as expected. The defect was then reverted with
`git checkout course_registration/offering.py`.

**Changes made or rejected after review:** _[candidate]_

