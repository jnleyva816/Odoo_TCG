"""Monitoring and observability utilities."""

import logging
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

try:
    from prometheus_client import (
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


@dataclass
class MetricsCollector:
    """Centralized metrics collection.

    Provides a unified interface for collecting application metrics.
    Supports Prometheus format export.
    """

    registry: "CollectorRegistry | None" = field(
        default_factory=lambda: CollectorRegistry() if PROMETHEUS_AVAILABLE else None
    )
    _enabled: bool = PROMETHEUS_AVAILABLE

    def __post_init__(self):
        """Initialize metrics."""
        if not self._enabled:
            return

        # HTTP metrics
        self.http_requests_total = Counter(
            "http_requests_total",
            "Total HTTP requests",
            ["method", "endpoint", "status"],
            registry=self.registry,
        )

        self.http_request_duration_seconds = Histogram(
            "http_request_duration_seconds",
            "HTTP request latency",
            ["method", "endpoint"],
            registry=self.registry,
            buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0),
        )

        # Authentication metrics
        self.login_attempts_total = Counter(
            "login_attempts_total",
            "Total login attempts",
            ["status"],
            registry=self.registry,
        )

        self.active_sessions = Gauge(
            "active_sessions_total",
            "Number of active user sessions",
            registry=self.registry,
        )

        # Cache metrics
        self.cache_hits_total = Counter(
            "cache_hits_total",
            "Total cache hits",
            ["cache_name"],
            registry=self.registry,
        )

        self.cache_misses_total = Counter(
            "cache_misses_total",
            "Total cache misses",
            ["cache_name"],
            registry=self.registry,
        )

        # Rate limiting metrics
        self.rate_limit_hits_total = Counter(
            "rate_limit_hits_total",
            "Total rate limit violations",
            ["endpoint"],
            registry=self.registry,
        )

        # Odoo metrics
        self.odoo_requests_total = Counter(
            "odoo_requests_total",
            "Total Odoo XML-RPC requests",
            ["model", "method", "status"],
            registry=self.registry,
        )

        self.odoo_request_duration_seconds = Histogram(
            "odoo_request_duration_seconds",
            "Odoo request latency",
            ["model", "method"],
            registry=self.registry,
            buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
        )

        # Database metrics
        self.db_queries_total = Counter(
            "db_queries_total",
            "Total database queries",
            ["operation"],
            registry=self.registry,
        )

        # Security metrics
        self.security_events_total = Counter(
            "security_events_total",
            "Security-related events",
            ["event_type"],
            registry=self.registry,
        )

        # Circuit breaker metrics
        self.circuit_breaker_state = Gauge(
            "circuit_breaker_state",
            "Circuit breaker state (0=closed, 1=open, 2=half-open)",
            ["service"],
            registry=self.registry,
        )

    def record_http_request(self, method: str, endpoint: str, status: int, duration: float):
        """Record HTTP request metrics."""
        if not self._enabled:
            return

        self.http_requests_total.labels(
            method=method, endpoint=endpoint, status=status
        ).inc()
        self.http_request_duration_seconds.labels(
            method=method, endpoint=endpoint
        ).observe(duration)

    def record_login_attempt(self, success: bool):
        """Record login attempt."""
        if not self._enabled:
            return

        status = "success" if success else "failure"
        self.login_attempts_total.labels(status=status).inc()

    def record_cache_access(self, cache_name: str, hit: bool):
        """Record cache access."""
        if not self._enabled:
            return

        if hit:
            self.cache_hits_total.labels(cache_name=cache_name).inc()
        else:
            self.cache_misses_total.labels(cache_name=cache_name).inc()

    def record_rate_limit_hit(self, endpoint: str):
        """Record rate limit violation."""
        if not self._enabled:
            return

        self.rate_limit_hits_total.labels(endpoint=endpoint).inc()

    def record_odoo_request(self, model: str, method: str, status: str, duration: float):
        """Record Odoo request."""
        if not self._enabled:
            return

        self.odoo_requests_total.labels(model=model, method=method, status=status).inc()
        self.odoo_request_duration_seconds.labels(model=model, method=method).observe(duration)

    def record_security_event(self, event_type: str):
        """Record security event."""
        if not self._enabled:
            return

        self.security_events_total.labels(event_type=event_type).inc()

    def set_circuit_breaker_state(self, service: str, state: str):
        """Set circuit breaker state."""
        if not self._enabled:
            return

        state_map = {"CLOSED": 0, "OPEN": 1, "HALF_OPEN": 2}
        self.circuit_breaker_state.labels(service=service).set(state_map.get(state, 0))

    def export_metrics(self) -> bytes:
        """Export metrics in Prometheus format."""
        if not self._enabled:
            return b""

        return generate_latest(self.registry)


