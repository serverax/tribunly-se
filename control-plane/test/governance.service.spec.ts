import { GovernanceService } from '../src/modules/governance/governance.service';

describe('GovernanceService', () => {
  const svc = new GovernanceService();

  it('accepts grounded rules_table assessment', () => {
    const result = svc.validateAssessment({
      status: 'ok',
      source: 'rules_table',
      invokes_llm: false,
      lane: 'FAST_DETERMINISTIC',
      rules: [{ rule_key: 'era1996.s94' }],
      trace_id: 't-1',
    });
    expect(result.passed).toBe(true);
    expect(result.checks).toContain('schema_ok');
  });

  it('rejects ok+llm without grounding', () => {
    const result = svc.validateAssessment({
      status: 'ok',
      invokes_llm: true,
      lane: 'REASONING',
      rules: [],
      citations: [],
    });
    expect(result.passed).toBe(false);
    expect(result.checks).toContain('grounding_missing');
  });

  it('allows not_supported fail-closed', () => {
    const result = svc.validateAssessment({
      status: 'not_supported',
      message: 'Out of scope',
    });
    expect(result.passed).toBe(true);
    expect(result.assessment.status).toBe('not_supported');
  });

  it('rejects malformed payload', () => {
    const result = svc.validateAssessment({ status: 'bogus' });
    expect(result.passed).toBe(false);
    expect(result.assessment.status).toBe('error');
  });
});
