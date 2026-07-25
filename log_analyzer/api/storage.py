"""
In-memory report store.

Reports are stored as (AnalysisReport, filename) pairs keyed by a UUID.
Thread-safe via a RLock so multiple concurrent requests are safe.

For production use, swap this out for Redis or a database backend.
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from log_analyzer.models import AnalysisReport


class ReportStore:
    """Thread-safe in-memory store for AnalysisReport objects."""

    def __init__(self) -> None:
        self._store: Dict[str, Tuple[AnalysisReport, str]] = {}
        self._lock = threading.RLock()

    def save(self, report: AnalysisReport, filename: str) -> str:
        """
        Persist *report* and return its unique ID.

        Args:
            report:   The analysis report to store.
            filename: Original uploaded filename (for display purposes).

        Returns:
            A UUID string that can be used to retrieve the report later.
        """
        report_id = str(uuid.uuid4())
        with self._lock:
            self._store[report_id] = (report, filename)
        return report_id

    def get(self, report_id: str) -> Optional[Tuple[AnalysisReport, str]]:
        """Return ``(report, filename)`` or ``None`` if not found."""
        with self._lock:
            return self._store.get(report_id)

    def list_all(self) -> Dict[str, Tuple[AnalysisReport, str]]:
        """Return a snapshot of all stored reports."""
        with self._lock:
            return dict(self._store)

    def delete(self, report_id: str) -> bool:
        """Delete a report. Returns True if it existed."""
        with self._lock:
            return self._store.pop(report_id, None) is not None

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)


# Singleton store shared across all requests
store = ReportStore()
