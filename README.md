# 🔍 Log Analyzer

> A modular, extensible log analysis tool for DevOps pipelines.  
> Detects errors, warnings, and performance issues in **Jenkins**, **Docker**, **Kubernetes**, and generic log files — then generates rich reports with remediation steps.

---

## ✨ Features

- **Multi-source parsing** — Jenkins console output, Docker daemon/container logs, Kubernetes events and klog, syslog/plaintext
- **Smart auto-detection** — `--source auto` scores parsers and picks the best match
- **40+ detection rules** — build failures, OOM kills, CrashLoopBackOff, SSL errors, connection refusals, slow queries, and more
- **3 report formats** — interactive dark-mode HTML, Markdown, and JSON
- **Remediation knowledge base** — actionable fix steps and official doc links for every issue type
- **Modular architecture** — add a new log source by implementing one abstract class

---

## 📦 Installation

```bash
# Clone the repository
git clone https://github.com/acme/log-analyzer.git
cd log-analyzer

# Create a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install the package and dependencies
pip install -e .

# Or install just the runtime dependencies
pip install -r requirements.txt
```

**Requirements:** Python 3.9+

---

## 🚀 Quick Start

### Analyze a single log file

```bash
# Auto-detect the source and generate all report formats
log-analyzer analyze sample_logs/jenkins_build.log

# Specify source explicitly
log-analyzer analyze sample_logs/docker_daemon.log --source docker

# Specify output format and location
log-analyzer analyze sample_logs/kubernetes_pod.log \
  --source kubernetes \
  --format html \
  --output reports/k8s_report.html
```

### Analyze an entire directory

```bash
log-analyzer analyze sample_logs/ --source auto --format all --output reports/
```

### Filter by minimum severity

```bash
log-analyzer analyze app.log --min-severity ERROR
```

### List available sources and formats

```bash
log-analyzer list-sources
log-analyzer list-formats
```

---

## 📊 Example Output

After running:
```bash
log-analyzer analyze sample_logs/ --format all --output reports/
```

You'll get:

```
reports/
├── sample_logs_report.html     ← Interactive dark-mode dashboard
├── sample_logs_report.json     ← Machine-readable JSON
└── sample_logs_report.md       ← Markdown for docs/PRs
```

### Console Summary

```
╭─────────────────────────────────────╮
│  Log Analyzer v1.0.0                │
│  Analyzing: sample_logs/            │
│  Source: auto   Format: all         │
╰─────────────────────────────────────╯

          Analysis Summary
 ─────────────────────────────────────
  File             sample_logs/
  Source           Jenkins
  Lines Processed  128
 ─────────────────────────────────────
  🔴 Critical      4
  🟠 Error         7
  🟡 Warning       9
  🔵 Info          0
 ─────────────────────────────────────
  Total Issues     20

  Top Issues
  CRITICAL │ Jenkins Build Failure          │ Line 18   │ Build Failure
  CRITICAL │ Kubernetes Pod CrashLoopBackOff│ Line 22   │ Runtime Error
  CRITICAL │ Pod Killed by OOM              │ Line 25   │ Resource
  ERROR    │ Test Failures Detected         │ Line 10   │ Build Failure
  ERROR    │ Authentication Failed          │ Line 15   │ Security
  ...
```

---

## 🏗️ Architecture

```
log-analyzer/
├── log_analyzer/
│   ├── models.py           # LogEvent, Issue, AnalysisReport data classes
│   ├── engine.py           # AnalysisEngine — orchestration pipeline
│   ├── cli.py              # Click CLI (log-analyzer command)
│   ├── parsers/
│   │   ├── base.py         # BaseParser abstract class
│   │   ├── jenkins.py      # Jenkins build log parser
│   │   ├── docker.py       # Docker container/daemon log parser
│   │   ├── kubernetes.py   # Kubernetes log and event parser
│   │   └── generic.py      # Syslog / Python / Log4j / Apache parser
│   ├── detectors/
│   │   ├── base.py         # BaseDetector abstract class
│   │   ├── error_detector.py       # 20+ error patterns
│   │   ├── warning_detector.py     # 12+ warning patterns
│   │   └── performance_detector.py # 9+ performance patterns + latency check
│   ├── reporters/
│   │   ├── base.py         # BaseReporter abstract class
│   │   ├── json_reporter.py
│   │   ├── markdown_reporter.py
│   │   └── html_reporter.py
│   └── remediation/
│       └── suggestions.py  # 40+ keyed remediation entries
├── sample_logs/            # Example log files
├── tests/                  # pytest test suite
└── docs/USAGE.md           # Full CLI reference
```