# Global metrics collector
_metrics_collector = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """Get global metrics collector."""
    return _metrics_collector


@contextmanager
def track_time(metric_name: str, labels: dict[str, str] | None = None):
    """Context manager to track execution time.

    Usage:
        with track_time("database_query", {"operation": "select"}):
            result = await db.execute(query)
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        duration = time.perf_counter() - start
        logging.debug(f"{metric_name} took {duration:.3f}s", extra=labels or {})


class StructuredLogger:
    """Structured logging with context.

    Provides consistent log formatting with additional context fields.
    """

    def __init__(self, name: str, default_context: dict[str, Any] | None = None):
        self.logger = logging.getLogger(name)
        self.default_context = default_context or {}

    def _log(self, level: int, message: str, **context):
        """Log with structured context."""
        full_context = {**self.default_context, **context}
        self.logger.log(level, message, extra=full_context)

    def debug(self, message: str, **context):
        """Log debug message."""
        self._log(logging.DEBUG, message, **context)

    def info(self, message: str, **context):
        """Log info message."""
        self._log(logging.INFO, message, **context)

    def warning(self, message: str, **context):
        """Log warning message."""
        self._log(logging.WARNING, message, **context)

    def error(self, message: str, **context):
        """Log error message."""
        self._log(logging.ERROR, message, **context)

    def critical(self, message: str, **context):
        """Log critical message."""
        self._log(logging.CRITICAL, message, **context)


class AuditLogger:
    """Audit logging for security-sensitive operations."""

    def __init__(self):
        self.logger = StructuredLogger("audit")

    def log_login(self, username: str, ip: str, success: bool, reason: str = ""):
        """Log login attempt."""
        self.logger.info(
            "Login attempt",
            event="login",
            username=username,
            ip=ip,
            success=success,
            reason=reason,
        )

        # Record metric
        get_metrics_collector().record_login_attempt(success)

        # Record security event
        if not success:
            get_metrics_collector().record_security_event("failed_login")

    def log_permission_denied(self, user_id: int, resource: str, action: str, ip: str):
        """Log permission denied."""
        self.logger.warning(
            "Permission denied",
            event="permission_denied",
            user_id=user_id,
            resource=resource,
            action=action,
            ip=ip,
        )

        get_metrics_collector().record_security_event("permission_denied")

    def log_data_access(self, user_id: int, resource_type: str, resource_id: int, action: str):
        """Log data access."""
        self.logger.info(
            "Data access",
            event="data_access",
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
        )

    def log_data_modification(
        self, user_id: int, resource_type: str, resource_id: int, action: str, changes: dict
    ):
        """Log data modification."""
        self.logger.info(
            "Data modification",
            event="data_modification",
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            changes=changes,
        )

    def log_security_event(self, event_type: str, details: dict[str, Any]):
        """Log generic security event."""
        self.logger.warning(
            f"Security event: {event_type}",
            event="security",
            event_type=event_type,
            **details,
        )

        get_metrics_collector().record_security_event(event_type)


# Global audit logger
_audit_logger = AuditLogger()


def get_audit_logger() -> AuditLogger:
    """Get global audit logger."""
    return _audit_logger


class HealthChecker:
    """Health check utilities for dependencies."""

    def __init__(self):
        self.checks: dict[str, Any] = {}
        self._check_results: dict[str, dict[str, Any]] = {}

    def register_check(self, name: str, check_func):
        """Register a health check function."""
        self.checks[name] = check_func

    async def run_checks(self) -> dict[str, Any]:
        """Run all registered health checks."""
        results = {}

        for name, check_func in self.checks.items():
            try:
                start = time.perf_counter()
                result = await check_func()
                duration = time.perf_counter() - start

                results[name] = {
                    "status": "healthy" if result else "unhealthy",
                    "latency_ms": round(duration * 1000, 2),
                }
            except Exception as e:
                results[name] = {
                    "status": "unhealthy",
                    "error": str(e),
                }

        self._check_results = results
        return results

    @property
    def is_healthy(self) -> bool:
        """Check if all dependencies are healthy."""
        return all(r.get("status") == "healthy" for r in self._check_results.values())

    @property
    def is_ready(self) -> bool:
        """Check if service is ready to accept traffic."""
        # Must have at least checked once and be healthy
        return bool(self._check_results) and self.is_healthy


# Global health checker
_health_checker = HealthChecker()


def get_health_checker() -> HealthChecker:
    """Get global health checker."""
    return _health_checker


class RequestTracer:
    """Request tracing for distributed systems."""

    def __init__(self):
        self._traces: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def start_span(self, request_id: str, span_name: str, **attributes):
        """Start a new span for tracing."""
        span = {
            "name": span_name,
            "start_time": time.time(),
            "attributes": attributes,
        }

        self._traces[request_id].append(span)
        return span

    def end_span(self, request_id: str, span: dict[str, Any], **attributes):
        """End a span and record duration."""
        span["end_time"] = time.time()
        span["duration_ms"] = (span["end_time"] - span["start_time"]) * 1000
        span["attributes"].update(attributes)

    def get_trace(self, request_id: str) -> list[dict[str, Any]]:
        """Get all spans for a request."""
        return self._traces.get(request_id, [])

    def clear_trace(self, request_id: str):
        """Clear trace data for a request."""
        if request_id in self._traces:
            del self._traces[request_id]


# Global request tracer
_request_tracer = RequestTracer()


def get_request_tracer() -> RequestTracer:
    """Get global request tracer."""
    return _request_tracer


class AlertManager:
    """Alert management for critical events."""

    def __init__(self):
        self.logger = StructuredLogger("alerts")
        self._alert_thresholds: dict[str, int] = {}
        self._alert_counts: dict[str, int] = defaultdict(int)

    def set_threshold(self, alert_type: str, threshold: int):
        """Set alert threshold."""
        self._alert_thresholds[alert_type] = threshold

    def trigger_alert(self, alert_type: str, message: str, **context):
        """Trigger an alert."""
        self._alert_counts[alert_type] += 1

        # Check if threshold exceeded
        threshold = self._alert_thresholds.get(alert_type, 1)
        if self._alert_counts[alert_type] >= threshold:
            self.logger.critical(
                f"ALERT: {message}",
                alert_type=alert_type,
                count=self._alert_counts[alert_type],
                **context,
            )

            # Reset counter after alerting
            self._alert_counts[alert_type] = 0

            # Here you would integrate with alerting systems:
            # - Send email via SMTP
            # - Post to Slack webhook
            # - Trigger PagerDuty incident
            # - Send SMS via Twilio
            # etc.

    def reset_counter(self, alert_type: str):
        """Reset alert counter."""
        self._alert_counts[alert_type] = 0


# Global alert manager
_alert_manager = AlertManager()


def get_alert_manager() -> AlertManager:
    """Get global alert manager."""
    return _alert_manager
