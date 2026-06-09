/**
 * lawapp Document Preview — Client-side document assembly.
 *
 * Generates a basic draft document preview from confirmed case facts,
 * entirely client-side. No sensitive data is sent to the server for preview.
 *
 * GUARDRAIL: This module only uses confirmed facts already on the client.
 *            No unconfirmed extraction results are used.
 *            No API call is made for preview generation.
 *            Raw document content is NEVER transmitted unless user explicitly
 *            chooses to generate the full server-side draft.
 *
 * Use cases:
 *   - Show a "draft preview" before the user pays/generates a full document.
 *   - Validate that the facts are complete before generation.
 *   - Run deadline/notice arithmetic (uses LawappDeadline WASM/JS fallback).
 */

(function (global) {
  'use strict';

  const _LEGAL_BOUNDARY = [
    'SELF-HELP DRAFT — NOT LEGAL ADVICE',
    '─────────────────────────────────────────────────────',
    'This preview was generated client-side from your confirmed facts.',
    'It is NOT a final legal document.',
    'lawapp is not a solicitor and does not provide regulated legal advice.',
    'Review, verify, and correct this document before using it.',
    'lawapp does not file, submit, represent you, or conduct litigation.',
    '─────────────────────────────────────────────────────',
    '',
  ].join('\n');

  function _formatDate(s) {
    if (!s) return '[Date not provided]';
    try {
      const d = new Date(s + (s.length === 10 ? 'T00:00:00' : ''));
      return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' });
    } catch { return s; }
  }

  function _or(val, fallback) {
    return val || fallback;
  }

  /**
   * Generate a Particulars of Claim preview string from local facts.
   * No server call. No PII sent anywhere.
   *
   * @param {object} facts  - Confirmed case facts (edt, service_start_date, reason, etc.)
   * @param {object} assessment - Assessment result from session (for viability summary)
   * @returns {string} Plain text preview
   */
  function generateParticularsPreview(facts, assessment) {
    facts = facts || {};
    assessment = assessment || {};

    const edt = facts.edt || null;
    const start = facts.service_start_date || null;
    const reason = facts.reason_for_dismissal || null;
    const weeklyPay = facts.weekly_pay || null;

    const lines = [
      _LEGAL_BOUNDARY,
      'IN THE EMPLOYMENT TRIBUNAL',
      '',
      'PARTICULARS OF CLAIM — UNFAIR DISMISSAL',
      'Claim type: Unfair Dismissal (Employment Rights Act 1996, Part X)',
      '',
      'Claimant:   [YOUR FULL LEGAL NAME]',
      '            [YOUR ADDRESS]',
      '',
      'Respondent: [EMPLOYER FULL LEGAL NAME]',
      '            [EMPLOYER REGISTERED ADDRESS]',
      '',
      '─── EMPLOYMENT DETAILS ─────────────────────────────────────────',
      'Employment started: ' + _formatDate(start),
      'Employment ended:   ' + _formatDate(edt),
      reason ? ('Reason given:       ' + reason) : 'Reason given:       [Not provided — please specify]',
      weeklyPay ? ('Weekly pay (gross): £' + parseFloat(weeklyPay).toFixed(2)) : 'Weekly pay:         [Not provided — required for compensation calculation]',
      '',
      '─── NATURE OF CLAIM ────────────────────────────────────────────',
      '1. The Claimant was employed by the Respondent.',
      '2. The Claimant was dismissed on ' + _formatDate(edt) + '.',
      '3. The Claimant has the qualifying period of continuous employment required by ERA 1996 s.108.',
      '4. The Claimant contends the dismissal was unfair within the meaning of ERA 1996 s.94.',
      reason ? ('5. The Respondent stated the reason for dismissal was: ' + reason + '.') : '5. The reason for dismissal was: [to be completed].',
      '',
      '─── REMEDY SOUGHT ──────────────────────────────────────────────',
      'The Claimant seeks:',
      '(a) Reinstatement or re-engagement; or',
      '(b) Compensation comprising the basic award (ERA 1996 s.119) and',
      '    the compensatory award (ERA 1996 s.123).',
      '',
      '─── PREVIEW ENDS HERE ──────────────────────────────────────────',
      'Full document generation requires review and confirmation.',
      'Use "Generate full document" in the assessment to produce the',
      'complete, server-side draft with all legal sections populated.',
      _LEGAL_BOUNDARY,
    ];

    return lines.join('\n');
  }

  /**
   * Validate that all required facts are present for document generation.
   * Returns an object with { valid: bool, missing: string[] }.
   * No server call needed.
   */
  function validateFactsForDocument(facts, documentType) {
    facts = facts || {};
    const missing = [];

    const _REQUIRED_UD = {
      edt: 'Date your employment ended (EDT)',
      service_start_date: 'Date you started employment',
    };

    const _REQUIRED_UPW = {
      wages_due_date: 'Date wages were due',
      unpaid_amount:  'Amount unpaid or deducted',
    };

    const required = (documentType === 'schedule_of_loss' || documentType === 'particulars_of_claim')
      ? _REQUIRED_UD
      : {};

    for (const [field, label] of Object.entries(required)) {
      if (!facts[field]) missing.push(label);
    }

    return { valid: missing.length === 0, missing };
  }

  /**
   * Compute deadline locally using LawappDeadline (WASM/JS fallback).
   * Proves no server call is needed for deadline arithmetic.
   * Returns null if LawappDeadline is not loaded.
   */
  function computeDeadlineLocally(edt, timeLimitMonths, ecDayA, ecDayB) {
    if (!global.LawappDeadline) {
      return { error: 'LawappDeadline module not loaded. Include /js/deadline.js.' };
    }
    const result = global.LawappDeadline.computeDeadline(
      edt,
      timeLimitMonths || 3,
      ecDayA || null,
      ecDayB || null
    );
    return Object.assign({}, result, {
      computed_by: 'client_wasm_or_js_fallback',
      server_call: false,
      no_personal_data_sent: true,
    });
  }

  const api = {
    generateParticularsPreview,
    validateFactsForDocument,
    computeDeadlineLocally,
    LEGAL_BOUNDARY: _LEGAL_BOUNDARY,
  };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  } else {
    global.LawappDocPreview = api;
  }

}(typeof globalThis !== 'undefined' ? globalThis : this));
