from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
import json
from pathlib import Path
import tempfile
import time

from .config import AiConfig
from .domain import DEMO_PROFILE
from .ollama import OllamaUnavailable
from .runtime import create_runtime
from .ted import TedClient, normalize
from .storage import utc_now


SCENARIOS = [
    {"name":"Finland + data","filters":{"buyer_country":"FIN","keywords":"data"}},
    {"name":"Finland + software","filters":{"buyer_country":"FIN","keywords":"software"}},
    {"name":"Finland + artificial intelligence","filters":{"buyer_country":"FIN","keywords":"artificial intelligence"}},
    {"name":"Finland + analytics","filters":{"buyer_country":"FIN","keywords":"analytics"}},
    {"name":"EU + machine learning","filters":{"keywords":"machine learning"}},
    {"name":"ICT/Data CPV 72*","filters":{"buyer_country":"FIN","cpv":"72*"}},
]


def main()->None:
    started=time.perf_counter(); client=TedClient(); seen={}; scenario_results=[]; fetched_at=utc_now()
    period={"published_from":str(date.today()-timedelta(days=180)),"published_to":str(date.today())}
    for scenario in SCENARIOS:
        call_started=time.perf_counter()
        try:
            response=client.search({**scenario["filters"],**period},limit=8)
            notices=[normalize(item,fetched_at) for item in response.get("notices",[])]
            for notice in notices: seen[notice["notice_id"]]=notice
            scenario_results.append({"name":scenario["name"],"query":response.get("query"),"returned":len(notices),"total_notice_count":response.get("totalNoticeCount"),"latency_ms":round((time.perf_counter()-call_started)*1000,3),"publication_ids":[n["publication_id"] for n in notices]})
        except Exception as error:
            scenario_results.append({"name":scenario["name"],"error":f"{type(error).__name__}: {error}","returned":0})
    with tempfile.TemporaryDirectory() as tmp:
        config=AiConfig.from_env(); config=replace(config,database_path=Path(tmp)/"live.sqlite3",trace_path=Path("artifacts/tender-live-agent-trace.jsonl"))
        runtime=create_runtime(config); notices=list(seen.values())
        enriched_notices=[]; xml_failures=[]
        for index, notice in enumerate(notices):
            if index < 12:
                try: notice=client.enrich_from_xml(notice)
                except Exception as error: xml_failures.append({"publication_id":notice["publication_id"],"error":f"{type(error).__name__}: {error}"})
            enriched_notices.append(notice)
        notices=enriched_notices; persistence=runtime.storage.ingest(notices,DEMO_PROFILE)
        try: indexing=runtime.retriever.index_pending(limit=500)
        except OllamaUnavailable as error: indexing={"indexed":0,"error":str(error)}
        try:
            hits,retrieval_metrics=runtime.retriever.search("data analytics artificial intelligence services in Finland",top_k=5,country="FIN")
            retrieval=[hit.public() for hit in hits]
        except OllamaUnavailable as error: retrieval_metrics={"error":str(error)}; retrieval=[]
        sample=next((notice for notice in notices if notice.get("requirements")),notices[0] if notices else None)
        sample_id = sample["notice_id"] if sample else "missing"
        try: agent=runtime.agent.ask(f"Use get_notice for notice_id {sample_id}. State this notice's title and buyer using only its evidence IDs.")
        except OllamaUnavailable as error: agent=None; agent_error=str(error)
        sample_assessment=runtime.storage.latest_assessment(sample_id) if sample else None
        artifact={
            "verified_at":utc_now(),"source":"Official TED Search API v3","endpoint":"https://api.ted.europa.eu/v3/notices/search",
            "period":period,"scenarios":scenario_results,"unique_notices":len(notices),"persistence":persistence,
            "knowledge_base":runtime.storage.stats(),"xml_documents":{"attempted":min(12,len(notices)),"failures":xml_failures},"embedding_index":indexing,"retrieval":{"metrics":retrieval_metrics,"hits":retrieval},
            "sample_normalized_notice": sample,
            "sample_assessment": sample_assessment,
            "agent_execution": asdict_agent(agent) if agent else {"error":agent_error},
            "elapsed_ms":round((time.perf_counter()-started)*1000,3),
            "version_demo":"No live amendment is claimed here; deterministic version regression is documented separately.",
        }
    out=Path("artifacts/tender-live-verification.json"); out.parent.mkdir(exist_ok=True); out.write_text(json.dumps(artifact,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"unique_notices":artifact["unique_notices"],"persistence":persistence,"embedding_index":indexing,"retrieval_hits":len(retrieval),"agent":artifact["agent_execution"]},ensure_ascii=False,indent=2))


def asdict_agent(agent):
    from dataclasses import asdict
    return asdict(agent)


if __name__=="__main__": main()
