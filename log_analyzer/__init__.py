"""
Log Analyzer — A modular log analysis tool for DevOps pipelines.

Supports Jenkins, Docker, Kubernetes, and generic log sources.
"""

__version__ = "1.0.0"
__author__ = "Log Analyzer Team"

from .engine import AnalysisEngine
from .models import AnalysisReport, Issue, LogEvent, Severity

__all__ = ["AnalysisEngine", "AnalysisReport", "Issue", "LogEvent", "Severity"]
