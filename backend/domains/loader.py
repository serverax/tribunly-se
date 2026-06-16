"""
Load domain packs from domains/<code>/domain_config.json.

No domain-specific imports. Packs are data-only JSON + optional asset folders.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

from backend.domains.pack_contract import DomainPack, PackStatus, validate_pack_config

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DOMAINS_ROOT = _REPO_ROOT / "domains"
_SKIP_DIRS = {"_schema", "employment_uk"}


def domains_root() -> Path:
    return _DOMAINS_ROOT


def _parse_status(raw: str) -> PackStatus:
    try:
        return PackStatus(raw)
    except ValueError:
        return PackStatus.UNAVAILABLE


def _load_raw_config(pack_dir: Path) -> Optional[dict]:
    cfg = pack_dir / "domain_config.json"
    if not cfg.is_file():
        return None
    try:
        return json.loads(cfg.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed to read %s: %s", cfg, exc)
        return None


def load_domain_pack(code: str, *, reload: bool = False) -> Optional[DomainPack]:
    """Load one pack by module_code (directory name under domains/)."""
    if reload:
        _discover_all_packs.cache_clear()

    pack_dir = _DOMAINS_ROOT / code
    raw = _load_raw_config(pack_dir)
    if raw is None:
        return None

    errors = validate_pack_config(raw, code)
    if errors:
        logger.warning("Domain pack %s validation: %s", code, "; ".join(errors))

    status = _parse_status(str(raw.get("status", PackStatus.UNAVAILABLE.value)))
    enabled = bool(raw.get("enabled", False))

    template_paths = raw.get("template_paths") or []
    if isinstance(template_paths, str):
        template_paths = [template_paths]

    return DomainPack(
        module_code=str(raw.get("module_code", code)),
        title=str(raw.get("title", code.replace("_", " ").title())),
        jurisdiction=list(raw.get("jurisdiction") or []),
        country_code=str(raw.get("country_code", "GB")),
        enabled=enabled,
        status=status,
        rules_namespace=raw.get("rules_namespace"),
        retrieval_domain=raw.get("retrieval_domain") or raw.get("rules_namespace"),
        enabled_modules=list(raw.get("enabled_modules") or []),
        ingestion_sources_path=raw.get("ingestion_sources"),
        template_paths=list(template_paths),
        prompt_overrides_path=raw.get("prompt_overrides_path"),
        validation_rules_path=raw.get("validation_rules_path"),
        pack_root=pack_dir,
        raw=raw,
    )


@lru_cache(maxsize=1)
def _discover_all_packs() -> dict[str, DomainPack]:
    packs: dict[str, DomainPack] = {}
    if not _DOMAINS_ROOT.is_dir():
        return packs
    for entry in sorted(_DOMAINS_ROOT.iterdir()):
        if not entry.is_dir() or entry.name in _SKIP_DIRS or entry.name.startswith("."):
            continue
        pack = load_domain_pack(entry.name)
        if pack is not None:
            packs[pack.module_code] = pack
    return packs


def list_domain_packs(*, reload: bool = False) -> list[DomainPack]:
    if reload:
        _discover_all_packs.cache_clear()
    return list(_discover_all_packs().values())


def get_domain_pack(code: str) -> Optional[DomainPack]:
    return _discover_all_packs().get(code) or load_domain_pack(code)


def pack_codes() -> list[str]:
    return sorted(_discover_all_packs().keys())
