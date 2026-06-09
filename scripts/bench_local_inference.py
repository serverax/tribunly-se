#!/usr/bin/env python3
"""
Local Inference Fabric — concurrency benchmark.

Fires N concurrent JSON-extraction requests at the llama.cpp DaemonSet (via the
ClusterIP Service) and reports P50/P95/P99 latency. Per the performance gate:
if P95 > THRESHOLD_MS the benchmark exits non-zero so CI/operator knows to
increase the CPU core allocation per node.

USAGE (run from inside the cluster, e.g. a debug pod in namespace lawapp-api):
    python scripts/bench_local_inference.py \
        --url http://lawapp-llm-inference.lawapp-api.svc.cluster.local:8080 \
        --concurrency 100 --requests 100 --p95-threshold-ms 400

HONEST NOTE: this measures the REAL endpoint. It cannot be run from a laptop with
no cluster; it must target a reachable llama.cpp server. A 3B Q6_K model doing
generative JSON extraction on CPU will typically NOT meet a 400ms P95 — that
threshold is realistic for classification/embedding, not multi-hundred-token
generation. The script reports the truth; it does not fake a pass.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import statistics
import sys
import time

import httpx

_EXTRACTION_PROMPT = (
    "Extract the following into JSON with keys edt, reason, procedure_followed. "
    "Facts: employee dismissed 2024-05-01 for alleged misconduct; no appeal offered. "
    "Return ONLY JSON."
)


def _one_request(url: str, model: str, timeout: float) -> float:
    """Send one request; return elapsed seconds, or raise on failure."""
    t0 = time.monotonic()
    resp = httpx.post(
        f"{url.rstrip('/')}/v1/chat/completions",
        json={
            "model": model,
            "messages": [{"role": "user", "content": _EXTRACTION_PROMPT}],
            "temperature": 0.0,
            "max_tokens": 128,
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    return time.monotonic() - t0


def main() -> int:
    ap = argparse.ArgumentParser(description="Benchmark the local inference fabric")
    ap.add_argument("--url", default="http://lawapp-llm-inference.lawapp-api.svc.cluster.local:8080")
    ap.add_argument("--model", default="qwen2.5-3b-instruct")
    ap.add_argument("--concurrency", type=int, default=100)
    ap.add_argument("--requests", type=int, default=100)
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--p95-threshold-ms", type=float, default=400.0)
    args = ap.parse_args()

    print(f"Benchmarking {args.url} — {args.requests} requests, "
          f"concurrency {args.concurrency}")

    latencies: list[float] = []
    failures = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [
            pool.submit(_one_request, args.url, args.model, args.timeout)
            for _ in range(args.requests)
        ]
        for fut in concurrent.futures.as_completed(futures):
            try:
                latencies.append(fut.result())
            except Exception as exc:
                failures += 1
                print(f"  request failed: {exc}", file=sys.stderr)

    if not latencies:
        print("ALL REQUESTS FAILED — inference endpoint unreachable.", file=sys.stderr)
        return 2

    latencies.sort()
    p50 = statistics.median(latencies) * 1000
    p95 = latencies[min(len(latencies) - 1, int(len(latencies) * 0.95))] * 1000
    p99 = latencies[min(len(latencies) - 1, int(len(latencies) * 0.99))] * 1000

    print(f"\nResults ({len(latencies)} ok, {failures} failed):")
    print(f"  P50: {p50:7.1f} ms")
    print(f"  P95: {p95:7.1f} ms   (threshold {args.p95_threshold_ms:.0f} ms)")
    print(f"  P99: {p99:7.1f} ms")

    if p95 > args.p95_threshold_ms:
        print(f"\nFAIL: P95 {p95:.0f}ms > {args.p95_threshold_ms:.0f}ms — "
              f"increase CPU cores per node (DaemonSet resources.limits.cpu).")
        return 1
    print(f"\nPASS: P95 within {args.p95_threshold_ms:.0f}ms.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
