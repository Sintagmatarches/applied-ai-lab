from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tender_ai.storage import utc_now
from tender_ai.ted import FIELDS, TedClient, _localized, _strings

from .datasets import EVAL_DIR


SELECTED_FIELDS = tuple(FIELDS)


def _weights(raw: dict[str, Any]) -> list[float | None]:
    values = _strings(raw.get("BT-541-Lot"))
    result: list[float | None] = []
    for value in values:
        try:
            result.append(float(value))
        except ValueError:
            result.append(None)
    return result


def _expected(raw: dict[str, Any]) -> dict[str, Any]:
    """Build source-derived fields without calling the production normalizer.

    These are mechanical copies/conversions of named official fields. Category
    interpretation is intentionally absent from collection and can only be
    added explicitly with a rationale in the committed fixture.
    """
    lot_ids = _strings(raw.get("identifier-lot"))
    languages = _strings(raw.get("submission-language"))
    deadlines = _strings(raw.get("deadline-date-lot"))
    cpv_codes = _strings(raw.get("classification-cpv"))
    buyer_countries = _strings(raw.get("buyer-country"))
    award_names = _localized(raw.get("award-criterion-name-lot"))
    return {
        "labelMethod": "source-derived-mechanical",
        "labelRationale": "Exact copies or numeric conversions of explicitly named official TED Search API fields; no independent human annotation.",
        "lotIds": lot_ids,
        "buyerCountry": buyer_countries[0] if buyer_countries else None,
        "submissionLanguages": languages,
        "deadlines": deadlines,
        "cpvCodes": cpv_codes,
        "awardCriterionCount": len(award_names),
        "awardWeights": _weights(raw),
        "structuredRequirementCategories": [],
        "requirementLotAssignments": [],
    }


def collect(plan: dict[str, Any], client: TedClient) -> dict[str, Any]:
    retrieved_at = utc_now()
    notices = []
    for selection in plan["selections"]:
        publication = str(selection["publicationNumber"])
        raw = client.get_latest_publication(publication)
        if raw is None:
            raise RuntimeError(f"official TED API returned no notice for {publication}")
        official_url = f"https://ted.europa.eu/en/notice/-/detail/{publication}"
        xml_links = raw.get("links", {}).get("xml", {}) if isinstance(raw.get("links"), dict) else {}
        xml_url = next(iter(xml_links.values()), None) if isinstance(xml_links, dict) else None
        notices.append({
            "publicationNumber": publication,
            "noticeIdentifier": str(raw.get("notice-identifier") or publication),
            "noticeVersion": raw.get("notice-version"),
            "officialSourceUrl": official_url,
            "officialXmlUrl": xml_url,
            "retrievedAt": retrieved_at,
            "sourceQuery": plan["sourceQuery"],
            "selectionRationale": selection["rationale"],
            "raw": {key: raw[key] for key in SELECTED_FIELDS if key in raw},
            "expected": _expected(raw),
        })
    return {
        "datasetSchemaVersion": "2.0.0",
        "datasetVersion": "recorded-real-ted-v2.0.0",
        "generatedAt": retrieved_at,
        "source": "Official TED Search API v3 (published public procurement notices)",
        "endpoint": "https://api.ted.europa.eu/v3/notices/search",
        "fieldList": list(SELECTED_FIELDS),
        "labelMethod": "source-derived expectations: mechanically verifiable fields plus explicitly documented interpretations only",
        "notices": notices,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Explicitly refresh the recorded-real TED candidate corpus.")
    parser.add_argument("--plan", type=Path, default=EVAL_DIR / "collection_plan.json")
    parser.add_argument("--output", type=Path, default=EVAL_DIR / "real_ted_notices.candidate.json")
    parser.add_argument("--replace-committed", action="store_true", help="deliberately replace real_ted_notices.json; never used by CI")
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    result = collect(plan, TedClient())
    output = EVAL_DIR / "real_ted_notices.json" if args.replace_committed else args.output
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "noticeCount": len(result["notices"]), "retrievedAt": result["generatedAt"]}, indent=2))


if __name__ == "__main__":
    main()
