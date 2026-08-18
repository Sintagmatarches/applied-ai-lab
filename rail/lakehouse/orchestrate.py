from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from rail.pipeline import SourceClient

from .pipeline import DEFAULT_CONTRACT, DEFAULT_LAKEHOUSE, DEFAULT_STATIONS, LakehousePipeline
from .planning import date_range
from .spark import build_spark


ROOT = Path(__file__).resolve().parents[2]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Acquire, validate and build the Finland Rail Delta Lakehouse")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--source-cache", type=Path, default=ROOT / "data/rail")
    parser.add_argument("--lakehouse", type=Path, default=DEFAULT_LAKEHOUSE)
    parser.add_argument("--stations", type=Path, default=DEFAULT_STATIONS)
    parser.add_argument("--contracts", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--refresh-source", action="store_true", help="Re-request source dates; validation occurs before cache replacement")
    parser.add_argument("--force-transform", action="store_true", help="Force partition replacement for recovery/backfill")
    parser.add_argument("--master", default=None, help="Optional local Spark master; hosted runtimes reuse their active session")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
    source = SourceClient(args.source_cache, refresh=args.refresh_source)
    acquired = []
    for day in date_range(start, end):
        acquired.append(str(source.cache_trains(day)))
    spark = build_spark(master=args.master)
    try:
        result = LakehousePipeline(
            spark, args.lakehouse, args.source_cache / "trains", args.stations, args.contracts
        ).process(start, end, force=args.force_transform)
        print(json.dumps({"acquiredPartitions": acquired, "lakehouse": result}, default=str))
        return 0
    finally:
        spark.stop()


if __name__ == "__main__":
    sys.exit(main())
