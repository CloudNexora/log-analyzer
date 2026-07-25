"""
Base reporter interface.

Reporters consume an :class:`~log_analyzer.models.AnalysisReport` and write
output to a file or return a string.
"""

from __future__ import annotations

import abc
import os
from pathlib import Path
from typing import Optional

from log_analyzer.models import AnalysisReport


class BaseReporter(abc.ABC):
    """Abstract base class for all reporters."""

    #: File extension produced by this reporter (without leading dot)
    extension: str = "txt"

    @abc.abstractmethod
    def render(self, report: AnalysisReport) -> str:
        """Render *report* to a string."""

    def write(self, report: AnalysisReport, output_path: Optional[str] = None) -> str:
        """
        Render and write *report* to *output_path*.

        If *output_path* is a directory, a filename is generated automatically.
        Returns the absolute path of the written file.
        """
        content = self.render(report)

        if output_path is None:
            output_path = "."

        path = Path(output_path)

        if path.is_dir() or not path.suffix:
            # Generate a filename inside the directory
            base = Path(report.file_path).stem if report.file_path else "report"
            path = path / f"{base}_report.{self.extension}"

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return str(path.resolve())
