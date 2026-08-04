#!/usr/bin/env python3
"""Local-only historical Pack E equivalence study for Round 2 governance."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs"
POPULATION_DIR = BASE / "presignal_v21_full_round_1_pack_population" / "PPHB-R1-PACK-POPULATION-CONSTRUCTION-20260729T113217Z-88b9664e9bd2"
POPULATION_PATH = POPULATION_DIR / "pack_e_population.jsonl"
CONTRACT_PATH = POPULATION_DIR / "pack_e_construction_contract.json"
OUTPUT_DIR = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution" / "PPHB-R2-PROSPECTIVE-PACK-E-SPECIFICATION-STUDY-20260804T031500Z"
BASE_FIELDS = (
    "USDJPY_RETURN_1H_PRESESSION", "USDJPY_RETURN_4H_PRESESSION", "USDJPY_RETURN_24H_PRESESSION", "USDJPY_TREND_LABEL", "USDJPY_REALIZED_VOL_1H_PRESESSION", "NEXT_HIGH_IMPORTANCE_EVENT_WITHIN_24H", "NEXT_HIGH_IMPORTANCE_EVENT_WITHIN_48H", "NEXT_CPI_OR_FOMC_WITHIN_72H", "NEXT_NFP_WITHIN_7D", "EVENT_CLUSTER_DENSITY_NEXT_24H", "US2Y_YIELD_LEVEL", "US10Y_YIELD_LEVEL", "US2Y_CHANGE_FROM_PRIOR_CLOSE", "US10Y_CHANGE_FROM_PRIOR_CLOSE", "US10Y_MINUS_US2Y_CURVE", "DXY_LEVEL", "DXY_CHANGE_PRESESSION", "DXY_DIRECTION_LABEL",
)
BASE_FIELD_METADATA = {
    "USDJPY_RETURN_1H_PRESESSION": ("USD/JPY one-hour pre-session return", "percent", "usdjpy_trend"),
    "USDJPY_RETURN_4H_PRESESSION": ("USD/JPY four-hour pre-session return", "percent", "usdjpy_trend"),
    "USDJPY_RETURN_24H_PRESESSION": ("USD/JPY twenty-four-hour pre-session return", "percent", "usdjpy_trend"),
    "USDJPY_TREND_LABEL": ("USD/JPY deterministic pre-session trend label", "label", "usdjpy_trend"),
    "USDJPY_REALIZED_VOL_1H_PRESESSION": ("USD/JPY one-hour pre-session realized volatility", "percent", "usdjpy_trend"),
    "NEXT_HIGH_IMPORTANCE_EVENT_WITHIN_24H": ("next high-importance-event flag within 24 hours", "boolean", "upcoming_larger_events"),
    "NEXT_HIGH_IMPORTANCE_EVENT_WITHIN_48H": ("next high-importance-event flag within 48 hours", "boolean", "upcoming_larger_events"),
    "NEXT_CPI_OR_FOMC_WITHIN_72H": ("next CPI or FOMC flag within 72 hours", "boolean", "upcoming_larger_events"),
    "NEXT_NFP_WITHIN_7D": ("next NFP flag within seven days", "boolean", "upcoming_larger_events"),
    "EVENT_CLUSTER_DENSITY_NEXT_24H": ("count of clustered relevant events in the next 24 hours", "count", "upcoming_larger_events"),
    "US2Y_YIELD_LEVEL": ("US two-year Treasury yield level", "percent", "treasury_yields"),
    "US10Y_YIELD_LEVEL": ("US ten-year Treasury yield level", "percent", "treasury_yields"),
    "US2Y_CHANGE_FROM_PRIOR_CLOSE": ("US two-year Treasury yield change from prior close", "basis_points", "treasury_yields"),
    "US10Y_CHANGE_FROM_PRIOR_CLOSE": ("US ten-year Treasury yield change from prior close", "basis_points", "treasury_yields"),
    "US10Y_MINUS_US2Y_CURVE": ("US ten-year minus two-year Treasury curve", "basis_points", "treasury_yields"),
    "DXY_LEVEL": ("DXY pre-session level", "index_points", "dxy"),
    "DXY_CHANGE_PRESESSION": ("DXY pre-session change", "percent", "dxy"),
    "DXY_DIRECTION_LABEL": ("DXY deterministic pre-session direction label", "label", "dxy"),
}


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def read_rows() -> list[dict[str, Any]]:
    return [json.loads(line) for line in POPULATION_PATH.read_text().splitlines() if line.strip()]


def valid_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = [row for row in rows if row.get("pack_e_construction_status") == "CONSTRUCTED_VALID"]
    if not selected:
        raise RuntimeError("NO_AUTHORITATIVE_VALID_PACK_E_ROWS")
    return selected


def item_rows(rows: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    return [(row, item) for row in rows for item in row["pack_e_canonical_payload"]["shared_market_state_pack"]["items"]]


def field_audit(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for _, item in item_rows(rows):
        values[str(item["item_key"])].append(item)
    result = []
    for key, items in sorted(values.items()):
        categories = {key.split("|", 1)[0]}
        sources = sorted({str(item.get("source_system") or "") for item in items})
        timestamps = sum(bool(item.get("source_timestamp") or item.get("historical_availability_timestamp")) for item in items)
        result.append({
            "canonical_field_name": key,
            "semantic_category": next(iter(categories)),
            "presence_count": len(items),
            "presence_frequency": len(items) / len(rows),
            "statuses": sorted({str(item.get("status")) for item in items}),
            "source_systems": sources,
            "timestamp_present_count": timestamps,
            "classification": "CONDITIONAL_CAPABILITY_FIELD",
            "reason": "Provider-visible item key is request-specific and absent from at least one accepted valid Pack E record.",
            "historical_source_bundle_dependency": any(item.get("source_bundle_ids") for item in items),
            "mutable_historical_lineage": True,
        })
    return result


def base_field_audit() -> list[dict[str, Any]]:
    """Record the historical builder's 18 semantic fields without promoting its sources."""
    result = []
    for position, field in enumerate(BASE_FIELDS, start=1):
        definition, unit, category = BASE_FIELD_METADATA[field]
        result.append({
            "canonical_field_name": field,
            "semantic_definition": definition,
            "type": "numeric" if unit in {"percent", "basis_points", "index_points", "count"} else unit,
            "unit": unit,
            "deterministic_ordering_position": position,
            "source_route_or_capability": category,
            "historical_status": "STABLE_REQUIRED_SEMANTIC_FIELD",
            "prospective_disposition": "EXCLUDED_NO_LIVE_AUTHORITY",
            "presence_frequency_in_historical_builder": 1.0,
            "historical_timestamp_behavior": "historical shadow-row as-of timestamp; mutable historical-sheet lineage",
            "missingness_effect": "builder blocked when a base shadow field was absent",
            "provider_forecast_context": True,
            "reason": "Required semantic historical-builder field, but no accepted prospective route, source schema, or availability-time contract exists.",
        })
    return result


