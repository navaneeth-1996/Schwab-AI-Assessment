"""Enrollment, drop, and FIFO waitlist promotion for one course offering."""

from __future__ import annotations

import threading
from collections import OrderedDict
from types import MappingProxyType

from .directory import LearnerDirectory
from .models import LearnerStatus, OfferingState, Outcome, RemovalRecord, Result


def _valid_id(value: object) -> bool:
    return isinstance(value, str) and value.strip() != ""


class CourseOffering:
    """A single course offering with a fixed capacity and one prerequisite course.

    Policy (see docs/DESIGN.md):
      * Eligible  <=>  the learner has completed ``prerequisite_course_id``.
      * Ineligible learners are rejected at enroll time and never join the waitlist.
      * Eligibility is re-checked at promotion time; a learner who is no longer eligible is
        skipped and REMOVED (with an audit record), and promotion moves to the next learner.
      * DROPPED and REMOVED learners may not enroll again; WITHDRAWN learners may.

    Thread safety: every public method runs entirely under one lock, so a drop and the
    promotion it triggers are a single atomic step.
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
        self._enrolled: dict[str, None] = {}            # insertion-ordered set
        self._waitlist: OrderedDict[str, int] = OrderedDict()  # learner -> join sequence
        self._removals: list[RemovalRecord] = []
        self._seq = 0

    # ------------------------------------------------------------------ public API

    def enroll(self, learner_id: object) -> Result:
        with self._lock:
            invalid = self._validate(learner_id)
            if invalid:
                return invalid
            assert isinstance(learner_id, str)

            status = self._status.get(learner_id)
            if status is LearnerStatus.ENROLLED:
                return self._result(Outcome.ALREADY_ENROLLED, learner_id, "Learner is already enrolled.")
            if status is LearnerStatus.WAITLISTED:
                pos = list(self._waitlist).index(learner_id) + 1
                return self._result(
                    Outcome.ALREADY_WAITLISTED, learner_id, f"Learner is already waitlisted (position {pos})."
                )
            if status is LearnerStatus.DROPPED:
                return self._result(
                    Outcome.PREVIOUSLY_DROPPED, learner_id, "Learner dropped this course and cannot re-enroll."
                )
            if status is LearnerStatus.REMOVED:
                return self._result(
                    Outcome.PREVIOUSLY_REMOVED,
                    learner_id,
                    "Learner was removed from the waitlist for not meeting the prerequisite and cannot re-enroll.",
                )
            # status is None or WITHDRAWN: treat as a fresh request.
            if not self._eligible(learner_id):
                return self._result(
                    Outcome.PREREQUISITE_NOT_MET,
                    learner_id,
                    f"Prerequisite {self.prerequisite_course_id} not completed.",
                )

            if len(self._enrolled) < self.capacity:
                self._enrolled[learner_id] = None
                self._status[learner_id] = LearnerStatus.ENROLLED
                return self._result(Outcome.ENROLLED, learner_id, "Enrolled.")

            self._waitlist[learner_id] = self._next_seq()
            self._status[learner_id] = LearnerStatus.WAITLISTED
            return self._result(
                Outcome.WAITLISTED, learner_id, f"Course full; waitlisted at position {len(self._waitlist)}."
            )

    def drop(self, learner_id: object) -> Result:
        with self._lock:
            invalid = self._validate(learner_id)
            if invalid:
                return invalid
            assert isinstance(learner_id, str)

            status = self._status.get(learner_id)
            if status is LearnerStatus.DROPPED:
                return self._result(Outcome.ALREADY_DROPPED, learner_id, "Learner has already dropped this course.")
            if status is not LearnerStatus.ENROLLED:
                hint = " Use leave_waitlist to leave the waitlist." if status is LearnerStatus.WAITLISTED else ""
                return self._result(Outcome.NOT_ENROLLED, learner_id, "Learner is not enrolled." + hint)

            del self._enrolled[learner_id]
            self._status[learner_id] = LearnerStatus.DROPPED
            promoted, removed = self._promote()
            return self._result(
                Outcome.DROPPED, learner_id, "Dropped.", promoted=tuple(promoted), removed=tuple(removed)
            )

    def leave_waitlist(self, learner_id: object) -> Result:
        with self._lock:
            invalid = self._validate(learner_id)
            if invalid:
                return invalid
            assert isinstance(learner_id, str)

            if self._status.get(learner_id) is not LearnerStatus.WAITLISTED:
                return self._result(Outcome.NOT_WAITLISTED, learner_id, "Learner is not on the waitlist.")

            del self._waitlist[learner_id]
            self._status[learner_id] = LearnerStatus.WITHDRAWN
            # No seat opened, so no promotion is needed.
            return self._result(Outcome.WITHDRAWN, learner_id, "Withdrawn from the waitlist; may enroll again.")

    def snapshot(self) -> OfferingState:
        with self._lock:
            return OfferingState(
                course_id=self.course_id,
                prerequisite_course_id=self.prerequisite_course_id,
                capacity=self.capacity,
                enrolled=tuple(self._enrolled),
                waitlist=tuple(self._waitlist),
                statuses=MappingProxyType(dict(self._status)),
                removals=tuple(self._removals),
            )

    # ------------------------------------------------------------------ internals (lock held)

    def _promote(self) -> tuple[list[str], list[RemovalRecord]]:
        """Fill open seats from the front of the waitlist, skipping and removing ineligible learners."""
        promoted: list[str] = []
        removed: list[RemovalRecord] = []
        while len(self._enrolled) < self.capacity and self._waitlist:
            learner_id, _ = self._waitlist.popitem(last=False)
            if self._eligible(learner_id):
                self._enrolled[learner_id] = None
                self._status[learner_id] = LearnerStatus.ENROLLED
                promoted.append(learner_id)
            else:
                record = RemovalRecord(learner_id, Outcome.PREREQUISITE_NOT_MET, self._next_seq())
                self._removals.append(record)
                self._status[learner_id] = LearnerStatus.REMOVED
                removed.append(record)
        return promoted, removed

    def _eligible(self, learner_id: str) -> bool:
        return self._directory.has_completed(learner_id, self.prerequisite_course_id)

    def _validate(self, learner_id: object) -> Result | None:
        if not _valid_id(learner_id):
            return self._result(Outcome.INVALID_REQUEST, learner_id, "learner_id must be a non-empty string.")
        if not self._directory.exists(learner_id):  # type: ignore[arg-type]
            return self._result(Outcome.INVALID_REQUEST, learner_id, "Unknown learner.")
        return None

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    @staticmethod
    def _result(outcome: Outcome, learner_id: object, message: str, **extra) -> Result:
        return Result(outcome=outcome, learner_id=learner_id, message=message, **extra)
