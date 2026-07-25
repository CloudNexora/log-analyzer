"""Reporters sub-package."""

from .base import BaseReporter
from .html_reporter import HtmlReporter
from .json_reporter import JsonReporter
from .markdown_reporter import MarkdownReporter

__all__ = ["BaseReporter", "JsonReporter", "MarkdownReporter", "HtmlReporter"]

REPORTER_REGISTRY = {
    "json": JsonReporter,
    "markdown": MarkdownReporter,
    "md": MarkdownReporter,
    "html": HtmlReporter,
}
