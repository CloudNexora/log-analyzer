"""
Base detector interface.

Each detector receives the full list of :class:`~log_analyzer.models.LogEvent`
objects from a parser and returns a (possibly empty) list of
:class:`~log_analyzer.models.Issue` objects.
"""

from __future__ import annotations

import abc
from typing import List

from log_analyzer.models import Issue, LogEvent


class BaseDetector(abc.ABC):
    """
    Abstract base class for all issue detectors.

    Subclasses must implement :meth:`detect` which receives parsed events
    and returns a list of issues.
    """

    #: Human-readable detector name used in Issue.detector field
    name: str = "BaseDetector"

    @abc.abstractmethod
    def detect(self, events: List[LogEvent]) -> List[Issue]:
        """
        Analyse *events* and return detected :class:`~log_analyzer.models.Issue` objects.

        Args:
            events: All parsed log events for a single file.

        Returns:
            List of issues. Return an empty list if nothing was found.
        """

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _context_window(
        events: List[LogEvent], index: int, before: int = 2, after: int = 2
    ) -> List[LogEvent]:
        """Return *before* events before and *after* events after *index*."""
        start = max(0, index - before)
        end = min(len(events), index + after + 1)
        return events[start:end]