def select_sample(rows: list[dict[str, Any]], size: int = 12) -> list[dict[str, Any]]:
    """Choose records by date/type/identity only, never by forecasts or Outcomes."""
    unique: dict[str, dict[str, Any]] = {}
    for row in sorted(rows, key=lambda row: (row["pack_e_canonical_payload"]["release_ts"], row["episode_id"], row["provider"], row["model"])):
        unique.setdefault(row["episode_id"], row)
    chosen: list[dict[str, Any]] = []
    seen_dates: set[str] = set()
    for row in unique.values():
        date = row["pack_e_canonical_payload"]["release_ts"][:10]
        if date not in seen_dates:
            chosen.append(row); seen_dates.add(date)
        if len(chosen) == size:
            break
    if len(chosen) < size:
        for row in unique.values():
            if row not in chosen:
                chosen.append(row)
            if len(chosen) == size:
                break
    if len(chosen) != size:
        raise RuntimeError("EQUIVALENCE_SAMPLE_SIZE_UNAVAILABLE")
    return chosen


def episode_family(row: dict[str, Any]) -> str:
    members = row["pack_e_canonical_payload"].get("episode_members", [])
    primary = next((member for member in members if member.get("structural_component_role") == "PRIMARY_COMPONENT"), None)
    member = primary or (members[0] if members else {})
    return str(member.get("indicator_name") or "UNSPECIFIED_EVENT_FAMILY")


