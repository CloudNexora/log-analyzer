"""
Docker log parser.

Handles two common Docker log formats:
  1. ``docker logs`` output with RFC 3339 timestamps (produced by json-file driver):
       2024-01-15T10:22:05.123456789Z  <message>
  2. Docker daemon logs (journald / logfile):
       time="2024-01-15T10:22:05.123Z" level=error msg="..."
  3. Plain container stdout without timestamps (pass-through).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import List, Optional

from log_analyzer.models import LogEvent, LogSource
from log_analyzer.parsers.base import BaseParser

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# RFC 3339 timestamp as first token (docker logs --timestamps)
_RFC3339 = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?(?:[+-]\d{2}:\d{2})?)\s+"
)

# Docker daemon structured log line
#   time="2024-01-15T10:22:05.123456789Z" level=error msg="container OOM killed"
_DAEMON_LINE = re.compile(
    r'time="([^"]+)"\s+level=(\w+)\s+msg="([^"]*)"(.*)'
)

# Additional k=v pairs on a daemon line (quoted or unquoted values)
_KV = re.compile(r'(\w+)=(?:"([^"]*)"|([^\s"]+))')

# Level keywords in plain text
_PLAIN_LEVEL = re.compile(
    r"\b(DEBUG|INFO|NOTICE|WARNING|WARN|ERROR|FATAL|CRITICAL|PANIC)\b", re.IGNORECASE
)

_DOCKER_KEYWORDS = [
    "docker daemon",
    "containerd",
    "runc",
    "OOM",
    "container_id",
    "time=",
    "level=",
    "msg=",
    "dockerd",
    "docker.io",
]


class DockerParser(BaseParser):
    """Parser for Docker container and daemon logs."""

    source = LogSource.DOCKER

    @classmethod
    def score_source(cls, lines: List[str]) -> float:
        sample = cls._sample(lines)
        hits = sum(
            1 for line in sample if any(kw.lower() in line.lower() for kw in _DOCKER_KEYWORDS)
        )
        # Also reward RFC3339 timestamps as first token
        rfc_hits = sum(1 for line in sample if _RFC3339.match(line))
        return min((hits + rfc_hits * 2) / max(len(sample), 1) * 5, 1.0)

    def parse(self, lines: List[str]) -> List[LogEvent]:
        events: List[LogEvent] = []

        for lineno, raw in enumerate(lines, start=1):
            line = raw.rstrip("\n\r")
            ts: Optional[datetime] = None
            level: Optional[str] = None
            message = line
            meta: dict = {}

            # --- Try daemon structured format ---
            daemon_match = _DAEMON_LINE.match(line)
            if daemon_match:
                ts = _parse_ts(daemon_match.group(1))
                level = daemon_match.group(2).upper()
                if level == "WARN":
                    level = "WARNING"
                message = daemon_match.group(3)
                # Parse remaining k=v pairs
                extras = daemon_match.group(4)
                for kv in _KV.finditer(extras):
                    # group(2) = quoted value, group(3) = unquoted value
                    meta[kv.group(1)] = kv.group(2) if kv.group(2) is not None else kv.group(3)
            else:
                # --- Try RFC 3339 prefix ---
                rfc_match = _RFC3339.match(line)
                if rfc_match:
                    ts = _parse_ts(rfc_match.group(1))
                    message = line[rfc_match.end():]

                # --- Plain level keyword ---
                lvl_match = _PLAIN_LEVEL.search(message)
                if lvl_match:
                    level = lvl_match.group(1).upper()
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


def _parse_ts(raw: str) -> Optional[datetime]:
    """Best-effort parse of a timestamp string."""
    raw = raw.rstrip("Z").replace("+00:00", "")
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            return datetime.strptime(raw[:26], fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None
