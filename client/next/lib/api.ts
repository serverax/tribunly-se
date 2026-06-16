import type {
  DeadlineCalcRequest,
  DeadlineCalcResponse,
  DiagnosisRequest,
  StructuredAssessment,
} from "@/types/assessment";
import type { CreateCaseRequest, LawAppCase } from "@/types/case";
import { fetchWithAuth } from "@/lib/auth";

/** Server-side absolute base; browser uses same-origin rewrites. */
export const API_BASE =
  typeof window === "undefined"
    ? (process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000")
    : "";

/** Optional NestJS control-plane (:3001). Server-side only; browser should use rewrites if added. */
export const CONTROL_PLANE_BASE =
  typeof window === "undefined"
    ? process.env.NEXT_PUBLIC_CONTROL_PLANE_URL?.replace(/\/$/, "")
    : undefined;

function apiPath(path: string): string {
  if (API_BASE) return `${API_BASE}${path}`;
  return path;
}

function controlPlanePath(path: string): string {
  if (!CONTROL_PLANE_BASE) return apiPath(path);
  return `${CONTROL_PLANE_BASE}${path}`;
}

export type HealthResponse = {
  status?: string;
  service?: string;
};

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(apiPath("/health"), { cache: "no-store" });
  if (!res.ok) throw new Error(`Health check failed: ${res.status}`);
  return res.json();
}

export async function runControlPlaneProcess(payload: {
  claim_type: string;
  facts?: string | Record<string, unknown>;
  query?: string;
  jurisdiction?: string;
}): Promise<Record<string, unknown>> {
  const res = await fetch(controlPlanePath("/api/process"), {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Control plane process failed: ${res.status}`);
  return res.json();
}

/**
 * Diagnosis: use NestJS control plane when NEXT_PUBLIC_CONTROL_PLANE_URL is set,
 * otherwise call FastAPI /api/diagnosis (Brain + CitationGuard).
 */
export async function runDiagnosis(
  body: DiagnosisRequest,
): Promise<StructuredAssessment> {
  const res = await fetch(apiPath("/api/diagnosis"), {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query: body.query,
      facts: body.facts,
      jurisdiction: body.jurisdiction ?? "EW",
      use_model: body.use_model ?? true,
      client_deadline: body.client_deadline,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Diagnosis failed: ${res.status}`);
  }
  return res.json();
}

export async function runClaimAssessment(
  facts: string | Record<string, unknown>,
  matterId?: string,
): Promise<Record<string, unknown>> {
  const res = await fetch(apiPath("/api/features/claim-assessment"), {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ facts, matter_id: matterId }),
  });
  if (!res.ok) throw new Error(`Claim assessment failed: ${res.status}`);
  return res.json();
}

export async function calculateDeadline(
  body: DeadlineCalcRequest,
): Promise<DeadlineCalcResponse> {
  const res = await fetch(apiPath("/api/deadline/calc"), {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Deadline calc failed: ${res.status}`);
  }
  return res.json();
}

export async function listCases(): Promise<LawAppCase[]> {
  const res = await fetchWithAuth(apiPath("/cases"));
  if (!res.ok) throw new Error(`Cases list failed: ${res.status}`);
  const data = await res.json();
  if (Array.isArray(data)) return data;
  if (data?.cases) return data.cases;
  return [];
}

export async function getCase(caseId: string): Promise<LawAppCase> {
  const res = await fetchWithAuth(apiPath(`/cases/${caseId}`));
  if (!res.ok) throw new Error(`Case fetch failed: ${res.status}`);
  return res.json();
}

export async function createCase(body: CreateCaseRequest): Promise<LawAppCase> {
  const res = await fetchWithAuth(apiPath("/cases"), {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Create case failed: ${res.status}`);
  return res.json();
}

export async function createPaymentSession(caseId: string): Promise<Record<string, unknown>> {
  const res = await fetchWithAuth(apiPath("/api/workflow/payment/create"), {
    method: "POST",
    body: JSON.stringify({ case_id: caseId }),
  });
  if (!res.ok) throw new Error(`Payment session failed: ${res.status}`);
  return res.json();
}

export async function submitHandoffLead(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  const res = await fetchWithAuth(apiPath("/handoff/leads"), {
    method: "POST",
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Handoff failed: ${res.status}`);
  return res.json();
}

export async function generateDocuments(
  caseId: string,
  documentType: string,
): Promise<Record<string, unknown>> {
  const res = await fetchWithAuth(apiPath("/api/workflow/documents/generate"), {
    method: "POST",
    body: JSON.stringify({ case_id: caseId, document_type: documentType }),
  });
  if (!res.ok) throw new Error(`Document generation failed: ${res.status}`);
  return res.json();
}
