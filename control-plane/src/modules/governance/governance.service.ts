import { Injectable } from '@nestjs/common';
import {
  governedAssessmentSchema,
  GovernedAssessment,
  processResponseSchema,
  ProcessResponse,
  RetrievalBundle,
} from '../../core/types';

export type GovernanceResult = {
  passed: boolean;
  checks: string[];
  assessment: GovernedAssessment;
};

@Injectable()
export class GovernanceService {
  validateAssessment(raw: unknown): GovernanceResult {
    const checks: string[] = [];
    const parsed = governedAssessmentSchema.safeParse(raw);
    if (!parsed.success) {
      return {
        passed: false,
        checks: [`schema_invalid:${parsed.error.issues.map((i) => i.path.join('.')).join(',')}`],
        assessment: {
          status: 'error',
          message: 'Governance rejected malformed brain response',
        },
      };
    }

    const assessment = parsed.data;
    checks.push('schema_ok');

    if (assessment.status === 'ok') {
      const hasGrounding =
        (assessment.rules?.length ?? 0) > 0 ||
        (assessment.citations?.length ?? 0) > 0 ||
        assessment.source === 'rules_table';
      if (!hasGrounding && assessment.invokes_llm) {
        checks.push('grounding_missing');
        return {
          passed: false,
          checks,
          assessment: {
            ...assessment,
            status: 'error',
            message: 'CitationGuard policy: ok response without rules/citations',
          },
        };
      }
      checks.push('grounding_ok');
    } else if (assessment.status === 'not_supported') {
      checks.push('fail_closed_not_supported');
    } else if (assessment.status === 'error') {
      checks.push('brain_error');
    } else {
      checks.push(`brain_status_${assessment.status}`);
    }

    const brainGovernanceOk =
      assessment.governance_passed !== false &&
      assessment.governance_verdict !== 'FAIL';
    if (!brainGovernanceOk && assessment.status === 'ok') {
      checks.push('brain_governance_failed');
      return { passed: false, checks, assessment };
    }

    return { passed: true, checks, assessment };
  }

  buildProcessResponse(
    retrieval: RetrievalBundle,
    governance: GovernanceResult,
    traceId?: string,
  ): ProcessResponse {
    const body: ProcessResponse = {
      status: governance.assessment.status,
      trace_id: traceId ?? governance.assessment.trace_id,
      control_plane: 'nestjs-v1',
      retrieval: {
        rules_count: retrieval.rules.length,
        graph_nodes: retrieval.graph.nodes.length,
        source: retrieval.graph.source,
      },
      assessment: governance.assessment,
      governance: {
        passed: governance.passed,
        checks: governance.checks,
      },
    };
    return processResponseSchema.parse(body);
  }
}
