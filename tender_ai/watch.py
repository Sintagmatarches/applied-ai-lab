from __future__ import annotations

import argparse
import json

from .domain import DEMO_PROFILE
from .runtime import create_runtime
from .storage import utc_now
from .ted import TedClient, normalize


def recheck() -> dict:
    runtime, client = create_runtime(), TedClient()
    report = {"watched": 0, "updated": 0, "unchanged": 0, "failures": []}
    for item in runtime.storage.watched():
        report["watched"] += 1
        try:
            raw = client.get_latest_publication(item["publication_id"])
            if raw is None:
                raise RuntimeError("publication is no longer returned by TED")
            notice = normalize(raw, utc_now())
            try:
                notice = client.enrich_from_xml(notice)
            except Exception as error:
                report["failures"].append({"notice_id": item["notice_id"], "stage": "xml", "category": type(error).__name__, "message": str(error)[:300]})
            stats = runtime.storage.ingest([notice], DEMO_PROFILE)
            report["updated"] += stats["updated"]
            report["unchanged"] += stats["unchanged"]
            report["failures"].extend(stats["failure_details"])
            runtime.storage.mark_watched_checked(item["notice_id"])
        except Exception as error:
            report["failures"].append({"notice_id": item["notice_id"], "stage": "recheck", "category": type(error).__name__, "message": str(error)[:300]})
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Persistent local TED watchlist recheck")
    parser.add_argument("--add", metavar="NOTICE_ID")
    parser.add_argument("--recheck", action="store_true")
    args = parser.parse_args()
    runtime = create_runtime()
    if args.add:
        runtime.storage.watch(args.add, DEMO_PROFILE.profile_id)
    report = recheck() if args.recheck else {"watchlist": runtime.storage.watched()}
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
