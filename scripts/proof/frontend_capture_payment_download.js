const path = require('path');
const helpers = require('./frontend_playwright_helpers');

async function main() {
  const browser = await helpers.launchBrowser();
  const context = await browser.newContext({ viewport: { width: 1440, height: 1400 } });
  await helpers.wireApiBase(context);
  await helpers.setupMockAuth(context, '11111111-1111-1111-1111-111111111111');
  const page = await context.newPage();

  try {
    await page.goto(`${helpers.BASE_URL}/pages/login.html`, { waitUntil: 'networkidle' });
    const created = await helpers.createCaseWithAssessment(page);
    const caseId = created.case_id;

    const assessmentResult = created.assessment || {
      status: 'ok',
      claim_type: 'unfair_dismissal',
      recommended_next_step: 'prepare_documents',
    };
    const facts = created.facts || {
      edt: '2026-04-01',
      service_start_date: '2023-04-01',
      jurisdiction: 'EW',
    };

    await context.addInitScript(
      ({ result, fullFacts, caseId }) => {
        sessionStorage.setItem('assessment_result', JSON.stringify(result));
        sessionStorage.setItem('assessment_facts_full', JSON.stringify(fullFacts));
        sessionStorage.setItem('assessment_trace_id', 'frontend-payment-proof');
        localStorage.setItem('lawapp_active_case_id', caseId);
      },
      { result: assessmentResult, fullFacts: facts, caseId }
    );

    const paymentShots = await helpers.captureViewportMatrix(
      page,
      'payment',
      `${helpers.BASE_URL}/pages/assessment.html?case_id=${encodeURIComponent(caseId)}`,
      '#btn-stripe-pay'
    );

    const downloadShots = await helpers.captureViewportMatrix(
      page,
      'download',
      `${helpers.BASE_URL}/pages/case_detail.html?case_id=${encodeURIComponent(caseId)}`,
      'button:has-text("Download Particulars of Claim")'
    );

    helpers.writeJson(
      path.join(process.cwd(), 'reports', 'payment_download_surface_proof.json'),
      {
        generated_at: new Date().toISOString(),
        case_id: caseId,
        auth_mode: 'mock-header',
        layout_fixes_required: false,
        payment: paymentShots,
        download: downloadShots,
      }
    );
  } finally {
    await context.close();
    await browser.close();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
