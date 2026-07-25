"""
Performance detector.

Detects signs of performance degradation: high latency, memory pressure,
connection pool exhaustion, GC pauses, and throughput drops.
"""

from __future__ import annotations

import re
from typing import List

from log_analyzer.models import Category, Issue, LogEvent, Severity
from log_analyzer.detectors.base import BaseDetector
from log_analyzer.detectors.error_detector import _group_by_proximity
from log_analyzer.remediation.suggestions import get_remediation

# ---------------------------------------------------------------------------
# Latency threshold (ms) above which we flag as performance issue
# ---------------------------------------------------------------------------
_LATENCY_THRESHOLD_MS = 1000

_LATENCY_RE = re.compile(
    r"(?:took|elapsed|duration|latency|response_time)[=:\s]+(\d+(?:\.\d+)?)\s*(ms|s|seconds?|milliseconds?)",
    re.IGNORECASE,
)

_RULES = [
    {
        "pattern": re.compile(r"OutOfMemoryError|out of memory|memory\s+(?:pressure|limit\s+exceeded)", re.IGNORECASE),
        "title": "Out of Memory Error",
        "severity": Severity.CRITICAL,
        "category": Category.PERFORMANCE,
        "key": "oom_error",
    },
    {
        "pattern": re.compile(r"GC\s+overhead\s+limit\s+exceeded", re.IGNORECASE),
        "title": "JVM GC Overhead Limit Exceeded",
        "severity": Severity.CRITICAL,
        "category": Category.PERFORMANCE,
        "key": "gc_overhead",
    },
    {
        "pattern": re.compile(r"connection\s+pool\s+(?:exhausted|full|timeout)", re.IGNORECASE),
        "title": "Connection Pool Exhausted",
        "severity": Severity.ERROR,
        "category": Category.PERFORMANCE,
        "key": "connection_pool",
    },
    {
        "pattern": re.compile(r"(?:request|operation|job)\s+timed?\s*out|ETIMEDOUT|deadline\s+exceeded", re.IGNORECASE),
        "title": "Request / Operation Timeout",
        "severity": Severity.ERROR,
        "category": Category.PERFORMANCE,
        "key": "timeout",
    },
    {
        "pattern": re.compile(r"high\s+(?:cpu|memory)\s+usage|cpu\s+(?:throttled|throttling)", re.IGNORECASE),
        "title": "High CPU / Memory Usage",
        "severity": Severity.WARNING,
        "category": Category.PERFORMANCE,
        "key": "high_resource_usage",
    },
    {
        "pattern": re.compile(r"queue\s+(?:full|overflow|depth\s+exceeded)", re.IGNORECASE),
        "title": "Message Queue Full / Overflow",
        "severity": Severity.ERROR,
        "category": Category.PERFORMANCE,
        "key": "queue_overflow",
    },
    {
        "pattern": re.compile(r"thread\s+(?:pool\s+exhausted|deadlock|starvation)", re.IGNORECASE),
        "title": "Thread Pool Exhausted / Deadlock",
        "severity": Severity.ERROR,
        "category": Category.PERFORMANCE,
        "key": "thread_exhaustion",
    },
    {
        "pattern": re.compile(r"pause\s+time\s+\d+|Stop-the-world\s+GC\s+pause", re.IGNORECASE),
        "title": "Long GC Pause / Stop-the-World",
        "severity": Severity.WARNING,
        "category": Category.PERFORMANCE,
        "key": "gc_pause",
    },
    {
        "pattern": re.compile(r"(?:cpu\s+)?throttling.*container|container.*(?:cpu\s+)?throttl", re.IGNORECASE),
        "title": "Kubernetes Container CPU Throttling",
        "severity": Severity.WARNING,
        "category": Category.PERFORMANCE,
        "key": "cpu_throttling",
    },
]


class PerformanceDetector(BaseDetector):
    """Detects performance issues: latency spikes, OOM, pool exhaustion, timeouts."""

    name = "PerformanceDetector"

    def detect(self, events: List[LogEvent]) -> List[Issue]:
        issues: List[Issue] = []

        # --- Rule-based matching ---
        for rule in _RULES:
            matched: List[LogEvent] = [
                evt for evt in events if rule["pattern"].search(evt.raw)
            ]
            if not matched:
                continue
            for group in _group_by_proximity(matched, gap=50):
                rem = get_remediation(rule["key"])
                issues.append(
                    Issue(
                        title=rule["title"],
                        severity=rule["severity"],
                        category=rule["category"],
                        source=group[0].source,
                        detector=self.name,
                        pattern=rule["pattern"].pattern,
                        events=group,
                        remediation=rem["steps"],
                        references=rem["references"],
                    )
                )

        # --- Latency threshold check ---
        slow_events: List[LogEvent] = []
        for evt in events:
            m = _LATENCY_RE.search(evt.raw)
            if m:
                value = float(m.group(1))
                unit = m.group(2).lower()
                ms = value * 1000 if unit.startswith("s") else value
                if ms >= _LATENCY_THRESHOLD_MS:
                    slow_events.append(evt)

        if slow_events:
            rem = get_remediation("high_latency")
            for group in _group_by_proximity(slow_events, gap=100):
                issues.append(
                    Issue(
                        title=f"High Response Latency (≥ {_LATENCY_THRESHOLD_MS} ms)",
                        severity=Severity.WARNING,
                        category=Category.PERFORMANCE,
                        source=group[0].source,
                        detector=self.name,
                        pattern=_LATENCY_RE.pattern,
                        events=group,
                        remediation=rem["steps"],
                        references=rem["references"],
                        extra={"threshold_ms": _LATENCY_THRESHOLD_MS},
                    )
                )

        return issues
