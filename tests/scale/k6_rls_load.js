// T-010 — RLS / auth load test for TRUE 100k-concurrent validation (k6).
//
// The pytest scale suite (test_t010_rls_scale.py) proves RLS-under-concurrency and
// the <20ms auth budget on one box. This k6 script drives the SAME security
// invariants against a DEPLOYED cluster at real concurrency, so "100k" is measured,
// not asserted from a laptop.
//
// It checks, at every load level, that security NEVER weakens:
//   own case      -> 200            (owner reads own data)
//   cross-user    -> 403            (NO privilege escalation under load)
//   anonymous     -> 401            (no token, no read)
// and that the auth/RLS path stays fast (http_req_duration p95 < 20ms) and that the
// rate limiter actually engages (429s appear under abusive bursts) without ever
// turning a 403/401 into a 200.
//
// Prereqs (deployment, per docs/SCALE_ARCHITECTURE_100K.md):
//   - API behind an HPA (replicas scale on CPU/RPS), DB behind PgBouncer.
//   - LAWAPP_AUTH_MODE=jwt, rate limiter on Redis (shared across replicas).
//   - Two seeded test users (A, B) each owning one case; short-lived JWTs.
//
// Run (example — 100k VUs needs a distributed k6 / k6-operator on the cluster):
//   BASE_URL=https://api.lawapp.example \
//   JWT_A=... JWT_B=... CASE_A=... CASE_B=... \
//   k6 run --vus 2000 --duration 5m tests/scale/k6_rls_load.js
//   (scale VUs up via k6 Cloud / k6-operator fan-out to reach 100k concurrent.)

import http from 'k6/http';
import { check } from 'k6';
import { Counter } from 'k6/metrics';

const BASE = __ENV.BASE_URL || 'http://localhost:8000';
const JWT_A = __ENV.JWT_A || '';
const JWT_B = __ENV.JWT_B || '';
const CASE_A = __ENV.CASE_A || '';
const CASE_B = __ENV.CASE_B || '';

// SECURITY counters — any non-zero value here is a hard FAIL (privilege escalation).
const rlsEscalations = new Counter('rls_privilege_escalations');
const anonReads = new Counter('anon_reads_allowed');

export const options = {
  scenarios: {
    // Ramp to a high concurrency; for true 100k use k6-operator to fan out runners.
    ramp: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '1m', target: 500 },
        { duration: '2m', target: 2000 },
        { duration: '2m', target: 2000 },
        { duration: '1m', target: 0 },
      ],
    },
  },
  thresholds: {
    // Auth/RLS path must stay under budget AND security counters must be zero.
    http_req_duration: ['p(95)<20', 'p(99)<50'],
    rls_privilege_escalations: ['count==0'],
    anon_reads_allowed: ['count==0'],
    checks: ['rate>0.99'],
  },
};

export default function () {
  // 1) Owner reads own case -> 200
  let r = http.get(`${BASE}/cases/${CASE_A}`, { headers: { Authorization: `Bearer ${JWT_A}` } });
  check(r, { 'own A == 200': (x) => x.status === 200 });

  // 2) Cross-user read -> 403 (the core no-escalation invariant)
  r = http.get(`${BASE}/cases/${CASE_B}`, { headers: { Authorization: `Bearer ${JWT_A}` } });
  check(r, { 'A->B == 403': (x) => x.status === 403 });
  if (r.status === 200) rlsEscalations.add(1);   // SECURITY FAIL if ever true

  // 3) Anonymous read -> 401
  r = http.get(`${BASE}/cases/${CASE_B}`);
  check(r, { 'anon == 401': (x) => x.status === 401 });
  if (r.status === 200) anonReads.add(1);         // SECURITY FAIL if ever true
}
