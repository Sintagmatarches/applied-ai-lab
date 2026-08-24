from __future__ import annotations

import argparse
import json

from .datasets import CORPUS_PATH, MANIFEST_PATH, QUERY_PATH, expected_manifest, load_json, validate_corpus, validate_queries


def main() -> None:
    parser = argparse.ArgumentParser(description="Explicitly update the committed TED evaluation manifest.")
    parser.add_argument("--write", action="store_true", help="required to change dataset_manifest.json")
    args = parser.parse_args()
    corpus, query_set = load_json(CORPUS_PATH), load_json(QUERY_PATH)
    validate_corpus(corpus)
    validate_queries(query_set, {item["publicationNumber"] for item in corpus["notices"]})
    manifest = expected_manifest(corpus, query_set)
    if args.write:
        MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({**manifest, "written": bool(args.write)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
