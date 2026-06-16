"""
Corpus Ingestion AIA  -  builds and maintains the local legal DB (NOT a user-facing
reasoning agent). Workflow C reasons only from this DB; the ingestion AIA is the
only component allowed to fetch/parse/store legal sources.

Config-driven so future domains/countries plug in via a domain pack
(domains/<domain>/). Today it orchestrates the existing UK employment ingestors
and enforces the corpus validation gates (reject rows lacking source_url /
content_hash / last_verified_at / authority_ref). Find Case Law bulk stays
fail-closed unless FCL_BULK_LICENCE_GRANTED=true.
"""

from __future__ import annotations

import importlib
import logging
import os

logger = logging.getLogger(__name__)

# Domain pack -> ordered ingestion modules (CLI entrypoints run via -m elsewhere).
_DOMAIN_PIPELINES: dict[str, list[tuple[str, str]]] = {
    "employment_uk": [
        ("legislation", "ingestion.legislation.ingest"),
        ("limits_orders", "ingestion.rules.seed_limits_orders"),
        ("acas", "ingestion.acas.ingest"),
        ("govuk", "ingestion.govuk.ingest"),
        ("embeddings", "ingestion.embeddings.embedder"),
    ],
}


def pipeline_for(domain: str = "employment_uk") -> list[tuple[str, str]]:
    if domain not in _DOMAIN_PIPELINES:
        raise ValueError(f"no ingestion pipeline registered for domain {domain!r}")
    return _DOMAIN_PIPELINES[domain]


def check_pipeline_available(domain: str = "employment_uk") -> dict:
    """Confirm every ingestor module for a domain is importable (config-driven)."""
    report = {"domain": domain, "modules": {}, "ok": True}
    for name, mod in pipeline_for(domain):
        try:
            importlib.import_module(mod)
            report["modules"][name] = "available"
        except Exception as exc:
            report["modules"][name] = f"error:{exc}"
            report["ok"] = False
    return report


def fcl_bulk_allowed() -> bool:
    """Find Case Law bulk ingestion is fail-closed unless the licence flag is set."""
    return os.environ.get("FCL_BULK_LICENCE_GRANTED", "false").strip().lower() == "true"


def validate_corpus(conn=None) -> dict:
    """Corpus validation gates. Returns {'passed': bool, 'failures': [...]}.
    Fails closed on any placeholder/uncited/unsourced legal row."""
    own = conn is None
    failures: list[str] = []
    try:
        if own:
            from ingestion.db import get_connection
            conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM legislation WHERE source_url IS NULL OR source_url='' "
                "OR content_hash IS NULL OR content_hash='' OR last_verified_at IS NULL"
            )
            n = cur.fetchone()[0]
            if n:
                failures.append(f"{n} legislation rows missing source_url/content_hash/last_verified_at")
            cur.execute("SELECT count(*) FROM legislation WHERE section_ref IS NULL OR section_ref=''")
            ns = cur.fetchone()[0]
            if ns:
                failures.append(f"{ns} legislation rows missing section_ref")
            cur.execute("SELECT count(*) FROM rules WHERE authority_ref IS NULL OR authority_ref=''")
            r = cur.fetchone()[0]
            if r:
                failures.append(f"{r} rules missing authority_ref")
            cur.execute("SELECT count(*) FROM acas_guidance WHERE source_url IS NULL OR source_url=''")
            a = cur.fetchone()[0]
            if a:
                failures.append(f"{a} acas_guidance rows missing source_url")
            # case_law must not be populated without the licence flag
            cur.execute("SELECT count(*) FROM case_law_documents")
            cl = cur.fetchone()[0]
            if cl and not fcl_bulk_allowed():
                failures.append(f"{cl} case_law rows present without FCL_BULK_LICENCE_GRANTED")
        return {"passed": len(failures) == 0, "failures": failures}
    except Exception as exc:
        return {"passed": False, "failures": [f"corpus validation error: {exc}"]}
    finally:
        if own and conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def validate_domain_pack(domain: str = "employment_uk") -> dict:
    """Fail-closed gate: the domain pack and its required manifests must exist.
    The corpus AIA refuses to operate without sources.yaml / rules_manifest.yaml /
    licence_policy.yaml / citation_policy.yaml / workflows.yaml / domain_config.json."""
    try:
        from ingestion.domain_loader import check_pack, load_domain_pack
    except Exception as exc:
        return {"passed": False, "failures": [f"domain_loader import error: {exc}"]}
    chk = check_pack(domain)
    if not chk["ok"]:
        if not chk["exists"]:
            return {"passed": False, "failures": [f"domain pack missing: {chk['root']}"]}
        return {"passed": False, "failures": [f"missing manifest(s): {', '.join(chk['missing'])}"]}
    try:
        pack = load_domain_pack(domain)
    except Exception as exc:
        return {"passed": False, "failures": [f"domain pack load error: {exc}"]}
    failures: list[str] = []
    if not pack.legislation_targets():
        failures.append("sources.yaml declares no active legislation targets")
    if not pack.required_rule_keys():
        failures.append("rules_manifest.yaml declares no required rules")
    fcl = pack.fcl_record()
    if fcl and fcl.get("bulk_allowed") and not fcl_bulk_allowed():
        failures.append("licence_policy declares FCL bulk_allowed=true but licence flag not set")
    return {"passed": not failures, "failures": failures, "pack_root": str(pack.root)}


