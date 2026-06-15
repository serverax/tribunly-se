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
    http_req_failed: ["rate<0.05"],
    http_req_duration: ["p(95)<1000"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://127.0.0.1:8000";

export default function () {
  const home = http.get(`${BASE_URL}/`);
  check(home, { "homepage 200": (r) => r.status === 200 });

  const health = http.get(`${BASE_URL}/health`);
  check(health, { "health 200": (r) => r.status === 200 });

  const login = http.post(
    `${BASE_URL}/api/auth/login`,
    JSON.stringify({ email: `load-${__VU}-${__ITER}@example.invalid`, password: "not-a-real-password" }),
    { headers: { "Content-Type": "application/json" } },
  );
  check(login, { "login rejects bad creds safely": (r) => [400, 401, 404, 422].includes(r.status) });

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
    { headers: { "Content-Type": "application/json" } },
  );
  check(assessment, { "assessment responds": (r) => r.status === 200 });

  const saveCase = http.post(
    `${BASE_URL}/cases`,
    JSON.stringify({ claim_type: "unfair_dismissal", facts: {}, assessment: {}, key_dates: {} }),
    { headers: { "Content-Type": "application/json" } },
  );
  check(saveCase, { "anonymous save blocked": (r) => [401, 403].includes(r.status) });

  const docGate = http.post(
    `${BASE_URL}/api/documents/generate`,
    JSON.stringify({
      case_id: "00000000-0000-0000-0000-000000000000",
      document_type: "particulars_of_claim",
      confirmed_facts: {},
    }),
    { headers: { "Content-Type": "application/json" } },
  );
  check(docGate, { "anonymous document gate blocked": (r) => [401, 403].includes(r.status) });

  sleep(1);
}
