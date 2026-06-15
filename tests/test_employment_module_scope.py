from fastapi.testclient import TestClient
from pathlib import Path

from backend.api.main import app
from backend.domains.registry import supported_matter_types
from backend.domains.employment.modules import (
    REQUIRED_EMPLOYMENT_MODULES,
    module_coverage,
    module_keys,
    production_module_keys,
)
from shared.schemas import RetrievalBundle

from backend.core.employment_assessment import ASSESSMENT_HANDLERS, assess_case


client = TestClient(app)


def test_workflow_diagnosis_fails_closed_for_unverified_employment_module():
    resp = client.post(
        "/api/workflow/diagnosis",
        json={
            "claim_type": "discrimination",
            "jurisdiction": "EW",
            "facts": {"discriminatory_event_date": "2026-05-01", "protected_characteristic": "sex"},
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "not_covered"
    assert body["claim_type"] == "discrimination"
    assert body["supported_types"] == supported_matter_types()
    assert "not covered" in body["message"].lower()


def test_registry_is_current_production_employment_scope():
    assert supported_matter_types() == [
        "unfair_dismissal",
        "unpaid_wages",
        "wrongful_dismissal",
        "redundancy",
        "flexible_working",
        "holiday_pay",
        "working_time",
        "part_time_workers",
        "fixed_term_workers",
        "agency_workers",
        "employment_contracts",
    ]


def test_twenty_four_employment_modules_are_declared_server_side():
    coverage = module_coverage()
    assert coverage["required_total"] == 24
    assert len(module_keys()) == 24
    assert all(module["db_backed_required"] is True for module in REQUIRED_EMPLOYMENT_MODULES)
    statuses = {module["key"]: module["status"] for module in REQUIRED_EMPLOYMENT_MODULES}
    assert statuses["redundancy"] == "production"
    assert statuses["wrongful_dismissal"] == "production"
    assert statuses["working_time"] == "production"
    assert statuses["holiday_pay"] == "production"
    assert statuses["national_minimum_wage"] == "partial"
    assert statuses["flexible_working"] == "production"
    assert statuses["discrimination"] == "partial"
    assert statuses["pregnancy_maternity_discrimination"] == "partial"
    assert statuses["equal_pay"] == "partial"
    assert statuses["whistleblowing"] == "partial"
    assert statuses["maternity_rights"] == "partial"
    assert statuses["paternity_rights"] == "partial"
    assert statuses["parental_leave"] == "partial"
    assert statuses["shared_parental_leave"] == "partial"
    assert statuses["constructive_dismissal"] == "partial"
    assert statuses["employment_contracts"] == "production"
    assert statuses["fixed_term_workers"] == "production"
    assert statuses["part_time_workers"] == "production"
    assert statuses["agency_workers"] == "production"
    assert statuses["health_and_safety"] == "partial"
    assert statuses["trade_union_rights"] == "partial"
    assert statuses["tupe"] == "partial"


def test_only_production_modules_are_exposed_as_supported():
    assert supported_matter_types() == production_module_keys()
    assert sorted(ASSESSMENT_HANDLERS) == sorted(production_module_keys())


def test_legacy_assessment_dispatcher_rejects_unverified_modules():
    result = assess_case(
        "discrimination",
        {"years_service": 5, "gross_weekly_pay": 600, "age": 40},
        {"weeks_pay_cap": 700},
    )

    assert result["viable_claim"] is None
    assert "not supported" in result["error"]
    assert result["supported_types"] == production_module_keys()


def test_partial_modules_are_not_exposed_as_supported():
    partial_modules = {
        "national_minimum_wage",
        "discrimination",
        "pregnancy_maternity_discrimination",
        "equal_pay",
        "whistleblowing",
        "maternity_rights",
        "paternity_rights",
        "parental_leave",
        "shared_parental_leave",
        "constructive_dismissal",
        "health_and_safety",
        "trade_union_rights",
        "tupe",
    }
    for module in partial_modules:
        assert module not in supported_matter_types()
        assert module not in ASSESSMENT_HANDLERS


def test_redundancy_and_wrongful_migration_seeds_verified_rules():
    sql = Path("db/migrations/060_redundancy_wrongful_dismissal_rules.sql").read_text(encoding="utf-8")

    for rule_key in (
        "wrongful_dismissal.notice_qualifying_period_months",
        "wrongful_dismissal.max_statutory_notice_weeks",
        "wrongful_dismissal.statutory_notice_formula",
        "wrongful_dismissal.et_time_limit_months",
        "wrongful_dismissal.et_contract_claim_scope",
        "redundancy.payment_right",
        "redundancy.definition",
        "redundancy.qualifying_period_years",
        "redundancy.time_limit_months",
        "redundancy.payment_formula",
    ):
        assert rule_key in sql

    for authority in (
        "ERA 1996 s.86",
        "ERA 1996 s.135",
        "ERA 1996 s.139",
        "ERA 1996 s.155",
        "ERA 1996 s.162",
        "ERA 1996 s.164",
        "Employment Tribunals Extension of Jurisdiction (England and Wales) Order 1994",
    ):
        assert authority in sql

    assert "verification_status" in sql
    assert "'verified'" in sql


def test_redundancy_wrongful_promotion_migration_adds_required_cap_and_status():
    sql = Path("db/migrations/065_promote_redundancy_wrongful_workflows.sql").read_text(encoding="utf-8")

    assert "redundancy.weeks_pay_cap_amount" in sql
    assert "redundancy.max_years_counted" in sql
    assert "redundancy.multiplier_under_22" in sql
    assert "redundancy.multiplier_22_to_40" in sql
    assert "redundancy.multiplier_41_plus" in sql
    assert "ERA 1996 s.227(1) + SI 2026/310" in sql
    assert "UPDATE employment_modules" in sql
    assert "'redundancy', 'wrongful_dismissal'" in sql


def test_working_time_holiday_flexible_promotion_migration_sets_status():
    sql = Path("db/migrations/067_promote_working_time_holiday_flexible_workflows.sql").read_text(encoding="utf-8")

    assert "UPDATE employment_modules" in sql
    assert "'working_time', 'holiday_pay', 'flexible_working'" in sql


def test_worker_status_contract_promotion_migration_sets_status():
    sql = Path("db/migrations/068_promote_worker_status_contract_modules.sql").read_text(encoding="utf-8")

    assert "UPDATE employment_modules" in sql
    for module in ("employment_contracts", "fixed_term_workers", "part_time_workers", "agency_workers"):
        assert module in sql


def test_wrongful_dismissal_assessment_uses_db_rules():
    result = assess_case(
        "wrongful_dismissal",
        {
            "termination_date": "2026-05-01",
            "employment_start_date": "2020-01-01",
            "weekly_pay": 600,
            "notice_given_weeks": 1,
        },
        {
            "notice_qualifying_period_months": 1,
            "max_statutory_notice_weeks": 12,
            "et_time_limit_months": 3,
        },
    )

    assert result["viable_claim"] is True
    assert result["notice_shortfall_weeks"] == 5
    assert result["estimated_notice_pay"] == 3000
    assert result["deadline"] == "2026-07-31"
    assert result["citations"]


def test_redundancy_assessment_uses_db_rules_and_weekly_cap():
    result = assess_case(
        "redundancy",
        {
            "dismissal_date": "2026-05-01",
            "employment_start_date": "2020-01-01",
            "age": 45,
            "weekly_pay": 900,
        },
        {
            "qualifying_period_years": 2,
            "time_limit_months": 6,
            "weeks_pay_cap_amount": 751,
            "max_years_counted": 20,
            "multiplier_under_22": 0.5,
            "multiplier_22_to_40": 1,
            "multiplier_41_plus": 1.5,
        },
    )

    assert result["viable_claim"] is True
    assert result["weekly_pay_cap_amount"] == 751
    assert result["redundancy_weeks"] == 8.5
    assert result["estimated_statutory_redundancy_payment"] == 6383.5
    assert result["deadline"] == "2026-10-31"
    assert result["citations"]


def test_promoted_modules_fail_closed_when_required_rules_missing():
    wrongful = assess_case(
        "wrongful_dismissal",
        {"termination_date": "2026-05-01", "employment_start_date": "2020-01-01", "weekly_pay": 600},
        {},
    )
    redundancy = assess_case(
        "redundancy",
        {"dismissal_date": "2026-05-01", "employment_start_date": "2020-01-01", "weekly_pay": 600, "age": 40},
        {"qualifying_period_years": 2, "time_limit_months": 6, "weeks_pay_cap_amount": 751},
    )

    assert wrongful["insufficient_grounding"] is True
    assert "notice_qualifying_period_months" in wrongful["missing_rules"]
    assert redundancy["insufficient_grounding"] is True
    assert "max_years_counted" in redundancy["missing_rules"]


def test_working_time_assessment_uses_db_rules():
    result = assess_case(
        "working_time",
        {
            "average_weekly_hours": 55,
            "daily_rest_hours": 8,
            "weekly_rest_hours": 20,
            "shift_hours": 8,
            "rest_break_minutes": 10,
        },
        {
            "max_weekly_hours": 48,
            "daily_rest_hours": 11,
            "weekly_rest_hours": 24,
            "rest_break_minutes": 20,
            "rest_break_trigger_hours": 6,
        },
    )

    assert result["viable_claim"] is True
    assert "weekly_hours_above_48_without_opt_out" in result["violations"]
    assert result["thresholds"]["max_weekly_hours"] == 48
    assert result["citations"]


def test_holiday_pay_assessment_uses_db_rules():
    result = assess_case(
        "holiday_pay",
        {"annual_leave_taken_weeks": 3, "employment_ended": True, "weekly_pay": 500},
        {
            "annual_leave_weeks": 4,
            "additional_leave_weeks": 1.6,
            "total_annual_leave_weeks": 5.6,
        },
    )

    assert result["viable_claim"] is True
    assert result["annual_leave_entitlement_weeks"] == 5.6
    assert result["leave_shortfall_weeks"] == 2.6
    assert result["estimated_untaken_holiday_pay"] == 1300
    assert result["citations"]


def test_flexible_working_assessment_uses_db_rules():
    result = assess_case(
        "flexible_working",
        {
            "requests_last_12_months": 1,
            "request_date": "2026-01-10",
            "decision_date": "2026-04-20",
            "refused": True,
            "consulted_before_refusal": False,
        },
        {
            "day_one_application_right": 0,
            "max_requests_per_12_months": 2,
            "decision_period_months": 2,
        },
    )

    assert result["viable_claim"] is True
    assert result["eligible_to_apply"] is True
    assert result["decision_due_date"] == "2026-03-09"
    assert "refused_without_required_consultation" in result["breach_reasons"]
    assert "decision_outside_statutory_period" in result["breach_reasons"]
    assert result["citations"]


def test_newly_promoted_modules_fail_closed_when_required_rules_missing():
    working_time = assess_case("working_time", {"average_weekly_hours": 55}, {})
    holiday_pay = assess_case("holiday_pay", {"annual_leave_taken_weeks": 3}, {"annual_leave_weeks": 4})
    flexible = assess_case("flexible_working", {"requests_last_12_months": 1}, {"day_one_application_right": 0})

    assert working_time["insufficient_grounding"] is True
    assert "max_weekly_hours" in working_time["missing_rules"]
    assert holiday_pay["insufficient_grounding"] is True
    assert "total_annual_leave_weeks" in holiday_pay["missing_rules"]
    assert flexible["insufficient_grounding"] is True
    assert "decision_period_months" in flexible["missing_rules"]


def test_employment_contracts_assessment_uses_db_rules():
    result = assess_case(
        "employment_contracts",
        {"received_written_statement": False},
        {
            "day_one_particulars_anchor": 0,
            "written_particulars_right": "worker_right_to_written_statement_of_particulars",
            "tribunal_reference_route": "employment_tribunal_reference_route",
            "section_38_award_anchor": "additional_award_possible",
        },
    )

    assert result["viable_claim"] is True
    assert "written_statement_not_received" in result["breach_reasons"]
    assert result["citations"]


def test_fixed_term_workers_assessment_uses_db_rules():
    result = assess_case(
        "fixed_term_workers",
        {
            "successive_fixed_term_contract_years": 4,
            "less_favourable_treatment": True,
            "objective_justification_given": False,
        },
        {
            "successive_contracts_years": 4,
            "less_favourable_treatment_right": "right_not_to_be_treated_less_favourably",
            "objective_justification_anchor": "objective_justification_possible",
        },
    )

    assert result["viable_claim"] is True
    assert "successive_fixed_term_contracts_at_or_above_four_year_anchor" in result["breach_reasons"]
    assert "less_favourable_treatment_without_objective_justification" in result["breach_reasons"]
    assert result["citations"]


def test_part_time_workers_assessment_uses_db_rules():
    result = assess_case(
        "part_time_workers",
        {
            "less_favourable_treatment": True,
            "comparable_full_time_worker": True,
            "objective_justification_given": False,
        },
        {
            "less_favourable_treatment_right": "right_not_to_be_treated_less_favourably",
            "objective_justification_anchor": "objective_justification_possible",
            "complaint_route": "employment_tribunal_complaint_route",
        },
    )

    assert result["viable_claim"] is True
    assert "less_favourable_treatment_without_objective_justification" in result["breach_reasons"]
    assert result["citations"]


def test_agency_workers_assessment_uses_db_rules():
    result = assess_case(
        "agency_workers",
        {"weeks_on_assignment": 13, "less_favourable_basic_conditions": True},
        {
            "qualifying_period_weeks": 12,
            "equal_treatment_after_qualifying_period": "equal_treatment_basic_working_and_employment_conditions_after_qualifying_period",
            "tribunal_complaint_route": "employment_tribunal_complaint_route",
        },
    )

    assert result["viable_claim"] is True
    assert result["qualifying_period_met"] is True
    assert "less_favourable_basic_conditions_after_qualifying_period" in result["breach_reasons"]
    assert result["citations"]


def test_worker_status_contract_modules_fail_closed_when_rules_missing():
    contracts = assess_case("employment_contracts", {"received_written_statement": False}, {})
    fixed = assess_case("fixed_term_workers", {"successive_fixed_term_contract_years": 4}, {})
    part_time = assess_case("part_time_workers", {"less_favourable_treatment": True}, {})
    agency = assess_case("agency_workers", {"weeks_on_assignment": 13}, {})

    assert contracts["insufficient_grounding"] is True
    assert "day_one_particulars_anchor" in contracts["missing_rules"]
    assert fixed["insufficient_grounding"] is True
    assert "successive_contracts_years" in fixed["missing_rules"]
    assert part_time["insufficient_grounding"] is True
    assert "complaint_route" in part_time["missing_rules"]
    assert agency["insufficient_grounding"] is True
    assert "qualifying_period_weeks" in agency["missing_rules"]


def test_workflow_diagnosis_supports_promoted_modules_with_retrieval_proof(monkeypatch):
    from backend.core import retrieve as retrieve_module

    def fake_retrieve_rules(claim_type, _jurisdiction, _date):
        if claim_type == "wrongful_dismissal":
            return [
                {"rule_key": "wrongful_dismissal.notice_qualifying_period_months", "value_numeric": 1},
                {"rule_key": "wrongful_dismissal.max_statutory_notice_weeks", "value_numeric": 12},
                {"rule_key": "wrongful_dismissal.et_time_limit_months", "value_numeric": 3},
            ]
        if claim_type == "redundancy":
            return [
                {"rule_key": "redundancy.qualifying_period_years", "value_numeric": 2},
                {"rule_key": "redundancy.time_limit_months", "value_numeric": 6},
                {"rule_key": "redundancy.weeks_pay_cap_amount", "value_numeric": 751},
                {"rule_key": "redundancy.max_years_counted", "value_numeric": 20},
                {"rule_key": "redundancy.multiplier_under_22", "value_numeric": 0.5},
                {"rule_key": "redundancy.multiplier_22_to_40", "value_numeric": 1},
                {"rule_key": "redundancy.multiplier_41_plus", "value_numeric": 1.5},
            ]
        if claim_type == "working_time":
            return [
                {"rule_key": "working_time.max_weekly_hours", "value_numeric": 48},
                {"rule_key": "working_time.daily_rest_hours", "value_numeric": 11},
                {"rule_key": "working_time.weekly_rest_hours", "value_numeric": 24},
                {"rule_key": "working_time.rest_break_minutes", "value_numeric": 20},
                {"rule_key": "working_time.rest_break_trigger_hours", "value_numeric": 6},
            ]
        if claim_type == "employment_contracts":
            return [
                {"rule_key": "employment_contracts.day_one_particulars_anchor", "value_numeric": 0},
                {"rule_key": "employment_contracts.written_particulars_right", "value_text": "worker_right_to_written_statement_of_particulars"},
                {"rule_key": "employment_contracts.tribunal_reference_route", "value_text": "employment_tribunal_reference_route"},
                {"rule_key": "employment_contracts.section_38_award_anchor", "value_text": "additional_award_possible"},
            ]
        return []

    monkeypatch.setattr(retrieve_module, "retrieve_rules", fake_retrieve_rules)
    monkeypatch.setattr(
        retrieve_module,
        "retrieve",
        lambda *_args, **_kwargs: RetrievalBundle(
            exact_rules=[],
            authorities=[{"cite": "ERA 1996 s.86", "url": "https://www.legislation.gov.uk/ukpga/1996/18/section/86"}],
            insufficient_grounding=False,
        ),
    )

    resp = client.post(
        "/api/workflow/diagnosis",
        json={
            "claim_type": "wrongful_dismissal",
            "jurisdiction": "EW",
            "facts": {
                "termination_date": "2026-05-01",
                "employment_start_date": "2020-01-01",
                "weekly_pay": 600,
                "notice_given_weeks": 1,
            },
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["claim_type"] == "wrongful_dismissal"
    assert body["assessment"]["viable_claim"] is True
    assert body["assessment"]["retrieval_proof"]["exact_rule_count"] == 3

    resp = client.post(
        "/api/workflow/diagnosis",
        json={
            "claim_type": "working_time",
            "jurisdiction": "EW",
            "facts": {
                "average_weekly_hours": 55,
                "daily_rest_hours": 8,
                "weekly_rest_hours": 20,
                "shift_hours": 8,
                "rest_break_minutes": 10,
            },
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["claim_type"] == "working_time"
    assert body["assessment"]["viable_claim"] is True
    assert body["assessment"]["retrieval_proof"]["exact_rule_count"] == 5

    resp = client.post(
        "/api/workflow/diagnosis",
        json={
            "claim_type": "employment_contracts",
            "jurisdiction": "EW",
            "facts": {"received_written_statement": False},
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["claim_type"] == "employment_contracts"
    assert body["assessment"]["viable_claim"] is True
    assert body["assessment"]["retrieval_proof"]["exact_rule_count"] == 4


def test_working_time_holiday_nmw_flexible_migration_seeds_verified_rules():
    sql = Path("db/migrations/061_working_time_holiday_nmw_flexible_rules.sql").read_text(encoding="utf-8")

    for rule_key in (
        "working_time.max_weekly_hours",
        "working_time.daily_rest_hours",
        "working_time.weekly_rest_hours",
        "working_time.rest_break_minutes",
        "working_time.rest_break_trigger_hours",
        "holiday_pay.annual_leave_weeks",
        "holiday_pay.additional_leave_weeks",
        "holiday_pay.total_annual_leave_weeks",
        "holiday_pay.termination_payment_in_lieu",
        "holiday_pay.tribunal_complaint_route",
        "national_minimum_wage.worker_entitlement",
        "national_minimum_wage.worker_definition",
        "national_minimum_wage.records_right",
        "national_minimum_wage.arrears_anchor",
        "national_minimum_wage.enforcement_notice_anchor",
        "flexible_working.day_one_application_right",
        "flexible_working.max_requests_per_12_months",
        "flexible_working.decision_period_months",
        "flexible_working.consultation_required_before_refusal",
        "flexible_working.tribunal_complaint_route",
    ):
        assert rule_key in sql

    for authority in (
        "Working Time Regulations 1998 reg.4",
        "Working Time Regulations 1998 reg.13",
        "National Minimum Wage Act 1998 s.1",
        "National Minimum Wage Act 1998 s.17",
        "ERA 1996 s.80F",
        "ERA 1996 s.80G",
        "ERA 1996 s.80H",
    ):
        assert authority in sql

    assert "verification_status" in sql
    assert "'verified'" in sql


def test_equality_and_whistleblowing_migration_seeds_verified_rules():
    sql = Path("db/migrations/062_equality_whistleblowing_rules.sql").read_text(encoding="utf-8")

    for rule_key in (
        "discrimination.protected_characteristics",
        "discrimination.direct_discrimination",
        "discrimination.indirect_discrimination",
        "discrimination.harassment",
        "discrimination.victimisation",
        "discrimination.work_context",
        "discrimination.tribunal_jurisdiction",
        "discrimination.time_limit_months",
        "pregnancy_maternity_discrimination.unfavourable_treatment",
        "pregnancy_maternity_discrimination.work_context",
        "pregnancy_maternity_discrimination.tribunal_jurisdiction",
        "pregnancy_maternity_discrimination.time_limit_months",
        "pregnancy_maternity_discrimination.characteristic_anchor",
        "equal_pay.equal_work",
        "equal_pay.sex_equality_clause",
        "equal_pay.material_factor_defence",
        "equal_pay.tribunal_jurisdiction",
        "equal_pay.time_limit_months",
        "whistleblowing.qualifying_disclosure",
        "whistleblowing.protected_disclosure",
        "whistleblowing.detriment_protection",
        "whistleblowing.automatic_unfair_dismissal",
        "whistleblowing.complaint_route",
    ):
        assert rule_key in sql

    for authority in (
        "Equality Act 2010 s.4",
        "Equality Act 2010 s.13",
        "Equality Act 2010 s.18",
        "Equality Act 2010 s.19",
        "Equality Act 2010 s.26",
        "Equality Act 2010 s.27",
        "Equality Act 2010 s.39",
        "Equality Act 2010 s.65",
        "Equality Act 2010 s.66",
        "Equality Act 2010 s.69",
        "Equality Act 2010 s.120",
        "Equality Act 2010 s.123",
        "Equality Act 2010 s.129",
        "ERA 1996 s.43B",
        "ERA 1996 s.47B",
        "ERA 1996 s.48",
        "ERA 1996 s.103A",
    ):
        assert authority in sql

    assert "verification_status" in sql
    assert "'verified'" in sql


def test_family_leave_migration_seeds_verified_rules():
    sql = Path("db/migrations/063_family_leave_rules.sql").read_text(encoding="utf-8")

    for rule_key in (
        "maternity_rights.ordinary_maternity_leave_anchor",
        "maternity_rights.ordinary_maternity_leave_weeks",
        "maternity_rights.additional_maternity_leave_anchor",
        "maternity_rights.additional_maternity_leave_weeks",
        "maternity_rights.total_maternity_leave_weeks",
        "paternity_rights.paternity_leave_birth_anchor",
        "paternity_rights.paternity_leave_adoption_anchor",
        "paternity_rights.rights_during_after_leave",
        "paternity_rights.bereavement_anchor",
        "parental_leave.entitlement_anchor",
        "parental_leave.rights_during_after_leave",
        "parental_leave.complaint_route",
        "parental_leave.day_one_reform_anchor",
        "shared_parental_leave.birth_anchor",
        "shared_parental_leave.adoption_anchor",
        "shared_parental_leave.regulation_power_anchor",
    ):
        assert rule_key in sql

    for authority in (
        "ERA 1996 s.71",
        "ERA 1996 s.73",
        "ERA 1996 s.75E",
        "ERA 1996 s.75G",
        "ERA 1996 s.76",
        "ERA 1996 s.77",
        "ERA 1996 s.80",
        "ERA 1996 s.80A",
        "ERA 1996 s.80B",
        "ERA 1996 s.80C",
        "Paternity Leave (Bereavement) Act 2024 s.1",
        "Children and Families Act 2014 Part 7",
    ):
        assert authority in sql

    assert "verification_status" in sql
    assert "'verified'" in sql


def test_remaining_module_anchor_migration_seeds_verified_rules():
    sql = Path("db/migrations/064_remaining_employment_module_anchors.sql").read_text(encoding="utf-8")

    for rule_key in (
        "constructive_dismissal.dismissal_definition",
        "constructive_dismissal.unfair_dismissal_right_anchor",
        "constructive_dismissal.time_limit_months",
        "employment_contracts.written_particulars_right",
        "employment_contracts.day_one_particulars_anchor",
        "employment_contracts.tribunal_reference_route",
        "employment_contracts.section_38_award_anchor",
        "fixed_term_workers.less_favourable_treatment_right",
        "fixed_term_workers.objective_justification_anchor",
        "fixed_term_workers.successive_contracts_years",
        "part_time_workers.less_favourable_treatment_right",
        "part_time_workers.objective_justification_anchor",
        "part_time_workers.complaint_route",
        "agency_workers.equal_treatment_after_qualifying_period",
        "agency_workers.qualifying_period_weeks",
        "agency_workers.tribunal_complaint_route",
        "health_and_safety.detriment_protection",
        "health_and_safety.automatic_unfair_dismissal",
        "health_and_safety.complaint_route",
        "trade_union_rights.detriment_protection",
        "trade_union_rights.automatic_unfair_dismissal",
        "trade_union_rights.time_off_duties",
        "tupe.relevant_transfer_anchor",
        "tupe.automatic_transfer_anchor",
        "tupe.dismissal_anchor",
        "tupe.information_consultation_anchor",
    ):
        assert rule_key in sql

    for authority in (
        "ERA 1996 s.1",
        "ERA 1996 s.11",
        "ERA 1996 s.44",
        "ERA 1996 s.48",
        "ERA 1996 s.95",
        "ERA 1996 s.100",
        "ERA 1996 s.111",
        "Employment Act 2002 s.38",
        "Fixed-term Employees Regulations 2002 reg.3",
        "Fixed-term Employees Regulations 2002 reg.8",
        "Part-time Workers Regulations 2000 reg.5",
        "Part-time Workers Regulations 2000 reg.8",
        "Agency Workers Regulations 2010 reg.5",
        "Agency Workers Regulations 2010 reg.7",
        "Agency Workers Regulations 2010 reg.18",
        "TULRCA 1992 s.146",
        "TULRCA 1992 s.152",
        "TULRCA 1992 s.168",
        "TUPE Regulations 2006 reg.3",
        "TUPE Regulations 2006 reg.4",
        "TUPE Regulations 2006 reg.7",
        "TUPE Regulations 2006 reg.13",
    ):
        assert authority in sql

    assert "verification_status" in sql
    assert "'verified'" in sql


def test_legacy_assessment_dispatcher_fails_closed_without_required_rules():
    result = assess_case(
        "unfair_dismissal",
        {
            "dismissal_date": "2026-05-01",
            "employment_start_date": "2020-01-01",
            "gross_weekly_pay": 600,
            "age": 35,
        },
        {},
    )

    assert result["viable_claim"] is None
    assert result["insufficient_grounding"] is True
    assert "qualifying_period_months" in result["missing_rules"]
    assert "time_limit_months" in result["missing_rules"]


def test_legacy_assessment_dispatcher_uses_explicit_rule_bundle():
    result = assess_case(
        "unfair_dismissal",
        {
            "dismissal_date": "2026-05-01",
            "employment_start_date": "2020-01-01",
            "gross_weekly_pay": 600,
            "age": 35,
        },
        {
            "qualifying_period_months": 24,
            "time_limit_months": 3,
            "weeks_pay_cap_amount": 700,
            "basic_award_min": 0,
            "compensatory_cap_amount": 100000,
        },
    )

    assert result["viable_claim"] is True
    assert result["deadline"] == "2026-07-31"


def test_database_integrity_script_hard_gates_all_24_modules_for_go_live():
    script = Path("scripts/proof/prove_database_integrity.sh").read_text(encoding="utf-8")

    assert "exactly 24 employment modules" in script
    assert "all employment modules require DB backing" in script
    assert "all required employment modules are production-ready for go-live" in script
    assert "production employment modules have verified DB rules" in script


def test_full_workflow_proof_script_covers_release_gate_before_pass():
    script = Path("scripts/proof/prove_lawapp_full_workflows.sh").read_text(encoding="utf-8")

    assert "ALLOW_PARTIAL_PROOF" in script
    assert "full workflow proof completed" in script
    assert "User A registers" in script
    assert "User A saves case" in script
    assert "User B cannot access User A case" in script
    assert "unpaid user cannot generate full documents" in script
    assert "payment checkout session created" in script
    assert "invalid payment cannot unlock documents" in script
    assert "admin/reporting pages are protected" in script
    assert "/api/payments/confirm-test" in script
    assert "paid user can generate" in script