---

## 🔌 Extending the Analyzer

### Adding a New Log Source

1. Create `log_analyzer/parsers/nginx.py`:

```python
from log_analyzer.parsers.base import BaseParser
from log_analyzer.models import LogEvent, LogSource

class NginxParser(BaseParser):
    source = LogSource.GENERIC  # or add NGINX to the enum

    @classmethod
    def score_source(cls, lines):
        # Return confidence score 0.0–1.0
        hits = sum(1 for l in cls._sample(lines) if 'nginx' in l.lower())
        return min(hits / max(len(cls._sample(lines)), 1) * 10, 1.0)

    def parse(self, lines):
        events = []
        for i, raw in enumerate(lines, 1):
            # Parse your format here
            events.append(LogEvent(line_number=i, raw=raw, message=raw.strip()))
        return events
```

2. Register it in `log_analyzer/parsers/__init__.py`:

```python
from .nginx import NginxParser
PARSER_REGISTRY["nginx"] = NginxParser
```

That's it — the engine auto-picks it for `--source nginx` and includes it in `--source auto` scoring.

### Adding New Detection Rules

Open `log_analyzer/detectors/error_detector.py` and add a dict to `_RULES`:

```python
{
    "pattern": re.compile(r"my custom error pattern", re.IGNORECASE),
    "title": "My Custom Error",
    "severity": Severity.ERROR,
    "category": Category.RUNTIME_ERROR,
    "key": "my_custom_key",    # add matching entry to remediation/suggestions.py
},
```

### Adding Remediation Entries

Open `log_analyzer/remediation/suggestions.py` and add to `REMEDIATION_DB`:

```python
"my_custom_key": {
    "steps": [
        "Step 1: investigate X",
        "Step 2: fix Y",
    ],
    "references": ["https://official-docs.example.com/"],
},
```

---

## 🧪 Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=log_analyzer --cov-report=term-missing

# Run a specific test file
pytest tests/test_parsers.py -v
```

---

## 📖 Python API

```python
from log_analyzer import AnalysisEngine

engine = AnalysisEngine()

# Analyze a file
report = engine.analyze("path/to/app.log", source="auto")

print(f"Total issues: {report.summary['total']}")
print(f"Critical: {report.summary['critical']}")

for issue in report.sorted_issues:
    print(f"[{issue.severity.value}] {issue.title} — Line {issue.line_numbers}")
    for step in issue.remediation:
        print(f"  → {step}")

# Write reports
written = engine.report(report, formats=["html", "json"], output_dir="./reports")
```

---

## 🛠️ CLI Reference

| Option | Description | Default |
|---|---|---|
| `--source` | Log source: `auto`, `jenkins`, `docker`, `kubernetes`, `generic` | `auto` |
| `--format` | Output format: `json`, `markdown`, `html`, `all` | `all` |
| `--output` | Output file or directory | `reports` |
| `--min-severity` | Minimum severity to include: `INFO`, `WARNING`, `ERROR`, `CRITICAL` | `INFO` |
| `--quiet` | Suppress console output | false |

---

## 📋 Supported Issue Types

| Category | Examples |
|---|---|
| Build Failure | Jenkins BUILD FAILURE, compile errors, dependency resolution |
| Runtime Error | CrashLoopBackOff, container crashed, unhandled exceptions |
| Resource | OOM kill, pod eviction, disk full, no space left |
| Network | Connection refused, SSL error, request timeout |
| Security | Auth failure, permission denied, privileged container |
| Performance | High latency, GC overhead, connection pool exhaustion |
| Configuration | Image pull error, missing config, readiness probe failure |
| Deprecation | Deprecated APIs, insecure registries |

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
