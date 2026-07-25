"""Unit tests for all log parsers."""

import pytest
from log_analyzer.parsers.jenkins import JenkinsParser
from log_analyzer.parsers.docker import DockerParser
from log_analyzer.parsers.kubernetes import KubernetesParser
from log_analyzer.parsers.generic import GenericParser
from log_analyzer.models import LogSource


# ---------------------------------------------------------------------------
# Jenkins Parser Tests
# ---------------------------------------------------------------------------

class TestJenkinsParser:
    def setup_method(self):
        self.parser = JenkinsParser()

    def test_source_tag(self):
        assert self.parser.source == LogSource.JENKINS

    def test_parses_build_failure(self):
        lines = ["09:14:21  BUILD FAILURE\n"]
        events = self.parser.parse(lines)
        assert len(events) == 1
        assert "BUILD FAILURE" in events[0].message
        assert events[0].level == "ERROR"

    def test_parses_error_level(self):
        lines = ["09:14:20  [ERROR] compilation error: cannot find symbol\n"]
        events = self.parser.parse(lines)
        assert events[0].level == "ERROR"

    def test_parses_warning_level(self):
        lines = ["09:14:12  [WARNING] bootstrap class path not set\n"]
        events = self.parser.parse(lines)
        assert events[0].level == "WARNING"

    def test_parses_timestamp(self):
        lines = ["09:14:01  Checking out from SCM...\n"]
        events = self.parser.parse(lines)
        assert events[0].timestamp is not None
        assert events[0].timestamp.hour == 9
        assert events[0].timestamp.minute == 14

    def test_parses_stage(self):
        lines = ["[Pipeline] { (Build)\n"]
        events = self.parser.parse(lines)
        assert events[0].metadata.get("stage") == "Build"

    def test_detects_test_failure(self):
        lines = ["09:14:30  Tests run: 47, Failures: 3, Errors: 1, Skipped: 0\n"]
        events = self.parser.parse(lines)
        assert events[0].level == "ERROR"
        assert events[0].metadata["failures"] == 3

    def test_score_source_high_for_jenkins_log(self):
        lines = [
            "Started by user admin\n",
            "[Pipeline] { (Build)\n",
            "09:14:21  BUILD FAILURE\n",
            "Finished: FAILURE\n",
        ]
        score = JenkinsParser.score_source(lines)
        assert score > 0.5

    def test_score_source_low_for_docker_log(self):
        lines = [
            'time="2024-01-15T10:22:00Z" level=info msg="Starting Docker"\n',
            'time="2024-01-15T10:22:01Z" level=error msg="container died"\n',
        ]
        score = JenkinsParser.score_source(lines)
        assert score < 0.2

    def test_line_numbers_are_correct(self):
        lines = ["line one\n", "line two\n", "line three\n"]
        events = self.parser.parse(lines)
        assert [e.line_number for e in events] == [1, 2, 3]

    def test_empty_input(self):
        events = self.parser.parse([])
        assert events == []


# ---------------------------------------------------------------------------
# Docker Parser Tests
# ---------------------------------------------------------------------------

class TestDockerParser:
    def setup_method(self):
        self.parser = DockerParser()

    def test_source_tag(self):
        assert self.parser.source == LogSource.DOCKER

    def test_parses_daemon_structured_line(self):
        lines = ['time="2024-01-15T10:22:30Z" level=error msg="container OOM killed" container_id=abc123\n']
        events = self.parser.parse(lines)
        assert events[0].level == "ERROR"
        assert "OOM killed" in events[0].message
        assert events[0].metadata.get("container_id") == "abc123"

    def test_parses_rfc3339_prefix(self):
        lines = ["2024-01-15T10:22:05.123456789Z [INFO] App started\n"]
        events = self.parser.parse(lines)
        assert events[0].timestamp is not None
        assert events[0].level == "INFO"

    def test_parses_level_warning(self):
        lines = ['time="2024-01-15T10:22:00Z" level=warning msg="disk full"\n']
        events = self.parser.parse(lines)
        assert events[0].level == "WARNING"

    def test_score_source_high_for_docker_log(self):
        lines = [
            'time="2024-01-15T10:22:00Z" level=info msg="Starting Docker daemon"\n',
            '2024-01-15T10:22:05Z containerd: starting...\n',
        ]
        score = DockerParser.score_source(lines)
        assert score > 0.0

    def test_score_source_low_for_jenkins_log(self):
        lines = [
            "Started by user admin\n",
            "09:14:21  BUILD FAILURE\n",
        ]
        score = DockerParser.score_source(lines)
        # May or may not be 0 — just ensure Jenkins scores higher than Docker
        jenkins_score = JenkinsParser.score_source(lines)
        assert jenkins_score >= score


