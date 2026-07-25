"""JSON reporter — outputs machine-readable JSON."""

from __future__ import annotations

import json

from log_analyzer.models import AnalysisReport
from log_analyzer.reporters.base import BaseReporter


class JsonReporter(BaseReporter):
    """Serialises the analysis report to pretty-printed JSON."""

    extension = "json"

    def __init__(self, indent: int = 2) -> None:
        self.indent = indent

    def render(self, report: AnalysisReport) -> str:
        return json.dumps(report.to_dict(), indent=self.indent, default=str)
