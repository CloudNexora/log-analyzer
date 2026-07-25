"""
Remediation knowledge base.

Maps issue keys to structured remediation advice.  Each entry contains:
  - steps:      Ordered list of actionable fix steps (plain text).
  - references: List of URLs to official docs / runbooks.

Add new entries to :data:`REMEDIATION_DB` to extend the knowledge base.
"""

from __future__ import annotations

from typing import Dict, List, TypedDict


class RemediationEntry(TypedDict):
    steps: List[str]
    references: List[str]


REMEDIATION_DB: Dict[str, RemediationEntry] = {
    # -----------------------------------------------------------------------
    # Build / CI
    # -----------------------------------------------------------------------
    "jenkins_build_failure": {
        "steps": [
            "Check the Jenkins console output for the first ERROR line to pinpoint the root cause.",
            "Look for missing environment variables or credentials (use 'Credentials' plugin).",
            "Verify that all required tools (Maven, Gradle, npm) are installed on the agent.",
            "Check available disk space on the Jenkins agent: `df -h`.",
            "Re-run the build after fixing the issue; use 'Replay' if the failure is in a Pipeline script.",
        ],
        "references": [
            "https://www.jenkins.io/doc/book/pipeline/getting-started/",
            "https://www.jenkins.io/doc/book/managing/troubleshooting/",
        ],
    },
    "test_failure": {
        "steps": [
            "Open the Test Results page in Jenkins (click 'Test Result' on the build page).",
            "Identify which test class/method failed and read the failure message.",
            "Run the failing test locally: `mvn test -Dtest=<FailingTest>` or `pytest -k <test_name>`.",
            "Check for flaky tests — re-run the build to see if the failure is intermittent.",
            "Look for environment-specific differences (database, ports, credentials) between CI and local.",
        ],
        "references": [
            "https://www.jenkins.io/doc/book/using/using-junit/",
        ],
    },
    "non_zero_exit": {
        "steps": [
            "Identify which command exited with a non-zero code from the surrounding log context.",
            "Run the command manually on the agent to reproduce the error.",
            "Check the command's stderr output for the actual error message.",
            "Verify that input files, environment variables, and permissions are correct.",
        ],
        "references": [],
    },
    "dependency_resolution": {
        "steps": [
            "Check your internet connectivity or internal artifact repository (Nexus/Artifactory) health.",
            "Verify the dependency version exists: search https://mvnrepository.com or https://pypi.org.",
            "Clear the local dependency cache: `rm -rf ~/.m2/repository` (Maven) or `pip cache purge`.",
            "If using a private mirror, ensure its credentials are configured correctly.",
            "Check for typos in the dependency name or version string in pom.xml / requirements.txt.",
        ],
        "references": [
            "https://maven.apache.org/guides/mini/guide-configuring-maven.html",
        ],
    },
    "compile_error": {
        "steps": [
            "Read the compiler error message — it will include file, line number, and description.",
            "Check for syntax errors, missing imports, or type mismatches introduced in recent commits.",
            "Run `git diff HEAD~1` to review recent changes.",
            "Ensure the correct compiler/SDK version is installed on the agent.",
        ],
        "references": [],
    },
    # -----------------------------------------------------------------------
    # Kubernetes
    # -----------------------------------------------------------------------
    "crash_loop_backoff": {
        "steps": [
            "Inspect pod logs: `kubectl logs <pod> --previous` to see the last crash output.",
            "Describe the pod: `kubectl describe pod <pod>` to see exit codes and events.",
            "Check the container's entrypoint/command — a misconfigured CMD causes immediate exit.",
            "Verify required ConfigMaps and Secrets exist: `kubectl get cm,secret -n <ns>`.",
            "Look for liveness probe misconfiguration causing premature kills.",
            "Increase resource limits if the container is OOM-killed on startup.",
        ],
        "references": [
            "https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/",
            "https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/",
        ],
    },
    "oom_killed": {
        "steps": [
            "Check actual memory consumption: `kubectl top pod <pod> -n <namespace>`.",
            "Increase the container's memory limit in the Deployment spec: `resources.limits.memory`.",
            "Profile the application for memory leaks using heap dumps or profilers.",
            "Consider enabling memory autoscaling with VPA (Vertical Pod Autoscaler).",
            "Review application code for unbounded caches or large in-memory data structures.",
        ],
        "references": [
            "https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/",
            "https://kubernetes.io/docs/tasks/configure-pod-container/assign-memory-resource/",
        ],
    },
    "pod_evicted": {
        "steps": [
            "Check node resource pressure: `kubectl describe node <node>` — look for 'Conditions'.",
            "Add resource requests to prevent scheduling on overcommitted nodes.",
            "Set PodDisruptionBudgets if evictions affect availability.",
            "Enable cluster autoscaler to add nodes when resource pressure rises.",
            "Review eviction thresholds in kubelet configuration.",
        ],
        "references": [
            "https://kubernetes.io/docs/concepts/scheduling-eviction/node-pressure-eviction/",
        ],
    },
    "image_pull_error": {
        "steps": [
            "Verify the image name and tag are correct: `docker pull <image>:<tag>`.",
            "Check that the image registry credentials are configured: `kubectl get secret regcred`.",
            "For private registries, create an imagePullSecret: "
            "`kubectl create secret docker-registry regcred --docker-server=... --docker-username=...`.",
            "Ensure the image exists in the registry (it may have been deleted or overwritten).",
            "Check node network connectivity to the registry.",
        ],
        "references": [
            "https://kubernetes.io/docs/tasks/configure-pod-container/pull-image-private-registry/",
        ],
    },
    "liveness_probe_failed": {
        "steps": [
            "Review the liveness probe configuration: path, port, initialDelaySeconds, and timeoutSeconds.",
            "Increase `initialDelaySeconds` to give the application more time to start.",
            "Test the probe endpoint manually: `kubectl exec <pod> -- wget -qO- http://localhost:<port>/health`.",
            "Review application startup logs for slow initialization.",
            "Consider switching to a startupProbe to avoid premature liveness failures during boot.",
        ],
        "references": [
            "https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/",
        ],
    },
    "readiness_probe_failed": {
        "steps": [
            "Test the readiness endpoint: `kubectl exec <pod> -- wget -qO- http://localhost:<port>/ready`.",
            "Ensure all downstream dependencies (DB, cache) are available before the pod becomes ready.",
            "Increase `failureThreshold` and `periodSeconds` to tolerate transient slowdowns.",
            "Check application logs for errors that prevent it from entering a ready state.",
        ],
        "references": [
            "https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/",
        ],
    },
    "pod_not_ready": {
        "steps": [
            "Describe the pod: `kubectl describe pod <pod>` to check conditions and events.",
            "Ensure all required ConfigMaps, Secrets, and PVCs are available.",
            "Check node capacity: `kubectl get nodes` and `kubectl describe node`.",
            "Review network policies that might block pod communication.",
        ],
        "references": [
            "https://kubernetes.io/docs/tasks/debug/debug-application/",
        ],
    },
    "resource_quota": {
        "steps": [
            "Check quota usage: `kubectl describe resourcequota -n <namespace>`.",
            "Reduce resource requests/limits for existing workloads.",
            "Request a quota increase from the cluster administrator.",
            "Move workloads to a namespace with available quota.",
        ],
        "references": [
            "https://kubernetes.io/docs/concepts/policy/resource-quotas/",
        ],
    },
    "k8s_backoff": {
        "steps": [
            "Identify the backing-off pod: `kubectl get pods --all-namespaces | grep -v Running`.",
            "Inspect events: `kubectl get events --sort-by='.metadata.creationTimestamp'`.",
            "Check image availability and pull credentials.",
            "Review restart policy — consider setting `restartPolicy: Never` for batch jobs.",
        ],
        "references": [
            "https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#restart-policy",
        ],
    },
    # -----------------------------------------------------------------------
    # Docker
    # -----------------------------------------------------------------------
    "container_died": {
        "steps": [
            "Retrieve exit code: `docker inspect <container> --format='{{.State.ExitCode}}'`.",
            "View container logs: `docker logs <container>` and `docker logs --tail 100 <container>`.",
            "Common exit codes: 137 = OOM kill, 139 = SIGSEGV, 1 = application error.",
            "Add `--restart unless-stopped` or configure Docker Compose `restart: always`.",
            "Investigate root cause before enabling automatic restarts.",
        ],
        "references": [
            "https://docs.docker.com/config/containers/start-containers-automatically/",
        ],
    },
    "disk_full": {
        "steps": [
            "Identify large files: `du -sh /* 2>/dev/null | sort -rh | head -20`.",
            "Prune unused Docker objects: `docker system prune -a --volumes`.",
            "Expand the filesystem or add storage to the host.",
            "Configure log rotation for containers: set `log-opts` in `/etc/docker/daemon.json`.",
            "Move data directories to a larger volume.",
        ],
        "references": [
            "https://docs.docker.com/config/containers/logging/configure/",
        ],
    },
    "insecure_registry": {
        "steps": [
            "Add the registry to Docker's insecure-registries list only in development/internal environments.",
            "For production, configure TLS on the registry server.",
            "Use a self-signed CA and add it to the Docker daemon trust store.",
            "Consider migrating to a managed registry (Docker Hub, GCR, ECR, ACR) with built-in TLS.",
        ],
        "references": [
            "https://docs.docker.com/registry/insecure/",
        ],
    },
    # -----------------------------------------------------------------------
    # Network / Security
    # -----------------------------------------------------------------------
    "connection_refused": {
        "steps": [
            "Verify the target service is running: `systemctl status <service>` or `kubectl get svc`.",
            "Check that the correct host and port are configured in your application.",
            "Test connectivity: `curl -v <host>:<port>` or `nc -zv <host> <port>`.",
            "Review firewall / security group rules blocking the port.",
            "Check if the service is listening on the expected interface (0.0.0.0 vs 127.0.0.1).",
        ],
        "references": [],
    },
    "ssl_error": {
        "steps": [
            "Verify the certificate is valid: `openssl s_client -connect <host>:<port>`.",
            "Check certificate expiry date: `openssl x509 -noout -dates -in cert.pem`.",
            "Ensure the CA bundle is up-to-date on the client: `update-ca-certificates`.",
            "If using self-signed certs, add the CA to the system or application trust store.",
            "Check hostname matches the certificate's CN or SAN fields.",
        ],
        "references": [
            "https://letsencrypt.org/docs/",
        ],
    },
    "permission_denied": {
        "steps": [
            "Identify the file/resource: `ls -la <path>` to check ownership and permissions.",
            "Run as correct user or use `sudo` if appropriate.",
            "Fix permissions: `chmod 644 <file>` or `chown <user>:<group> <file>`.",
            "In Kubernetes, check RBAC: `kubectl auth can-i <verb> <resource> --as=<service-account>`.",
            "Review SELinux/AppArmor labels if running on a hardened host.",
        ],
        "references": [
            "https://kubernetes.io/docs/reference/access-authn-authz/rbac/",
        ],
    },
    "auth_failed": {
        "steps": [
            "Verify credentials are correct and not expired.",
            "Check if API keys or tokens need rotation.",
            "Ensure the service account / IAM role has required permissions.",
            "Review audit logs on the target service for the authentication attempt.",
            "Check for clock skew if using time-based tokens (JWT, TOTP).",
        ],
        "references": [],
    },
    "cert_expiry": {
        "steps": [
            "Check certificate expiry: `openssl x509 -noout -enddate -in cert.pem`.",
            "Set up automatic renewal with Let's Encrypt / cert-manager.",
            "In Kubernetes, use cert-manager: `kubectl apply -f https://github.com/cert-manager/cert-manager/releases/latest/download/cert-manager.yaml`.",
            "Rotate certificates before expiry to avoid downtime.",
            "Set calendar reminders 30 / 7 days before expiry.",
        ],
        "references": [
            "https://cert-manager.io/docs/",
        ],
    },
    "privileged_container": {
        "steps": [
            "Avoid running containers as root — set `runAsNonRoot: true` in securityContext.",
            "Drop all capabilities and add only required ones: `capabilities.drop: [ALL]`.",
            "Use a read-only root filesystem: `readOnlyRootFilesystem: true`.",
            "Scan images for vulnerabilities: `docker scout cves <image>`.",
            "Apply Pod Security Standards (restricted profile) to namespaces.",
        ],
        "references": [
            "https://kubernetes.io/docs/concepts/security/pod-security-standards/",
        ],
    },
    # -----------------------------------------------------------------------
    # Database
    # -----------------------------------------------------------------------
    "db_connection_failed": {
        "steps": [
            "Verify the database host, port, and credentials in your application configuration.",
            "Test connectivity: `psql -h <host> -U <user> -d <db>` or `mysql -h <host> -u <user> -p`.",
            "Check if the database service is running: `systemctl status postgresql` / `systemctl status mysql`.",
            "Review connection pool settings — ensure max connections are not exceeded.",
            "Check firewall rules allowing traffic from the application host to the DB port.",
        ],
        "references": [],
    },
    "slow_query": {
        "steps": [
            "Enable slow query logging on your database to capture problematic queries.",
            "Use EXPLAIN / EXPLAIN ANALYZE to understand the query execution plan.",
            "Add appropriate indexes on frequently-queried columns.",
            "Rewrite N+1 queries using JOINs or eager loading.",
            "Consider query result caching (Redis, Memcached) for read-heavy workloads.",
        ],
        "references": [
            "https://www.postgresql.org/docs/current/performance-tips.html",
        ],
    },
    # -----------------------------------------------------------------------
    # Performance
    # -----------------------------------------------------------------------
    "oom_error": {
        "steps": [
            "Identify the memory-hungry component from the stack trace.",
            "Increase heap size: `-Xmx2g` (JVM) or container memory limit.",
            "Profile memory with heap dump analysis (jmap, VisualVM) or py-spy / memory_profiler.",
            "Look for object retention / unbounded caches causing heap growth.",
            "Enable GC logging: `-Xlog:gc*` (JVM) to understand allocation rates.",
        ],
        "references": [
            "https://docs.oracle.com/javase/8/docs/technotes/tools/unix/java.html",
        ],
    },
    "gc_overhead": {
        "steps": [
            "Increase the JVM heap: `-Xmx4g` and `-Xms1g` to reduce GC frequency.",
            "Switch to a low-pause GC algorithm: G1GC (`-XX:+UseG1GC`) or ZGC (`-XX:+UseZGC`).",
            "Analyze heap dump: `jmap -dump:format=b,file=heap.hprof <pid>` then open in Eclipse MAT.",
            "Reduce object allocation rate — look for temporary object creation in hot paths.",
        ],
        "references": [
            "https://docs.oracle.com/javase/9/gctuning/",
        ],
    },
    "connection_pool": {
        "steps": [
            "Increase pool size in your connection pool configuration (HikariCP, pgBouncer, etc.).",
            "Ensure connections are released promptly — check for missing `close()` calls.",
            "Add connection pool metrics to identify peak usage times.",
            "Use connection multiplexing / pgBouncer in transaction pooling mode for PostgreSQL.",
            "Reduce query duration to free connections faster.",
        ],
        "references": [
            "https://github.com/brettwooldridge/HikariCP/wiki/About-Pool-Sizing",
        ],
    },
    "timeout": {
        "steps": [
            "Identify which downstream call timed out from the log context.",
            "Check the health of the downstream service.",
            "Increase timeout thresholds if the operation is legitimately slow.",
            "Implement circuit breakers (Resilience4j, Hystrix) to handle upstream failures gracefully.",
            "Add retry logic with exponential back-off for transient timeouts.",
        ],
        "references": [
            "https://resilience4j.readme.io/docs/circuitbreaker",
        ],
    },
    "high_resource_usage": {
        "steps": [
            "Profile the process to identify the hot code path: `py-spy top --pid <pid>` or `async-profiler`.",
            "Check for infinite loops or unbounded growth in data structures.",
            "Set resource limits and requests in Kubernetes to prevent noisy-neighbour issues.",
            "Review recent deployments that may have introduced a regression.",
        ],
        "references": [],
    },
    "queue_overflow": {
        "steps": [
            "Increase the queue size if consumers are expected to process at a lower rate.",
            "Add more consumer instances to process messages faster.",
            "Implement back-pressure to slow down producers.",
            "Monitor queue depth and set up alerts before it reaches capacity.",
        ],
        "references": [],
    },
    "thread_exhaustion": {
        "steps": [
            "Capture a thread dump: `jstack <pid>` or `kill -3 <pid>` for JVM applications.",
            "Identify blocked/waiting threads holding locks.",
            "Increase thread pool size or switch to async/non-blocking I/O.",
            "Audit synchronisation primitives for deadlock conditions.",
        ],
        "references": [],
    },
    "gc_pause": {
        "steps": [
            "Enable GC logging and analyse pause times with GCViewer or GCEasy.io.",
            "Switch to ZGC or Shenandoah for sub-10ms pause goals.",
            "Reduce heap fragmentation by tuning region sizes.",
            "Reduce allocation rate — use object pooling for frequently-created objects.",
        ],
        "references": [
            "https://wiki.openjdk.org/display/zgc",
        ],
    },
    "cpu_throttling": {
        "steps": [
            "Check CPU usage: `kubectl top pod <pod>`.",
            "Increase CPU limits: `resources.limits.cpu` in the pod spec.",
            "Profile the application for CPU-intensive code paths.",
            "Consider horizontal scaling (HPA) if CPU demand is consistently high.",
        ],
        "references": [
            "https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/",
        ],
    },
    "high_latency": {
        "steps": [
            "Identify the slowest operations from the log timestamps.",
            "Check downstream dependencies (database, cache, external APIs) for latency.",
            "Add distributed tracing (OpenTelemetry, Jaeger) to pinpoint bottlenecks.",
            "Optimise hot code paths with profiling.",
            "Consider caching frequently-accessed data.",
        ],
        "references": [
            "https://opentelemetry.io/docs/",
        ],
    },
    # -----------------------------------------------------------------------
    # Misc
    # -----------------------------------------------------------------------
    "deprecated_api": {
        "steps": [
            "Identify the deprecated API from the warning message.",
            "Consult the framework/library migration guide for the replacement API.",
            "Update the code to use the new API before the deprecated one is removed.",
            "Run tests after migrating to confirm behaviour is unchanged.",
        ],
        "references": [],
    },
    "retry_warning": {
        "steps": [
            "Identify what is being retried and why (network error, rate limit, etc.).",
            "Check the health of the target service.",
            "Review retry policy — ensure exponential back-off with jitter is used.",
            "Alert on excessive retries as a leading indicator of downstream failures.",
        ],
        "references": [],
    },
    "high_disk_usage": {
        "steps": [
            "Identify large directories: `du -sh /* 2>/dev/null | sort -rh | head -20`.",
            "Archive or delete old log files.",
            "Configure log rotation: `logrotate` on Linux.",
            "Set up disk usage alerts at 80% to act before reaching 100%.",
        ],
        "references": [],
    },
    "missing_config": {
        "steps": [
            "Identify the missing configuration key from the error message.",
            "Add the key to the appropriate config file, environment variable, or Kubernetes ConfigMap.",
            "Use configuration validation at startup to fail fast on missing required values.",
            "Document all required configuration keys in the project README.",
        ],
        "references": [],
    },
    "jenkins_unstable": {
        "steps": [
            "An unstable build usually means test failures without a build error.",
            "Check the Test Results page for flaky or consistently failing tests.",
            "Fix the failing tests or mark genuinely flaky ones with `@Ignore` and file a ticket.",
            "Configure post-build actions to send notifications on unstable status.",
        ],
        "references": [
            "https://www.jenkins.io/doc/book/pipeline/syntax/#post",
        ],
    },
    "unhandled_exception": {
        "steps": [
            "Read the full stack trace to identify the exception type and origin.",
            "Add proper error handling (try/except, try/catch) around the failing code.",
            "Validate input data before processing to catch edge cases.",
            "Add logging for the caught exception to aid future debugging.",
        ],
        "references": [],
    },
    "segfault": {
        "steps": [
            "Generate a core dump: `ulimit -c unlimited` then re-run the process.",
            "Analyse with GDB: `gdb <binary> <core>`.",
            "Check for buffer overflows, dangling pointers, or use-after-free bugs.",
            "Run with AddressSanitizer: `-fsanitize=address` during development.",
            "Check for out-of-date native libraries or mismatched versions.",
        ],
        "references": [],
    },
}

_FALLBACK: RemediationEntry = {
    "steps": [
        "Review the surrounding log context for more detail.",
        "Search the project issue tracker for similar errors.",
        "Consult the relevant official documentation.",
    ],
    "references": [],
}


def get_remediation(key: str) -> RemediationEntry:
    """Return remediation steps for the given issue key, or a generic fallback."""
    return REMEDIATION_DB.get(key, _FALLBACK)
