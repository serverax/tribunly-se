"""
OpenTelemetry observability (order §18).

Provides one correlated request id (== Brain trace_id == response X-Trace-ID ==
log field == outbox/audit trace_id == OTEL span attribute) plus real metric
counters and a /metrics + /ready endpoint.

Export sink (chosen by owner): OTLP if OTEL_EXPORTER_OTLP_ENDPOINT is set,
otherwise ConsoleSpanExporter for local proof. Degrades to request-id + counters
only if the OpenTelemetry SDK is not installed  -  never breaks the app.

Secret/PII safety:
  * auth/cookie/api-key headers are NEVER recorded on spans or logs
  * span attributes carry IDs only, never user facts or payloads
"""

from __future__ import annotations

import logging
import os
import uuid
from contextvars import ContextVar
from typing import Optional

logger = logging.getLogger(__name__)

# ── Per-request correlation id ────────────────────────────────────────────────
_request_id: ContextVar[str] = ContextVar("lawapp_request_id", default="-")


def get_request_id() -> str:
    return _request_id.get()


# ── Counters (in-process snapshot is the source of truth for /metrics; the same
#    increments are mirrored to OTEL instruments for OTLP/console export) ───────
_COUNTERS: dict[str, float] = {
    "http_requests_total":                 0.0,
    "brain_assessments_total":             0.0,
    "rag_search_total":                    0.0,
    "legal_safety_blocks_total":           0.0,
    "citation_validation_failures_total":  0.0,
    "model_calls_total":                   0.0,
    "errors_total":                        0.0,
}
_otel_counters: dict[str, object] = {}
_OTEL_OK = False


def increment(name: str, amount: float = 1.0, attributes: Optional[dict] = None) -> None:
    _COUNTERS[name] = _COUNTERS.get(name, 0.0) + amount
    inst = _otel_counters.get(name)
    if inst is not None:
        try:
            inst.add(amount, attributes or {})
        except Exception:
            pass


def snapshot() -> dict:
    return dict(_COUNTERS)


def metrics_text() -> str:
    """Prometheus text exposition (0.0.4) of the real counters."""
    out = []
    for k, v in _COUNTERS.items():
        out.append(f"# TYPE {k} counter")
        out.append(f"{k} {v}")
    return "\n".join(out) + "\n"


# ── structured logging with request_id ────────────────────────────────────────
class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id.get()
        return True


def _install_logging() -> None:
    root = logging.getLogger()
    flt = _RequestIdFilter()
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s [request_id=%(request_id)s] %(name)s %(message)s"
    )
    if not root.handlers:
        h = logging.StreamHandler()
        h.setFormatter(fmt)
        h.addFilter(flt)
        root.addHandler(h)
        root.setLevel(os.getenv("LOG_LEVEL", "INFO"))
    else:
        for h in root.handlers:
            h.addFilter(flt)
            try:
                h.setFormatter(fmt)
            except Exception:
                pass


# ── request context ASGI middleware (same task as endpoint → contextvar
#    propagates to run_brain; sets response X-Request-ID / X-Trace-ID) ──────────
class RequestContextMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        from starlette.datastructures import Headers, MutableHeaders

        headers = Headers(scope=scope)
        rid = headers.get("x-request-id") or str(uuid.uuid4())
        token = _request_id.set(rid)
        increment("http_requests_total")

        async def _send(message):
            if message["type"] == "http.response.start":
                mh = MutableHeaders(scope=message)
                mh["X-Request-ID"] = rid
                mh["X-Trace-ID"] = rid
            await send(message)

        try:
            await self.app(scope, receive, _send)
        except Exception:
            increment("errors_total")
            raise
        finally:
            _request_id.reset(token)


