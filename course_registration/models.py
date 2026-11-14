"""Value types shared by the service and its callers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Mapping


class LearnerStatus(str, Enum):
    """The single state a learner holds with respect to one offering."""

    ENROLLED = "ENROLLED"
    WAITLISTED = "WAITLISTED"
    DROPPED = "DROPPED"        # was enrolled, then dropped -> may NOT enroll again
    WITHDRAWN = "WITHDRAWN"    # left the waitlist voluntarily -> MAY enroll again
    REMOVED = "REMOVED"        # skipped at promotion for failing the prerequisite -> may NOT enroll again


class Outcome(str, Enum):
    # enroll
    ENROLLED = "ENROLLED"
    WAITLISTED = "WAITLISTED"
    ALREADY_ENROLLED = "ALREADY_ENROLLED"
    ALREADY_WAITLISTED = "ALREADY_WAITLISTED"
    PREVIOUSLY_DROPPED = "PREVIOUSLY_DROPPED"
    PREVIOUSLY_REMOVED = "PREVIOUSLY_REMOVED"
    PREREQUISITE_NOT_MET = "PREREQUISITE_NOT_MET"
    # drop
    DROPPED = "DROPPED"
    ALREADY_DROPPED = "ALREADY_DROPPED"
    NOT_ENROLLED = "NOT_ENROLLED"
    # leave_waitlist
    WITHDRAWN = "WITHDRAWN"
    NOT_WAITLISTED = "NOT_WAITLISTED"
    # any operation
    INVALID_REQUEST = "INVALID_REQUEST"


# Outcomes that change offering state. Every other outcome is guaranteed to leave state untouched.
SUCCESS_OUTCOMES = frozenset({Outcome.ENROLLED, Outcome.WAITLISTED, Outcome.DROPPED, Outcome.WITHDRAWN})


@dataclass(frozen=True)
class RemovalRecord:
    """Audit entry written when an ineligible learner is skipped and removed during promotion."""

    learner_id: str
    reason: Outcome
    sequence: int  # offering-local event counter at the time of removal


@dataclass(frozen=True)
class Result:
    outcome: Outcome
    learner_id: object
    message: str
    promoted: tuple[str, ...] = ()               # learners moved waitlist -> enrolled by this call
    removed: tuple[RemovalRecord, ...] = ()      # learners skipped and removed by this call

    @property
    def ok(self) -> bool:
        return self.outcome in SUCCESS_OUTCOMES


@dataclass(frozen=True)
class OfferingState:
    """Immutable, point-in-time copy of an offering's state."""

    course_id: str
    prerequisite_course_id: str
    capacity: int
    enrolled: tuple[str, ...]
    waitlist: tuple[str, ...]                    # front of queue first
    statuses: Mapping[str, LearnerStatus] = field(default_factory=lambda: MappingProxyType({}))
    removals: tuple[RemovalRecord, ...] = ()

    @property
    def seats_available(self) -> int:
        return self.capacity - len(self.enrolled)
