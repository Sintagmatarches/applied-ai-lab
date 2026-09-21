from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import asynccontextmanager
import sqlite3
from typing import Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .agent import as_json, unavailable_result
from .domain import DEMO_PROFILE, SupplierProfile
from .ollama import OllamaUnavailable
from .runtime import create_runtime
from .ted import TedClient, normalize
from .storage import utc_now
from .telemetry import RequestTelemetry, configure


@asynccontextmanager
async def lifespan(app):
    shutdown = configure()
    try:
        yield
    finally:
        shutdown()


runtime=create_runtime(); ted=TedClient(); app=FastAPI(title="Applied AI Lab · EU Tender Intelligence",version="2.1.0", lifespan=lifespan)
app.add_middleware(RequestTelemetry)
app.add_middleware(CORSMiddleware,allow_origins=["http://localhost:3000","http://127.0.0.1:3000"],allow_credentials=False,allow_methods=["GET","POST"],allow_headers=["content-type"])


class IngestRequest(BaseModel):
    filters: dict[str,Any]=Field(default_factory=lambda:{"buyer_country":"FIN","keywords":"data"})
    limit:int=Field(default=20,ge=1,le=250)
    profile:dict[str,Any]|None=None
    include_documents:bool=True
class AskRequest(BaseModel):
    question:str=Field(min_length=2,max_length=1000); profile:dict[str,Any]=Field(default_factory=lambda:DEMO_PROFILE.public())


@app.get("/live")
async def live():
    return {"status": "alive"}


@app.get("/ready")
def ready():
    try:
        # A real read from the required schema; no expensive counts or model generation.
        with runtime.storage.connection() as connection:
            connection.execute("SELECT notice_id FROM notices LIMIT 1").fetchone()
        models = runtime.ollama.available_models()
        if not {runtime.config.chat_model, runtime.config.embedding_model}.issubset(models):
            raise OllamaUnavailable("Required models unavailable")
    except (sqlite3.Error, OSError, OllamaUnavailable):
        raise HTTPException(status_code=503, detail="Dependencies unavailable") from None
    return {"status": "ready"}


def profile_from(value:dict[str,Any]|None)->SupplierProfile:
    return SupplierProfile(**(value or DEMO_PROFILE.public()))


@app.get("/health")
def health()->dict[str,Any]:
    try: models=runtime.ollama.available_models(); connected=runtime.config.chat_model in models and runtime.config.embedding_model in models; error=None
    except OllamaUnavailable as unavailable: models=[]; connected=False; error=str(unavailable)
    return {"connected":connected,"chat_model":runtime.config.chat_model,"embedding_model":runtime.config.embedding_model,"available_models":models,"knowledge_base":runtime.storage.stats(),"error":error,"boundary":"local-only"}


@app.post("/ingest")
def ingest(request:IngestRequest)->dict[str,Any]:
    response=ted.search(request.filters,limit=request.limit); fetched=utc_now(); notices=[normalize(item,fetched) for item in response.get("notices",[])]
    document_failures=[]
    if request.include_documents:
        enriched=[None]*len(notices)
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures={executor.submit(ted.enrich_from_xml,notice):index for index,notice in enumerate(notices)}
            for future in as_completed(futures):
                index=futures[future]
                try: enriched[index]=future.result()
                except Exception as error:
                    enriched[index]=notices[index]
                    document_failures.append({"publication_id":notices[index]["publication_id"],"category":type(error).__name__,"error":str(error)[:300]})
        notices=[item for item in enriched if item is not None]
    persistence=runtime.storage.ingest(notices,profile_from(request.profile))
    try: indexing=runtime.retriever.index_pending()
    except OllamaUnavailable as error: indexing={"indexed":0,"error":str(error)}
    return {"source":"TED Search API v3","query":response.get("query"),"total_notice_count":response.get("totalNoticeCount"),"documents":{"attempted":len(notices) if request.include_documents else 0,"failures":document_failures},"persistence":persistence,"indexing":indexing,"knowledge_base":runtime.storage.stats(),"notices":[{"notice_id":n["notice_id"],"publication_id":n["publication_id"],"title":n["title"],"notice_url":n["notice_url"],"requirements":len(n["requirements"])} for n in notices]}


@app.post("/ask")
def ask(request:AskRequest)->dict[str,Any]:
    try: return as_json(runtime.agent.ask(request.question,profile=profile_from(request.profile)))
    except OllamaUnavailable as error: return as_json(unavailable_result(error,runtime.config.chat_model))
