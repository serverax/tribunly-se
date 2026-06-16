export type CaseStatus =
  | "draft"
  | "active"
  | "acas"
  | "et1_filed"
  | "settled"
  | "closed";

export type LawAppCase = {
  id: string;
  title?: string;
  status?: CaseStatus | string;
  claim_type?: string;
  created_at?: string;
  updated_at?: string;
  facts?: Record<string, unknown>;
  key_dates?: Record<string, string>;
  user_id?: string;
};

export type CaseListResponse = {
  cases?: LawAppCase[];
};

export type CreateCaseRequest = {
  title?: string;
  claim_type?: string;
  facts?: Record<string, unknown>;
};
