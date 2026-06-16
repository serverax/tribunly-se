"""Domain pack discovery API (generic, no domain-specific logic)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.domains.loader import get_domain_pack, list_domain_packs
from backend.domains.registry import get_active_domain, list_domains

router = APIRouter(prefix="/api/domains", tags=["domains"])


@router.get("")
def list_domain_packs_endpoint() -> dict:
    """List all domain packs and operational status."""
    packs = list_domains()
    return {
        "active_domain": get_active_domain(),
        "domains": packs,
        "count": len(packs),
    }


@router.get("/{code}")
def get_domain_pack_endpoint(code: str) -> dict:
    """Return metadata for one domain pack."""
    pack = get_domain_pack(code)
    if pack is None:
        raise HTTPException(status_code=404, detail=f"Domain pack {code!r} not found")
    return pack.to_api_dict()


def include_domain_routes(app) -> None:
    app.include_router(router)
