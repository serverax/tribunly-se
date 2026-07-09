"""Benchmark harness for SE retrieval strategies.

This script is intentionally offline-friendly. It compares result sets that are
produced later by two retrieval strategies:
  - translate-at-boundary
  - multilingual embedder

At this phase we do not pull any model weights. The harness scores supplied
result files against the golden set and computes recall@k and precision.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ScoredQuery:
    query_id: str
    language: str
    expected_passage_id: str
    predicted_passage_ids: list[str]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_passage_id(value: str) -> str:
    return value.strip()


def score_at_k(expected: str, predicted: list[str], k: int) -> float:
    top_k = [normalize_passage_id(item) for item in predicted[:k]]
    return 1.0 if normalize_passage_id(expected) in top_k else 0.0


def precision(expected: str, predicted: list[str], k: int) -> float:
    top_k = [normalize_passage_id(item) for item in predicted[:k]]
    if not top_k:
        return 0.0
    correct = sum(1 for item in top_k if item == normalize_passage_id(expected))
    return correct / len(top_k)


def evaluate(golden: list[dict[str, Any]], results: list[dict[str, Any]], k: int) -> dict[str, float]:
    results_by_id = {item["query_id"]: item for item in results}
    recall_scores = []
    precision_scores = []
    for entry in golden:
        result = results_by_id.get(entry["query_id"], {})
        predicted = list(result.get("predicted_passage_ids") or [])
        recall_scores.append(score_at_k(entry["expected_passage_id"], predicted, k))
        precision_scores.append(precision(entry["expected_passage_id"], predicted, k))
    total = max(len(golden), 1)
    return {
        f"recall@{k}": sum(recall_scores) / total,
        f"precision@{k}": sum(precision_scores) / total,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--golden", required=True, type=Path)
    parser.add_argument("--translate-results", required=True, type=Path)
    parser.add_argument("--multilingual-results", required=True, type=Path)
    parser.add_argument("--k", default=3, type=int)
    args = parser.parse_args()

    golden = load_json(args.golden)
    translate = load_json(args.translate_results)
    multilingual = load_json(args.multilingual_results)

    payload = {
        "translate_at_boundary": evaluate(golden, translate, args.k),
        "multilingual_embedder": evaluate(golden, multilingual, args.k),
        "k": args.k,
        "queries": len(golden),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
