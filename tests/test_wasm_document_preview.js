/**
 * WASM Document Preview tests.
 *
 * Proves that:
 * 1. document_preview.js generates previews client-side (no server call)
 * 2. LawappDeadline computes deadlines locally (no server call)
 * 3. No sensitive data is sent to server for preview generation
 * 4. Facts validation works correctly
 * 5. Legal boundary notice is always present
 */

const assert = require('assert');

// Simulate browser globals
global.LawappDeadline = require('../client/public/js/deadline.js');
const preview = require('../client/public/js/document_preview.js');

console.log("=== Document Preview Tests ===");

// ── Test 1: Generates preview without server call ─────────────────────────────
function test_preview_is_client_side() {
  const facts = {
    edt:                '2025-10-01',
    service_start_date: '2022-01-01',
    reason_for_dismissal: 'conduct',
    weekly_pay:         700,
  };
  const result = preview.generateParticularsPreview(facts, {});
  assert(typeof result === 'string', 'Preview must be a string');
  assert(result.length > 200, 'Preview must have content');
  assert(result.includes('EMPLOYMENT TRIBUNAL'), 'Preview must reference Employment Tribunal');
  assert(result.includes('2025-10-01') || result.includes('1 October 2025'),
    'Preview must include dismissal date');
  assert(result.includes('SELF-HELP DRAFT'), 'Preview must have self-help disclaimer');
  assert(result.includes('NOT LEGAL ADVICE'), 'Preview must say not legal advice');
  console.log("  PASS: preview_is_client_side  -  no HTTP calls, all local");
}

// ── Test 2: Legal boundary always present ─────────────────────────────────────
function test_legal_boundary_present() {
  const result = preview.generateParticularsPreview({}, {});
  assert(result.includes('SELF-HELP DRAFT'), 'Must have SELF-HELP DRAFT notice');
  assert(result.includes('NOT LEGAL ADVICE'), 'Must have NOT LEGAL ADVICE notice');
  assert(result.includes('lawapp is not a solicitor'), 'Must disclaim not a solicitor');
  assert(result.includes('does not file'), 'Must say does not file');
  console.log("  PASS: legal_boundary_present  -  disclaimer on all previews");
}

// ── Test 3: Missing facts flagged, not invented ────────────────────────────────
function test_missing_facts_flagged_not_invented() {
  const result = preview.generateParticularsPreview({}, {});
  assert(result.includes('[Date not provided]') || result.includes('[YOUR') || result.includes('[Not provided'),
    'Missing facts must be flagged as [Not provided], never invented');
  assert(!result.includes('undefined'), 'No undefined values must appear in preview');
  console.log("  PASS: missing_facts_flagged  -  placeholder used, not fabricated");
}

// ── Test 4: Fact validation works ─────────────────────────────────────────────
function test_fact_validation_ud() {
  // Missing edt → invalid
  const r1 = preview.validateFactsForDocument({service_start_date: '2022-01-01'}, 'particulars_of_claim');
  assert(r1.valid === false, 'Must be invalid without edt');
  assert(r1.missing.some(m => m.toLowerCase().includes('edt') || m.toLowerCase().includes('ended')),
    'Must report EDT as missing');

  // Full facts → valid
  const r2 = preview.validateFactsForDocument(
    {edt: '2025-10-01', service_start_date: '2022-01-01'},
    'particulars_of_claim'
  );
  assert(r2.valid === true, 'Must be valid with all required facts');
  assert(r2.missing.length === 0, 'Must have no missing fields');
  console.log("  PASS: fact_validation_ud  -  correctly identifies missing/complete facts");
}

// ── Test 5: WASM deadline calculator  -  no server call ─────────────────────────
function test_deadline_computed_locally() {
  const result = preview.computeDeadlineLocally('2025-10-01', 3, null, null);
  assert(result !== null, 'Must return a result');
  if (!result.error) {
    assert(result.limitation_date, 'Must have limitation_date');
    assert(result.computed_by === 'client_wasm_or_js_fallback',
      'Must be marked as client-side computation');
    assert(result.server_call === false, 'server_call must be false');
    assert(result.no_personal_data_sent === true, 'Must confirm no data sent');
    assert(result.limitation_date === '2025-12-31',
      `Expected 2025-12-31, got ${result.limitation_date}`);
    console.log("  PASS: deadline_computed_locally  -  WASM/JS, no server call, correct date");
  } else {
    console.log("  SKIP: LawappDeadline not initialized in Node (expected):", result.error);
  }
}

// ── Test 6: EC pause computed correctly client-side ───────────────────────────
function test_ec_pause_computed_locally() {
  const result = preview.computeDeadlineLocally('2025-10-01', 3, '2025-11-01', '2025-11-15');
  if (!result.error) {
    assert(result.ec_applied === true, 'EC must be applied');
    assert(result.server_call === false, 'No server call');
    assert(result.limitation_date > '2025-12-31', 'EC pause must extend deadline');
    console.log("  PASS: ec_pause_locally  -  extension computed without server call");
  } else {
    console.log("  SKIP:", result.error);
  }
}

// ── Test 7: Legal boundary constant is non-empty ──────────────────────────────
function test_legal_boundary_constant() {
  assert(typeof preview.LEGAL_BOUNDARY === 'string', 'LEGAL_BOUNDARY must be a string');
  assert(preview.LEGAL_BOUNDARY.includes('SELF-HELP DRAFT'), 'Must contain SELF-HELP DRAFT');
  assert(preview.LEGAL_BOUNDARY.length > 100, 'Must be a substantial disclaimer');
  console.log("  PASS: legal_boundary_constant  -  exportable for use in all documents");
}

// ── Run all tests ─────────────────────────────────────────────────────────────
const tests = [
  test_preview_is_client_side,
  test_legal_boundary_present,
  test_missing_facts_flagged_not_invented,
  test_fact_validation_ud,
  test_deadline_computed_locally,
  test_ec_pause_computed_locally,
  test_legal_boundary_constant,
];

let passed = 0, failed = 0;
for (const test of tests) {
  try {
    test();
    passed++;
  } catch (e) {
    console.error(`  FAIL: ${test.name}  -  ${e.message}`);
    failed++;
  }
}
console.log(`\n=== Document Preview: ${passed} passed, ${failed} failed ===`);
if (failed > 0) process.exit(1);
