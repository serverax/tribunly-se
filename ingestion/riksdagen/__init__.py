"""Riksdagen open-data ingestion helpers for Swedish SFS fixtures."""

from .client import fetch_document_html, fetch_document_list, fetch_document_text
from .parser import load_fixture_bundle, parse_fixture_bundle, parse_document
from .provenance import extract_provenance
from .resolver import RiksdagenAmbiguityError, resolve_listing_item
from .sectionizer import split_sections

__all__ = [
    "RiksdagenAmbiguityError",
    "extract_provenance",
    "fetch_document_html",
    "fetch_document_list",
    "fetch_document_text",
    "load_fixture_bundle",
    "parse_document",
    "parse_fixture_bundle",
    "resolve_listing_item",
    "split_sections",
]
