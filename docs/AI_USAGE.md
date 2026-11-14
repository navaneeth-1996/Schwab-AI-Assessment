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
| Q2: removal block is permanent | Not answered explicitly; **AI default applied**, documented as A4. _[candidate: confirm]_ |
| Q3: enrolled learner keeps the seat | Not answered explicitly; **AI default applied**, documented as A7. _[candidate: confirm]_ |

## Interaction 3 – Implementation and tests
**Prompt (summary):** The DROPPED/WITHDRAWN decision above, which implied "go ahead".

**AI output:**
- `course_registration/` package: `models.py`, `directory.py`, `offering.py`, `cli.py`.
- 88 pytest tests in 7 modules, including a shared invariant checker, concurrency tests and
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

_[candidate: record your own review here. Suggested checks:]_
- [ ] Read `offering.py` end to end against DESIGN.md §2 and §8.
- [ ] Run `pytest -q` yourself and paste the output below.
- [ ] Introduce at least one defect of your own and confirm a test fails.
- [ ] Confirm or change A4 (permanent removal block) and A7 (enrolled learner keeps the seat).
- [ ] Note anything you changed or rejected from the generated code.

```
<paste your pytest output here>
```

## Files informed by AI
| File | AI contribution | Human decision points |
|------|-----------------|-----------------------|
| `docs/DESIGN.md` | Drafted | All policy rows A1–A6 decided by the candidate |
| `course_registration/*.py` | Generated | Status model (DROPPED vs WITHDRAWN), single prerequisite, skip-and-remove with record |
| `tests/*.py` | Generated | Coverage list from AC6; concurrency test fixed after deliberately breaking the code |
| `README.md`, `docs/AI_USAGE.md` | Drafted | _[candidate review]_ |
