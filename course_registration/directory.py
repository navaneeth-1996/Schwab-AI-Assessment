"""In-memory stand-in for an external student-records system."""

from __future__ import annotations

import threading
from typing import Iterable


class LearnerDirectory:
    """Maps learner IDs to the set of course IDs they have completed.

    Records are mutable on purpose: a learner's eligibility can change while they wait
    (e.g. a completion is revoked or corrected), which is what the promotion-time
    eligibility re-check exists to handle.
    """

    def __init__(self) -> None:
        self._completed: dict[str, set[str]] = {}
        self._lock = threading.Lock()

    def register(self, learner_id: str, completed_courses: Iterable[str] = ()) -> None:
        with self._lock:
            self._completed[learner_id] = set(completed_courses)

    def exists(self, learner_id: str) -> bool:
        with self._lock:
            return learner_id in self._completed

    def has_completed(self, learner_id: str, course_id: str) -> bool:
        with self._lock:
            return course_id in self._completed.get(learner_id, ())

    def add_completion(self, learner_id: str, course_id: str) -> None:
        with self._lock:
            self._completed[learner_id].add(course_id)

    def revoke_completion(self, learner_id: str, course_id: str) -> None:
        with self._lock:
            self._completed[learner_id].discard(course_id)
