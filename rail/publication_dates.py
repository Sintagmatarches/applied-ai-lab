"""Resolve the seven completed Finland-oriented Digitraffic publication dates."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


FINLAND_TIMEZONE = ZoneInfo("Europe/Helsinki")


def resolve_publication_window(
    *, now: datetime | None = None, requested_end: str | None = None
) -> tuple[date, date]:
    if requested_end:
        end = date.fromisoformat(requested_end)
    else:
        clock = now or datetime.now(timezone.utc)
        if clock.tzinfo is None:
            raise ValueError("Publication clock must include a timezone")
        end = clock.astimezone(FINLAND_TIMEZONE).date() - timedelta(days=1)
    return end - timedelta(days=6), end


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requested-end", help="Explicit completed departureDate (YYYY-MM-DD)")
    parser.add_argument("--github-output", type=Path, help="Append start/end outputs to this GitHub Actions file")
    args = parser.parse_args(argv)
    start, end = resolve_publication_window(requested_end=args.requested_end or None)
    lines = f"start={start.isoformat()}\nend={end.isoformat()}\n"
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as target:
            target.write(lines)
    else:
        print(lines, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