def _base_url_for(pack, source_id: str, source_type: str) -> str:
    """Resolve a source's base_url from the domain pack's sources.yaml."""
    if source_type == "case_law":
        cl = pack.sources.get("case_law") or {}
        return cl.get("base_url", "")
    if source_type == "official_guidance":
        for g in (pack.sources.get("guidance") or []):
            st = g.get("source_type")
            if (st == "acas" and source_id == "acas") or (st == "govuk" and source_id == "govuk"):
                return g.get("base_url", "")
        return ""
    # primary_legislation -> host root of the first declared act
    legs = pack.sources.get("legislation") or []
    if legs:
        url = legs[0].get("base_url", "")
        # https://www.legislation.gov.uk/ukpga/1996/18 -> https://www.legislation.gov.uk
        parts = url.split("/")
        if len(parts) >= 3:
            return "/".join(parts[:3])
        return url
    return ""


def register_legal_sources(domain: str = "employment_uk", conn=None) -> dict:
    """Upsert the domain pack's authorised sources into the legal_sources registry.
    Provenance lives in the DB so every corpus row traces to a registered, licensed
    source. Returns {'registered': n} or fails closed on error."""
    from ingestion.domain_loader import load_domain_pack
    pack = load_domain_pack(domain)
    default_juris = (pack.config.get("default_jurisdiction") or None)
    own = conn is None
    n = 0
    try:
        if own:
            from ingestion.db import get_connection
            conn = get_connection()
        with conn.cursor() as cur:
            for s in pack.licence_sources():
                stype = s.get("source_type", "")
                sid = s.get("source_id", "")
                cur.execute(
                    """
                    INSERT INTO legal_sources
                        (domain, source_id, source_name, source_type, base_url,
                         jurisdiction, licence_type, licence_status, bulk_allowed,
                         computational_analysis_allowed, requires_owner_approval,
                         gate_env_var, active, last_verified_at, notes)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (domain, source_id) DO UPDATE SET
                        source_name = EXCLUDED.source_name,
                        source_type = EXCLUDED.source_type,
                        base_url = EXCLUDED.base_url,
                        licence_type = EXCLUDED.licence_type,
                        licence_status = EXCLUDED.licence_status,
                        bulk_allowed = EXCLUDED.bulk_allowed,
                        computational_analysis_allowed = EXCLUDED.computational_analysis_allowed,
                        requires_owner_approval = EXCLUDED.requires_owner_approval,
                        gate_env_var = EXCLUDED.gate_env_var,
                        last_verified_at = EXCLUDED.last_verified_at,
                        notes = EXCLUDED.notes,
                        updated_at = now()
                    """,
                    (
                        domain, sid, s.get("source_name", sid), stype,
                        _base_url_for(pack, sid, stype), default_juris,
                        s.get("licence_type", ""), s.get("licence_status", ""),
                        bool(s.get("bulk_allowed", False)),
                        bool(s.get("computational_analysis_allowed", False)),
                        bool(s.get("requires_owner_approval", False)),
                        s.get("gate_env_var"), True,
                        s.get("last_verified_at"), (s.get("notes") or "").strip() or None,
                    ),
                )
                n += 1
        if own:
            conn.commit()
        return {"registered": n}
    except Exception as exc:
        if own and conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        return {"registered": n, "error": str(exc)}
    finally:
        if own and conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def validate_dataset(domain: str = "employment_uk", conn=None) -> dict:
    """End-to-end dataset gate used by prove_uk_legal_dataset.sh. Confirms every
    legislation section declared in the domain pack is actually present in the DB,
    and every required rule exists, is cited and effective-dated. Fail-closed."""
    pack_chk = validate_domain_pack(domain)
    if not pack_chk["passed"]:
        return {"passed": False, "failures": pack_chk["failures"]}

    from ingestion.domain_loader import load_domain_pack
    pack = load_domain_pack(domain)
    failures: list[str] = []
    own = conn is None
    try:
        if own:
            from ingestion.db import get_connection
            conn = get_connection()
        with conn.cursor() as cur:
            # 1) every declared (active) section present in legislation
            for act_title, section in pack.required_sections():
                cur.execute(
                    "SELECT count(*) FROM legislation WHERE section_ref = %s "
                    "AND source_url IS NOT NULL AND source_url <> '' "
                    "AND content_hash IS NOT NULL AND content_hash <> '' "
                    "AND last_verified_at IS NOT NULL",
                    (section,),
                )
                if cur.fetchone()[0] == 0:
                    failures.append(f"missing/uncited legislation section {section} ({act_title})")
            # 2) every required rule present, cited, effective-dated
            for rule_key in pack.required_rule_keys():
                cur.execute(
                    "SELECT count(*) FROM rules WHERE rule_key = %s "
                    "AND authority_ref IS NOT NULL AND authority_ref <> '' "
                    "AND effective_from IS NOT NULL",
                    (rule_key,),
                )
                if cur.fetchone()[0] == 0:
                    failures.append(f"missing/uncited/undated rule {rule_key}")
            # 3) legal_sources registry must be populated for this domain
            cur.execute("SELECT count(*) FROM legal_sources WHERE domain = %s", (domain,))
            if cur.fetchone()[0] == 0:
                failures.append("legal_sources registry empty for domain (run register_legal_sources)")
            # 4) Find Case Law must be fail-closed unless the licence flag is set
            cur.execute(
                "SELECT licence_status, bulk_allowed FROM legal_sources "
                "WHERE domain = %s AND source_type = 'case_law'",
                (domain,),
            )
            row = cur.fetchone()
            if row is not None:
                status, bulk = row[0], row[1]
                if bulk and not fcl_bulk_allowed():
                    failures.append("legal_sources marks case_law bulk_allowed=true without FCL flag")
                if status == "BLOCKED_BY_OWNER":
                    cur.execute("SELECT count(*) FROM case_law_documents")
                    if cur.fetchone()[0] and not fcl_bulk_allowed():
                        failures.append("case_law populated while source BLOCKED_BY_OWNER")
        # 5) reuse row-hygiene gates (placeholder/uncited/FCL leakage)
        hygiene = validate_corpus(conn)
        failures.extend(hygiene.get("failures", []))
        return {"passed": not failures, "failures": failures}
    except Exception as exc:
        return {"passed": False, "failures": [f"dataset validation error: {exc}"]}
    finally:
        if own and conn is not None:
            try:
                conn.close()
            except Exception:
                pass
