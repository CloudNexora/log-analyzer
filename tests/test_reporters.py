"""Unit tests for all reporters and the analysis engine."""

import json
import pytest
from pathlib import Path

from log_analyzer.engine import AnalysisEngine
from log_analyzer.models import AnalysisReport, Issue, LogEvent, LogSource, Severity, Category
from log_analyzer.reporters.json_reporter import JsonReporter
from log_analyzer.reporters.markdown_reporter import MarkdownReporter
from log_analyzer.reporters.html_reporter import HtmlReporter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_issue(
    title="Test Issue",
    severity=Severity.ERROR,
    category=Category.RUNTIME_ERROR,
    source=LogSource.GENERIC,
    line_number=10,
) -> Issue:
    event = LogEvent(
        line_number=line_number,
        raw=f"L{line_number}: some error happened\n",
        message="some error happened",
        source=source,
        level="ERROR",
    )
    return Issue(
        title=title,
        severity=severity,
        category=category,
        source=source,
        detector="TestDetector",
        pattern=r"error happened",
        events=[event],
        remediation=["Step 1: check logs", "Step 2: fix the issue"],
        references=["https://example.com/docs"],
    )


def make_report(issues=None) -> AnalysisReport:
    return AnalysisReport(
        file_path="/tmp/test.log",
        source=LogSource.GENERIC,
        issues=issues or [],
        total_lines=100,
    )


# ---------------------------------------------------------------------------
# JSON Reporter
# ---------------------------------------------------------------------------

class TestJsonReporter:
    def setup_method(self):
        self.reporter = JsonReporter()

    def test_renders_valid_json(self):
        report = make_report()
        output = self.reporter.render(report)
        data = json.loads(output)  # should not raise
        assert isinstance(data, dict)

    def test_includes_summary(self):
        report = make_report([make_issue()])
        data = json.loads(self.reporter.render(report))
        assert "summary" in data
        assert data["summary"]["total"] == 1

    def test_includes_issues(self):
        report = make_report([make_issue("My Error")])
        data = json.loads(self.reporter.render(report))
        assert len(data["issues"]) == 1
        assert data["issues"][0]["title"] == "My Error"

    def test_includes_remediation(self):
        report = make_report([make_issue()])
        data = json.loads(self.reporter.render(report))
        assert len(data["issues"][0]["remediation"]) == 2

    def test_includes_references(self):
        report = make_report([make_issue()])
        data = json.loads(self.reporter.render(report))
        assert "https://example.com/docs" in data["issues"][0]["references"]

    def test_empty_report(self):
        report = make_report()
        data = json.loads(self.reporter.render(report))
        assert data["summary"]["total"] == 0
        assert data["issues"] == []

    def test_severity_sorted(self):
        issues = [
            make_issue("Info Issue", severity=Severity.INFO),
            make_issue("Critical Issue", severity=Severity.CRITICAL),
            make_issue("Warning Issue", severity=Severity.WARNING),
        ]
        report = make_report(issues)
        data = json.loads(self.reporter.render(report))
        assert data["issues"][0]["severity"] == "CRITICAL"
        assert data["issues"][-1]["severity"] == "INFO"

    def test_write_to_directory(self, tmp_path):
        report = make_report()
        path = self.reporter.write(report, str(tmp_path))
        assert Path(path).exists()
        assert path.endswith(".json")


# ---------------------------------------------------------------------------
# Markdown Reporter
# ---------------------------------------------------------------------------

class TestMarkdownReporter:
    def setup_method(self):
        self.reporter = MarkdownReporter()

    def test_renders_string(self):
        report = make_report()
        output = self.reporter.render(report)
        assert isinstance(output, str)
        assert len(output) > 0

    def test_includes_header(self):
        report = make_report()
        output = self.reporter.render(report)
        assert "# 📊 Log Analysis Report" in output

    def test_includes_summary_table(self):
        report = make_report()
        output = self.reporter.render(report)
        assert "## 📈 Summary" in output

    def test_includes_issue_section(self):
        report = make_report([make_issue("My Critical Error", severity=Severity.CRITICAL)])
        output = self.reporter.render(report)
        assert "My Critical Error" in output
        assert "CRITICAL" in output

    def test_includes_remediation_steps(self):
        report = make_report([make_issue()])
        output = self.reporter.render(report)
        assert "Remediation Steps" in output
        assert "Step 1: check logs" in output

    def test_includes_references(self):
        report = make_report([make_issue()])
        output = self.reporter.render(report)
        assert "https://example.com/docs" in output

    def test_no_issues_message(self):
        report = make_report([])
        output = self.reporter.render(report)
        assert "No issues detected" in output

    def test_write_produces_md_file(self, tmp_path):
        report = make_report()
        path = self.reporter.write(report, str(tmp_path))
        assert path.endswith(".md")
        assert Path(path).read_text()


