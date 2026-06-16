"""UI beta scope enforcement  -  intake/onboarding pickers expose production modules only."""

from __future__ import annotations

from pathlib import Path

from backend.domains.employment.modules import production_module_keys

ROOT = Path(__file__).resolve().parent.parent
CLIENT = ROOT / "client" / "public"

PARTIAL_MODULES = {
    "constructive_dismissal",
    "discrimination",
    "pregnancy_maternity_discrimination",
    "equal_pay",
    "whistleblowing",
    "health_and_safety",
    "trade_union_rights",
    "maternity_rights",
    "paternity_rights",
    "parental_leave",
    "shared_parental_leave",
    "national_minimum_wage",
    "tupe",
}


def test_beta_scope_js_lists_eleven_production_modules():
    js = (CLIENT / "js" / "beta-scope.js").read_text(encoding="utf-8")
    for key in production_module_keys():
        assert f'key: "{key}"' in js, f"missing production module {key} in beta-scope.js"
    assert js.count('key: "') == 11


def test_beta_scope_js_hides_thirteen_partial_modules():
    js = (CLIENT / "js" / "beta-scope.js").read_text(encoding="utf-8")
    assert PARTIAL_MODULES == set(
        line.strip().strip('"').strip(",")
        for line in js.split("PARTIAL_HIDDEN = [")[1].split("];")[0].replace("\n", " ").split(",")
        if line.strip().strip('"')
    )


def test_intake_uses_beta_scope_picker_not_partial_modules():
    html = (CLIENT / "pages" / "intake.html").read_text(encoding="utf-8")
    assert "beta-scope.js" in html
    assert "claim-type-options" in html
    assert "constructive_dismissal" not in html
    assert "discrimination" not in html
    assert "controlled beta" in html.lower() or "beta-scope-note" in html


def test_onboarding_case_type_uses_beta_scope():
    html = (CLIENT / "pages" / "onboarding.html").read_text(encoding="utf-8")
    assert "beta-scope.js" in html
    assert "populateSelect(document.getElementById('case_type')" in html
    assert 'value="constructive_dismissal"' not in html
    assert 'value="discrimination"' not in html


def test_landing_copy_is_controlled_beta_not_full_coverage():
    html = (CLIENT / "index.html").read_text(encoding="utf-8")
    assert "11 employment topics" in html
    assert "not full UK employment law coverage" in html
    assert "full UK employment law" not in html.replace(
        "not full UK employment law coverage", ""
    )


def test_auth_banner_uses_controlled_beta_copy():
    js = (CLIENT / "js" / "auth.js").read_text(encoding="utf-8")
    assert "Controlled beta  -  11 employment topics" in js


def test_deadline_picker_hides_partial_modules():
    html = (CLIENT / "pages" / "deadline.html").read_text(encoding="utf-8")
    assert "constructive_dismissal" not in html
    assert "discrimination" not in html
