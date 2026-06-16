export type AssessmentStrength = "low" | "medium" | "high" | "uncertain";

export type AssessmentCitation = {
  cite?: string;
  rule_key?: string;
  source?: string;
  url?: string;
};

export type StructuredAssessment = {
  status?: string;
  claim_type?: string;
  has_viable_claim?: boolean | "uncertain";
  strength?: AssessmentStrength;
  value_range?: { low?: number; high?: number; currency?: string };
  key_weaknesses?: string[];
  deadline?: {
    limitation_date?: string;
    base_limit?: string;
    ec_applied?: boolean;
    authority?: string;
    notes?: string;
  };
  recommended_next_step?: string;
  citations?: AssessmentCitation[];
  insufficient_grounding?: boolean;
  trace_id?: string;
  deadline_mismatch?: boolean;
};

export type DiagnosisRequest = {
  query: string;
  facts: Record<string, unknown>;
  jurisdiction?: string;
  use_model?: boolean;
  client_deadline?: string;
};

export type DeadlineCalcRequest = {
  claim_type?: string;
  edt: string;
  acas_start?: string;
  acas_end?: string;
  ec_day_a?: string;
  ec_day_b?: string;
  jurisdiction?: string;
};

export type DeadlineCalcResponse = {
  claim_type?: string;
  edt?: string;
  limitation_date?: string;
  base_deadline?: string;
  paused_days?: number;
  floor_deadline?: string;
  ec_applied?: boolean;
  source?: string;
  authority?: string;
};
