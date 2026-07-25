"""
Jenkins build log parser.

Handles the classic Jenkins console output format, including:
  - Timestamped lines:  ``HH:MM:SS  <message>``
  - Stage markers:      ``[Pipeline] { (Stage Name)``
  - Maven/Gradle output with [ERROR] / [WARNING] / [INFO] prefixes
  - BUILD FAILURE / BUILD SUCCESS banners
  - Test result summary lines
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import List, Optional

from log_analyzer.models import LogEvent, LogSource
from log_analyzer.parsers.base import BaseParser

# ---------------------------------------------------------------------------
# Compiled patterns (module-level for performance)
# ---------------------------------------------------------------------------

# 09:14:03  or  09:14:03.123
_TS_PREFIX = re.compile(r"^(\d{2}:\d{2}:\d{2}(?:\.\d+)?)\s+")

# [INFO], [WARNING], [ERROR], [DEBUG]
_LEVEL_BRACKET = re.compile(r"\[(INFO|WARNING|WARN|ERROR|DEBUG|FATAL)\]", re.IGNORECASE)

# Pipeline stage markers
_STAGE_MARKER = re.compile(r"^\[Pipeline\].*?\((.+?)\)\s*$")

# Build result
_BUILD_RESULT = re.compile(
    r"^(BUILD\s+(?:SUCCESS|FAILURE|UNSTABLE|ABORTED))\s*$", re.IGNORECASE
)

# Test results  e.g.  Tests run: 42, Failures: 2, Errors: 0
_TEST_RESULT = re.compile(
    r"Tests\s+run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+)", re.IGNORECASE
)

# Signature keywords indicating Jenkins format
_JENKINS_KEYWORDS = [
    "BUILD SUCCESS",
    "BUILD FAILURE",
    "[Pipeline]",
    "Started by user",
    "Finished: SUCCESS",
    "Finished: FAILURE",
    "hudson.plugins",
    "jenkins.model",
]


class JenkinsParser(BaseParser):
    """Parser for Jenkins console log output."""

    source = LogSource.JENKINS

    # ------------------------------------------------------------------
    # Auto-detection
    # ------------------------------------------------------------------

    @classmethod
    def score_source(cls, lines: List[str]) -> float:
        sample = cls._sample(lines)
        hits = sum(
            1 for line in sample if any(kw in line for kw in _JENKINS_KEYWORDS)
        )
        return min(hits / max(len(sample), 1) * 10, 1.0)

    # ------------------------------------------------------------------
    # Parse
    # ------------------------------------------------------------------

    def parse(self, lines: List[str]) -> List[LogEvent]:
        events: List[LogEvent] = []
        current_stage: Optional[str] = None

        for lineno, raw in enumerate(lines, start=1):
            line = raw.rstrip("\n\r")

            # --- Extract timestamp ---
            ts: Optional[datetime] = None
            ts_match = _TS_PREFIX.match(line)
            if ts_match:
                try:
                    ts = datetime.strptime(ts_match.group(1), "%H:%M:%S")
                except ValueError:
                    pass
                message = line[ts_match.end():]
            else:
                message = line

            # --- Extract log level ---
            level: Optional[str] = None
            level_match = _LEVEL_BRACKET.search(message)
            if level_match:
                level = level_match.group(1).upper()
                if level == "WARN":
                    level = "WARNING"

            # --- Detect build result ---
            build_match = _BUILD_RESULT.match(message.strip())
            if build_match:
                level = "ERROR" if "FAIL" in build_match.group(1).upper() else "INFO"

            # --- Detect stage ---
            stage_match = _STAGE_MARKER.match(message)
            if stage_match:
                current_stage = stage_match.group(1)
                level = level or "INFO"

            # --- Detect test failures ---
            test_match = _TEST_RESULT.search(message)
            meta: dict = {}
            if current_stage:
                meta["stage"] = current_stage
            if test_match:
                meta["tests_run"] = int(test_match.group(1))
                meta["failures"] = int(test_match.group(2))
                meta["test_errors"] = int(test_match.group(3))
                if meta["failures"] > 0 or meta["test_errors"] > 0:
                    level = "ERROR"

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
