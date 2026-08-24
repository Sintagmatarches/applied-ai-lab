"""Validate and prepare the compact Finland Rail public data plane."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from rail.operational import POLICY, freshness_contract, sample_support, wilson_interval


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGIONS = ROOT / "artifacts/rail-station-regions.json"
MANIFEST_SCHEMA_VERSION = "rail-publication-manifest-v1"
PUBLICATION_RETENTION = 14
THRESHOLDS = (5, 10, 15, 30)
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class PublicationValidationError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PublicationValidationError(message)


def _iso_date(value: Any, field: str) -> date:
    _require(isinstance(value, str), f"{field} must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise PublicationValidationError(f"{field} must be an ISO timestamp") from error
    _require(parsed.tzinfo is not None, f"{field} must include a timezone")
    return parsed.date()


def _expected_dates(start: date, end: date) -> list[str]:
    return [(start + timedelta(days=offset)).isoformat() for offset in range((end - start).days + 1)]


def _close(left: float | None, right: float | None, tolerance: float = 1e-10) -> bool:
    if left is None or right is None:
        return left is right
    return math.isclose(float(left), float(right), rel_tol=tolerance, abs_tol=tolerance)


def _validate_metric(metric: Any, *, path: str, has_service: bool = True) -> None:
    _require(isinstance(metric, dict), f"{path} must be an object")
    counts = {}
    for field in ("observedTrains", "measuredTrains", "severeDelays", "cancellations"):
        value = metric.get(field)
        _require(isinstance(value, int) and not isinstance(value, bool) and value >= 0, f"{path}.{field} must be a non-negative integer")
        counts[field] = value
    observed, measured = counts["observedTrains"], counts["measuredTrains"]
    _require(measured <= observed, f"{path}.measuredTrains exceeds observedTrains")
    _require(counts["cancellations"] <= observed, f"{path}.cancellations exceeds observedTrains")
    _require(counts["severeDelays"] <= measured, f"{path}.severeDelays exceeds measuredTrains")
    delayed = metric.get("delayedTrainsByThreshold")
    shares = metric.get("delayedShareByThreshold")
    intervals = metric.get("delayedShareInterval95ByThreshold")
    _require(isinstance(delayed, dict) and isinstance(shares, dict) and isinstance(intervals, dict), f"{path} threshold maps are required")
    delayed_counts: list[int] = []
    for threshold in THRESHOLDS:
        key = str(threshold)
        value = delayed.get(key)
        _require(isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= measured, f"{path}.delayedTrainsByThreshold.{key} is invalid")
        delayed_counts.append(value)
        expected_share = value / measured if measured else None
        _require(_close(shares.get(key), expected_share), f"{path}.delayedShareByThreshold.{key} does not reconcile")
        expected_interval = wilson_interval(value, measured)
        actual_interval = intervals.get(key)
        if expected_interval is None:
            _require(actual_interval is None, f"{path}.delayedShareInterval95ByThreshold.{key} must be null")
        else:
            _require(isinstance(actual_interval, dict), f"{path}.delayedShareInterval95ByThreshold.{key} is invalid")
            _require(
                _close(actual_interval.get("lower"), expected_interval["lower"])
                and _close(actual_interval.get("upper"), expected_interval["upper"]),
                f"{path}.delayedShareInterval95ByThreshold.{key} does not reconcile",
            )
    _require(all(left >= right for left, right in zip(delayed_counts, delayed_counts[1:])), f"{path} delayed threshold counts are not monotonic")
    _require(metric.get("delayedTrains") == delayed_counts[0], f"{path}.delayedTrains is not the 5-minute alias")
    _require(_close(metric.get("delayedShare"), shares["5"]), f"{path}.delayedShare is not the 5-minute alias")
    expected_support = sample_support("7d", observed, measured, has_service=has_service)
    _require(metric.get("sampleSupport") == expected_support, f"{path}.sampleSupport violates policy")


def validate_snapshot(snapshot: Any, *, regions_path: Path = DEFAULT_REGIONS) -> dict[str, Any]:
    _require(isinstance(snapshot, dict), "snapshot must be an object")
    expected_versions = {
        "schemaVersion": POLICY["snapshotSchemaVersion"],
        "kpiDefinitionVersion": POLICY["kpiDefinitionVersion"],
        "sampleSupportPolicyVersion": POLICY["sampleSupport"]["version"],
        "freshnessPolicyVersion": POLICY["freshness"]["version"],
    }
    for field, expected in expected_versions.items():
        _require(snapshot.get(field) == expected, f"snapshot {field} is incompatible")
    _require(snapshot.get("mode") == "7d", "snapshot mode must be 7d")
    _require(snapshot.get("source") == "Fintraffic / Digitraffic", "snapshot source is not governed")
    start = _iso_date(snapshot.get("windowStart"), "windowStart")
    end = _iso_date(snapshot.get("windowEnd"), "windowEnd")
    expected_dates = _expected_dates(start, end)
    _require(len(expected_dates) == POLICY["freshness"]["requiredSevenDayPartitions"], "snapshot window must contain exactly seven dates")
    _require(snapshot.get("latestCompletePartition") == end.isoformat(), "latestCompletePartition must equal window end")
    coverage = snapshot.get("coverage")
    _require(isinstance(coverage, dict), "snapshot coverage is required")
    _require(coverage.get("status") == "complete", "snapshot coverage must be complete")
    _require(coverage.get("expectedDates") == expected_dates, "snapshot expected dates are invalid")
    _require(coverage.get("availableDates") == expected_dates, "snapshot must contain all seven available dates")
    _require(coverage.get("missingDates") == [] and coverage.get("failedDates") == [], "snapshot contains missing or failed dates")
    _require(coverage.get("duplicatePartitions") == 0 and _close(coverage.get("coverageRatio"), 1.0), "snapshot coverage does not reconcile")
    for field in ("sourceRetrievedAt", "validatedAt", "goldPublishedAt"):
        _iso_date(snapshot.get(field), field)
    at_publication = freshness_contract(
        "7d", now=snapshot["goldPublishedAt"], source_retrieved_at=snapshot["sourceRetrievedAt"],
        validated_at=snapshot["validatedAt"], gold_published_at=snapshot["goldPublishedAt"], coverage_status="complete",
    )
    _require(at_publication["state"] == "fresh", "snapshot timestamp ordering/publication freshness is invalid")
    _require(snapshot.get("freshness") == at_publication, "snapshot embedded freshness contract does not reconcile")
    governed = json.loads(regions_path.read_text(encoding="utf-8"))
    expected_codes = {region["code"] for region in governed["regions"]}
    regions = snapshot.get("regions")
    _require(isinstance(regions, list) and len(regions) == 19, "snapshot must contain exactly 19 regions")
    actual_codes = {region.get("code") for region in regions if isinstance(region, dict)}
    _require(actual_codes == expected_codes and len(actual_codes) == len(regions), "snapshot region codes are incomplete or duplicated")
    for region in regions:
        has_service = region.get("hasRailService")
        _require(isinstance(has_service, bool), f"region {region.get('code')} has invalid service flag")
        _validate_metric(region, path=f"regions.{region.get('code')}", has_service=has_service)
    aland = next(region for region in regions if region["code"] == "21")
    _require(aland["hasRailService"] is False and aland["status"] == "no-service", "Åland no-service invariant failed")
    _require(aland["disruptionScore"] is None and aland["reliabilityScore"] is None, "Åland scores must be null")
    _validate_metric(snapshot.get("network"), path="network")
    return snapshot


def snapshot_sha256(snapshot_bytes: bytes) -> str:
    return hashlib.sha256(snapshot_bytes).hexdigest()


def build_manifest(snapshot_bytes: bytes, snapshot: dict[str, Any]) -> dict[str, Any]:
    digest = snapshot_sha256(snapshot_bytes)
    publication_id = f"{snapshot['latestCompletePartition']}-{digest[:12]}"
    return {
        "schemaVersion": MANIFEST_SCHEMA_VERSION,
        "publicationId": publication_id,
        "generatedAt": snapshot["goldPublishedAt"],
        "windowStart": snapshot["windowStart"],
        "windowEnd": snapshot["windowEnd"],
        "latestCompletePartition": snapshot["latestCompletePartition"],
        "coverageStatus": snapshot["coverage"]["status"],
        "source": snapshot["source"],
        "snapshotPath": f"snapshots/{publication_id}.json",
        "snapshotSha256": digest,
        "kpiDefinitionVersion": snapshot["kpiDefinitionVersion"],
        "sampleSupportPolicyVersion": snapshot["sampleSupportPolicyVersion"],
        "freshnessPolicyVersion": snapshot["freshnessPolicyVersion"],
        "snapshotSchemaVersion": snapshot["schemaVersion"],
    }


def validate_manifest(manifest: Any, snapshot_bytes: bytes, snapshot: dict[str, Any]) -> dict[str, Any]:
    _require(isinstance(manifest, dict), "manifest must be an object")
    expected = build_manifest(snapshot_bytes, snapshot)
    _require(set(manifest) == set(expected), "manifest fields are incomplete or unexpected")
    _require(manifest.get("snapshotSha256") == expected["snapshotSha256"], "manifest snapshotSha256 does not match snapshot bytes")
    for field, value in expected.items():
        _require(manifest.get(field) == value, f"manifest {field} does not match snapshot")
    _require(SHA256_PATTERN.fullmatch(manifest["snapshotSha256"]) is not None, "manifest digest is invalid")
    return manifest


def prepare_publication(snapshot_path: Path, publication_dir: Path, *, retention: int = PUBLICATION_RETENTION) -> dict[str, Any]:
    _require(retention >= 1, "publication retention must be positive")
    snapshot_bytes = snapshot_path.read_bytes()
    try:
        snapshot = json.loads(snapshot_bytes)
    except json.JSONDecodeError as error:
        raise PublicationValidationError("snapshot is not valid JSON") from error
    validate_snapshot(snapshot)
    manifest = build_manifest(snapshot_bytes, snapshot)
    snapshots_dir = publication_dir / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    immutable_target = publication_dir / manifest["snapshotPath"]
    if immutable_target.exists():
        _require(immutable_target.read_bytes() == snapshot_bytes, "immutable publication path already contains different bytes")
    else:
        immutable_target.write_bytes(snapshot_bytes)
    manifest_target = publication_dir / "manifest.json"
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    temporary = manifest_target.with_suffix(".json.tmp")
    temporary.write_bytes(manifest_bytes)
    temporary.replace(manifest_target)
    history = sorted(snapshots_dir.glob("*.json"), key=lambda path: path.name, reverse=True)
    keep = {path.resolve() for path in history[:retention]}
    _require(immutable_target.resolve() in keep, "current publication fell outside the retention window")
    for path in history:
        if path.resolve() not in keep:
            path.unlink()
    validate_manifest(json.loads(manifest_target.read_bytes()), immutable_target.read_bytes(), json.loads(immutable_target.read_bytes()))
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--publication-dir", type=Path, required=True)
    parser.add_argument("--retention", type=int, default=PUBLICATION_RETENTION)
    args = parser.parse_args(argv)
    manifest = prepare_publication(args.snapshot, args.publication_dir, retention=args.retention)
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
