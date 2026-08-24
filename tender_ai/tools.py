from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable

from .assessment import assess
from .domain import DEMO_PROFILE, SupplierProfile
from .retrieval import HybridRetriever
from .storage import TenderKnowledgeBase
from .versioning import structured_diff


class ToolValidationError(ValueError): pass


@dataclass(frozen=True)
class ToolExecution:
    name: str; arguments: dict[str, Any]; result: dict[str, Any]; evidence: list[dict[str, Any]]; metrics: dict[str, Any] | None = None


def _schema(properties: dict[str, Any], required: list[str] | None=None) -> dict[str, Any]:
    return {"type":"object","properties":properties,"required":required or [],"additionalProperties":False}


class ToolRegistry:
    def __init__(self, storage: TenderKnowledgeBase, retriever: HybridRetriever, trusted_profile: SupplierProfile = DEMO_PROFILE):
        self.storage, self.retriever, self.trusted_profile=storage,retriever,trusted_profile
        text={"type":"string","maxLength":300}; ids={"type":"array","items":{"type":"string"},"maxItems":10}
        self.definitions={
            "search_tenders": ("Search persisted procurement notices.", _schema({"country":text,"buyer":text,"cpv":text,"limit":{"type":"integer","minimum":1,"maximum":50}})),
            "retrieve_tenders": ("Hybrid retrieve procurement evidence; never invent notices.", _schema({"query":text,"country":text,"cpv":text,"buyer":text,"top_k":{"type":"integer","minimum":1,"maximum":20}},["query"])),
            "get_notice": ("Get a stored notice.",_schema({"notice_id":text},["notice_id"])),
            "get_lots": ("Get lots for a stored notice.",_schema({"notice_id":text},["notice_id"])),
            "get_requirements": ("Get structured requirements and evidence.",_schema({"notice_id":text},["notice_id"])),
            "get_award_criteria": ("Get award criteria and evidence.",_schema({"notice_id":text},["notice_id"])),
            "assess_supplier_fit": ("Run deterministic lot-level eligibility using the trusted runtime supplier profile.",_schema({"notice_id":text},["notice_id"])),
            "explain_bid_decision": ("Return the persisted assessment evidence.",_schema({"notice_id":text},["notice_id"])),
            "compare_tenders": ("Compare two to ten notices.",_schema({"notice_ids":ids},["notice_ids"])),
            "find_supplier_gaps": ("Find blocking or unknown requirements using the trusted runtime supplier profile.",_schema({"notice_id":text},["notice_id"])),
            "get_notice_changes": ("Get detected changes.",_schema({"notice_id":text},["notice_id"])),
            "compare_notice_versions": ("Diff two notice versions.",_schema({"notice_id":text,"from_version":{"type":"integer","minimum":1},"to_version":{"type":"integer","minimum":1}},["notice_id","from_version","to_version"])),
            "search_similar_tenders": ("Search semantically similar procurement evidence.",_schema({"query":text,"top_k":{"type":"integer","minimum":1,"maximum":20}},["query"])),
            "aggregate_market_requirements": ("Count recurring structured requirements.",_schema({"country":text,"cpv":text,"limit":{"type":"integer","minimum":1,"maximum":30}})),
        }

    def ollama_tools(self) -> list[dict[str, Any]]:
        return [{"type":"function","function":{"name":name,"description":description,"parameters":schema}} for name,(description,schema) in self.definitions.items()]

    def _validate_value(self,path:str,value:Any,schema:dict[str,Any])->None:
        expected=schema.get("type")
        if expected=="string":
            if not isinstance(value,str): raise ToolValidationError(f"{path} must be a string")
            if len(value)>schema.get("maxLength",len(value)): raise ToolValidationError(f"{path} is too long")
        if expected=="integer":
            if not isinstance(value,int) or isinstance(value,bool): raise ToolValidationError(f"{path} must be an integer")
            if value < schema.get("minimum",value) or value > schema.get("maximum",value): raise ToolValidationError(f"{path} is out of range")
        if expected=="array":
            if not isinstance(value,list): raise ToolValidationError(f"{path} must be an array")
            if len(value)>schema.get("maxItems",len(value)): raise ToolValidationError(f"{path} has too many items")
            for index,item in enumerate(value): self._validate_value(f"{path}[{index}]",item,schema.get("items",{}))
        if expected=="object":
            if not isinstance(value,dict): raise ToolValidationError(f"{path} must be an object")
            properties=schema.get("properties",{}); extra=set(value)-set(properties)
            if schema.get("additionalProperties") is False and extra: raise ToolValidationError(f"unexpected {path} fields: {', '.join(sorted(extra))}")
            missing=[item for item in schema.get("required",[]) if item not in value]
            if missing: raise ToolValidationError(f"missing {path} fields: {', '.join(missing)}")
            for key,item in value.items():
                if key in properties: self._validate_value(f"{path}.{key}",item,properties[key])

    def execute(self,name:str,arguments:Any,*,trusted_profile:SupplierProfile|None=None)->ToolExecution:
        if name not in self.definitions: raise ToolValidationError(f"unknown tool: {name}")
        self._validate_value("arguments",arguments,self.definitions[name][1])
        handler=getattr(self,f"_{name}")
        if name in {"assess_supplier_fit", "find_supplier_gaps"}:
            return handler(arguments, trusted_profile or self.trusted_profile)
        return handler(arguments)

    def _evidence(self,notice:dict[str,Any])->list[dict[str,Any]]:
        rows=[]
        for item in notice.get("evidence",[]): rows.append({**item,"publication_id":notice.get("publication_id"),"text":item.get("excerpt",""),"title":notice.get("title"),"buyer":notice.get("buyer"),"notice_url":notice.get("notice_url")})
        if not rows: rows=[{"evidence_id":f"ted:{notice['notice_id']}:notice","notice_id":notice["notice_id"],"publication_id":notice.get("publication_id"),"text":notice.get("description","") or notice.get("title",""),"title":notice.get("title"),"buyer":notice.get("buyer"),"notice_url":notice.get("notice_url")}]
        return rows

    def _search_tenders(self,a):
        notices=self.storage.list_notices(country=a.get("country"),buyer=a.get("buyer"),cpv=a.get("cpv"),limit=a.get("limit",20)); return ToolExecution("search_tenders",a,{"notices":notices,"count":len(notices)},sum((self._evidence(n) for n in notices),[]))
    def _retrieve_tenders(self,a):
        hits,metrics=self.retriever.search(a["query"],top_k=a.get("top_k"),country=a.get("country"),cpv=a.get("cpv"),buyer=a.get("buyer")); return ToolExecution("retrieve_tenders",a,{"hits":[h.public() for h in hits]},[h.public() for h in hits],metrics)
    def _get_notice(self,a): return self._single("get_notice",a)
    def _get_lots(self,a): return self._field("get_lots",a,"lots")
    def _get_requirements(self,a): return self._field("get_requirements",a,"requirements")
    def _get_award_criteria(self,a): return self._field("get_award_criteria",a,"award_criteria")
    def _single(self,name,a):
        n=self.storage.get_notice(a["notice_id"]); return ToolExecution(name,a,{"notice":n} if n else {"error":"notice not found"},self._evidence(n) if n else [])
    def _field(self,name,a,field):
        n=self.storage.get_notice(a["notice_id"]); return ToolExecution(name,a,{field:n.get(field,[]) if n else []},self._evidence(n) if n else [])
    def _assess_supplier_fit(self,a,profile:SupplierProfile):
        n=self.storage.get_notice(a["notice_id"]); result=assess(n,profile) if n else {"error":"notice not found"}; return ToolExecution("assess_supplier_fit",a,result,[{**item,"_tool_evidence":result,"_tool_name":"assess_supplier_fit"} for item in self._evidence(n)] if n else [])
    def _explain_bid_decision(self,a):
        result=self.storage.latest_assessment(a["notice_id"]); n=self.storage.get_notice(a["notice_id"]); return ToolExecution("explain_bid_decision",a,result or {"error":"assessment not found"},[{**item,"_tool_evidence":result} for item in self._evidence(n)] if n else [])
    def _compare_tenders(self,a):
        notices=[n for item in a["notice_ids"] if (n:=self.storage.get_notice(item))]; return ToolExecution("compare_tenders",a,{"notices":notices},sum((self._evidence(n) for n in notices),[]))
    def _find_supplier_gaps(self,a,profile:SupplierProfile):
        execution=self._assess_supplier_fit(a,profile); result=execution.result; return ToolExecution("find_supplier_gaps",a,{"blocking":result.get("blocking_requirements",[]),"uncertain":result.get("uncertain_requirements",[])},execution.evidence)
    def _get_notice_changes(self,a):
        n=self.storage.get_notice(a["notice_id"]); return ToolExecution("get_notice_changes",a,{"changes":self.storage.changes(a["notice_id"])},self._evidence(n) if n else [])
    def _compare_notice_versions(self,a):
        versions={v["version"]:v["snapshot"] for v in self.storage.versions(a["notice_id"])}; diff=structured_diff(versions.get(a["from_version"],{}),versions.get(a["to_version"],{})); n=self.storage.get_notice(a["notice_id"]); return ToolExecution("compare_notice_versions",a,{"changes":diff},self._evidence(n) if n else [])
    def _search_similar_tenders(self,a): return self._retrieve_tenders(a)
    def _aggregate_market_requirements(self,a):
        notices=self.storage.list_notices(country=a.get("country"),cpv=a.get("cpv")); counts=Counter(r["category"] for n in notices for r in n.get("requirements",[])); return ToolExecution("aggregate_market_requirements",a,{"requirements":[{"category":k,"count":v} for k,v in counts.most_common(a.get("limit",20))],"notice_count":len(notices)},sum((self._evidence(n) for n in notices),[]))
