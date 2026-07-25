"""Unit tests for all detectors."""

import pytest
from log_analyzer.detectors.error_detector import ErrorDetector
from log_analyzer.detectors.warning_detector import WarningDetector
from log_analyzer.detectors.performance_detector import PerformanceDetector
from log_analyzer.models import LogEvent, LogSource, Severity, Category


def make_event(line_number: int, raw: str, level: str = None) -> LogEvent:
    return LogEvent(
        line_number=line_number,
        raw=raw,
        message=raw.strip(),
        source=LogSource.GENERIC,
        level=level,
    )


# ---------------------------------------------------------------------------
# ErrorDetector
# ---------------------------------------------------------------------------

class TestErrorDetector:
    def setup_method(self):
        self.detector = ErrorDetector()

    def test_detects_build_failure(self):
        events = [make_event(1, "09:14:21  BUILD FAILURE")]
        issues = self.detector.detect(events)
        titles = [i.title for i in issues]
        assert any("Build Failure" in t for t in titles)

    def test_detects_test_failure(self):
        events = [make_event(1, "Tests run: 47, Failures: 3, Errors: 1")]
        issues = self.detector.detect(events)
        titles = [i.title for i in issues]
        assert any("Test Failure" in t for t in titles)

    def test_detects_crash_loop_backoff(self):
        events = [make_event(1, "5m  Warning  CrashLoopBackOff  Pod/webapp  CrashLoopBackOff: back-off")]
        issues = self.detector.detect(events)
        assert any(i.severity == Severity.CRITICAL for i in issues)

    def test_detects_oom_killed(self):
        events = [make_event(1, "OOMKilled: container webapp exceeded memory limit")]
        issues = self.detector.detect(events)
        assert any("OOM" in i.title for i in issues)

    def test_detects_image_pull_error(self):
        events = [make_event(1, "Failed to pull image registry.acme.com/webapp:2.1.0")]
        issues = self.detector.detect(events)
        assert any("Image Pull" in i.title or "image pull" in i.title.lower() for i in issues)

    def test_detects_connection_refused(self):
        events = [make_event(1, "Error: connection refused: dial tcp 10.0.0.5:5432")]
        issues = self.detector.detect(events)
        assert any("Connection Refused" in i.title for i in issues)

    def test_detects_ssl_error(self):
        events = [make_event(1, "SSL handshake failed: certificate verify failed")]
        issues = self.detector.detect(events)
        assert any("SSL" in i.title for i in issues)

    def test_detects_permission_denied(self):
        events = [make_event(1, "Error: permission denied: cannot read /etc/ssl/private/server.key")]
        issues = self.detector.detect(events)
        assert any("Permission" in i.title for i in issues)

    def test_detects_auth_failed(self):
        events = [make_event(1, "authentication failed: invalid service account token")]
        issues = self.detector.detect(events)
        assert any("Authentication" in i.title for i in issues)

    def test_detects_unhandled_exception(self):
        events = [
            make_event(1, "Traceback (most recent call last):"),
            make_event(2, "  File '/app/db.py', line 88, in connect"),
            make_event(3, "psycopg2.OperationalError: connection refused"),
        ]
        issues = self.detector.detect(events)
        assert any("Exception" in i.title for i in issues)

    def test_detects_no_space_left(self):
        events = [make_event(1, "write /var/lib/docker/overlay2: no space left on device")]
        issues = self.detector.detect(events)
        assert any("Disk" in i.title or "Space" in i.title for i in issues)

    def test_issue_has_remediation(self):
        events = [make_event(1, "BUILD FAILURE")]
        issues = self.detector.detect(events)
        critical = [i for i in issues if i.severity == Severity.CRITICAL]
        assert all(len(i.remediation) > 0 for i in critical)

    def test_issue_has_events(self):
        events = [make_event(1, "BUILD FAILURE")]
        issues = self.detector.detect(events)
        assert all(len(i.events) > 0 for i in issues)

    def test_returns_empty_for_clean_log(self):
        events = [
            make_event(1, "INFO: Application started successfully"),
            make_event(2, "INFO: All systems nominal"),
        ]
        issues = self.detector.detect(events)
        # No error-level issues expected
        error_issues = [i for i in issues if i.severity in (Severity.ERROR, Severity.CRITICAL)]
        assert len(error_issues) == 0

    def test_groups_nearby_errors(self):
        events = [make_event(i, "BUILD FAILURE") for i in range(1, 6)]
        issues = self.detector.detect(events)
        # 5 consecutive same-pattern events should be grouped into 1 issue
        build_failure_issues = [i for i in issues if "Build Failure" in i.title]
        assert len(build_failure_issues) == 1


