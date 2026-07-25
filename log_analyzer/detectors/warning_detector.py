"""
Warning detector.

Matches log events for non-fatal warnings: deprecations, retries,
configuration issues, certificate expiry notices, etc.
"""

from __future__ import annotations

import re
from typing import List

from log_analyzer.models import Category, Issue, LogEvent, Severity
from log_analyzer.detectors.base import BaseDetector
from log_analyzer.detectors.error_detector import _group_by_proximity
from log_analyzer.remediation.suggestions import get_remediation

_RULES = [
    {
        "pattern": re.compile(r"DeprecationWarning|deprecated", re.IGNORECASE),
        "title": "Deprecated API / Feature Used",
        "severity": Severity.WARNING,
        "category": Category.DEPRECATION,
        "key": "deprecated_api",
    },
    {
        "pattern": re.compile(r"Retrying\s+(?:in|after|request)|retry\s+attempt\s+\d+", re.IGNORECASE),
        "title": "Retry Attempts Detected",
        "severity": Severity.WARNING,
        "category": Category.NETWORK,
        "key": "retry_warning",
    },
    {
        "pattern": re.compile(r"certificate\s+(?:will\s+expire|expir|expired)", re.IGNORECASE),
        "title": "TLS Certificate Expiring or Expired",
        "severity": Severity.WARNING,
        "category": Category.SECURITY,
        "key": "cert_expiry",
    },
    {
        "pattern": re.compile(r"running\s+as\s+root|privileged\s+container", re.IGNORECASE),
        "title": "Container Running as Root / Privileged",
        "severity": Severity.WARNING,
        "category": Category.SECURITY,
        "key": "privileged_container",
    },
    {
        "pattern": re.compile(r"disk\s+usage.*(?:8[5-9]|9\d)%|usage.*(?:8[5-9]|9\d)%\s+disk", re.IGNORECASE),
        "title": "High Disk Usage",
        "severity": Severity.WARNING,
        "category": Category.RESOURCE,
        "key": "high_disk_usage",
    },
    {
        "pattern": re.compile(r"(?:config|configuration)\s+(?:not\s+found|missing|invalid)", re.IGNORECASE),
        "title": "Missing or Invalid Configuration",
        "severity": Severity.WARNING,
        "category": Category.CONFIGURATION,
        "key": "missing_config",
    },
    {
        "pattern": re.compile(r"(?:slow\s+query|query\s+took|took\s+\d+\s*(?:ms|seconds?))\s*(?:>|\d)", re.IGNORECASE),
        "title": "Slow Database Query",
        "severity": Severity.WARNING,
        "category": Category.PERFORMANCE,
        "key": "slow_query",
    },
    {
        "pattern": re.compile(r"pod\s+(?:pending|not\s+ready|unschedulable)", re.IGNORECASE),
        "title": "Kubernetes Pod Not Ready",
        "severity": Severity.WARNING,
        "category": Category.RUNTIME_ERROR,
        "key": "pod_not_ready",
    },
    {
        "pattern": re.compile(r"resource\s+quota\s+exceeded|LimitRangeExceeded", re.IGNORECASE),
        "title": "Kubernetes Resource Quota Exceeded",
        "severity": Severity.WARNING,
        "category": Category.RESOURCE,
        "key": "resource_quota",
    },
    {
        "pattern": re.compile(r"back-off\s+restarting|Back-off\s+pulling", re.IGNORECASE),
        "title": "Kubernetes Back-Off Event",
        "severity": Severity.WARNING,
        "category": Category.RUNTIME_ERROR,
        "key": "k8s_backoff",
    },
    {
        "pattern": re.compile(r"Unstable\s+Build|BUILD\s+UNSTABLE", re.IGNORECASE),
        "title": "Jenkins Unstable Build",
        "severity": Severity.WARNING,
        "category": Category.BUILD_FAILURE,
        "key": "jenkins_unstable",
    },
    {
        "pattern": re.compile(r"(?:insecure|http://)\s+registry", re.IGNORECASE),
        "title": "Insecure Docker Registry",
        "severity": Severity.WARNING,
        "category": Category.SECURITY,
        "key": "insecure_registry",
    },
]


class WarningDetector(BaseDetector):
    """Detects warnings, deprecations, and configuration issues."""

    name = "WarningDetector"

    def detect(self, events: List[LogEvent]) -> List[Issue]:
        issues: List[Issue] = []

        for rule in _RULES:
            matched: List[LogEvent] = [
                evt for evt in events if rule["pattern"].search(evt.raw)
            ]
            if not matched:
                continue

            for group in _group_by_proximity(matched, gap=30):
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
