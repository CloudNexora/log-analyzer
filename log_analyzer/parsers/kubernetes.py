"""
Kubernetes log parser.

Handles two input styles:
  1. ``kubectl logs`` output — plain container stdout, optionally with
     ``--timestamps`` flag which prepends RFC 3339.
  2. ``kubectl get events`` output — tabular event format with columns:
       LAST SEEN  TYPE   REASON   OBJECT   MESSAGE
  3. Kubernetes control-plane component logs (klog format):
       I0115 10:22:05.123456   1 controller.go:100] message here
       W0115 ...
       E0115 ...
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import List, Optional

from log_analyzer.models import LogEvent, LogSource
from log_analyzer.parsers.base import BaseParser
from log_analyzer.parsers.docker import _parse_ts  # shared RFC 3339 helper

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# klog format: I0115 10:22:05.123456   1 source.go:42] message
_KLOG = re.compile(
    r"^([IWEF])(\d{4})\s+(\d{2}:\d{2}:\d{2}\.\d+)\s+\d+\s+[\w.]+:\d+\]\s+(.*)"
)
_KLOG_LEVEL = {"I": "INFO", "W": "WARNING", "E": "ERROR", "F": "CRITICAL"}

# kubectl events line (after header):
# 5m    Warning   BackOff    Pod/my-pod   Back-off restarting failed container
_EVENTS_LINE = re.compile(
    r"^(\S+)\s+(Normal|Warning)\s+(\S+)\s+(\S+/\S+|\S+)\s+(.*)"
)

# RFC 3339 prefix (kubectl logs --timestamps)
_RFC3339_PREFIX = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)\s+"
)

# Kubernetes-specific keywords for auto-detection
_K8S_KEYWORDS = [
    "CrashLoopBackOff",
    "OOMKilled",
    "Evicted",
    "BackOff",
    "kubelet",
    "kube-apiserver",
    "kube-scheduler",
    "kube-controller",
    "pod/",
    "deployment/",
    "replicaset/",
    "namespace/",
    "kubectl",
    "k8s.io",
]


class KubernetesParser(BaseParser):
    """Parser for Kubernetes pod logs and event output."""

    source = LogSource.KUBERNETES

    @classmethod
    def score_source(cls, lines: List[str]) -> float:
        sample = cls._sample(lines)
        hits = sum(
            1 for line in sample if any(kw.lower() in line.lower() for kw in _K8S_KEYWORDS)
        )
        klog_hits = sum(1 for line in sample if _KLOG.match(line))
        return min((hits + klog_hits * 3) / max(len(sample), 1) * 8, 1.0)

    def parse(self, lines: List[str]) -> List[LogEvent]:
        events: List[LogEvent] = []

        for lineno, raw in enumerate(lines, start=1):
            line = raw.rstrip("\n\r")
            ts: Optional[datetime] = None
            level: Optional[str] = None
            message = line
            meta: dict = {}

            # --- klog format ---
            klog_m = _KLOG.match(line)
            if klog_m:
                level = _KLOG_LEVEL.get(klog_m.group(1), "INFO")
                # month+day in group(2), time in group(3)  — no year in klog
                try:
                    time_part = klog_m.group(3)[:15]
                    ts = datetime.strptime(time_part, "%H:%M:%S.%f").replace(
                        tzinfo=timezone.utc
                    )
                except ValueError:
                    pass
                message = klog_m.group(4)

            else:
                # --- kubectl events ---
                evt_m = _EVENTS_LINE.match(line)
                if evt_m:
                    age, evt_type, reason, obj, msg = evt_m.groups()
                    level = "WARNING" if evt_type == "Warning" else "INFO"
                    message = msg
                    meta.update({"age": age, "reason": reason, "object": obj})
                else:
                    # --- RFC 3339 prefix (kubectl logs --timestamps) ---
                    rfc_m = _RFC3339_PREFIX.match(line)
                    if rfc_m:
                        ts = _parse_ts(rfc_m.group(1))
                        message = line[rfc_m.end():]

                    # Level keywords in remaining message
                    lvl_m = re.search(
                        r"\b(INFO|DEBUG|WARNING|WARN|ERROR|FATAL|CRITICAL|PANIC)\b",
                        message,
                        re.IGNORECASE,
                    )
                    if lvl_m:
                        level = lvl_m.group(1).upper()
                        if level == "WARN":
                            level = "WARNING"

            events.append(
                LogEvent(
                    line_number=lineno,
                    raw=raw,
                    message=message.strip(),
                    source=self.source,
                    timestamp=ts,
                    level=level,
                    metadata=meta,
                )
            )

        return events
