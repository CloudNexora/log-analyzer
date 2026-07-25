"""
FastAPI route handlers for the Log Analyzer API.

All business logic lives in log_analyzer.engine — these handlers are thin
wrappers that handle HTTP concerns (file upload, query params, responses).
"""

from __future__ import annotations

import tempfile
import os
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, Response

from log_analyzer.engine import AnalysisEngine
from log_analyzer.models import AnalysisReport, Issue, LogSource, Severity
from log_analyzer.parsers import PARSER_REGISTRY
from log_analyzer.reporters import REPORTER_REGISTRY
from log_analyzer.api.schemas import (
    ErrorOut,
    IssueOut,
    ReportListItem,
    ReportOut,
    SummaryOut,
)
from log_analyzer.api.storage import store

router = APIRouter()
_engine = AnalysisEngine()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SEVERITY_ORDER = {s.value: s.order for s in Severity}

def _issue_to_out(issue: Issue) -> IssueOut:
    return IssueOut(
        id=issue.id,
        title=issue.title,
        severity=issue.severity.value,
        category=issue.category.value,
        source=issue.source.value,
        detector=issue.detector,
        pattern=issue.pattern,
        line_numbers=issue.line_numbers,
        context=[e.raw.rstrip() for e in issue.events[:8]],
        remediation=issue.remediation,
        references=issue.references,
        extra=issue.extra,
    )


def _report_to_out(report: AnalysisReport, report_id: str, filename: str) -> ReportOut:
    return ReportOut(
        id=report_id,
        file_name=filename,
        source=report.source.value,
        analyzed_at=report.analyzed_at,
        total_lines=report.total_lines,
        summary=SummaryOut(**report.summary),
        issues=[_issue_to_out(i) for i in report.sorted_issues],
    )


def _report_to_list_item(report: AnalysisReport, report_id: str, filename: str) -> ReportListItem:
    return ReportListItem(
        id=report_id,
        file_name=filename,
        source=report.source.value,
        analyzed_at=report.analyzed_at,
        total_lines=report.total_lines,
        summary=SummaryOut(**report.summary),
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get(
    "/health",
    summary="Health Check",
    tags=["System"],
    response_description="Service status",
)
def health():
    """
    Returns `200 OK` when the service is running.

    Use this endpoint for load-balancer health probes or readiness checks.
    """
    return {
        "status": "ok",
        "service": "log-analyzer",
        "version": "1.0.0",
        "reports_stored": len(store),
    }


@router.get(
    "/sources",
    summary="List Log Sources",
    tags=["Discovery"],
    response_description="Available log parser names",
)
def list_sources():
    """
    Returns all supported log source parsers.

    Pass one of these values as the `source` parameter when calling `/analyze`.
    Use `auto` to let the engine detect the source automatically.
    """
    descriptions = {
        "jenkins": "Jenkins build console output (timestamped lines, stages, Maven/Gradle)",
        "docker":  "Docker container logs and daemon logs (json-file driver, structured)",
        "kubernetes": "kubectl logs, kubectl events, klog format (control-plane components)",
        "generic": "Syslog, Python logging, Log4j, Apache — generic plaintext fallback",
    }
    return {
        "sources": [
            {
                "name": key,
                "parser": cls.__name__,
                "description": descriptions.get(key, ""),
            }
            for key, cls in PARSER_REGISTRY.items()
        ],
        "tip": "Use 'auto' to let the engine pick the best parser automatically.",
    }


@router.get(
    "/formats",
    summary="List Report Formats",
    tags=["Discovery"],
    response_description="Available output format names",
)
def list_formats():
    """
    Returns all supported report output formats.

    Pass one of these values as the `format` query parameter when calling
    `/reports/{id}/download`.
    """
    descriptions = {
        "json":     "Machine-readable JSON with full issue details",
        "markdown": "Human-readable Markdown with tables and code blocks",
        "md":       "Alias for markdown",
        "html":     "Interactive dark-mode HTML dashboard with charts and collapsible cards",
    }
    return {
        "formats": [
            {
                "name": key,
                "extension": f".{cls.extension}",
                "description": descriptions.get(key, ""),
            }
            for key, cls in REPORTER_REGISTRY.items()
        ]
    }


@router.post(
    "/analyze",
    summary="Analyze a Log File",
    tags=["Analysis"],
    response_model=ReportOut,
    responses={
        200: {"description": "Analysis complete — returns detected issues and remediation steps."},
        400: {"model": ErrorOut, "description": "Invalid source or file."},
        422: {"description": "Validation error."},
    },
)
async def analyze(
    file: UploadFile = File(..., description="Log file to analyze (any text format)"),
    source: str = Form(
        default="auto",
        description="Log source type: auto | jenkins | docker | kubernetes | generic",
    ),
    min_severity: str = Form(
        default="INFO",
        description="Minimum severity to include: INFO | WARNING | ERROR | CRITICAL",
    ),
):
    """
    Upload a log file and receive a structured analysis report.

    ### How it works
    1. The uploaded file is saved to a temporary location.
    2. The `AnalysisEngine` selects the appropriate parser (or auto-detects).
    3. All detectors run across the parsed events.
    4. The report is stored in memory and returned as JSON.

    ### Tip
    Use `GET /reports/{id}/download?format=html` to get the rich interactive
    HTML dashboard version of the same report.
    """
    # Validate source
    valid_sources = list(PARSER_REGISTRY.keys()) + ["auto"]
    if source.lower() not in valid_sources:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid source '{source}'. Valid options: {valid_sources}",
        )

    # Validate min_severity
    valid_severities = [s.value for s in Severity]
    if min_severity.upper() not in valid_severities:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid min_severity '{min_severity}'. Valid options: {valid_severities}",
        )

    # Save upload to a temp file
    suffix = Path(file.filename or "upload.log").suffix or ".log"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        report = _engine.analyze(tmp_path, source=source.lower())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Analysis failed: {exc}")
    finally:
        os.unlink(tmp_path)

    # Apply min-severity filter
    min_sev = Severity(min_severity.upper())
    report.issues = [i for i in report.issues if i.severity >= min_sev]

    # Persist and return
    filename = file.filename or "upload.log"
    report_id = store.save(report, filename)
    return _report_to_out(report, report_id, filename)


