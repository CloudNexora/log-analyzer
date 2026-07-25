"""
Base parser interface.

All parsers must implement `parse()` which converts raw log lines into a
list of `LogEvent` objects. Optionally override `detect_source()` to
provide heuristics for auto-detection.
"""

from __future__ import annotations

import abc
from typing import List

from log_analyzer.models import LogEvent, LogSource


class BaseParser(abc.ABC):
    """Abstract base class for all log parsers.

    Subclasses must implement :meth:`parse`.  They may optionally
    override :meth:`score_source` to participate in auto-detection.
    """

    #: Override in subclasses — the canonical source tag
    source: LogSource = LogSource.GENERIC

    def __init__(self) -> None:
        self._events: List[LogEvent] = []

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abc.abstractmethod
    def parse(self, lines: List[str]) -> List[LogEvent]:
        """
        Convert raw log lines into :class:`~log_analyzer.models.LogEvent` objects.

        Args:
            lines: Raw lines from the log file (newlines stripped).

        Returns:
            List of parsed log events.
        """

    # ------------------------------------------------------------------
    # Auto-detection heuristic
    # ------------------------------------------------------------------

    @classmethod
    def score_source(cls, lines: List[str]) -> float:
        """
        Return a confidence score in [0, 1] indicating how likely these lines
        belong to this parser's log format.

        The engine picks the parser with the highest score when ``--source auto``
        is requested.  The default implementation returns 0.0 (no opinion).
        """
        return 0.0

    # ------------------------------------------------------------------
    # Helpers available to all subclasses
    # ------------------------------------------------------------------

    @staticmethod
    def _sample(lines: List[str], n: int = 200) -> List[str]:
        """Return up to *n* evenly-spaced lines for quick scoring."""
        if len(lines) <= n:
            return lines
        step = len(lines) // n
        return lines[::step][:n]