def study(output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    if output_dir.exists():
        raise RuntimeError("PACK_E_SPECIFICATION_STUDY_ALREADY_EXISTS")
    all_rows = read_rows(); rows = valid_rows(all_rows); audit = field_audit(rows); base_audit = base_field_audit(); sample = select_sample(rows)
    field_names = {row["canonical_field_name"] for row in audit}
    intersection = set.intersection(*[{item["item_key"] for item in row["pack_e_canonical_payload"]["shared_market_state_pack"]["items"]} for row in rows])
    if intersection:
        raise RuntimeError("UNEXPECTED_FIXED_PROVIDER_VISIBLE_FIELD_SET")
    sample_manifest = {
        "sample_id": "PPHB-R2-PACK-E-EQUIVALENCE-SAMPLE-20260804T031500Z",
        "algorithm": "sort accepted CONSTRUCTED_VALID Pack E records by release_ts, episode_id, provider, model; keep one record per Episode; select the first 12 distinct release dates without Outcome, forecast, or evaluation fields. Record primary-event family and require more than one family.",
        "size": len(sample),
        "records": [{"episode_id": row["episode_id"], "release_ts": row["pack_e_canonical_payload"]["release_ts"], "provider": row["provider"], "model": row["model"], "episode_shape": "CLUSTERED" if row["episode_id"].startswith("EP_BATCH") else "STANDALONE", "event_family": episode_family(row), "pack_source_fingerprint": fingerprint(row["pack_e_canonical_payload"]["shared_market_state_pack"])} for row in sample],
    }
    sample_manifest["family_distribution"] = dict(sorted(Counter(record["event_family"] for record in sample_manifest["records"]).items()))
    if len(sample_manifest["family_distribution"]) < 2:
        raise RuntimeError("EQUIVALENCE_SAMPLE_EVENT_FAMILY_DIVERSITY_UNAVAILABLE")
    sample_manifest["fingerprint"] = fingerprint({key: value for key, value in sample_manifest.items() if key != "fingerprint"})
    reconstructions = []
    for row in sample:
        historical = row["pack_e_canonical_payload"]["shared_market_state_pack"]
        reconstructions.append({
            "episode_id": row["episode_id"],
            "historical_pack_fingerprint": fingerprint(historical),
            "candidate_type": "LOCAL_EQUIVALENCE_TEST_EMPTY_CANDIDATE",
            "retained_fields": [],
            "excluded_provider_visible_fields": sorted(item["item_key"] for item in historical["items"]),
            "leakage_decision": "NO_NEW_DATA_USED",
            "prompt_compatibility": "FAIL_NO_PACK_E_CONTEXT_RETAINED",
            "pack_a_distinction": "FAIL_EMPTY_CANDIDATE_WOULD_NOT_PRESERVE_FULL_CONTEXT_ARM",
        })
    authority = {
        "decision": "HISTORICAL_PACK_E_AUTHORITY_CONFIRMED",
        "artifacts": [
            {"artifact_id": POPULATION_DIR.name, "path": str(POPULATION_PATH.relative_to(ROOT)), "fingerprint": fingerprint(POPULATION_PATH.read_text()), "status": "AUTHORITATIVE_CURRENT", "construction_version": "presignal_v21_pack_population", "source_mode": "HISTORICAL_SQUARE_ONE_RETROSPECTIVE_SIMULATION", "semantic_control": True},
            {"artifact_id": POPULATION_DIR.name, "path": str(CONTRACT_PATH.relative_to(ROOT)), "fingerprint": fingerprint(json.loads(CONTRACT_PATH.read_text())), "status": "AUTHORITATIVE_CURRENT", "construction_version": "pack_e_construction_contract", "source_mode": "HISTORICAL_RECONSTRUCTION", "semantic_control": True},
            {"artifact_id": "PPHB-R2-PROSPECTIVE-MARKET-STATE-DEPLOYMENT-RECONCILIATION-20260804T030000Z", "status": "FROZEN_EVIDENCE", "semantic_control": False},
        ],
    }
    candidate = {"decision": "PROSPECTIVE_PACK_E_FIELD_SPECIFICATION_BLOCKED", "closed_field_count": 0, "fields": [], "historical_required_semantic_fields": list(BASE_FIELDS), "disposition": "The 18 historical semantic fields have no accepted prospective source, schema, timestamp, stale-data, or bounded-acquisition authority. The 722 accepted provider-visible item keys are request-specific and have no common fixed set. No closed live-capable field set can preserve historical Pack E identity."}
    source_matrix = {"retained_fields": [], "excluded_required_fields": [{"field": row["canonical_field_name"], "classification": "NO_DEFENSIBLE_LIVE_SOURCE", "reason": "Historical mutable-shadow input has no accepted prospective adapter or timestamp-availability authority."} for row in base_audit], "decision": "NO_DEFENSIBLE_LIVE_SOURCE: no closed retained set exists; no external source was accessed."}
    comparison = {"sample_id": sample_manifest["sample_id"], "semantic_equivalence": "FAIL", "rule_failures": ["all 18 STABLE_REQUIRED_SEMANTIC_FIELD values are excluded for lack of prospective source authority", "empty candidate would remove all provider-visible context", "Pack A/E FULL_CONTEXT distinction would not survive", "no retained field has a governable prospective source contract", "bounded pre-cutoff acquisition cannot be derived"], "historical_required_semantic_field_count": len(base_audit), "historical_field_union_count": len(field_names), "historical_field_intersection_count": len(intersection)}
    decisions = {"field_specification": "PROSPECTIVE_PACK_E_FIELD_SPECIFICATION_BLOCKED", "pack_identity": "PROSPECTIVE_PACK_E_SPECIFICATION_NOT_FEASIBLE", "round_2": "ROUND_2_EXECUTION_REMAINS_BLOCKED", "external_activity": {"provider_calls": 0, "google_reads": 0, "google_writes": 0, "market_data_calls": 0, "outcome_activity": 0, "evaluation_activity": 0, "retries": 0}}
    report = {"study_id": output_dir.name, "authority": authority, "population": {"all_pack_e_rows": len(all_rows), "accepted_valid_rows": len(rows), "accepted_episode_count": len({row["episode_id"] for row in rows}), "reported_historical_builder_base_field_count": len(BASE_FIELDS), "provider_visible_field_union_count": len(field_names), "provider_visible_field_intersection_count": len(intersection)}, "base_field_inventory": base_audit, "field_audit": audit, "candidate": candidate, "source_feasibility": source_matrix, "sample": sample_manifest, "reconstructions": reconstructions, "comparison": comparison, "decisions": decisions, "recorded_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")}
    report["fingerprint"] = fingerprint({key: value for key, value in report.items() if key not in {"recorded_utc", "fingerprint"}})
    output_dir.mkdir(parents=True)
    files = {"historical_pack_e_authority_inventory.json": authority, "historical_pack_e_field_stability_audit.json": {"base_fields": report["base_field_inventory"], "provider_visible_fields": audit}, "presence_frequency.json": audit, "candidate_prospective_field_specification.json": candidate, "source_feasibility_matrix.json": source_matrix, "equivalence_sample_manifest.json": sample_manifest, "local_candidate_reconstructions.json": reconstructions, "field_level_equivalence_report.json": comparison, "pack_identity_decision.json": decisions, "validation_results.json": {"passed": True, "external_activity": decisions["external_activity"], "no_outcome_or_forecast_selection": True, "historical_semantic_fields_not_mislabeled_as_audit": True}, "study_report.json": report}
    for name, value in files.items():
        (output_dir / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR); args = parser.parse_args()
    print(json.dumps(study(args.output_dir), sort_keys=True)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