# ---------------------------------------------------------------------------
# HTML Reporter
# ---------------------------------------------------------------------------

class TestHtmlReporter:
    def setup_method(self):
        self.reporter = HtmlReporter()

    def test_renders_html(self):
        report = make_report()
        output = self.reporter.render(report)
        assert "<!DOCTYPE html>" in output
        assert "<html" in output

    def test_includes_issue_cards(self):
        report = make_report([make_issue("Dangerous Bug", severity=Severity.CRITICAL)])
        output = self.reporter.render(report)
        assert "Dangerous Bug" in output
        assert "CRITICAL" in output

    def test_includes_summary_counts(self):
        report = make_report([make_issue(severity=Severity.ERROR)])
        output = self.reporter.render(report)
        assert "1" in output  # error count

    def test_self_contained_no_cdn(self):
        report = make_report()
        output = self.reporter.render(report)
        # Ensure no external CDN URLs
        assert "cdn.jsdelivr.net" not in output
        assert "cdnjs.cloudflare.com" not in output
        assert "unpkg.com" not in output

    def test_escapes_html_in_log_context(self):
        event = LogEvent(
            line_number=1,
            raw="<script>alert('xss')</script>\n",
            message="<script>",
            source=LogSource.GENERIC,
        )
        issue = Issue(
            title="XSS Test",
            severity=Severity.ERROR,
            category=Category.SECURITY,
            source=LogSource.GENERIC,
            detector="Test",
            pattern="xss",
            events=[event],
        )
        report = make_report([issue])
        output = self.reporter.render(report)
        # The raw XSS payload must be HTML-escaped in the log context section
        assert "&lt;script&gt;alert" in output  # escaped version must appear
        # The dangerous unescaped payload (as XSS) must NOT appear as a literal inline script element
        # (the HTML has a legitimate <script> tag for JS, but not our payload)
        assert "alert('xss')</script>" not in output

    def test_write_produces_html_file(self, tmp_path):
        report = make_report()
        path = self.reporter.write(report, str(tmp_path))
        assert path.endswith(".html")


# ---------------------------------------------------------------------------
# Engine Integration Tests
# ---------------------------------------------------------------------------

class TestAnalysisEngine:
    def setup_method(self):
        self.engine = AnalysisEngine()

    def test_analyze_jenkins_log(self):
        sample_path = Path("sample_logs/jenkins_build.log")
        if not sample_path.exists():
            pytest.skip("Sample log not found")
        report = self.engine.analyze(sample_path, source="jenkins")
        assert report.total_lines > 0
        assert len(report.issues) > 0
        # Must detect build failure
        assert any("Build Failure" in i.title for i in report.issues)

    def test_analyze_docker_log(self):
        sample_path = Path("sample_logs/docker_daemon.log")
        if not sample_path.exists():
            pytest.skip("Sample log not found")
        report = self.engine.analyze(sample_path, source="docker")
        assert report.total_lines > 0
        assert len(report.issues) > 0

    def test_analyze_kubernetes_log(self):
        sample_path = Path("sample_logs/kubernetes_pod.log")
        if not sample_path.exists():
            pytest.skip("Sample log not found")
        report = self.engine.analyze(sample_path, source="kubernetes")
        assert report.total_lines > 0
        assert any(
            "CrashLoop" in i.title or "OOM" in i.title or "Image Pull" in i.title
            for i in report.issues
        )

    def test_analyze_generic_log(self):
        sample_path = Path("sample_logs/generic_syslog.log")
        if not sample_path.exists():
            pytest.skip("Sample log not found")
        report = self.engine.analyze(sample_path, source="generic")
        assert report.total_lines > 0
        assert len(report.issues) > 0

    def test_auto_detect_source(self):
        sample_path = Path("sample_logs/jenkins_build.log")
        if not sample_path.exists():
            pytest.skip("Sample log not found")
        report = self.engine.analyze(sample_path, source="auto")
        assert report.source == LogSource.JENKINS

    def test_report_writes_all_formats(self, tmp_path):
        sample_path = Path("sample_logs/generic_syslog.log")
        if not sample_path.exists():
            pytest.skip("Sample log not found")
        report = self.engine.analyze(sample_path, source="generic")
        written = self.engine.report(report, formats=["json", "markdown", "html"], output_dir=str(tmp_path))
        assert len(written) == 3
        for path in written:
            assert Path(path).exists()
            assert Path(path).stat().st_size > 0

    def test_report_raises_on_unknown_format(self):
        report = make_report()
        with pytest.raises(ValueError, match="Unknown format"):
            self.engine.report(report, formats=["xml"])

    def test_analyze_directory(self):
        sample_dir = Path("sample_logs")
        if not sample_dir.exists():
            pytest.skip("sample_logs directory not found")
        report = self.engine.analyze(sample_dir, source="auto")
        assert report.total_lines > 0
