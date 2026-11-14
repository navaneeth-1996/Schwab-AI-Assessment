"""Value types shared by the service and its callers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Mapping


class LearnerStatus(str, Enum):
    """The single state a learner holds with respect to one offering (DESIGN.md §3)."""

    ENROLLED = "ENROLLED"      # active
    WAITLISTED = "WAITLISTED"  # active
    DROPPED = "DROPPED"        # inactive: dropped an enrolled seat; may enroll again
    WITHDRAWN = "WITHDRAWN"    # inactive: left the waitlist; may enroll again


ACTIVE_STATUSES = frozenset({LearnerStatus.ENROLLED, LearnerStatus.WAITLISTED})


class Outcome(str, Enum):
    # enroll
    ENROLLED = "ENROLLED"
    WAITLISTED = "WAITLISTED"
    ALREADY_ENROLLED = "ALREADY_ENROLLED"
    ALREADY_WAITLISTED = "ALREADY_WAITLISTED"
    REJECTED = "REJECTED"                  # prerequisite not met; nothing stored
    # drop
    DROPPED = "DROPPED"
    ALREADY_DROPPED = "ALREADY_DROPPED"
    NOT_ENROLLED = "NOT_ENROLLED"
    # leave_waitlist
    WITHDRAWN = "WITHDRAWN"
    NOT_WAITLISTED = "NOT_WAITLISTED"
    # any operation
    INVALID_REQUEST = "INVALID_REQUEST"


# Outcomes that change offering state. Every other outcome leaves state untouched (invariant 5).
SUCCESS_OUTCOMES = frozenset({Outcome.ENROLLED, Outcome.WAITLISTED, Outcome.DROPPED, Outcome.WITHDRAWN})


@dataclass(frozen=True)
class Result:
    outcome: Outcome
    learner_id: object
    message: str
    promoted: tuple[str, ...] = ()   # learners moved waitlist -> enrolled by this call
    skipped: tuple[str, ...] = ()    # ineligible learners passed over and retained by this call

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
    waitlist: tuple[str, ...]        # front of queue first
    statuses: Mapping[str, LearnerStatus] = field(default_factory=lambda: MappingProxyType({}))

    @property
    def seats_available(self) -> int:
        return self.capacity - len(self.enrolled)
