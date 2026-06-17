import { z } from 'zod';

/** Incoming POST /api/process body */
export const processRequestSchema = z.object({
  claim_type: z.string().min(1),
  facts: z.union([z.string(), z.record(z.unknown())]).optional(),
  query: z.string().optional(),
  jurisdiction: z.string().default('EW'),
  use_model: z.boolean().optional(),
  case_id: z.string().optional(),
  user_id: z.string().optional(),
});

export type ProcessRequest = z.infer<typeof processRequestSchema>;

/** Governed assessment shape returned by Python /assess (subset enforced at boundary). */
export const governedAssessmentSchema = z.object({
  status: z.string(),
  trace_id: z.string().optional(),
  source: z.string().optional(),
  lane: z.string().optional(),
  invokes_llm: z.boolean().optional(),
  result_type: z.string().optional(),
  message: z.string().optional(),
  rules: z.array(z.record(z.unknown())).optional(),
  citations: z.array(z.record(z.unknown())).optional(),
  answer: z.string().optional(),
  governance_passed: z.boolean().optional(),
  governance_verdict: z.string().optional(),
});

export type GovernedAssessment = z.infer<typeof governedAssessmentSchema>;

export const processResponseSchema = z.object({
  status: z.string(),
  trace_id: z.string().optional(),
  control_plane: z.literal('nestjs-v1'),
  retrieval: z.object({
    rules_count: z.number(),
    graph_nodes: z.number(),
    source: z.string(),
  }),
  assessment: governedAssessmentSchema,
  governance: z.object({
    passed: z.boolean(),
    checks: z.array(z.string()),
  }),
});

export type ProcessResponse = z.infer<typeof processResponseSchema>;

export type GraphNode = {
  node_id: string;
  node_type: string;
  label: string;
  description?: string;
  jurisdiction: string;
  authority_level?: number;
};

export type GraphEdge = {
  from_node_id: string;
  to_node_id: string;
  relationship_type: string;
};

export type RetrievalBundle = {
  rules: Array<Record<string, unknown>>;
  graph: {
    nodes: GraphNode[];
    edges: GraphEdge[];
    source: string;
    context_text?: string;
    engine?: string;
  };
};
