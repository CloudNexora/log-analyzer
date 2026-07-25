"""
Analysis Engine — orchestrates the parse → detect → report pipeline.

Usage::

    engine = AnalysisEngine()
    report = engine.analyze("path/to/app.log", source="auto")
    engine.report(report, formats=["html", "json"], output_dir="reports/")
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional, Union

from log_analyzer.detectors import ALL_DETECTORS
from log_analyzer.models import AnalysisReport, LogSource
from log_analyzer.parsers import PARSER_REGISTRY, GenericParser
from log_analyzer.parsers.base import BaseParser
from log_analyzer.reporters import REPORTER_REGISTRY


class AnalysisEngine:
    """
    Orchestrates the full log analysis pipeline:

    1. **Auto-detect or select** the appropriate parser for the log source.
    2. **Parse** raw lines into :class:`~log_analyzer.models.LogEvent` objects.
    3. **Run detectors** in sequence to produce :class:`~log_analyzer.models.Issue` objects.
    4. **Collect** results into an :class:`~log_analyzer.models.AnalysisReport`.
    """

    def __init__(self) -> None:
        self._detectors = [cls() for cls in ALL_DETECTORS]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self,
        log_path: Union[str, Path],
        source: Union[str, LogSource] = LogSource.AUTO,
    ) -> AnalysisReport:
        """
        Analyse a log file (or directory of log files).

        Args:
            log_path: Path to a log file or directory.
            source:   Log source type or ``"auto"`` for auto-detection.

        Returns:
            An :class:`~log_analyzer.models.AnalysisReport` with all findings.
        """
        log_path = Path(log_path)

        if log_path.is_dir():
            return self._analyze_directory(log_path, source)
        else:
            return self._analyze_file(log_path, source)

    def report(
        self,
        analysis: AnalysisReport,
        formats: Optional[List[str]] = None,
        output_dir: Optional[str] = None,
    ) -> List[str]:
        """
        Write reports for *analysis* in the requested *formats*.

        Args:
            analysis:   The report to render.
            formats:    List of format names: ``["json", "markdown", "html"]``.
                        Defaults to ``["html", "json", "markdown"]``.
            output_dir: Directory to write files into.

        Returns:
            List of absolute file paths that were written.
        """
        if formats is None:
            formats = ["html", "json", "markdown"]

        written: List[str] = []
        for fmt in formats:
            fmt_lower = fmt.lower().strip()
            reporter_cls = REPORTER_REGISTRY.get(fmt_lower)
            if reporter_cls is None:
                raise ValueError(
                    f"Unknown format '{fmt}'. "
                    f"Available: {list(REPORTER_REGISTRY.keys())}"
                )
            reporter = reporter_cls()
            out = reporter.write(analysis, output_dir)
            written.append(out)

        return written

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _analyze_file(
        self, path: Path, source: Union[str, LogSource]
    ) -> AnalysisReport:
        lines = _read_lines(path)
        parser = self._select_parser(lines, source)
        events = parser.parse(lines)

        issues = []
        for detector in self._detectors:
            issues.extend(detector.detect(events))

        return AnalysisReport(
            file_path=str(path),
            source=parser.source,
            issues=issues,
            total_lines=len(lines),
            metadata={"parser": type(parser).__name__},
        )

    def _analyze_directory(
        self, directory: Path, source: Union[str, LogSource]
    ) -> AnalysisReport:
        """Merge analysis of all log files inside a directory."""
        all_issues = []
        total_lines = 0
        file_sources = []

        log_files = [
            f for f in sorted(directory.rglob("*"))
            if f.is_file() and f.suffix in (".log", ".txt", ".out", "")
        ]

        if not log_files:
            # Accept any file if no .log files found
            log_files = [f for f in sorted(directory.rglob("*")) if f.is_file()]

        for log_file in log_files:
            try:
                sub = self._analyze_file(log_file, source)
                all_issues.extend(sub.issues)
                total_lines += sub.total_lines
                file_sources.append(sub.source.value)
            except Exception:
                pass

        dominant_source = _most_common(file_sources) if file_sources else "generic"

        return AnalysisReport(
            file_path=str(directory),
            source=LogSource(dominant_source),
            issues=all_issues,
            total_lines=total_lines,
            metadata={"files_analyzed": len(log_files)},
        )

    def _select_parser(
        self, lines: List[str], source: Union[str, LogSource]
    ) -> BaseParser:
        source_str = source.value if isinstance(source, LogSource) else str(source).lower()

        if source_str != "auto" and source_str in PARSER_REGISTRY:
            return PARSER_REGISTRY[source_str]()

        # Auto-detect: score every parser and pick the best
        best_score = -1.0
        best_cls = GenericParser
        for cls in PARSER_REGISTRY.values():
            score = cls.score_source(lines)
            if score > best_score:
                best_score = score
                best_cls = cls

        return best_cls()


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _read_lines(path: Path) -> List[str]:
    """Read a file, trying UTF-8 then latin-1 as fallback."""
    try:
        return path.read_text(encoding="utf-8").splitlines(keepends=True)
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1").splitlines(keepends=True)


def _most_common(lst: List[str]) -> str:
    return max(set(lst), key=lst.count)