# ── OTEL SDK init (degrades gracefully) ───────────────────────────────────────
def _init_otel(app) -> None:
    global _OTEL_OK
    try:
        from opentelemetry import metrics, trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,
            ConsoleSpanExporter,
            SimpleSpanProcessor,
        )
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        resource = Resource.create(
            {"service.name": os.getenv("OTEL_SERVICE_NAME", "lawapp-backend")}
        )
        provider = TracerProvider(resource=resource)
        endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
        if endpoint:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        elif os.getenv("OTEL_CONSOLE_EXPORT", "").lower() == "true":
            # Console span export ONLY when explicitly requested. Under frequent
            # kube-probe traffic the per-span console JSON floods stdout and starves
            # /health, causing probe timeouts and pod restarts  -  so default = OFF.
            provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
        # else: no span exporter (request-id + in-process counters remain).
        trace.set_tracer_provider(provider)

        # Metrics → OTEL counters (mirrored from increment()).
        try:
            from opentelemetry.sdk.metrics import MeterProvider
            from opentelemetry.sdk.metrics.export import (
                ConsoleMetricExporter,
                PeriodicExportingMetricReader,
            )
            reader = None
            if endpoint:
                from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
                reader = PeriodicExportingMetricReader(OTLPMetricExporter())
            elif os.getenv("OTEL_CONSOLE_EXPORT", "").lower() == "true":
                reader = PeriodicExportingMetricReader(
                    ConsoleMetricExporter(), export_interval_millis=15000
                )
            readers = [reader] if reader is not None else []
            metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=readers))
            meter = metrics.get_meter("lawapp")
            for name in _COUNTERS:
                _otel_counters[name] = meter.create_counter(name)
        except Exception as exc:
            logger.warning("OTEL metrics init skipped: %s", exc)

        # Do NOT capture request/response headers on spans (avoids secret leakage).
        FastAPIInstrumentor.instrument_app(app)
        _OTEL_OK = True
    except Exception as exc:
        logger.warning(
            "OpenTelemetry SDK unavailable  -  request-id + counters only: %s", exc
        )
        _OTEL_OK = False


def _install_routes(app) -> None:
    from fastapi import Response

    @app.get("/metrics", include_in_schema=False)
    def _metrics():
        return Response(content=metrics_text(), media_type="text/plain; version=0.0.4")

    @app.get("/ready", include_in_schema=False)
    def _ready():
        # Readiness FAILS (503) if a critical dependency (DB) is unreachable.
        try:
            from ingestion.db import get_connection

            conn = get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            finally:
                conn.close()
            return {"status": "ready", "db": "connected", "request_id": get_request_id()}
        except Exception:
            return Response(
                content='{"status":"not_ready","db":"disconnected"}',
                status_code=503,
                media_type="application/json",
            )


def record_brain_metrics(result: dict) -> None:
    """Derive Brain counters from a run_brain() result and correlate the Brain
    trace_id onto the active OTEL span. IDs only  -  no user facts touched."""
    try:
        trace = result.get("trace", {}) or {}
        status = (result.get("assessment", {}) or {}).get("status", "unknown")
        increment("brain_assessments_total", 1, {"status": status})

        if (result.get("safety", {}) or {}).get("blocked"):
            increment("legal_safety_blocks_total")

        failed = trace.get("citations_failed", 0) or 0
        if failed:
            increment("citation_validation_failures_total", failed)

        names = {s.get("step") for s in trace.get("steps", []) if s}
        if trace.get("sources_retrieved") or any(
            n and ("search" in n or "retriev" in n or "rag" in n) for n in names
        ):
            increment("rag_search_total")
        if "generate_draft" in names:
            increment("model_calls_total")

        if _OTEL_OK and trace.get("trace_id"):
            from opentelemetry import trace as _t

            _t.get_current_span().set_attribute("lawapp.trace_id", trace["trace_id"])
    except Exception as exc:
        logger.debug("record_brain_metrics skipped: %s", exc)


def setup_telemetry(app) -> None:
    _install_logging()
    _init_otel(app)
    app.add_middleware(RequestContextMiddleware)
    _install_routes(app)
    logger.info(
        "telemetry configured (otel_sdk=%s, otlp_endpoint=%s)",
        _OTEL_OK,
        bool(os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")),
    )
