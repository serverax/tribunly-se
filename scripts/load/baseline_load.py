#!/usr/bin/env python3
"""LawApp baseline load harness (T-014).

Honest, local, scaled-down load probe to surface code-level bottlenecks BEFORE the
full distributed 100k test (which needs the AKS cluster + load-gen fleet — owner-blocked).

Measures P50/P95/P99 latency, throughput, and error rate against one endpoint using a
bounded thread pool. NOT a 100k test — it documents current single-node capacity and the
latency profile that justifies pooling/async/replicas per docs/SCALE_ARCHITECTURE_100K.md.

Usage:
  python scripts/load/baseline_load.py --url http://localhost:8000/health --concurrency 100 --requests 2000
  python scripts/load/baseline_load.py --url http://localhost:8000/api/brain/trace --method POST \
      --concurrency 20 --requests 200 --json-body '{"message":"unfair dismissal?","facts":{},"jurisdiction":"england-wales"}' \
      --header "X-User-ID: loadtest"
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib import request as _req
from urllib.error import HTTPError, URLError


def _one(url: str, method: str, body, headers: dict, timeout: float):
    t0 = time.perf_counter()
    r = _req.Request(url, data=body, method=method, headers=headers)
    try:
        with _req.urlopen(r, timeout=timeout) as resp:
            resp.read()
            return (time.perf_counter() - t0) * 1000.0, resp.status, None
    except HTTPError as e:
        return (time.perf_counter() - t0) * 1000.0, e.code, f"HTTP{e.code}"
    except (URLError, TimeoutError, OSError) as e:
        return (time.perf_counter() - t0) * 1000.0, 0, type(e).__name__


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--url", required=True)
    p.add_argument("--method", default="GET")
    p.add_argument("--concurrency", type=int, default=100)
    p.add_argument("--requests", type=int, default=2000)
    p.add_argument("--json-body", default=None)
    p.add_argument("--header", action="append", default=[])
    p.add_argument("--timeout", type=float, default=30.0)
    p.add_argument("--out", default=None)
    a = p.parse_args()

    headers = {"Content-Type": "application/json"}
    for h in a.header:
        k, _, v = h.partition(":")
        headers[k.strip()] = v.strip()
    body = a.json_body.encode() if a.json_body else None

    lat = []
    codes = {}
    errs = {}
    wall0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=a.concurrency) as ex:
        futs = [ex.submit(_one, a.url, a.method, body, headers, a.timeout)
                for _ in range(a.requests)]
        for f in as_completed(futs):
            ms, code, err = f.result()
            lat.append(ms)
            codes[code] = codes.get(code, 0) + 1
            if err:
                errs[err] = errs.get(err, 0) + 1
    wall = time.perf_counter() - wall0

    lat.sort()
    def pct(q):
        if not lat:
            return 0.0
        return lat[min(len(lat) - 1, int(q * len(lat)))]
    ok = sum(v for c, v in codes.items() if 200 <= c < 400)
    total = len(lat)
    result = {
        "url": a.url, "method": a.method,
        "concurrency": a.concurrency, "requests": total,
        "wall_seconds": round(wall, 3),
        "throughput_rps": round(total / wall, 1) if wall else 0,
        "ok": ok, "errors": total - ok,
        "error_rate_pct": round(100 * (total - ok) / total, 3) if total else 0,
        "latency_ms": {
            "p50": round(pct(0.50), 1), "p95": round(pct(0.95), 1),
            "p99": round(pct(0.99), 1), "max": round(max(lat), 1) if lat else 0,
            "mean": round(statistics.fmean(lat), 1) if lat else 0,
        },
        "status_codes": codes, "error_types": errs,
    }
    out = json.dumps(result, indent=2)
    print(out)
    if a.out:
        with open(a.out, "w") as fh:
            fh.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
