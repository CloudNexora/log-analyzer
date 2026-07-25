"""Detectors sub-package."""

from .base import BaseDetector
from .error_detector import ErrorDetector
from .performance_detector import PerformanceDetector
from .warning_detector import WarningDetector

__all__ = [
    "BaseDetector",
    "ErrorDetector",
    "WarningDetector",
    "PerformanceDetector",
]

ALL_DETECTORS = [ErrorDetector, WarningDetector, PerformanceDetector]