# ---------------------------------------------------------------------------
# Kubernetes Parser Tests
# ---------------------------------------------------------------------------

class TestKubernetesParser:
    def setup_method(self):
        self.parser = KubernetesParser()

    def test_source_tag(self):
        assert self.parser.source == LogSource.KUBERNETES

    def test_parses_klog_error(self):
        lines = [
            "E0115 10:22:10.001234   1 controller.go:300] Failed to create pod\n"
        ]
        events = self.parser.parse(lines)
        assert events[0].level == "ERROR"
        assert "Failed to create pod" in events[0].message

    def test_parses_klog_warning(self):
        lines = [
            "W0115 10:22:05.001234   1 controller.go:200] Resource quota exceeded\n"
        ]
        events = self.parser.parse(lines)
        assert events[0].level == "WARNING"

    def test_parses_klog_info(self):
        lines = [
            "I0115 10:22:00.001234   1 controller.go:100] Starting deployment controller\n"
        ]
        events = self.parser.parse(lines)
        assert events[0].level == "INFO"

    def test_parses_kubectl_events_line(self):
        lines = [
            "5m    Warning   BackOff    Pod/my-pod   Back-off restarting failed container\n"
        ]
        events = self.parser.parse(lines)
        assert events[0].level == "WARNING"
        assert events[0].metadata.get("reason") == "BackOff"
        assert events[0].metadata.get("object") == "Pod/my-pod"

    def test_parses_normal_event(self):
        lines = [
            "30m   Normal    Scheduled   Pod/my-pod   Successfully assigned to node\n"
        ]
        events = self.parser.parse(lines)
        assert events[0].level == "INFO"

    def test_score_source_high_for_k8s_log(self):
        lines = [
            "E0115 10:22:10.001234   1 controller.go:300] CrashLoopBackOff detected\n",
            "5m    Warning   OOMKilled    Pod/webapp   Pod killed\n",
        ]
        score = KubernetesParser.score_source(lines)
        assert score > 0.2


# ---------------------------------------------------------------------------
# Generic Parser Tests
# ---------------------------------------------------------------------------

class TestGenericParser:
    def setup_method(self):
        self.parser = GenericParser()

    def test_source_tag(self):
        assert self.parser.source == LogSource.GENERIC

    def test_parses_syslog_line(self):
        lines = [
            "Jan 15 10:22:05 host myapp[1234]: ERROR Something went wrong\n"
        ]
        events = self.parser.parse(lines)
        assert events[0].level == "ERROR"

    def test_parses_python_logging(self):
        lines = [
            "2024-01-15 10:22:05,123 - root - ERROR - Database connection failed\n"
        ]
        events = self.parser.parse(lines)
        assert events[0].level == "ERROR"
        assert events[0].timestamp is not None

    def test_parses_bare_level_keyword(self):
        lines = ["Something bad happened [CRITICAL]\n"]
        events = self.parser.parse(lines)
        assert events[0].level == "CRITICAL"

    def test_level_alias_warn_to_warning(self):
        lines = ["2024-01-15 10:22:05,123 - root - WARN - Retrying\n"]
        events = self.parser.parse(lines)
        assert events[0].level == "WARNING"

    def test_level_alias_fatal_to_critical(self):
        lines = ["Jan 15 10:22:05 host app[1]: FATAL Segfault\n"]
        events = self.parser.parse(lines)
        assert events[0].level == "CRITICAL"

    def test_empty_input(self):
        events = self.parser.parse([])
        assert events == []

    def test_preserves_raw_line(self):
        raw = "Jan 15 10:22:05 host app[1]: ERROR Something\n"
        events = self.parser.parse([raw])
        assert events[0].raw == raw

    def test_score_source_returns_nonzero(self):
        score = GenericParser.score_source(["some random log line\n"])
        assert score > 0.0
