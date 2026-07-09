"""SE fixture-backed ingestion for Riksdagen source bundles.

This module seeds the Swedish draft domain from live-verified fixture bundles
only. It is intentionally conservative:

* Registers the SE jurisdiction row and source registry entries.
* Ingests fixture-backed legislation rows from tests/fixtures/riksdagen/.
* Writes matching corpus_chunks rows for those fixtures.
* Seeds only rules whose literal quote/value appears in the fixture text.
* Parks everything else instead of guessing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from ingestion.db import transaction, upsert_legislation
from ingestion.riksdagen import load_fixture_bundle, parse_fixture_bundle

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
DOMAIN_ROOT = REPO_ROOT / "domains" / "employment_se"
FIXTURES_ROOT = REPO_ROOT / "tests" / "fixtures" / "riksdagen"

FIXTURE_SLUGS = ["sfs-1982-80", "sfs-1976-580", "sfs-2008-567"]
DOMAIN_CODE = "employment_se"
DOMAIN_TITLE = "Swedish Employment Law"
JURISDICTION_CODE = "SE"
COUNTRY_CODE = "SE"
LEGAL_SYSTEM = "Swedish employment law"

SECTION_TO_CLAIM_TYPE = {
    "1982:80": {
        "2 b §": "collective_agreement_boundary",
        "2 c §": "collective_agreement_boundary",
        "5 a §": "fixed_term_conversion",
        "6 §": "trial_employment",
        "7 §": "dismissal",
        "11 §": "dismissal",
        "18 §": "dismissal",
        "22 §": "dismissal",
        "25 §": "dismissal",
        "33 d §": "dismissal",
        "40 §": "invalidity",
        "41 §": "damages",
    },
    "1976:580": {
        "4 §": "collective_agreement_boundary",
    },
    "2008:567": {
        "3 §": "discrimination",
    },
}

RULE_VALUE_NUMERIC = {
    "dismissal.notice_period.min_one_month": 1,
    "dismissal.notice_period.tenure_2y": 2,
    "dismissal.notice_period.tenure_4y": 3,
    "dismissal.notice_period.tenure_6y": 4,
    "dismissal.notice_period.tenure_8y": 5,
    "dismissal.notice_period.tenure_10y": 6,
    "trial_employment.max_months": 6,
    "fixed_term_conversion.special_visstid_12m": 12,
    "fixed_term_conversion.vikariat_2y": 2,
    "fixed_term_conversion.follow_on_gap_6m": 6,
    "invalidity.deadline_2_weeks": 2,
    "invalidity.deadline_1_month_no_warning": 1,
    "invalidity.fixed_term_claim_1_month": 1,
    "damages.notice_4_months": 4,
}

RULE_UNITS = {
    "dismissal.notice_period.min_one_month": "months",
    "dismissal.notice_period.tenure_2y": "months",
    "dismissal.notice_period.tenure_4y": "months",
    "dismissal.notice_period.tenure_6y": "months",
    "dismissal.notice_period.tenure_8y": "months",
    "dismissal.notice_period.tenure_10y": "months",
    "trial_employment.max_months": "months",
    "fixed_term_conversion.special_visstid_12m": "months",
    "fixed_term_conversion.vikariat_2y": "years",
    "fixed_term_conversion.follow_on_gap_6m": "months",
    "invalidity.deadline_2_weeks": "weeks",
    "invalidity.deadline_1_month_no_warning": "months",
    "invalidity.fixed_term_claim_1_month": "months",
    "damages.notice_4_months": "months",
}

RULE_EFFECTIVE_FROM = {
    "1982:80": lambda meta: date.fromisoformat(meta.get("amendment_effective_from") or meta["datum"]),
    "1976:580": lambda meta: date.fromisoformat(meta["datum"]),
    "2008:567": lambda meta: date.fromisoformat(meta["datum"]),
}

def _load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _norm(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _slug_for_sfs(sfs_number: str) -> str:
    return f"sfs-{sfs_number.replace(':', '-')}"


def _source_id_for_sfs(sfs_number: str) -> str:
    return _slug_for_sfs(sfs_number)


def _act_short_name(sfs_number: str) -> str:
    return {
        "1982:80": "LAS",
        "1976:580": "MBL",
        "2008:567": "Diskrimineringslagen",
    }[sfs_number]


def _claim_type_for(sfs_number: str, section_ref: str) -> str:
    return SECTION_TO_CLAIM_TYPE.get(sfs_number, {}).get(section_ref, "collective_agreement_boundary")


def _fixture_text_map() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for slug in FIXTURE_SLUGS:
        bundle = load_fixture_bundle(FIXTURES_ROOT / slug)
        meta = bundle["metadata"]
        out[str(meta["beteckning"])] = {
            "slug": slug,
            "bundle": bundle,
            "text": bundle["text"],
            "text_norm": _norm(bundle["text"]),
        }
    return out


def _literal_in_fixture(value: str | None, fixture_norm: str) -> bool:
    if not value:
        return False
    return _norm(value) in fixture_norm


def _ensure_jurisdiction(cur) -> None:
    cur.execute(
        """
        INSERT INTO legal_jurisdictions (
            jurisdiction_code, country_code, label, legal_system,
            applies_to_employment_law, notes
        ) VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (jurisdiction_code) DO UPDATE SET
            country_code = EXCLUDED.country_code,
            label = EXCLUDED.label,
            legal_system = EXCLUDED.legal_system,
            applies_to_employment_law = EXCLUDED.applies_to_employment_law,
            notes = EXCLUDED.notes
        """,
        (JURISDICTION_CODE, COUNTRY_CODE, "Sweden", LEGAL_SYSTEM, True, "SE employment-law pack"),
    )


def _source_rows() -> list[dict[str, Any]]:
    sources = _load_yaml(DOMAIN_ROOT / "sources.yaml")
    rows: list[dict[str, Any]] = []
    for entry in sources.get("legislation") or []:
        rows.append(
            {
                "source_id": _source_id_for_sfs(str(entry["sfs_number"])),
                "source_name": str(entry["act_title"]),
                "source_type": "legislation",
                "base_url": str(entry["base_url"]),
                "jurisdiction": JURISDICTION_CODE,
                "licence_type": str(entry.get("licence_type") or "open_public_data"),
                "licence_name": "Riksdagen open data",
                "licence_url": "https://data.riksdagen.se/",
                "licence_status": "open",
                "bulk_allowed": True,
                "computational_analysis_allowed": True,
                "bulk_ingestion_allowed": True,
                "requires_application": False,
                "application_status": "not_required",
                "requires_owner_approval": False,
                "gate_env_var": None,
                "active": True,
                "notes": str(entry.get("notes") or "").strip() or None,
            }
        )
    case_law = sources.get("case_law") or {}
    if case_law:
        rows.append(
            {
                "source_id": "arbetsdomstolen_publicerade_avgoranden",
                "source_name": str(case_law.get("source_name") or "Arbetsdomstolen publicerade avgöranden"),
                "source_type": str(case_law.get("source_type") or "case_law"),
                "base_url": str(case_law.get("base_url") or "https://www.domstol.se/arbetsdomstolen/"),
                "jurisdiction": JURISDICTION_CODE,
                "licence_type": "court_publication",
                "licence_name": "Arbetsdomstolen publications",
                "licence_url": str(case_law.get("base_url") or ""),
                "licence_status": "assessment_only",
                "bulk_allowed": False,
                "computational_analysis_allowed": False,
                "bulk_ingestion_allowed": False,
                "requires_application": False,
                "application_status": "assessment_only",
                "requires_owner_approval": True,
                "gate_env_var": "LAWAPP_ENABLE_AD_ACCESS",
                "active": True,
                "notes": "Official publications are available for assessment only; bulk fetch is disallowed.",
            }
        )
    return rows


def _upsert_legal_source(cur, row: dict[str, Any]) -> None:
    source_key = f"{DOMAIN_CODE}:{row['source_id']}"
    cur.execute(
        """
        INSERT INTO legal_sources (
            domain, source_id, source_key, source_name, source_type, base_url,
            jurisdiction, licence_type, licence_name, licence_url, licence_status,
            bulk_allowed, bulk_ingestion_allowed, computational_analysis_allowed,
            requires_application, application_status, requires_owner_approval,
            gate_env_var, active, last_verified_at, last_checked_at, notes
        ) VALUES (
            %(domain)s, %(source_id)s, %(source_key)s, %(source_name)s, %(source_type)s, %(base_url)s,
            %(jurisdiction)s, %(licence_type)s, %(licence_name)s, %(licence_url)s, %(licence_status)s,
            %(bulk_allowed)s, %(bulk_ingestion_allowed)s, %(computational_analysis_allowed)s,
            %(requires_application)s, %(application_status)s, %(requires_owner_approval)s,
            %(gate_env_var)s, %(active)s, %(last_verified_at)s, %(last_checked_at)s, %(notes)s
        )
        ON CONFLICT (domain, source_id) DO UPDATE SET
            source_key = EXCLUDED.source_key,
            source_name = EXCLUDED.source_name,
            source_type = EXCLUDED.source_type,
            base_url = EXCLUDED.base_url,
            jurisdiction = EXCLUDED.jurisdiction,
            licence_type = EXCLUDED.licence_type,
            licence_name = EXCLUDED.licence_name,
            licence_url = EXCLUDED.licence_url,
            licence_status = EXCLUDED.licence_status,
            bulk_allowed = EXCLUDED.bulk_allowed,
            bulk_ingestion_allowed = EXCLUDED.bulk_ingestion_allowed,
            computational_analysis_allowed = EXCLUDED.computational_analysis_allowed,
            requires_application = EXCLUDED.requires_application,
            application_status = EXCLUDED.application_status,
            requires_owner_approval = EXCLUDED.requires_owner_approval,
            gate_env_var = EXCLUDED.gate_env_var,
            active = EXCLUDED.active,
            last_verified_at = EXCLUDED.last_verified_at,
            last_checked_at = EXCLUDED.last_checked_at,
            notes = EXCLUDED.notes,
            updated_at = now()
        """,
        {
            **row,
            "domain": DOMAIN_CODE,
            "source_key": source_key,
            "last_verified_at": date.today(),
            "last_checked_at": datetime.now(timezone.utc),
        },
    )


def _seed_legislation_and_corpus(cur, fixture_map: dict[str, dict[str, Any]]) -> dict[str, int]:
    counts = {"legislation_rows": 0, "corpus_chunks": 0}
    for slug in FIXTURE_SLUGS:
        bundle = fixture_map[_slug_to_sfs(slug)]["bundle"]
        parsed_chunks = parse_fixture_bundle(FIXTURES_ROOT / slug)
        meta = bundle["metadata"]
        sfs_number = str(meta["beteckning"])
        act_title = str(meta["titel"])
        source_url = str(meta["dokument_url_text"])
        source_code = _source_id_for_sfs(sfs_number)
        source_id = _lookup_legal_source_id(cur, sfs_number)
        eff_from = RULE_EFFECTIVE_FROM[sfs_number](meta)
        for chunk in parsed_chunks:
            section_ref = str(chunk["section_ref"])
            claim_type = _claim_type_for(sfs_number, section_ref)
            legislation_row = {
                "act_title": act_title,
                "leg_type": "sfs",
                "year": int(sfs_number.split(":", 1)[0]),
                "chapter": sfs_number.split(":", 1)[1],
                "section_ref": section_ref,
                "jurisdiction": JURISDICTION_CODE,
                "heading": chunk["section_heading"] or section_ref,
                "body_text": chunk["text"],
                "chunk_index": int(chunk["chunk_index"]),
                "source_url": source_url,
                "version_date": date.fromisoformat(str(meta["datum"])),
                "effective_from": eff_from,
                "effective_to": None,
                "is_prospective": False,
                "country_code": COUNTRY_CODE,
                "domain": DOMAIN_CODE,
                "source_type": "primary_legislation",
                "licence_status": "open",
                "parser_type": "riksdagen_consolidated_text",
                "parent_source_id": source_code,
                "jurisdiction_code": JURISDICTION_CODE,
                "legal_system": LEGAL_SYSTEM,
                "applies_to_ni": False,
                "applies_to_scotland": False,
                "applies_to_england_wales": False,
                "applies_to_gb": False,
            }
            upsert_legislation(cur, legislation_row)
            cur.execute(
                "SELECT id FROM legislation WHERE source_url = %s AND chunk_index = %s",
                (source_url, int(chunk["chunk_index"])),
            )
            legislation_id = cur.fetchone()["id"]
            chunk_hash = hashlib.sha256(
                f"legislation:{source_url}:{chunk['chunk_index']}:{chunk['text']}".encode("utf-8")
            ).hexdigest()
            cur.execute(
                """
                INSERT INTO corpus_chunks (
                    source_table, source_row_uuid, source_id, domain, claim_type,
                    jurisdiction_code, country_code, authority_ref, source_url,
                    title, heading, body_text, chunk_index, chunk_hash,
                    tokens_estimate, embedding, embedding_model, embedding_created_at,
                    effective_from, effective_to, is_current, is_prospective,
                    source_type, licence_status, quality_score, authority_weight
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s
                )
                ON CONFLICT (chunk_hash) DO NOTHING
                """,
                (
                    "legislation",
                    legislation_id,
                    source_id,
                    DOMAIN_CODE,
                    claim_type,
                    JURISDICTION_CODE,
                    COUNTRY_CODE,
                    f"{_act_short_name(sfs_number)} {section_ref}",
                    source_url,
                    act_title,
                    chunk["section_heading"] or None,
                    chunk["text"],
                    int(chunk["chunk_index"]),
                    chunk_hash,
                    max(1, len(chunk["text"]) // 4),
                    None,
                    None,
                    None,
                    eff_from,
                    None,
                    True,
                    False,
                    "legislation",
                    "open",
                    0.8,
                    "primary_legislation",
                ),
            )
            counts["legislation_rows"] += 1
            counts["corpus_chunks"] += 1
    return counts


def _lookup_legal_source_id(cur, sfs_number: str) -> int:
    cur.execute(
        "SELECT id FROM legal_sources WHERE domain = %s AND source_id = %s",
        (DOMAIN_CODE, _source_id_for_sfs(sfs_number)),
    )
    row = cur.fetchone()
    if row is None:
        raise RuntimeError(f"legal_sources row missing for {sfs_number}")
    return int(row["id"])


def _slug_to_sfs(slug: str) -> str:
    return slug.replace("sfs-", "").replace("-", ":")


def _seed_rules(cur, fixture_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    manifest = _load_yaml(DOMAIN_ROOT / "rules_manifest.yaml")
    candidate_rows = list(manifest.get("candidate_rules") or [])
    parked: list[dict[str, str]] = []
    seeded = 0

    for row in candidate_rows:
        sfs_number = str(row.get("sfs_number") or "")
        slug = _slug_for_sfs(sfs_number) if sfs_number else ""
        fixture = fixture_map.get(sfs_number)
        if fixture is None:
            parked.append({"rule_key": row["rule_key"], "reason": "no fixture for SFS number", "source_fixture": ""})
            continue
        if not (_literal_in_fixture(row.get("quote"), fixture["text_norm"]) or _literal_in_fixture(row.get("value"), fixture["text_norm"])):
            parked.append(
                {
                    "rule_key": row["rule_key"],
                    "reason": "literal quote/value not found in fixture",
                    "source_fixture": str(FIXTURES_ROOT / slug / "text.txt"),
                }
            )
            continue

        effective_from = RULE_EFFECTIVE_FROM[sfs_number](fixture["bundle"]["metadata"])
        value_numeric = RULE_VALUE_NUMERIC.get(row["rule_key"])
        unit = RULE_UNITS.get(row["rule_key"])
        value_text = row.get("value")
        description = f"{row['section_ref']} draft seed from fixture {slug}"
        if row.get("boundary_note"):
            description = f"{description} | {row['boundary_note']}"

        cur.execute(
            """
            INSERT INTO rules (
                rule_key, claim_type, jurisdiction, value_numeric, value_text, unit,
                description, authority_type, authority_ref, authority_url,
                effective_from, effective_to, is_prospective, last_verified_at,
                verification_status, verification_notes, domain, country_code,
                jurisdiction_code, legal_system, applies_to_ni, applies_to_scotland,
                applies_to_england_wales, applies_to_gb, is_current
            ) VALUES (
                %(rule_key)s, %(claim_type)s, %(jurisdiction)s, %(value_numeric)s,
                %(value_text)s, %(unit)s, %(description)s, %(authority_type)s,
                %(authority_ref)s, %(authority_url)s, %(effective_from)s,
                %(effective_to)s, %(is_prospective)s, now(),
                %(verification_status)s, %(verification_notes)s, %(domain)s, %(country_code)s,
                %(jurisdiction_code)s, %(legal_system)s, %(applies_to_ni)s, %(applies_to_scotland)s,
                %(applies_to_england_wales)s, %(applies_to_gb)s, %(is_current)s
            )
            ON CONFLICT (rule_key, jurisdiction, effective_from) DO UPDATE SET
                claim_type = EXCLUDED.claim_type,
                value_numeric = EXCLUDED.value_numeric,
                value_text = EXCLUDED.value_text,
                unit = EXCLUDED.unit,
                description = EXCLUDED.description,
                authority_type = EXCLUDED.authority_type,
                authority_ref = EXCLUDED.authority_ref,
                authority_url = EXCLUDED.authority_url,
                effective_to = EXCLUDED.effective_to,
                is_prospective = EXCLUDED.is_prospective,
                last_verified_at = EXCLUDED.last_verified_at,
                verification_status = EXCLUDED.verification_status,
                verification_notes = EXCLUDED.verification_notes,
                domain = EXCLUDED.domain,
                country_code = EXCLUDED.country_code,
                jurisdiction_code = EXCLUDED.jurisdiction_code,
                legal_system = EXCLUDED.legal_system,
                applies_to_ni = EXCLUDED.applies_to_ni,
                applies_to_scotland = EXCLUDED.applies_to_scotland,
                applies_to_england_wales = EXCLUDED.applies_to_england_wales,
                applies_to_gb = EXCLUDED.applies_to_gb,
                is_current = EXCLUDED.is_current
            """,
            {
                "rule_key": row["rule_key"],
                "claim_type": row["claim_type"],
                "jurisdiction": JURISDICTION_CODE,
                "value_numeric": value_numeric,
                "value_text": value_text,
                "unit": unit,
                "description": description,
                "authority_type": "legislation",
                "authority_ref": f"{_act_short_name(sfs_number)} {row['section_ref']}",
                "authority_url": str(row["source_url"]),
                "effective_from": effective_from,
                "effective_to": None,
                "is_prospective": False,
                "verification_status": "DRAFT-UNVALIDATED",
                "verification_notes": f"fixture: {FIXTURES_ROOT / slug / 'text.txt'}",
                "domain": DOMAIN_CODE,
                "country_code": COUNTRY_CODE,
                "jurisdiction_code": JURISDICTION_CODE,
                "legal_system": LEGAL_SYSTEM,
                "applies_to_ni": False,
                "applies_to_scotland": False,
                "applies_to_england_wales": False,
                "applies_to_gb": False,
                "is_current": True,
            },
        )
        seeded += 1

    for row in manifest.get("boundary_notes") or []:
        sfs_number = str(row.get("act") or "").split()[-1] if row.get("act") else ""
        fixture = fixture_map.get(sfs_number)
        if fixture is None:
            parked.append(
                {
                    "rule_key": f"boundary.{row.get('topic')}",
                    "reason": "no fixture for boundary note act",
                    "source_fixture": "",
                }
            )
            continue
        if not _literal_in_fixture(row.get("quote"), fixture["text_norm"]):
            parked.append(
                {
                    "rule_key": f"boundary.{row.get('topic')}",
                    "reason": "literal boundary note not found in fixture",
                    "source_fixture": str(FIXTURES_ROOT / _slug_for_sfs(sfs_number) / "text.txt"),
                }
            )
            continue
        parked.append(
            {
                "rule_key": f"boundary.{row.get('topic')}",
                "reason": "boundary notes are parked commentary, not seeded rules rows",
                "source_fixture": str(FIXTURES_ROOT / _slug_for_sfs(sfs_number) / "text.txt"),
            }
        )

    return {"seeded": seeded, "parked": parked}


def seed_employment_se() -> dict[str, Any]:
    fixture_map = _fixture_text_map()
    with transaction() as cur:
        _ensure_jurisdiction(cur)
        for row in _source_rows():
            row = dict(row)
            row["domain"] = DOMAIN_CODE
            row["last_verified_at"] = date.today()
            row["last_checked_at"] = datetime.now(timezone.utc)
            _upsert_legal_source(cur, row)

        corpus_counts = _seed_legislation_and_corpus(cur, fixture_map)
        rules_report = _seed_rules(cur, fixture_map)

    return {
        "jurisdiction": JURISDICTION_CODE,
        "fixtures": len(FIXTURE_SLUGS),
        **corpus_counts,
        **rules_report,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the Swedish fixture-backed employment pack")
    parser.parse_args()
    report = seed_employment_se()
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s  -  %(message)s")
    main()
