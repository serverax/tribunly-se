"""
Domain-pack loader — makes domains/<domain>/ the source of truth for the corpus.

The legislation source list, required rules, licence policy and citation policy
live in the domain pack (YAML/JSON), NOT only in Python. This loader reads them
and exposes them to:
  - ingestion/legislation/ingest.py  (legislation_targets)
  - backend/core/agents/corpus_ingestion_aia.py  (load_domain_pack / validate)
  - scripts/prove_uk_legal_dataset.sh  (required_sections, required_rules)

Fail-closed: a missing pack or missing manifest raises DomainPackError so the
ingestion AIA and proof scripts stop rather than silently ingesting nothing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# Repo root = parent of the ingestion package directory.
_REPO_ROOT = Path(__file__).resolve().parents[1]
_DOMAINS_DIR = _REPO_ROOT / "domains"

_REQUIRED_MANIFESTS = (
    "domain_config.json",
    "sources.yaml",
    "rules_manifest.yaml",
    "citation_policy.yaml",
    "licence_policy.yaml",
    "workflows.yaml",
)


class DomainPackError(RuntimeError):
    """Raised when a domain pack or one of its required manifests is missing/invalid."""


@dataclass
class DomainPack:
    domain: str
    root: Path
    config: dict
    sources: dict
    rules: dict
    citation_policy: dict
    licence_policy: dict
    workflows: dict
    missing: list[str] = field(default_factory=list)

    # ── legislation ────────────────────────────────────────────────────────
    def legislation_targets(self, include_inactive: bool = False) -> list[tuple]:
        """Return [(act_title, leg_type, year, chapter, [sections]), ...] from the
        pack's sources.yaml. Inactive acts (e.g. Equality Act 2010) are excluded
        unless include_inactive=True."""
        targets: list[tuple] = []
        for act in self.sources.get("legislation", []) or []:
            if not include_inactive and act.get("active") is False:
                continue
            sections = [str(s) for s in (act.get("sections") or [])]
            targets.append((
                act["act_title"],
                act["leg_type"],
                int(act["year"]),
                str(act["chapter"]),
                sections,
            ))
        return targets

    def required_sections(self, include_inactive: bool = False) -> list[tuple[str, str]]:
        """Flat [(act_title, section_ref), ...] of every section the pack declares
        as required in the corpus. Used by the proof to assert DB parity."""
        out: list[tuple[str, str]] = []
        for act_title, _t, _y, _c, sections in self.legislation_targets(include_inactive):
            for s in sections:
                out.append((act_title, s))
        return out

    # ── rules ──────────────────────────────────────────────────────────────
    def required_rule_keys(self) -> list[str]:
        return [r["rule_key"] for r in (self.rules.get("required_rules") or [])]

    # ── licence ────────────────────────────────────────────────────────────
    def licence_sources(self) -> list[dict]:
        return list(self.licence_policy.get("sources") or [])

    def forbidden_sources(self) -> list[str]:
        return list(self.licence_policy.get("forbidden_sources") or [])

    def fcl_record(self) -> dict | None:
        for s in self.licence_sources():
            if s.get("source_type") == "case_law" or s.get("source_id") == "find_case_law":
                return s
        return None


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise DomainPackError(f"{path} did not parse to a mapping")
    return data


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def domain_dir(domain: str) -> Path:
    return _DOMAINS_DIR / domain


def check_pack(domain: str = "employment_uk") -> dict:
    """Non-raising health check: which required manifests are present/missing."""
    root = domain_dir(domain)
    present, missing = [], []
    for name in _REQUIRED_MANIFESTS:
        (present if (root / name).is_file() else missing).append(name)
    return {
        "domain": domain,
        "root": str(root),
        "exists": root.is_dir(),
        "present": present,
        "missing": missing,
        "ok": root.is_dir() and not missing,
    }


def load_domain_pack(domain: str = "employment_uk") -> DomainPack:
    """Load and validate a domain pack. Fail-closed: raise on missing pack/manifest."""
    root = domain_dir(domain)
    if not root.is_dir():
        raise DomainPackError(f"domain pack not found: {root}")
    missing = [n for n in _REQUIRED_MANIFESTS if not (root / n).is_file()]
    if missing:
        raise DomainPackError(
            f"domain pack {domain!r} missing required manifest(s): {', '.join(missing)}"
        )
    return DomainPack(
        domain=domain,
        root=root,
        config=_load_json(root / "domain_config.json"),
        sources=_load_yaml(root / "sources.yaml"),
        rules=_load_yaml(root / "rules_manifest.yaml"),
        citation_policy=_load_yaml(root / "citation_policy.yaml"),
        licence_policy=_load_yaml(root / "licence_policy.yaml"),
        workflows=_load_yaml(root / "workflows.yaml"),
    )


if __name__ == "__main__":  # pragma: no cover — manual smoke check
    import sys
    dom = sys.argv[1] if len(sys.argv) > 1 else "employment_uk"
    chk = check_pack(dom)
    print(json.dumps(chk, indent=2))
    if not chk["ok"]:
        sys.exit(1)
    pack = load_domain_pack(dom)
    print(f"legislation targets: {len(pack.legislation_targets())} act(s)")
    print(f"required sections:   {len(pack.required_sections())}")
    print(f"required rules:      {pack.required_rule_keys()}")
    fcl = pack.fcl_record()
    print(f"FCL licence status:  {fcl and fcl.get('licence_status')}")