@router.get(
    "/reports",
    summary="List All Reports",
    tags=["Reports"],
    response_model=List[ReportListItem],
)
def list_reports():
    """
    Returns a lightweight summary of all analysis runs stored in memory.

    Use `GET /reports/{id}` to retrieve the full report with all issues.
    """
    all_reports = store.list_all()
    return [
        _report_to_list_item(report, rid, filename)
        for rid, (report, filename) in sorted(
            all_reports.items(),
            key=lambda x: x[1][0].analyzed_at,
            reverse=True,
        )
    ]


@router.get(
    "/reports/{report_id}",
    summary="Get Report by ID",
    tags=["Reports"],
    response_model=ReportOut,
    responses={
        404: {"model": ErrorOut, "description": "Report not found."},
    },
)
def get_report(report_id: str):
    """
    Retrieve the full analysis report (with all issues and remediation steps)
    for the given `report_id`.

    The `report_id` is returned by `POST /analyze`.
    """
    entry = store.get(report_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found.")
    report, filename = entry
    return _report_to_out(report, report_id, filename)


@router.get(
    "/reports/{report_id}/download",
    summary="Download Report",
    tags=["Reports"],
    responses={
        200: {"description": "Report file content."},
        400: {"model": ErrorOut, "description": "Invalid format."},
        404: {"model": ErrorOut, "description": "Report not found."},
    },
)
def download_report(
    report_id: str,
    format: str = Query(
        default="html",
        description="Output format: html | markdown | json",
    ),
):
    """
    Download a previously analyzed report as **HTML**, **Markdown**, or **JSON**.

    | Format | Content-Type | Best for |
    |---|---|---|
    | `html` | text/html | Viewing in a browser |
    | `markdown` | text/markdown | Docs, GitHub PRs, Slack |
    | `json` | application/json | Programmatic processing |

    ### Example
    ```
    GET /reports/abc-123/download?format=html
    ```
    """
    entry = store.get(report_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found.")

    report, filename = entry
    fmt = format.lower().strip()

    reporter_cls = REPORTER_REGISTRY.get(fmt)
    if not reporter_cls:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid format '{fmt}'. Valid options: {list(REPORTER_REGISTRY.keys())}",
        )

    content = reporter_cls().render(report)

    content_type_map = {
        "html": "text/html; charset=utf-8",
        "markdown": "text/markdown; charset=utf-8",
        "md": "text/markdown; charset=utf-8",
        "json": "application/json",
    }
    content_type = content_type_map.get(fmt, "text/plain")
    stem = Path(filename).stem
    ext = reporter_cls.extension
    disposition = f'attachment; filename="{stem}_report.{ext}"'

    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": disposition},
    )


@router.delete(
    "/reports/{report_id}",
    summary="Delete Report",
    tags=["Reports"],
    responses={
        200: {"description": "Report deleted."},
        404: {"model": ErrorOut, "description": "Report not found."},
    },
)
def delete_report(report_id: str):
    """Delete a specific report from the in-memory store."""
    deleted = store.delete(report_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found.")
    return {"deleted": report_id, "status": "ok"}
