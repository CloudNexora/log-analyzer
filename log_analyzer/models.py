"""
Core data models for the Log Analyzer.

Defines the canonical types used throughout the pipeline:
  LogEvent  — a single parsed log line with metadata
  Issue     — a detected problem with severity, remediation, and context
  AnalysisReport — aggregated results from a full analysis run
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    """Issue severity levels, ordered from lowest to highest."""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    @property
    def order(self) -> int:
        return {"INFO": 0, "WARNING": 1, "ERROR": 2, "CRITICAL": 3}[self.value]

    def __lt__(self, other: "Severity") -> bool:
        return self.order < other.order

    def __le__(self, other: "Severity") -> bool:
        return self.order <= other.order


class Category(str, Enum):
    """High-level categorisation of an issue."""
    BUILD_FAILURE = "Build Failure"
    RUNTIME_ERROR = "Runtime Error"
    CONFIGURATION = "Configuration"
    PERFORMANCE = "Performance"
    SECURITY = "Security"
    NETWORK = "Network"
    RESOURCE = "Resource"
    DEPRECATION = "Deprecation"
    UNKNOWN = "Unknown"


class LogSource(str, Enum):
    """Identifies which log parser produced the events."""
    JENKINS = "jenkins"
    DOCKER = "docker"
    KUBERNETES = "kubernetes"
    GENERIC = "generic"
    AUTO = "auto"


# ---------------------------------------------------------------------------
# LogEvent
# ---------------------------------------------------------------------------

@dataclass
class LogEvent:
    """
    A single parsed log entry.

    Attributes:
        line_number: 1-based line number in the original file.
        raw:         The unmodified original log line.
        timestamp:   Parsed timestamp (if available).
        level:       Log level string as it appeared (e.g. "ERROR", "WARN").
        message:     Extracted message body.
        source:      Which parser produced this event.
        metadata:    Parser-specific key/value pairs (pod name, container ID, etc.).
    """
    line_number: int
    raw: str
    message: str
    source: LogSource = LogSource.GENERIC
    timestamp: Optional[datetime] = None
    level: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:  # pragma: no cover
        ts = self.timestamp.isoformat() if self.timestamp else "no-ts"
        return f"<LogEvent L{self.line_number} [{self.level}] {ts}: {self.message[:60]}>"


# ---------------------------------------------------------------------------
# Issue
# ---------------------------------------------------------------------------

@dataclass
class Issue:
    """
    A detected problem extracted from one or more log events.

    Attributes:
        id:           Unique identifier for deduplication / linking in reports.
        title:        Short human-readable description.
        severity:     Severity enum value.
        category:     High-level issue category.
        source:       Log source that produced this issue.
        detector:     Name of the detector class that found this issue.
        pattern:      The regex/keyword pattern that matched.
        events:       The log events that triggered this issue.
        remediation:  Ordered list of suggested fix steps.
        references:   Optional URLs to relevant docs or runbooks.
        extra:        Any additional structured metadata.
    """
    title: str
    severity: Severity
    category: Category
    source: LogSource
    detector: str
    pattern: str
    events: List[LogEvent]
    remediation: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    @property
    def first_event(self) -> Optional[LogEvent]:
        return self.events[0] if self.events else None

    @property
    def line_numbers(self) -> List[int]:
        return [e.line_number for e in self.events]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict (JSON-safe)."""
        return {
            "id": self.id,
            "title": self.title,
            "severity": self.severity.value,
            "category": self.category.value,
            "source": self.source.value,
            "detector": self.detector,
            "pattern": self.pattern,
            "line_numbers": self.line_numbers,
            "remediation": self.remediation,
            "references": self.references,
            "context": [e.raw for e in self.events],
            "extra": self.extra,
        }


# ---------------------------------------------------------------------------
# AnalysisReport
# ---------------------------------------------------------------------------

@dataclass
class AnalysisReport:
    """
    The final output of an analysis run.

    Attributes:
        file_path:   The log file (or directory) that was analysed.
        source:      Detected or specified log source type.
        issues:      All detected issues, unsorted.
        analyzed_at: UTC timestamp of the run.
        total_lines: Number of log lines processed.
        metadata:    Additional context (tool versions, etc.).
    """
    file_path: str
    source: LogSource
    issues: List[Issue] = field(default_factory=list)
    analyzed_at: datetime = field(default_factory=datetime.utcnow)
    total_lines: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    def by_severity(self, severity: Severity) -> List[Issue]:
        return [i for i in self.issues if i.severity == severity]

    @property
    def criticals(self) -> List[Issue]:
        return self.by_severity(Severity.CRITICAL)

    @property
    def errors(self) -> List[Issue]:
        return self.by_severity(Severity.ERROR)

    @property
    def warnings(self) -> List[Issue]:
        return self.by_severity(Severity.WARNING)

    @property
    def infos(self) -> List[Issue]:
        return self.by_severity(Severity.INFO)

    @property
    def sorted_issues(self) -> List[Issue]:
        """Issues sorted by severity (critical first) then by first line number."""
        return sorted(
            self.issues,
            key=lambda i: (-i.severity.order, i.line_numbers[0] if i.line_numbers else 0),
        )

    @property
    def summary(self) -> Dict[str, int]:
        return {
            "total": len(self.issues),
            "critical": len(self.criticals),
            "error": len(self.errors),
            "warning": len(self.warnings),
            "info": len(self.infos),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "source": self.source.value,
            "analyzed_at": self.analyzed_at.isoformat(),
            "total_lines": self.total_lines,
            "summary": self.summary,
            "metadata": self.metadata,
            "issues": [i.to_dict() for i in self.sorted_issues],
        }
