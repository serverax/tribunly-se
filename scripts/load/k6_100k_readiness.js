import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  scenarios: {
    smoke_readiness: {
      executor: "ramping-vus",
      stages: [
        { duration: "30s", target: 25 },
        { duration: "1m", target: 50 },
        { duration: "30s", target: 0 },
      ],
      gracefulRampDown: "10s",
    },
  },
  thresholds: {
    "http_req_duration{type:assess}": ["p(95)<3000"],
    "http_req_failed{type:assess}": ["rate<0.02"],
    "checks{check:assessment responds 200}": ["rate>0.90"],
    "checks{check:scope-cut module returns not_covered}": ["rate>0.95"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://127.0.0.1:8000";
// Backend must run with LAWAPP_LOAD_TEST_MODE=1 (or LAWAPP_ASSESS_RATE_LIMIT) so
// POST /assess is not capped at 30/min per client IP  -  otherwise 50 VUs hit 429.
const EXPECTED_AUTH_STATUSES = [401, 402, 403];
const EXPECTED_REJECT_STATUSES = [400, 401, 402, 403, 404, 422];

function isExpectedStatus(status, allowed) {
  return allowed.includes(status);
}

export default function () {
  const home = http.get(`${BASE_URL}/`);
  check(home, { "homepage 200": (r) => r.status === 200 });

  const health = http.get(`${BASE_URL}/health`);
  check(health, { "health 200": (r) => r.status === 200 });

  const login = http.post(
    `${BASE_URL}/api/auth/login`,
    JSON.stringify({ email: `load-${__VU}-${__ITER}@example.invalid`, password: "not-a-real-password" }),
    { headers: { "Content-Type": "application/json" }, tags: { type: "auth_gate" } },
  );
  check(login, {
    "login rejects bad creds safely": (r) => isExpectedStatus(r.status, EXPECTED_REJECT_STATUSES),
  });

  const assessment = http.post(
    `${BASE_URL}/assess`,
    JSON.stringify({
      query: "I was dismissed after five years with no hearing",
      jurisdiction: "EW",
      use_model: false,
      facts: {
        claim_type: "unfair_dismissal",
        edt: "2026-05-01",
        service_start_date: "2020-01-01",
        reason_for_dismissal: "conduct",
        was_procedure_followed: false,
        weekly_pay: 600,
      },
    }),
    { headers: { "Content-Type": "application/json" }, tags: { type: "assess" } },
  );
  check(assessment, {
    "assessment responds 200": (r) => r.status === 200,
    "assessment has trace_id": (r) => {
      try {
        const body = r.json();
        return typeof body.trace_id === "string" && body.trace_id.length > 8;
      } catch (_) {
        return false;
      }
    },
  });

  const scopeCut = http.post(
    `${BASE_URL}/api/workflow/diagnosis`,
    JSON.stringify({
      claim_type: "discrimination",
      jurisdiction: "EW",
      facts: { discriminatory_event_date: "2026-05-01", protected_characteristic: "sex" },
    }),
    { headers: { "Content-Type": "application/json" } },
  );
  check(scopeCut, {
    "scope-cut module returns not_covered": (r) => {
      if (r.status !== 200) return false;
      try {
        const body = r.json();
        return body.status === "not_covered" && body.claim_type === "discrimination";
      } catch (_) {
        return false;
      }
    },
  });

  const saveCase = http.post(
    `${BASE_URL}/cases`,
    JSON.stringify({ claim_type: "unfair_dismissal", facts: {}, assessment: {}, key_dates: {} }),
    { headers: { "Content-Type": "application/json" } },
  );
  check(saveCase, {
    "anonymous save blocked (401/403)": (r) => isExpectedStatus(r.status, EXPECTED_AUTH_STATUSES),
  });

  const docGate = http.post(
    `${BASE_URL}/api/documents/generate`,
    JSON.stringify({
      case_id: "00000000-0000-0000-0000-000000000000",
      document_type: "particulars_of_claim",
      confirmed_facts: {},
    }),
    { headers: { "Content-Type": "application/json" } },
  );
  check(docGate, {
    "anonymous document gate blocked (401/402/403)": (r) => isExpectedStatus(r.status, EXPECTED_AUTH_STATUSES),
  });

  sleep(1);
}
