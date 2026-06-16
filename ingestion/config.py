"""Ingestion pipeline configuration, loaded from environment variables."""

from pathlib import Path

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── PostgreSQL ────────────────────────────────────────────────────────────
    # Use POSTGRES_* individual env vars  -  they always resolve correctly.
    # DATABASE_URL in the .env file is intentionally ignored here (env_file
    # reading causes conflicts between docker-compose and local dev paths).
    # CI sets POSTGRES_HOST=localhost + POSTGRES_PASSWORD=lawapp explicitly.
    # docker-compose sets POSTGRES_HOST=db + POSTGRES_PASSWORD from .env.
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "lawapp"
    postgres_user: str = "lawapp"
    postgres_password: str = "lawapp"

    @computed_field
    @property
    def database_url(self) -> str:
        import os
        # Read DATABASE_URL from process env first.
        # CI sets it explicitly; docker-compose does NOT set it (uses POSTGRES_HOST=db).
        # The .env file is NOT loaded via load_dotenv() so os.environ only has
        # real process env vars  -  no .env file contamination.
        db_url = os.environ.get("DATABASE_URL", "").strip()
        if db_url:
            return db_url
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # ── Embedding (local Ollama only) ────────────────────────────────────────
    openai_api_key: str = "placeholder"
    embedding_model: str = "bge-large-en-v1.5"
    embedding_dim: int = 1024

    # ── Reasoning model (Anthropic) ──────────────────────────────────────────
    anthropic_api_key: str = "placeholder"
    workhorse_model_id: str = "claude-haiku-4-5-20251001"

    # ── Reasoning model (OpenRouter  -  optional, disabled by default) ──────────
    # OpenRouter is an optional model provider. When enabled, it routes calls
    # through OpenRouter's API (openai-compatible endpoint).
    # De-identification MUST run before any call. Governance MUST run after.
    # Never enable this until de-id is proven (test_deidentify.py passes).
    openrouter_api_key: str = "placeholder"
    openrouter_model_fast: str = "meta-llama/llama-3.1-8b-instruct"    # fast/cheap tier
    openrouter_model_strong: str = "anthropic/claude-haiku-4-5"         # strong tier
    openrouter_enabled: bool = False   # default OFF  -  must be explicitly enabled

    # ── Reasoning model (Local Inference Fabric  -  Ollama DaemonSet) ────────────
    # Private, no-cloud reasoning on lawapp's own metal: one Ollama pod per node
    # (namespace lawapp-ai) behind a ClusterIP Service with internalTrafficPolicy:
    # Local (node-local preference). The Mother Algorithm calls the Service DNS,
    # NEVER a node IP or localhost. When enabled this is the PRIMARY reasoning
    # provider; if inference is unreachable the provider fails soft to the stub.
    # Endpoint is config/env-driven (OLLAMA_BASE_URL / LOCAL_INFERENCE_URL)  -  not
    # hardcoded in application logic.
    local_inference_enabled: bool = False   # default OFF  -  explicit opt-in
    local_inference_url: str = "http://llm-inference-service.lawapp-ai.svc.cluster.local:11434"
    local_inference_model: str = "qwen2.5:3b-instruct-q6_K"  # Q6_K per LLM Fabric directive

    # ── Rate limits ───────────────────────────────────────────────────────────
    legislation_requests_per_second: float = 1.0
    fcl_requests_per_second: float = 1.0

    # ── Find Case Law bulk licence gate ───────────────────────────────────────
    fcl_bulk_licence_granted: bool = False

    log_level: str = "INFO"
    environment: str = "development"

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent / ".env"),
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()

# ── Source constants ──────────────────────────────────────────────────────────

LEGISLATION_BASE = "https://www.legislation.gov.uk"

# Chapter numbers verified 2026-05-29 via /id?title= resolution endpoint.
# Do not change without re-running the title resolution check.
LEGISLATION_TARGETS = [
    # (act_title, leg_type, year, chapter, sections_to_ingest)
    # ERA 1996  -  unfair dismissal sections (Phase 1 priority)
    ("Employment Rights Act 1996", "ukpga", 1996, "18", [
        "94",   # Right not to be unfairly dismissed
        "95",   # Meaning of dismissal (incl. constructive)
        "97",   # Effective date of termination
        "98",   # Fairness / reasons
        "108",  # Qualifying period (+ prospective: ERA 2025 s.25)
        "111",  # Time limit (+ prospective: ERA 2025 s.152)
        "119",  # Basic award formula
        "120",  # Minimum basic award (automatically unfair)
        "122",  # Basic award reductions
        "123",  # Compensatory award
        "124",  # Compensatory cap (+ prospective: ERA 2025 s.25)
        "207B", # Early Conciliation stop-the-clock
        "227",  # Week's pay cap
    ]),
    # TULRCA 1992  -  ACAS Code uplift/reduction
    ("Trade Union and Labour Relations (Consolidation) Act 1992", "ukpga", 1992, "52", [
        "207A", # ACAS Code uplift/reduction (up to 25%)
        "156",  # Minimum basic award (TU dismissal)
    ]),
    # Employment Tribunals Act 1996  -  EC requirement
    ("Employment Tribunals Act 1996", "ukpga", 1996, "17", [
        "18A",  # Early Conciliation requirement
    ]),
    # ERA 2025  -  amending provisions (store for reference; fetch whole act for commencement SIs)
    ("Employment Rights Act 2025", "ukpga", 2025, "36", [
        "25",   # Qualifying period + compensation cap amendments
        "152",  # Time limit extension
        "159",  # Commencement
    ]),
    # TODO: Equality Act 2010 (ukpga/2010/15)  -  Phase 5 (discrimination). Deferred.
]

FCL_BASE = "https://caselaw.nationalarchives.gov.uk"
FCL_ATOM_URL = f"{FCL_BASE}/atom.xml"

# EAT atom feed  -  confirmed working via live test 2026-05-29.
FCL_EAT_ATOM_PARAMS = {"tribunal": "eat", "order": "-date", "per_page": "50"}

# First-tier ET decisions are NOT on Find Case Law.
# They are on GOV.UK: https://www.gov.uk/employment-tribunal-decisions
# Atom feed: https://www.gov.uk/employment-tribunal-decisions.atom
# Format: HTML/PDF links (not LegalDocML). A separate GOV.UK ingestion pipeline is needed.
# STATUS: flagged  -  build after EAT pipeline is proven. Licence: OGL v3 (verify at build time).
GOVUK_ET_ATOM_URL = "https://www.gov.uk/employment-tribunal-decisions.atom"
GOVUK_ET_BASE = "https://www.gov.uk"

ACAS_CODE_URL = "https://www.acas.org.uk/acas-code-of-practice-on-disciplinary-and-grievance-procedures"
ACAS_CODE_TITLE = "ACAS Code of Practice on Disciplinary and Grievance Procedures"
ACAS_CODE_EDITION = "March 2015"  # Verified: no later edition found as of 2026-05-29. Re-check at ingest.
