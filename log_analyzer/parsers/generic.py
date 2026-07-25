"""
Generic / fallback log parser.

Handles a wide variety of common plaintext log formats:
  - Syslog:  ``Jan 15 10:22:05 hostname process[pid]: message``
  - Apache/Nginx combined/error log
  - Python logging: ``2024-01-15 10:22:05,123 - name - LEVEL - message``
  - Log4j/Logback: ``2024-01-15 10:22:05.123 [thread] LEVEL  class - message``
  - Plain lines with no structure (pass-through)
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import List, Optional

from log_analyzer.models import LogEvent, LogSource
from log_analyzer.parsers.base import BaseParser

# ---------------------------------------------------------------------------
# Patterns (ordered most-specific → least-specific)
# ---------------------------------------------------------------------------

_PATTERNS = [
    # Python logging / Log4j ISO timestamp with embedded level
    # 2024-01-15 10:22:05,123 - root - ERROR - message
    # 2024-01-15 10:22:05.123 [main] ERROR  c.e.App - message
    (
        re.compile(
            r"^(\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2}[.,]\d+)"
            r".{0,60}?\b(DEBUG|INFO|NOTICE|WARNING|WARN|ERROR|CRITICAL|FATAL|SEVERE)\b"
            r"[^\n]*",
            re.IGNORECASE,
        ),
        "%Y-%m-%d %H:%M:%S",
        True,   # has_level group
    ),
    # Syslog: Jan 15 10:22:05 hostname process[pid]: message  (no explicit level)
    (
        re.compile(
            r"^([A-Za-z]{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+\S+\s+\S+:\s+(.*)"
        ),
        "%b %d %H:%M:%S",
        False,  # no level group — level comes from bare-keyword scan below
    ),
    # Apache/Nginx error: [Tue Jan 15 10:22:05.123456 2024] [level]
    (
        re.compile(
            r"^\[(\w{3}\s+\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?\s+\d{4})\]"
            r"\s+\[(\w+)\]"
        ),
        "%a %b %d %H:%M:%S %Y",
        True,   # has_level group
    ),
    # ISO date-only prefix with level keyword (RFC 3339 — fallback)
    (
        re.compile(
            r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)"
            r".*\b(DEBUG|INFO|NOTICE|WARNING|WARN|ERROR|CRITICAL|FATAL|SEVERE)\b",
            re.IGNORECASE,
        ),
        "%Y-%m-%dT%H:%M:%S",
        True,   # has_level group
    ),
]

# Bare level keyword (last resort)
_BARE_LEVEL = re.compile(
    r"\b(DEBUG|INFO|NOTICE|WARNING|WARN|ERROR|CRITICAL|FATAL|SEVERE|PANIC)\b",
    re.IGNORECASE,
)

_LEVEL_ALIASES = {"WARN": "WARNING", "SEVERE": "ERROR", "FATAL": "CRITICAL", "PANIC": "CRITICAL"}


class GenericParser(BaseParser):
    """Fallback parser for syslog, Python logging, Log4j, Apache, etc."""

    source = LogSource.GENERIC

    @classmethod
    def score_source(cls, lines: List[str]) -> float:
        """Generic is always an option — return a low base score."""
        return 0.1

    def parse(self, lines: List[str]) -> List[LogEvent]:
        events: List[LogEvent] = []

        for lineno, raw in enumerate(lines, start=1):
            line = raw.rstrip("\n\r")
            ts: Optional[datetime] = None
            level: Optional[str] = None
            message = line

            # Try structured patterns first
            for pattern, ts_fmt, has_level in _PATTERNS:
                m = pattern.match(line)
                if m:
                    ts_str = m.group(1)
                    # Normalise various separator styles
                    ts_str = ts_str.replace("T", " ").replace(",", ".").rstrip("Z")
                    ts_str = ts_str[:19]  # trim microseconds for strptime
                    try:
                        ts = datetime.strptime(ts_str, ts_fmt)
                    except ValueError:
                        pass
                    # Level is group(2) only if this pattern explicitly captures it
                    if has_level and m.lastindex and m.lastindex >= 2:
                        raw_level = m.group(2).upper()
                        level = _LEVEL_ALIASES.get(raw_level, raw_level)
                    break

            # Fall back to bare level keyword scan on the full line
            if level is None:
                bare_m = _BARE_LEVEL.search(line)
                if bare_m:
                    raw_level = bare_m.group(1).upper()
                    level = _LEVEL_ALIASES.get(raw_level, raw_level)

            events.append(
                LogEvent(
                    line_number=lineno,
                    raw=raw,
                    message=message.strip(),
                    source=self.source,
                    timestamp=ts,
                    level=level,
                    metadata={},
                )
            )

        return events
