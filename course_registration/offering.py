"""Enrollment, drop, and FIFO waitlist promotion for one course offering (DESIGN.md v2.0)."""

from __future__ import annotations

import threading
from collections import OrderedDict
from types import MappingProxyType

from .directory import LearnerDirectory
from .models import LearnerStatus, OfferingState, Outcome, Result


def _valid_id(value: object) -> bool:
    return isinstance(value, str) and value.strip() != ""


class CourseOffering:
    """A single course offering with a fixed capacity and one prerequisite course.

    Policy summary (see docs/DESIGN.md for the full rules):
      * Eligible  <=>  the learner has completed ``prerequisite_course_id`` (A1).
      * Eligibility is checked ONLY at: new enrollment, moving to the waitlist, and promotion
        (§2.2). Never for already-enrolled learners, duplicates, previously dropped learners,
        drops or withdrawals (A7, R3, R4).
      * "Enroll only once" (§2.1): no duplicate records, and a seat may be held at most once.
        A DROPPED learner gets PREVIOUSLY_DROPPED (R4); a WITHDRAWN learner never held a seat
        and may enroll again through the normal flow (R5).
      * A failed prerequisite check returns REJECTED and stores nothing (A2).
      * Promotion is FIFO over the waitlist. An ineligible learner is skipped and RETAINED at
        the same position (A3). Promotion runs after every drop (P1) and before an eligible
        newcomer is seated (P2), so eligible waitlisted learners always come first (SP1), and
        ineligible ones never block a newcomer from a vacant seat (SP2).

    Thread safety: every public method, and any promotion it triggers, runs entirely under one
    lock, so check-then-act sequences and drop -> promote are atomic.
    """

    def __init__(
        self,
        course_id: str,
        capacity: int,
        prerequisite_course_id: str,
        directory: LearnerDirectory,
    ) -> None:
        if not _valid_id(course_id):
            raise ValueError("course_id must be a non-empty string")
        if not _valid_id(prerequisite_course_id):
            raise ValueError("prerequisite_course_id must be a non-empty string")
        if prerequisite_course_id == course_id:
            raise ValueError("a course cannot be its own prerequisite")
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1:
            raise ValueError("capacity must be a positive integer")
        if directory is None:
            raise ValueError("directory is required")

        self.course_id = course_id
        self.prerequisite_course_id = prerequisite_course_id
        self.capacity = capacity
        self._directory = directory

        self._lock = threading.Lock()
        self._status: dict[str, LearnerStatus] = {}
        self._enrolled: dict[str, None] = {}                     # insertion-ordered set
        self._waitlist: OrderedDict[str, int] = OrderedDict()   # learner -> join sequence
        self._seq = 0

    # ------------------------------------------------------------------ public API

    def enroll(self, learner_id: object) -> Result:
        with self._lock:
            invalid = self._validate(learner_id)
            if invalid:
                return invalid
            assert isinstance(learner_id, str)

            # R3 then R4, both before the prerequisite check: active and previously dropped
            # learners are never evaluated for eligibility.
            status = self._status.get(learner_id)
            if status is LearnerStatus.ENROLLED:
                return Result(Outcome.ALREADY_ENROLLED, learner_id, "Learner is already enrolled.")
            if status is LearnerStatus.WAITLISTED:
                return Result(
                    Outcome.ALREADY_WAITLISTED,
                    learner_id,
                    f"Learner is already waitlisted (position {self._position(learner_id)}).",
                )

            if status is LearnerStatus.DROPPED:
                return Result(
                    Outcome.PREVIOUSLY_DROPPED,
                    learner_id,
                    "Learner dropped this course and cannot enroll again.",
                )

            # C1 / C2: one eligibility check, before the seat-or-waitlist decision.
            if not self._eligible(learner_id):
                return Result(
                    Outcome.REJECTED,
                    learner_id,
                    f"Rejected: prerequisite {self.prerequisite_course_id} not completed.",
                )

            promoted: list[str] = []
            skipped: list[str] = []
            if self._has_vacancy():
                # P2 / SP1: eligible waitlisted learners are seated before the newcomer.
                promoted, skipped = self._promote()
                if self._has_vacancy():
                    # SP2: any remaining vacancy goes to the newcomer.
                    self._enrolled[learner_id] = None
                    self._status[learner_id] = LearnerStatus.ENROLLED
                    return Result(
                        Outcome.ENROLLED, learner_id, "Enrolled.", tuple(promoted), tuple(skipped)
                    )

            self._waitlist[learner_id] = self._next_seq()
            self._status[learner_id] = LearnerStatus.WAITLISTED
            return Result(
                Outcome.WAITLISTED,
                learner_id,
                f"Course full; waitlisted at position {len(self._waitlist)}.",
                tuple(promoted),
                tuple(skipped),
            )

    def drop(self, learner_id: object) -> Result:
        with self._lock:
            invalid = self._validate(learner_id)
            if invalid:
                return invalid
            assert isinstance(learner_id, str)

            status = self._status.get(learner_id)
            if status is LearnerStatus.DROPPED:
                return Result(Outcome.ALREADY_DROPPED, learner_id, "Learner has already dropped this course.")
            if status is not LearnerStatus.ENROLLED:
                hint = " Use leave_waitlist to leave the waitlist." if status is LearnerStatus.WAITLISTED else ""
                return Result(Outcome.NOT_ENROLLED, learner_id, "Learner is not enrolled." + hint)

            # No eligibility check on drop (A7).
            del self._enrolled[learner_id]
            self._status[learner_id] = LearnerStatus.DROPPED
            promoted, skipped = self._promote()  # P1
            return Result(Outcome.DROPPED, learner_id, "Dropped.", tuple(promoted), tuple(skipped))

    def leave_waitlist(self, learner_id: object) -> Result:
        with self._lock:
            invalid = self._validate(learner_id)
            if invalid:
                return invalid
            assert isinstance(learner_id, str)

            if self._status.get(learner_id) is not LearnerStatus.WAITLISTED:
                return Result(Outcome.NOT_WAITLISTED, learner_id, "Learner is not on the waitlist.")

            del self._waitlist[learner_id]
            self._status[learner_id] = LearnerStatus.WITHDRAWN
            # No seat opened, so no promotion (§8.2).
            return Result(Outcome.WITHDRAWN, learner_id, "Withdrawn from the waitlist; may enroll again.")

    def snapshot(self) -> OfferingState:
        with self._lock:
            return OfferingState(
                course_id=self.course_id,
                prerequisite_course_id=self.prerequisite_course_id,
                capacity=self.capacity,
                enrolled=tuple(self._enrolled),
                waitlist=tuple(self._waitlist),
                statuses=MappingProxyType(dict(self._status)),
            )

    # ------------------------------------------------------------------ internals (lock held)

    def _promote(self) -> tuple[list[str], list[str]]:
        """One FIFO pass: seat the earliest eligible learners; skip and retain ineligible ones (C3)."""
        promoted: list[str] = []
        skipped: list[str] = []
        for learner_id in list(self._waitlist):
            if not self._has_vacancy():
                break
            if self._eligible(learner_id):
                del self._waitlist[learner_id]
                self._enrolled[learner_id] = None
                self._status[learner_id] = LearnerStatus.ENROLLED
                promoted.append(learner_id)
            else:
                skipped.append(learner_id)  # retained: same FIFO slot, re-checked next time
        return promoted, skipped

    def _has_vacancy(self) -> bool:
        return len(self._enrolled) < self.capacity

    def _eligible(self, learner_id: str) -> bool:
        return self._directory.has_completed(learner_id, self.prerequisite_course_id)

    def _position(self, learner_id: str) -> int:
        return list(self._waitlist).index(learner_id) + 1

    def _validate(self, learner_id: object) -> Result | None:
        if not _valid_id(learner_id):
            return Result(Outcome.INVALID_REQUEST, learner_id, "learner_id must be a non-empty string.")
        if not self._directory.exists(learner_id):  # type: ignore[arg-type]
            return Result(Outcome.INVALID_REQUEST, learner_id, "Unknown learner.")
        return None

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

