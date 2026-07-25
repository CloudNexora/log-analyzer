"""
Error detector.

Matches log events against patterns indicative of hard errors, crashes,
and build failures across Jenkins, Docker, Kubernetes, and generic sources.

Each rule is a dict with:
  - pattern:    compiled regex to match against event.message (or raw)
  - title:      short issue title
  - severity:   Severity enum value
  - category:   Category enum value
  - remediation_key: key into the remediation knowledge base
"""

from __future__ import annotations

import re
from typing import List

from log_analyzer.models import Category, Issue, LogEvent, LogSource, Severity
from log_analyzer.detectors.base import BaseDetector
from log_analyzer.remediation.suggestions import get_remediation

# ---------------------------------------------------------------------------
# Rule definitions
# ---------------------------------------------------------------------------

_RULES = [
    # ------- Build / CI -------
    {
        "pattern": re.compile(r"BUILD\s+FAILURE", re.IGNORECASE),
        "title": "Jenkins Build Failure",
        "severity": Severity.CRITICAL,
        "category": Category.BUILD_FAILURE,
        "key": "jenkins_build_failure",
    },
    {
        "pattern": re.compile(r"Tests\s+run:.*(?:Failures:\s*[1-9]|Errors:\s*[1-9])", re.IGNORECASE),
        "title": "Test Failures Detected",
        "severity": Severity.ERROR,
        "category": Category.BUILD_FAILURE,
        "key": "test_failure",
    },
    {
        "pattern": re.compile(r"FAILED.*exit code", re.IGNORECASE),
        "title": "Process Exited with Non-Zero Code",
        "severity": Severity.ERROR,
        "category": Category.RUNTIME_ERROR,
        "key": "non_zero_exit",
    },
    {
        "pattern": re.compile(r"Could not resolve dependencies", re.IGNORECASE),
        "title": "Dependency Resolution Failed",
        "severity": Severity.CRITICAL,
        "category": Category.BUILD_FAILURE,
        "key": "dependency_resolution",
    },
    {
        "pattern": re.compile(r"(?:compilation|compile)\s+(?:error|failed)", re.IGNORECASE),
        "title": "Compilation Error",
        "severity": Severity.CRITICAL,
        "category": Category.BUILD_FAILURE,
        "key": "compile_error",
    },
    # ------- Kubernetes -------
    {
        "pattern": re.compile(r"CrashLoopBackOff", re.IGNORECASE),
        "title": "Kubernetes Pod CrashLoopBackOff",
        "severity": Severity.CRITICAL,
        "category": Category.RUNTIME_ERROR,
        "key": "crash_loop_backoff",
    },
    {
        "pattern": re.compile(r"OOMKilled|OOM\s+kill", re.IGNORECASE),
        "title": "Pod Killed by OOM",
        "severity": Severity.CRITICAL,
        "category": Category.RESOURCE,
        "key": "oom_killed",
    },
    {
        "pattern": re.compile(r"Evicted", re.IGNORECASE),
        "title": "Pod Evicted",
        "severity": Severity.ERROR,
        "category": Category.RESOURCE,
        "key": "pod_evicted",
    },
    {
        "pattern": re.compile(r"ImagePullBackOff|ErrImagePull", re.IGNORECASE),
        "title": "Kubernetes Image Pull Failed",
        "severity": Severity.CRITICAL,
        "category": Category.CONFIGURATION,
        "key": "image_pull_error",
    },
    {
        "pattern": re.compile(r"Failed\s+to\s+pull\s+image", re.IGNORECASE),
        "title": "Docker Image Pull Error",
        "severity": Severity.ERROR,
        "category": Category.CONFIGURATION,
        "key": "image_pull_error",
    },
    {
        "pattern": re.compile(r"Liveness\s+probe\s+failed", re.IGNORECASE),
        "title": "Kubernetes Liveness Probe Failed",
        "severity": Severity.ERROR,
        "category": Category.RUNTIME_ERROR,
        "key": "liveness_probe_failed",
    },
    {
        "pattern": re.compile(r"Readiness\s+probe\s+failed", re.IGNORECASE),
        "title": "Kubernetes Readiness Probe Failed",
        "severity": Severity.ERROR,
        "category": Category.RUNTIME_ERROR,
        "key": "readiness_probe_failed",
    },
    # ------- Docker -------
    {
        "pattern": re.compile(r"container\s+died|container\s+exited", re.IGNORECASE),
        "title": "Docker Container Died Unexpectedly",
        "severity": Severity.CRITICAL,
        "category": Category.RUNTIME_ERROR,
        "key": "container_died",
    },
    {
        "pattern": re.compile(r"no\s+space\s+left\s+on\s+device", re.IGNORECASE),
        "title": "Disk Full — No Space Left",
        "severity": Severity.CRITICAL,
        "category": Category.RESOURCE,
        "key": "disk_full",
    },
    # ------- Generic runtime errors -------
    {
        "pattern": re.compile(
            r"(?:Traceback\s*\(most\s+recent\s+call\s+last\)|panic:|fatal error:|"
            r"Caused by:|Exception in thread|java\.lang\.\w+Exception)", re.IGNORECASE
        ),
        "title": "Unhandled Exception / Stack Trace",
        "severity": Severity.ERROR,
        "category": Category.RUNTIME_ERROR,
        "key": "unhandled_exception",
    },
    {
        "pattern": re.compile(r"segmentation\s+fault|SIGSEGV", re.IGNORECASE),
        "title": "Segmentation Fault",
        "severity": Severity.CRITICAL,
        "category": Category.RUNTIME_ERROR,
        "key": "segfault",
    },
    {
        "pattern": re.compile(r"connection\s+refused", re.IGNORECASE),
        "title": "Connection Refused",
        "severity": Severity.ERROR,
        "category": Category.NETWORK,
        "key": "connection_refused",
    },
    {
        "pattern": re.compile(r"SSL\s+(?:handshake\s+failed|certificate\s+verify\s+failed|error)", re.IGNORECASE),
        "title": "SSL/TLS Error",
        "severity": Severity.ERROR,
        "category": Category.SECURITY,
        "key": "ssl_error",
    },
    {
        "pattern": re.compile(r"permission\s+denied", re.IGNORECASE),
        "title": "Permission Denied",
        "severity": Severity.ERROR,
        "category": Category.SECURITY,
        "key": "permission_denied",
    },
    {
        "pattern": re.compile(r"authentication\s+failed|401\s+Unauthorized", re.IGNORECASE),
        "title": "Authentication Failed",
        "severity": Severity.ERROR,
        "category": Category.SECURITY,
        "key": "auth_failed",
    },
    {
        "pattern": re.compile(r"database\s+(?:connection\s+)?(?:failed|error|refused)", re.IGNORECASE),
        "title": "Database Connection Failed",
        "severity": Severity.CRITICAL,
        "category": Category.RUNTIME_ERROR,
        "key": "db_connection_failed",
    },
]


class ErrorDetector(BaseDetector):
    """Detects critical errors, crashes, and build failures."""

    name = "ErrorDetector"

    def detect(self, events: List[LogEvent]) -> List[Issue]:
        issues: List[Issue] = []

        for rule in _RULES:
            matched_events: List[LogEvent] = []
            for evt in events:
                if rule["pattern"].search(evt.raw):
                    matched_events.append(evt)

            if not matched_events:
                continue

            # Group consecutive matches into a single issue; emit separate
            # issues when there are large gaps (> 50 lines).
            groups = _group_by_proximity(matched_events, gap=50)
            for group in groups:
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

        return issues


def _group_by_proximity(events: List[LogEvent], gap: int = 50) -> List[List[LogEvent]]:
    """Split a flat list of events into groups of nearby line numbers."""
    if not events:
        return []
    groups: List[List[LogEvent]] = [[events[0]]]
    for evt in events[1:]:
        if evt.line_number - groups[-1][-1].line_number <= gap:
            groups[-1].append(evt)
        else:
            groups.append([evt])
    return groups
