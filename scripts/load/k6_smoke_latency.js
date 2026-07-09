import http from "k6/http";
import { check } from "k6";

export const options = {
  scenarios: {
    smoke: {
      executor: "shared-iterations",
      vus: 1,
      iterations: 5,
      maxDuration: "5m",
    },
  },
  thresholds: {
    "http_req_duration{type:health}": ["p(95)<500"],
    "http_req_duration{type:assess}": ["p(95)<60000"],
    "http_req_failed": ["rate<0.1"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://backend:8000";

export default function () {
  const health = http.get(`${BASE_URL}/health`, {
    tags: { type: "health" },
  });
  check(health, { "health 200": (r) => r.status === 200 });

  const assess = http.post(
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
        jurisdiction: "EW",
      },
    }),
    {
      headers: { "Content-Type": "application/json" },
      tags: { type: "assess" },
      timeout: "120s",
    }
  );
  check(assess, {
    "assess 200": (r) => r.status === 200,
    "assess has citations": (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.citations && body.citations.length > 0;
      } catch (_) {
        return false;
      }
    },
  });
}
