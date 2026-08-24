from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any


EVAL_DIR = Path(__file__).parent
CORPUS_PATH = EVAL_DIR / "real_ted_notices.json"
QUERY_PATH = EVAL_DIR / "retrieval_queries.json"
MANIFEST_PATH = EVAL_DIR / "dataset_manifest.json"


class DatasetContractError(ValueError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise DatasetContractError(f"{path.name} must contain a JSON object")
    return value


def validate_corpus(corpus: dict[str, Any]) -> None:
    required = {"datasetSchemaVersion", "datasetVersion", "generatedAt", "source", "labelMethod", "notices"}
    missing = required - set(corpus)
    if missing:
        raise DatasetContractError(f"corpus missing fields: {', '.join(sorted(missing))}")
    notices = corpus.get("notices")
    if not isinstance(notices, list) or not notices:
        raise DatasetContractError("corpus notices must be a non-empty array")
    publications = [str(item.get("publicationNumber", "")) for item in notices if isinstance(item, dict)]
    duplicates = sorted(key for key, count in Counter(publications).items() if key and count > 1)
    if duplicates:
        raise DatasetContractError(f"duplicate publication number: {', '.join(duplicates)}")
    for item in notices:
        if not isinstance(item, dict):
            raise DatasetContractError("every notice must be an object")
        for key in ("publicationNumber", "noticeIdentifier", "officialSourceUrl", "retrievedAt", "sourceQuery", "selectionRationale", "raw", "expected"):
            if key not in item:
                raise DatasetContractError(f"notice {item.get('publicationNumber', '?')} missing {key}")
        expected = item["expected"]
        if not isinstance(expected, dict) or not isinstance(expected.get("lotIds"), list):
            raise DatasetContractError(f"notice {item['publicationNumber']} has malformed expected labels")
        if expected.get("labelMethod") not in {"source-derived-mechanical", "source-derived-with-documented-interpretation"}:
            raise DatasetContractError(f"notice {item['publicationNumber']} has an unsupported label method")


def validate_queries(query_set: dict[str, Any], publications: set[str]) -> None:
    required = {"querySetSchemaVersion", "querySetVersion", "evaluationSplitVersion", "queries"}
    missing = required - set(query_set)
    if missing:
        raise DatasetContractError(f"query set missing fields: {', '.join(sorted(missing))}")
    queries = query_set.get("queries")
    if not isinstance(queries, list) or not queries:
        raise DatasetContractError("queries must be a non-empty array")
    ids = [str(item.get("query_id", "")) for item in queries if isinstance(item, dict)]
    duplicates = sorted(key for key, count in Counter(ids).items() if key and count > 1)
    if duplicates:
        raise DatasetContractError(f"duplicate query id: {', '.join(duplicates)}")
    seen_text_by_split: dict[str, set[str]] = {"tuning": set(), "holdout": set()}
    publication_splits: dict[str, set[str]] = {}
    for item in queries:
        if not isinstance(item, dict):
            raise DatasetContractError("every query must be an object")
        for key in ("query_id", "query", "relevance", "scenario", "rationale", "split"):
            if key not in item:
                raise DatasetContractError(f"query {item.get('query_id', '?')} missing {key}")
        split = item["split"]
        if split not in seen_text_by_split:
            raise DatasetContractError(f"query {item['query_id']} has invalid split")
        relevance = item["relevance"]
        if not isinstance(relevance, dict) or not relevance:
            raise DatasetContractError(f"query {item['query_id']} is missing relevance labels")
        unknown = sorted(set(relevance) - publications)
        if unknown:
            raise DatasetContractError(f"query {item['query_id']} references unknown publications: {', '.join(unknown)}")
        if any(not isinstance(grade, int) or grade < 1 or grade > 3 for grade in relevance.values()):
            raise DatasetContractError(f"query {item['query_id']} has invalid graded relevance")
        for publication in relevance:
            publication_splits.setdefault(publication, set()).add(split)
        normalized = " ".join(str(item["query"]).lower().split())
        seen_text_by_split[split].add(normalized)
    overlap = seen_text_by_split["tuning"] & seen_text_by_split["holdout"]
    if overlap:
        raise DatasetContractError(f"tuning/holdout query text overlap: {', '.join(sorted(overlap))}")
    publication_overlap = sorted(publication for publication, splits in publication_splits.items() if len(splits) > 1)
    if publication_overlap:
        raise DatasetContractError(
            "tuning/holdout publication overlap: " + ", ".join(publication_overlap)
        )


def expected_manifest(corpus: dict[str, Any], query_set: dict[str, Any]) -> dict[str, Any]:
    notices = corpus["notices"]
    return {
        "datasetSchemaVersion": "1.0.0",
        "datasetVersion": corpus["datasetVersion"],
        "generatedAt": corpus["generatedAt"],
        "source": corpus["source"],
        "noticeCount": len(notices),
        "queryCount": len(query_set["queries"]),
        "noticeIds": [item["publicationNumber"] for item in notices],
        "corpusDigest": digest(corpus),
        "querySetDigest": digest(query_set),
        "labelMethod": corpus["labelMethod"],
        "evaluationSplitVersion": query_set["evaluationSplitVersion"],
    }


def load_evaluation_inputs(*, verify_manifest: bool = True) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    corpus = load_json(CORPUS_PATH)
    query_set = load_json(QUERY_PATH)
    validate_corpus(corpus)
    publications = {item["publicationNumber"] for item in corpus["notices"]}
    validate_queries(query_set, publications)
    expected = expected_manifest(corpus, query_set)
    if verify_manifest:
        manifest = load_json(MANIFEST_PATH)
        if manifest != expected:
            changed = sorted(key for key in set(manifest) | set(expected) if manifest.get(key) != expected.get(key))
            raise DatasetContractError(f"dataset manifest mismatch: {', '.join(changed)}")
    return corpus, query_set, expected
