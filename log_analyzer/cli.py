"""
CLI entry point for the Log Analyzer.

Usage examples::

    log-analyzer analyze sample_logs/jenkins_build.log
    log-analyzer analyze sample_logs/ --source auto --format all --output reports/
    log-analyzer analyze app.log --source docker --format html --output ./report.html
    log-analyzer list-sources
    log-analyzer list-formats
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional, Tuple

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich import box

from log_analyzer.engine import AnalysisEngine
from log_analyzer.models import LogSource, Severity
from log_analyzer.parsers import PARSER_REGISTRY
from log_analyzer.reporters import REPORTER_REGISTRY

console = Console()

_SEVERITY_STYLE = {
    Severity.CRITICAL: "bold red",
    Severity.ERROR: "bold yellow",
    Severity.WARNING: "yellow",
    Severity.INFO: "cyan",
}

_FORMAT_CHOICES = list(REPORTER_REGISTRY.keys()) + ["all"]
_SOURCE_CHOICES = [s.value for s in LogSource]


# ---------------------------------------------------------------------------
# Main group
# ---------------------------------------------------------------------------

@click.group()
@click.version_option("1.0.0", prog_name="log-analyzer")
def main():
    """
    \b
    🔍 Log Analyzer — Modular log analysis for DevOps pipelines.

    Supports Jenkins, Docker, Kubernetes, and generic log sources.
    Detects errors, warnings, and performance issues with remediation steps.
    """


# ---------------------------------------------------------------------------
# analyze command
# ---------------------------------------------------------------------------

@main.command()
@click.argument("log_path", type=click.Path(exists=True))
@click.option(
    "--source", "-s",
    type=click.Choice(_SOURCE_CHOICES, case_sensitive=False),
    default="auto",
    show_default=True,
    help="Log source type. Use 'auto' to detect automatically.",
)
@click.option(
    "--format", "-f", "fmt",
    type=click.Choice(_FORMAT_CHOICES, case_sensitive=False),
    default="all",
    show_default=True,
    help="Output report format.",
)
@click.option(
    "--output", "-o",
    default="reports",
    show_default=True,
    help="Output file path or directory.",
)
@click.option(
    "--min-severity",
    type=click.Choice(["INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False),
    default="INFO",
    show_default=True,
    help="Minimum severity level to include in reports.",
)
@click.option("--quiet", "-q", is_flag=True, help="Suppress console output.")
def analyze(
    log_path: str,
    source: str,
    fmt: str,
    output: str,
    min_severity: str,
    quiet: bool,
):
    """Analyse LOG_PATH (file or directory) and generate a report."""

    if not quiet:
        console.print(
            Panel.fit(
                f"[bold cyan]Log Analyzer[/bold cyan] [dim]v1.0.0[/dim]\n"
                f"[dim]Analyzing:[/dim] [bold]{log_path}[/bold]\n"
                f"[dim]Source:[/dim] {source}  [dim]Format:[/dim] {fmt}",
                border_style="cyan",
            )
        )

    engine = AnalysisEngine()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        disable=quiet,
        transient=True,
    ) as progress:
        task = progress.add_task("Parsing log file(s)...", total=None)
        report = engine.analyze(log_path, source=source)
        progress.update(task, description="Running detectors...")

        # Apply min-severity filter
        min_sev = Severity(min_severity.upper())
        report.issues = [i for i in report.issues if i.severity >= min_sev]

        progress.update(task, description="Generating reports...")

        formats = list(REPORTER_REGISTRY.keys()) if fmt == "all" else [fmt]
        written = engine.report(report, formats=formats, output_dir=output)

    if not quiet:
        _print_summary(report)
        _print_written_files(written)

    # Exit with non-zero if critical or error issues found
    if report.criticals or report.errors:
        sys.exit(1)


# ---------------------------------------------------------------------------
# list-sources command
# ---------------------------------------------------------------------------

@main.command("list-sources")
def list_sources():
    """List all available log source parsers."""
    table = Table(title="Available Log Sources", box=box.ROUNDED, border_style="cyan")
    table.add_column("Source", style="bold")
    table.add_column("Parser Class")
    table.add_column("Description")

    descriptions = {
        "jenkins": "Jenkins build console output (timestamped, stages, Maven/Gradle)",
        "docker": "Docker container logs and daemon logs (json-file driver, structured)",
        "kubernetes": "kubectl logs, kubectl events, klog format (control-plane components)",
        "generic": "Syslog, Python logging, Log4j, Apache — generic plaintext fallback",
    }

    for key, cls in PARSER_REGISTRY.items():
        table.add_row(key, cls.__name__, descriptions.get(key, ""))

    console.print(table)


# ---------------------------------------------------------------------------
# list-formats command
# ---------------------------------------------------------------------------

@main.command("list-formats")
def list_formats():
    """List all available report output formats."""
    table = Table(title="Available Report Formats", box=box.ROUNDED, border_style="cyan")
    table.add_column("Format", style="bold")
    table.add_column("Extension")
    table.add_column("Description")

    descs = {
        "json": "Machine-readable JSON with full issue details",
        "markdown": "Human-readable Markdown with tables and code blocks",
        "md": "Alias for markdown",
        "html": "Interactive dark-mode HTML report with charts and collapsible cards",
        "all": "Generate all formats simultaneously",
    }

    for key, cls in REPORTER_REGISTRY.items():
        table.add_row(key, f".{cls.extension}", descs.get(key, ""))

    console.print(table)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print_summary(report) -> None:
    s = report.summary

    table = Table(title="Analysis Summary", box=box.ROUNDED, border_style="dim")
    table.add_column("Metric", style="dim")
    table.add_column("Value", justify="right")

    table.add_row("File", report.file_path)
    table.add_row("Source", report.source.value.title())
    table.add_row("Lines Processed", f"{report.total_lines:,}")
    table.add_section()
    table.add_row("🔴 Critical", f"[bold red]{s['critical']}[/bold red]")
    table.add_row("🟠 Error", f"[bold yellow]{s['error']}[/bold yellow]")
    table.add_row("🟡 Warning", f"[yellow]{s['warning']}[/yellow]")
    table.add_row("🔵 Info", f"[cyan]{s['info']}[/cyan]")
    table.add_section()
    table.add_row("Total Issues", f"[bold]{s['total']}[/bold]")

    console.print()
    console.print(table)

    if report.sorted_issues:
        console.print()
        issues_table = Table(
            title="Top Issues", box=box.SIMPLE, border_style="dim",
            show_lines=True,
        )
        issues_table.add_column("Sev", width=10)
        issues_table.add_column("Title")
        issues_table.add_column("Line(s)", justify="right", width=12)
        issues_table.add_column("Category", width=18)

        for issue in report.sorted_issues[:10]:
            style = _SEVERITY_STYLE.get(issue.severity, "")
            lines = ", ".join(str(n) for n in issue.line_numbers[:3])
            if len(issue.line_numbers) > 3:
                lines += "…"
            issues_table.add_row(
                f"[{style}]{issue.severity.value}[/{style}]",
                issue.title,
                lines,
                issue.category.value,
            )

        if len(report.sorted_issues) > 10:
            console.print(f"  [dim]…and {len(report.sorted_issues) - 10} more issues[/dim]")

        console.print(issues_table)


def _print_written_files(paths) -> None:
    console.print()
    console.print("[bold green]✅ Reports written:[/bold green]")
    for p in paths:
        console.print(f"   [link=file://{p}]{p}[/link]")


if __name__ == "__main__":
    main()
