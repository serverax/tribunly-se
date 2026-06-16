"""Unit tests for Reciprocal Rank Fusion (backend/core/retrieval/rrf.py).

Pure-function tests  -  no database. They prove the fusion maths, the
exact-citation priority, score preservation, and the cross-list 'hybrid'
detection that makes hybrid retrieval beat either path alone.
"""
from __future__ import annotations

import pytest

from backend.core.retrieval.rrf import (
    DEFAULT_RRF_K,
    reciprocal_rank_fusion,
)


def _lex(cite, text, rank):
    return {"cite": cite, "text": text, "rank": rank}


def _sem(cite, text, distance):
    return {"cite": cite, "text": text, "distance": distance}


def test_rrf_constant_default_is_60():
    assert DEFAULT_RRF_K == 60


def test_rrf_merges_and_doc_in_both_lists_outranks_single_list():
    # 'shared' is rank-2 in lexical and rank-2 in semantic.
    # 'lex_only' is rank-1 in lexical only. 'sem_only' is rank-1 in semantic only.
    lexical = [_lex("LEX1", "lex only top", 0.9), _lex("SHARED", "shared body", 0.5)]
    semantic = [_sem("SEM1", "sem only top", 0.10), _sem("SHARED", "shared body", 0.20)]

    out = reciprocal_rank_fusion(lexical, semantic, k=60)

    by_cite = {r["cite"]: r for r in out}
    # shared got 1/(60+2)+1/(60+2); each single-list top got 1/(60+1).
    assert by_cite["SHARED"]["retrieval"] == "hybrid"
    assert by_cite["LEX1"]["retrieval"] == "lexical"
    assert by_cite["SEM1"]["retrieval"] == "vector"
    assert by_cite["SHARED"]["rrf_score"] > by_cite["LEX1"]["rrf_score"]
    assert by_cite["SHARED"]["rrf_score"] > by_cite["SEM1"]["rrf_score"]
    # shared ranks first overall
    assert out[0]["cite"] == "SHARED"


def test_rrf_preserves_lexical_and_vector_scores():
    lexical = [_lex("A", "alpha", 0.42)]
    semantic = [_sem("A", "alpha", 0.30)]
    out = reciprocal_rank_fusion(lexical, semantic)
    a = out[0]
    assert a["lexical_score"] == pytest.approx(0.42)
    # vector_score = 1 - distance
    assert a["vector_score"] == pytest.approx(0.70)
    assert a["lexical_rank"] == 1
    assert a["semantic_rank"] == 1


def test_rrf_math_exact_value():
    lexical = [_lex("A", "a", 0.5)]   # rank 1 lexical
    semantic = [_sem("B", "b", 0.5)]  # rank 1 semantic
    out = reciprocal_rank_fusion(lexical, semantic, k=60)
    for r in out:
        assert r["rrf_score"] == pytest.approx(1.0 / 61)


def test_exact_section_citation_ranks_top1_over_better_cosine():
    # Query explicitly names s.98. A semantically-strong-but-wrong chunk
    # (s.139 redundancy) is rank-1 in BOTH lists. The exact s.98 hit appears
    # only weakly (rank-3 lexical). Exact-citation boost must lift it to #1.
    query = "what does section 98 ERA 1996 require for a fair dismissal"
    lexical = [
        _lex("ERA 1996 s.139", "redundancy definition", 0.9),
        _lex("ERA 1996 s.94", "right not to be unfairly dismissed", 0.7),
        _lex("ERA 1996 s.98", "fairness of dismissal", 0.3),
    ]
    semantic = [
        _sem("ERA 1996 s.139", "redundancy definition", 0.05),
        _sem("ERA 1996 s.94", "right not to be unfairly dismissed", 0.10),
    ]
    out = reciprocal_rank_fusion(lexical, semantic, query=query)
    assert out[0]["cite"] == "ERA 1996 s.98"
    assert out[0]["exact_citation_match"] is True
    # The non-matching ones must not be flagged as exact matches.
    assert all(not r["exact_citation_match"] for r in out if r["cite"] != "ERA 1996 s.98")


def test_neutral_citation_exact_match():
    query = "summarise [2021] UKSC 1"
    lexical = [_lex("Some Other Case [2020] EWCA 5", "x", 0.9),
               _lex("Uber BV v Aslam [2021] UKSC 1", "worker status", 0.2)]
    semantic = [_sem("Some Other Case [2020] EWCA 5", "x", 0.05)]
    out = reciprocal_rank_fusion(lexical, semantic, query=query)
    assert out[0]["cite"] == "Uber BV v Aslam [2021] UKSC 1"
    assert out[0]["exact_citation_match"] is True


def test_no_citation_in_query_means_no_boost():
    query = "was my dismissal fair"  # no explicit citation token
    lexical = [_lex("ERA 1996 s.98", "fairness", 0.5)]
    semantic = [_sem("ERA 1996 s.98", "fairness", 0.5)]
    out = reciprocal_rank_fusion(lexical, semantic, query=query)
    assert out[0]["exact_citation_match"] is False


def test_empty_inputs_return_empty():
    assert reciprocal_rank_fusion([], []) == []


def test_invalid_k_raises():
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([], [], k=0)


def test_final_limit_caps_results():
    lexical = [_lex(f"C{i}", f"body{i}", 1.0 / (i + 1)) for i in range(10)]
    out = reciprocal_rank_fusion(lexical, [], final_limit=3)
    assert len(out) == 3


def test_does_not_mutate_caller_dicts():
    lexical = [_lex("A", "a", 0.5)]
    semantic = [_sem("A", "a", 0.5)]
    reciprocal_rank_fusion(lexical, semantic)
    assert "rrf_score" not in lexical[0]
    assert "rrf_score" not in semantic[0]
    assert "retrieval" not in lexical[0]
