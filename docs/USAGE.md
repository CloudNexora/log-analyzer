# CLI Usage Guide

Full reference for the `log-analyzer` command-line interface.

---

## Commands

### `log-analyzer analyze`

Analyse a log file or directory and generate a report.

```
Usage: log-analyzer analyze [OPTIONS] LOG_PATH

  Analyse LOG_PATH (file or directory) and generate a report.

Options:
  -s, --source [auto|jenkins|docker|kubernetes|generic]
                                  Log source type.  [default: auto]
  -f, --format [json|markdown|md|html|all]
                                  Output report format.  [default: all]
  -o, --output TEXT               Output file path or directory.  [default: reports]
  --min-severity [INFO|WARNING|ERROR|CRITICAL]
                                  Minimum severity level.  [default: INFO]
  -q, --quiet                     Suppress console output.
  --version                       Show the version and exit.
  --help                          Show this message and exit.
```

#### Examples

```bash
# Basic: analyze with auto-detection, all formats
log-analyzer analyze sample_logs/jenkins_build.log

# Force Kubernetes source, HTML output only
log-analyzer analyze k8s.log --source kubernetes --format html

# Analyze a whole directory, output to reports/
log-analyzer analyze /var/log/ --source auto --format all --output reports/

# Only show ERROR and CRITICAL issues
log-analyzer analyze app.log --min-severity ERROR

# Quiet mode (useful in CI pipelines — check exit code)
log-analyzer analyze build.log --quiet
echo "Exit: $?"   # 0 = no issues, 1 = errors/criticals found
```

#### Exit Codes

| Code | Meaning |
|---|---|
| `0` | Success — no ERROR or CRITICAL issues found |
| `1` | ERROR or CRITICAL issues detected |
| `2` | Usage error (bad arguments) |

---

### `log-analyzer list-sources`

List all available log source parsers.

```bash
log-analyzer list-sources
```

Output:
```
╭──────────────┬──────────────────────┬──────────────────────────────────────────────╮
│ Source       │ Parser Class         │ Description                                  │
├──────────────┼──────────────────────┼──────────────────────────────────────────────┤
│ jenkins      │ JenkinsParser        │ Jenkins build console output                 │
│ docker       │ DockerParser         │ Docker container logs and daemon logs        │
│ kubernetes   │ KubernetesParser     │ kubectl logs, events, klog format            │
│ generic      │ GenericParser        │ Syslog, Python logging, Log4j, Apache        │
╰──────────────┴──────────────────────┴──────────────────────────────────────────────╯
```

---

### `log-analyzer list-formats`

List all available report output formats.

```bash
log-analyzer list-formats
```

---

## Output Formats

### JSON (`--format json`)

Machine-readable structured output suitable for programmatic processing:

```json
{
  "file_path": "sample_logs/jenkins_build.log",
  "source": "jenkins",
  "analyzed_at": "2024-01-15T10:22:00",
  "total_lines": 38,
  "summary": {
    "total": 8,
    "critical": 2,
    "error": 4,
    "warning": 2,
    "info": 0
  },
  "issues": [
    {
      "id": "a1b2c3d4",
      "title": "Jenkins Build Failure",
      "severity": "CRITICAL",
      "category": "Build Failure",
      "source": "jenkins",
      "detector": "ErrorDetector",
      "line_numbers": [18],
      "remediation": [
        "Check the Jenkins console output...",
        "Verify credentials..."
      ],
      "references": ["https://www.jenkins.io/doc/book/pipeline/"],
      "context": ["09:14:21  BUILD FAILURE"]
    }
  ]
}
```

### Markdown (`--format markdown`)

Human-readable report with tables and code blocks — ideal for Slack, GitHub PRs, or documentation.

### HTML (`--format html`)

Self-contained interactive dark-mode dashboard (no internet required):
- Summary cards by severity
- Animated bar chart
- Collapsible issue cards with syntax-highlighted log context
- Clickable references
- Severity filter buttons

---

## Auto-Detection Algorithm

When `--source auto` is used, the engine:

1. Samples up to 200 lines from the log file
2. Scores each parser using its `score_source()` classmethod (returns 0.0–1.0)
3. Selects the parser with the highest score
4. Falls back to `GenericParser` if all scores are equal (base score 0.1)

| Parser | Signals Used |
|---|---|
| Jenkins | `BUILD SUCCESS/FAILURE`, `[Pipeline]`, `Started by user`, `Finished:` |
| Docker | `time=` / `level=` / `msg=` pattern, RFC 3339 timestamps, Docker keywords |
| Kubernetes | `CrashLoopBackOff`, klog format (`E0115...`), kubectl event table |
| Generic | Always available with a base score of 0.1 |

---

## Using in CI/CD

### GitHub Actions

```yaml
- name: Analyze build log
  run: |
    log-analyzer analyze build.log \
      --source jenkins \
      --format html \
      --output artifacts/
  continue-on-error: true

- name: Upload report
  uses: actions/upload-artifact@v3
  with:
    name: log-analysis-report
    path: artifacts/
```

### Jenkins Pipeline

```groovy
post {
    always {
        sh '''
            log-analyzer analyze ${BUILD_LOG} \
              --source jenkins \
              --format all \
              --output reports/
        '''
        publishHTML([
            reportDir: 'reports',
            reportFiles: '*.html',
            reportName: 'Log Analysis Report'
        ])
    }
}
```

---

## Python API Reference

### `AnalysisEngine`

```python
from log_analyzer import AnalysisEngine

engine = AnalysisEngine()
```

#### `engine.analyze(log_path, source="auto") -> AnalysisReport`

Parse and detect issues from a log file or directory.

#### `engine.report(analysis, formats=None, output_dir=None) -> List[str]`

Write reports in requested formats. Returns list of written file paths.

---

### `AnalysisReport`

| Property | Type | Description |
|---|---|---|
| `.issues` | `List[Issue]` | All detected issues |
| `.sorted_issues` | `List[Issue]` | Issues sorted critical-first |
| `.criticals` | `List[Issue]` | Critical-severity issues |
| `.errors` | `List[Issue]` | Error-severity issues |
| `.warnings` | `List[Issue]` | Warning-severity issues |
| `.summary` | `dict` | Count by severity |
| `.total_lines` | `int` | Lines processed |
| `.to_dict()` | `dict` | JSON-serializable representation |

---

### `Issue`

| Property | Type | Description |
|---|---|---|
| `.id` | `str` | Unique 8-char ID |
| `.title` | `str` | Short description |
| `.severity` | `Severity` | CRITICAL / ERROR / WARNING / INFO |
| `.category` | `Category` | Build Failure, Runtime Error, etc. |
| `.events` | `List[LogEvent]` | Log lines that triggered this issue |
| `.remediation` | `List[str]` | Fix steps |
| `.references` | `List[str]` | Doc URLs |
| `.line_numbers` | `List[int]` | Source line numbers |
