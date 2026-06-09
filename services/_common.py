"""Shared service factory for lawapp distributed services.

Each extracted service is a thin FastAPI app that wraps the EXISTING, tested
backend/core logic (no logic duplication, no fake responses). This factory
provides the mandatory /health and /ready endpoints, a trace_id middleware, and
structured-JSON logging — identical across every service.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

from fastapi import FastAPI, Request

TRACE_HEADER = "X-Trace-ID"


def _structured_log(service: str, **fields) -> None:
    rec = {"service": service, **fields}
    logging.getLogger(service).info(json.dumps(rec, default=str))


def _db_ready() -> bool:
    try:
        from ingestion.db import get_connection
        c = get_connection()
        try:
            with c.cursor() as cur:
                cur.execute("SELECT 1")
        finally:
            c.close()
        return True
    except Exception:
        return False


def get_trace_id(request: Request) -> str:
    """The trace id for the current request: the inbound X-Trace-ID if the caller
    supplied one, otherwise a fresh uuid. Matches the middleware's own logic so a
    handler and its middleware always agree on the same id."""
    return request.headers.get("x-trace-id") or str(uuid.uuid4())


def call_service(
    base_url: str,
    method: str,
    path: str,
    *,
    json_body: dict | None = None,
    trace_id: str,
    timeout: float = 30.0,
    client_factory: Any = None,
) -> Any:
    """Make a downstream service call that PROPAGATES the trace id.

    The same `trace_id` is injected as the `X-Trace-ID` request header so a single
    logical request keeps one correlation id across every service it touches.

    Production: `client_factory=None` → a real sync `httpx.Client` over the network.

    Tests: pass `client_factory=lambda base: TestClient(other_service.app)` (Starlette
    TestClient bridges the ASGI app to a synchronous transport). The call then runs the
    FULL downstream app — middleware included — in-process, a real cross-service request
    with no network, while this function still injects the propagated trace header.

    Returns a response object exposing `.status_code`, `.headers` (the echoed
    `X-Trace-ID`), and `.json()`. Never swallows downstream failures.
    """
    headers = {TRACE_HEADER: trace_id}
    if client_factory is not None:
        client = client_factory(base_url)
        return client.request(method, path, json=json_body, headers=headers)
    import httpx

    with httpx.Client(base_url=base_url, timeout=timeout) as client:
        return client.request(method, path, json=json_body, headers=headers)


def create_service(service_name: str, *, needs_db: bool = True) -> FastAPI:
    """Build a FastAPI app with the standard health/ready/trace_id contract."""
    app = FastAPI(title=service_name, version="1.0.0")

    @app.middleware("http")
    async def _trace(request: Request, call_next):
        trace_id = request.headers.get("x-trace-id") or str(uuid.uuid4())
        t0 = time.monotonic()
        response = await call_next(request)
        response.headers["X-Trace-ID"] = trace_id
        _structured_log(service_name, trace_id=trace_id, route=request.url.path,
                        status=response.status_code,
                        latency_ms=round((time.monotonic() - t0) * 1000, 1))
        return response

    @app.get("/health", include_in_schema=False)
    def health():
        return {"status": "healthy", "service": service_name}

    @app.get("/ready", include_in_schema=False)
    def ready():
        if needs_db and not _db_ready():
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=503,
                                content={"status": "not_ready", "service": service_name, "db": "disconnected"})
        return {"status": "ready", "service": service_name}

    return app
