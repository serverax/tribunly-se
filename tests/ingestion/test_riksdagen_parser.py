from __future__ import annotations

from datetime import date
from pathlib import Path

from ingestion.riksdagen import load_fixture_bundle, parse_fixture_bundle, split_sections
from ingestion.riksdagen.client import normalise_sfs_number
from ingestion.riksdagen.parser import parse_document
from ingestion.riksdagen.provenance import extract_provenance
from ingestion.riksdagen.resolver import RiksdagenAmbiguityError, resolve_listing_item


FIXTURES_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "riksdagen"


def bundle_path(slug: str) -> Path:
    return FIXTURES_ROOT / slug


def test_resolver_cross_checks_title_and_sfs_number():
    bundle = load_fixture_bundle(bundle_path("sfs-1982-80"))
    resolved = resolve_listing_item(
        bundle["listing"],
        expected_sfs="1982:80",
        expected_title="Lag (1982:80) om anställningsskydd",
    )
    assert normalise_sfs_number(resolved.sfs_number) == "1982:80"
    assert resolved.title == "Lag (1982:80) om anställningsskydd"
    assert resolved.amended_to == "2022:836"


def test_resolver_raises_on_title_mismatch():
    bundle = load_fixture_bundle(bundle_path("sfs-1982-80"))
    try:
        resolve_listing_item(
            bundle["listing"],
            expected_sfs="1982:80",
            expected_title="Wrong title on purpose",
        )
    except RiksdagenAmbiguityError as exc:
        assert "1982:80" in str(exc)
        assert "Wrong title on purpose" in str(exc)
    else:
        raise AssertionError("Expected RiksdagenAmbiguityError")


def test_parser_splits_las_into_current_sections_only():
    bundle = load_fixture_bundle(bundle_path("sfs-1982-80"))
    chunks = parse_fixture_bundle(bundle_path("sfs-1982-80"))
    refs = [chunk["section_ref"] for chunk in chunks]
    assert "7 §" in refs
    assert "11 §" in refs
    assert "40 §" in refs
    assert all("Övergångsbestämmelser" not in chunk["text"] for chunk in chunks)


def test_las_transition_boundary_pre_and_post_2022_10_01():
    bundle = load_fixture_bundle(bundle_path("sfs-1982-80"))
    provenance = extract_provenance(bundle["metadata"])
    assert provenance.amended_to == "2022:836"
    assert provenance.amendment_effective_from == "2022-10-01"
    assert date.fromisoformat(provenance.amendment_effective_from) >= date(2022, 10, 1)


def test_specific_sections_have_expected_text():
    bundle = load_fixture_bundle(bundle_path("sfs-1982-80"))
    sections = split_sections(bundle["text"])
    by_ref = {chunk.section_ref: chunk.text for chunk in sections}
    assert "sakliga skäl" in by_ref["7 §"]
    assert "sex månader" in by_ref["6 §"]
    assert "två månader" in by_ref["11 §"]
    assert "Underrättelse" in by_ref["40 §"] or "underrätta" in by_ref["40 §"].lower()
    assert "fyra månader" in by_ref["41 §"]


def test_other_fixture_bundles_parse():
    for slug in ["sfs-1976-580", "sfs-2008-567"]:
        chunks = parse_fixture_bundle(bundle_path(slug))
        assert len(chunks) > 0
        assert chunks[0]["source_system"] == "riksdagen"
        assert chunks[0]["sfs_number"].count(":") == 1


def test_parser_document_output_is_json_friendly():
    bundle = load_fixture_bundle(bundle_path("sfs-1982-80"))
    chunks = parse_document(bundle["metadata"], bundle["text"])
    assert isinstance(chunks, list)
    assert isinstance(chunks[0]["text"], str)
    assert chunks[0]["source_url"].startswith("https://data.riksdagen.se/dokument/")