# ---------------------------------------------------------------------------
# WarningDetector
# ---------------------------------------------------------------------------

class TestWarningDetector:
    def setup_method(self):
        self.detector = WarningDetector()

    def test_detects_deprecated_api(self):
        events = [make_event(1, "DeprecationWarning: use of 'require_all' is deprecated")]
        issues = self.detector.detect(events)
        assert any("Deprecated" in i.title for i in issues)

    def test_detects_retry(self):
        events = [make_event(1, "Retrying in 5 seconds... attempt 1")]
        issues = self.detector.detect(events)
        assert any("Retry" in i.title for i in issues)

    def test_detects_cert_expiry(self):
        events = [make_event(1, "certificate will expire in 14 days: /etc/ssl/certs/webapp.pem")]
        issues = self.detector.detect(events)
        assert any("Certificate" in i.title for i in issues)

    def test_detects_privileged_container(self):
        events = [make_event(1, "Container is running as root (UID 0) — privileged container")]
        issues = self.detector.detect(events)
        assert any("Root" in i.title or "Privileged" in i.title for i in issues)

    def test_detects_k8s_backoff(self):
        events = [make_event(1, "Back-off restarting failed container")]
        issues = self.detector.detect(events)
        assert any("Back-Off" in i.title for i in issues)

    def test_detects_jenkins_unstable(self):
        events = [make_event(1, "BUILD UNSTABLE — some tests failed")]
        issues = self.detector.detect(events)
        assert any("Unstable" in i.title for i in issues)

    def test_all_issues_have_warning_severity(self):
        events = [
            make_event(1, "DeprecationWarning: old API"),
            make_event(2, "certificate will expire in 3 days"),
        ]
        issues = self.detector.detect(events)
        assert all(i.severity == Severity.WARNING for i in issues)


# ---------------------------------------------------------------------------
# PerformanceDetector
# ---------------------------------------------------------------------------

class TestPerformanceDetector:
    def setup_method(self):
        self.detector = PerformanceDetector()

    def test_detects_oom_error(self):
        events = [make_event(1, "OutOfMemoryError: Java heap space — process killed")]
        issues = self.detector.detect(events)
        assert any("Memory" in i.title or "OOM" in i.title for i in issues)

    def test_detects_gc_overhead(self):
        events = [make_event(1, "GC overhead limit exceeded — forcing full GC")]
        issues = self.detector.detect(events)
        assert any("GC" in i.title for i in issues)

    def test_detects_connection_pool_exhausted(self):
        events = [make_event(1, "connection pool exhausted: max connections (100) reached")]
        issues = self.detector.detect(events)
        assert any("Pool" in i.title for i in issues)

    def test_detects_timeout(self):
        events = [make_event(1, "request timed out after 30000ms — ETIMEDOUT")]
        issues = self.detector.detect(events)
        assert any("Timeout" in i.title for i in issues)

    def test_detects_high_latency_ms(self):
        events = [make_event(1, "response took=1500ms endpoint=/api/orders")]
        issues = self.detector.detect(events)
        assert any("Latency" in i.title for i in issues)

    def test_detects_high_latency_seconds(self):
        events = [make_event(1, "elapsed=2.5s query=SELECT_all_orders")]
        issues = self.detector.detect(events)
        assert any("Latency" in i.title for i in issues)

    def test_does_not_flag_low_latency(self):
        events = [make_event(1, "elapsed=50ms endpoint=/health")]
        issues = self.detector.detect(events)
        latency_issues = [i for i in issues if "Latency" in i.title]
        assert len(latency_issues) == 0

    def test_detects_thread_exhaustion(self):
        events = [make_event(1, "thread pool exhausted: executor rejected task")]
        issues = self.detector.detect(events)
        assert any("Thread" in i.title for i in issues)

    def test_detects_queue_overflow(self):
        events = [make_event(1, "queue full: message dropped — queue overflow detected")]
        issues = self.detector.detect(events)
        assert any("Queue" in i.title for i in issues)

    def test_critical_oom_severity(self):
        events = [make_event(1, "OutOfMemoryError: Java heap space")]
        issues = self.detector.detect(events)
        oom = [i for i in issues if "Memory" in i.title or "OOM" in i.title]
        assert any(i.severity == Severity.CRITICAL for i in oom)
