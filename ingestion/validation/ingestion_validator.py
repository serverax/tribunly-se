"""Ingestion validator  -  quarantine on fail."""

from __future__ import annotations

from dataclasses import dataclass, field

from ingestion.validation.legal_normaliser import normalise_record


@dataclass
class ValidationVerdict:
    passed: bool
    errors: list[str] = field(default_factory=list)


class IngestionValidator:
    """Validate normalised records before DB promotion."""

    REQUIRED = ("source_type", "authority_ref", "content_hash")

    def validate(self, record: dict) -> ValidationVerdict:
        normalised = normalise_record(record)
        errors: list[str] = []
        for key in self.REQUIRED:
            if not normalised.get(key):
                errors.append(f"missing_{key}")
        if normalised.get("body_text", "").strip() == "":
            errors.append("empty_body")
        if len(normalised.get("authority_ref", "")) < 3:
            errors.append("authority_ref_too_short")
        return ValidationVerdict(passed=len(errors) == 0, errors=errors)
