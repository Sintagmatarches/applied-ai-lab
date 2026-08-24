from __future__ import annotations

import argparse
import json
from pathlib import Path

from tender_ai.config import AiConfig
from tender_ai.ollama import OllamaClient
from tender_ai.retrieval import cosine
from tender_ai.storage import utc_now

from .datasets import digest, load_evaluation_inputs
from .retrieval_eval import RECORDED_SIMILARITY_PATH, evidence_documents


def main() -> None:
    parser = argparse.ArgumentParser(description="Record actual Ollama similarities for deterministic evaluation replay.")
    parser.add_argument("--output", type=Path, default=RECORDED_SIMILARITY_PATH)
    parser.add_argument("--write", action="store_true", help="required to replace the committed similarity artifact")
    args = parser.parse_args()
    corpus, query_set, manifest = load_evaluation_inputs()
    documents = evidence_documents(corpus)
    client = OllamaClient(AiConfig.from_env())
    model = client.model_fingerprint(client.config.embedding_model)
    texts = [item["text"] for item in documents]
    document_vectors, document_metrics = client.embed(texts)
    query_vectors, query_metrics = client.embed([item["query"] for item in query_set["queries"]])
    result = {
        "similaritySchemaVersion": "1.0.0",
        "generatedAt": utc_now(),
        "method": "Exact cosine similarity from actual Ollama /api/embed outputs; vectors are not committed, only the compact score matrix.",
        "model": model,
        "corpusDigest": manifest["corpusDigest"],
        "querySetDigest": manifest["querySetDigest"],
        "documentDigest": digest([{"evidence_id": item["evidence_id"], "publication": item["publication"], "text": item["text"]} for item in documents]),
        "evidenceIds": [item["evidence_id"] for item in documents],
        "scores": {query["query_id"]: [round(cosine(query_vectors[index], vector), 8) for vector in document_vectors] for index, query in enumerate(query_set["queries"])},
        "runtimeMetrics": {"documentEmbedding": document_metrics.public(), "queryEmbedding": query_metrics.public()},
        "limitations": ["A mutable configured tag is made inspectable by the recorded local model digest; reruns with a different digest require an explicit artifact and baseline update.", "The matrix supports deterministic replay of this bounded corpus, not byte-for-byte claims about every Ollama host."],
    }
    if args.write:
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "written": bool(args.write), "evidenceCount": len(documents), "queryCount": len(query_set["queries"]), "model": model}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
