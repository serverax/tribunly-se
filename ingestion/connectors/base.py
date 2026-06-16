"""Source connector interface for Mother ingestion engine."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class SourceConnector(ABC):
    """Fetch, normalise, and ingest from an official legal source."""

    source_type: str = "unknown"

    @abstractmethod
    def fetch(self, **kwargs: Any) -> Any:
        """Fetch raw source material (HTTP or local script)."""

    @abstractmethod
    def normalise(self, raw: Any) -> dict:
        """Normalise to a common ingestion record shape."""

    def ingest(self, normalised: dict) -> dict:
        """Persist via existing ingestion scripts (subclass may override)."""
        return {"status": "deferred", "authority_ref": normalised.get("authority_ref")}
