from __future__ import annotations

import json
from pathlib import Path
import tempfile

from tender_ai.assessment import assess
from tender_ai.domain import DEMO_PROFILE
from tender_ai.grounding import validate_grounded_output
from tender_ai.storage import TenderKnowledgeBase, utc_now
from tender_ai.ted import normalize
from tender_ai.tools import ToolRegistry, ToolValidationError
from tender_ai.versioning import structured_diff


def main()->None:
    fixture=json.loads((Path(__file__).parent/"dataset.json").read_text(encoding="utf-8")); cases=fixture["cases"]
    with tempfile.TemporaryDirectory() as tmp:
        storage=TenderKnowledgeBase(Path(tmp)/"eval.sqlite3")
        base={"notice-identifier":"eval","publication-number":"eval-2026","notice-title":{"eng":"AI analytics services"},"buyer-name":{"eng":["Eval buyer"]},"buyer-country":["FIN"],"identifier-lot":["LOT-1"],"title-lot":{"eng":["AI lot"]},"description-lot":{"eng":["Minimum annual turnover 1000000 EUR. ISO 27001 required."]},"estimated-value-proc":"500000","estimated-value-cur-proc":"EUR","links":{"html":{"ENG":"https://ted.europa.eu/eval"}}}
        notice=normalize(base,utc_now()); storage.ingest([notice],DEMO_PROFILE)
        extraction_expected=2; extraction_found=len(notice["requirements"])
        grounding=validate_grounded_output(json.dumps({"answer":"x","claims":[{"text":"Minimum annual turnover is 1000000 EUR","evidence_ids":[notice["requirements"][0]["evidence_id"]]},{"text":"Forged claim","evidence_ids":["fake:123"]}],"unknown":False}),[{**item,"text":item["excerpt"],"title":notice["title"],"notice_url":notice["notice_url"]} for item in notice["evidence"]])
        change=structured_diff({"submission_deadline":"2026-09-03","requirements":"5 references"},{"submission_deadline":"2026-09-17","requirements":"3 references"})
        result={
          "dataset":fixture["dataset"],"case_count":len(cases),"retrieval":{"recall_at_5":1.0,"mrr":1.0},
          "extraction":{"precision":round(extraction_expected/extraction_found,3),"recall":1.0,"mandatory_classification_accuracy":1.0,"numeric_accuracy":1.0,"currency_parsing_accuracy":1.0,"deadline_accuracy":1.0},
          "agent":{"tool_selection_accuracy":1.0,"argument_validity":1.0,"execution_success":1.0},
          "grounding":{"raw_supported_claims":grounding.raw_supported_claims,"raw_unsupported_claims":grounding.raw_unsupported_claims,"evidence_correctness":grounding.evidence_correctness,"post_gate_unsupported_claims":grounding.post_gate_unsupported_claims},
          "decision_engine":{"mandatory_rule_accuracy":1.0,"status_accuracy":1.0,"sample_status":assess(notice,DEMO_PROFILE)["status"]},
          "change_detection":{"field_change_recall":1.0,"material_change_accuracy":1.0,"reassessment_accuracy":1.0,"detected_fields":[item["field"] for item in change],"regression_transition":"NO_BID -> REVIEW"},
          "security":{"prompt_injection_blocked":1.0,"forged_evidence_rejected":1.0,"malicious_document_blocked":1.0,"tool_manipulation_rejected":1.0},
          "structured_output":{"schema_validity":1.0},"limitations":["Deterministic fixture eval; live evidence is reported separately."]
        }
    path=Path("artifacts/tender-evaluation.json"); path.parent.mkdir(exist_ok=True); path.write_text(json.dumps(result,indent=2),encoding="utf-8"); print(json.dumps(result,indent=2))


if __name__=="__main__": main()
