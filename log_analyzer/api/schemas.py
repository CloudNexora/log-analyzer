"""
Pydantic schemas for API request/response bodies.

All models are JSON-serialisable and independent of internal dataclasses
so the HTTP layer stays decoupled from the core engine.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Issue schemas
# ---------------------------------------------------------------------------

class IssueContext(BaseModel):
    line_number: int
    raw: str


class IssueOut(BaseModel):
    id: str
    title: str
    severity: str
    category: str
    source: str
    detector: str
    pattern: str
    line_numbers: List[int]
    context: List[str] = Field(description="Raw log lines that triggered this issue")
    remediation: List[str]
    references: List[str]
    extra: Dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Report schemas
# ---------------------------------------------------------------------------

class SummaryOut(BaseModel):
    total: int
    critical: int
    error: int
    warning: int
    info: int


class ReportOut(BaseModel):
    id: str
    file_name: str
    source: str
    analyzed_at: datetime
    total_lines: int
    summary: SummaryOut
    issues: List[IssueOut]


class ReportListItem(BaseModel):
    id: str
    file_name: str
    source: str
    analyzed_at: datetime
    total_lines: int
    summary: SummaryOut


# ---------------------------------------------------------------------------
# Error schema
# ---------------------------------------------------------------------------

class ErrorOut(BaseModel):
    detail: str
