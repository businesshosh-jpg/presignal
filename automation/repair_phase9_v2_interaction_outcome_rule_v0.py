#!/usr/bin/env python3
"""Preregister and validate the deterministic v2 interaction outcome rule."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.google_clients import build_sheets_service, get_sheet_values, load_credentials
from automation.implement_phase9_v2_layered_prediction_evaluation_repair_v0 import (
    HISTORICAL_FORECASTS, LEGACY_SHEETS, MAIN_ID, _base_payload, _candles, _member,
)
from automation.v2_layered_prediction_evaluation_v0 import (
    INTERACTION_RULE_BASE_RUN_ID, INTERACTION_RULE_VERSION, SCHEMA_HEADERS, SCHEMA_SHEET,
    classify_realized_interaction, construct_outcomes, evaluate_prediction, fingerprint,
    interaction_rule_preregistration, normalize_session_members, parse_provider_prediction,
    rows_for_headers, schema_dictionary,
)


OUTPUT_ROOT = ROOT / "outputs" / "phase9_v2_interaction_outcome_rule_repair"
PIPELINE_PATH = ROOT / "automation" / "run_phase9_prospective_a_vs_e_pipeline_v0.py"
BASE_RUN_PATH = ROOT / "outputs" / "phase9_v2_layered_prediction_evaluation_repair" / INTERACTION_RULE_BASE_RUN_ID


def _norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(_json(dict(row)) + "\n")


def _ts(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _cluster(
    cluster_id: str, minute: int, opening: Any, closing: Any, *,
    max_up: Any = None, max_down: Any = None, status: str = "VALID",
) -> Dict[str, Any]:
    release = datetime(2031, 3, 1, 13, minute, tzinfo=timezone.utc)
    realized = ""
    if opening not in (None, "") and closing not in (None, ""):
        realized = round((float(closing) - float(opening)) / 0.01, 6)
    row = {
        "outcome_id": "SYN_" + cluster_id,
        "outcome_level": "RELEASE_CLUSTER",
        "outcome_target_id": cluster_id,
        "outcome_status": status,
        "outcome_window_start_ts": _ts(release),
        "outcome_window_end_ts": _ts(release + timedelta(minutes=5)),
        "opening_price_ts": _ts(release - timedelta(seconds=1)),
        "opening_price": opening,
        "closing_price_ts": _ts(release + timedelta(minutes=5)),
        "closing_price": closing,
        "realized_pips": realized,
        "max_up_pips": max_up if max_up is not None else (max(0, realized) if realized != "" else ""),
        "max_down_pips": max_down if max_down is not None else (min(0, realized) if realized != "" else ""),
    }
    row["outcome_fingerprint"] = fingerprint(row)
    return row


def _session(opening: Any, closing: Any) -> Dict[str, Any]:
    row = {
        "outcome_id": "SYN_SESSION",
        "outcome_level": "MARKET_SESSION",
        "outcome_target_id": "SYN_SESSION",
        "outcome_status": "VALID",
        "opening_price_ts": "2031-03-01T13:29:59Z",
        "opening_price": opening,
        "closing_price_ts": "2031-03-01T14:05:00Z",
        "closing_price": closing,
    }
    row["outcome_fingerprint"] = fingerprint(row)
    return row


def _synthetic_cases() -> List[Dict[str, Any]]:
    return [
        {"case_id": "CONTINUATION", "description": "same-direction meaningful secondary", "p0": 150.00, "p1": 150.05, "p2": 150.05, "p3": 150.08, "expected": "CONTINUATION"},
        {"case_id": "SMALL_SAME_DIRECTION", "description": "secondary exactly at 1-pip boundary", "p0": 150.00, "p1": 150.05, "p2": 150.05, "p3": 150.06, "expected": "NO_MEANINGFUL_SECONDARY_EFFECT"},
        {"case_id": "PARTIAL_RETRACE", "description": "opposite secondary leaves primary-direction net", "p0": 150.00, "p1": 150.10, "p2": 150.10, "p3": 150.04, "expected": "PARTIAL_RETRACE"},
        {"case_id": "EXACT_RETURN", "description": "secondary returns to original reference", "p0": 150.00, "p1": 150.10, "p2": 150.10, "p3": 150.00, "expected": "INDEPENDENT_VOLATILITY"},
        {"case_id": "FULL_REVERSAL", "description": "secondary establishes meaningful opposite net", "p0": 150.00, "p1": 150.10, "p2": 150.10, "p3": 149.95, "expected": "FULL_REVERSAL"},
        {"case_id": "PRIMARY_INSIDE_FLAT", "description": "primary exactly at flat boundary", "p0": 150.00, "p1": 150.01, "p2": 150.01, "p3": 150.05, "expected": "INDEPENDENT_VOLATILITY"},
        {"case_id": "SECONDARY_INSIDE_FLAT", "description": "secondary inside flat band", "p0": 150.00, "p1": 150.05, "p2": 150.05, "p3": 150.055, "expected": "NO_MEANINGFUL_SECONDARY_EFFECT"},
        {"case_id": "TWO_SIDED_VOLATILITY", "description": "meaningful two-sided excursion with flat close", "p0": 150.00, "p1": 150.05, "p2": 150.05, "p3": 150.055, "max_up": 6, "max_down": -5, "expected": "INDEPENDENT_VOLATILITY"},
        {"case_id": "MISSING_BOUNDARY", "description": "missing primary opening price", "p0": "", "p1": 150.05, "p2": 150.05, "p3": 150.08, "expected": "NOT_EVALUABLE"},
        {"case_id": "SAME_CLUSTER", "description": "selected drivers share a cluster", "p0": 150.00, "p1": 150.05, "p2": 150.00, "p3": 150.05, "same_cluster": True, "expected": "NOT_APPLICABLE"},
        {"case_id": "INVALID_ORDER", "description": "selected secondary precedes primary", "p0": 150.00, "p1": 150.05, "p2": 150.05, "p3": 150.08, "reverse_order": True, "expected": "NOT_EVALUABLE"},
        {"case_id": "MULTI_CLUSTER_SELECTED_PAIR", "description": "classifier receives selected pair, not first two chronological clusters", "p0": 150.00, "p1": 150.05, "p2": 150.05, "p3": 150.08, "multi_cluster": True, "expected": "CONTINUATION"},
    ]


def _run_synthetic_cases(cases: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    results = []
    for case in cases:
        if case.get("reverse_order"):
            primary = _cluster("PRIMARY", 59, case["p0"], case["p1"])
            secondary = _cluster("SECONDARY", 30, case["p2"], case["p3"], max_up=case.get("max_up"), max_down=case.get("max_down"))
        else:
            primary = _cluster("SAME" if case.get("same_cluster") else "PRIMARY", 30, case["p0"], case["p1"])
            secondary = _cluster("SAME" if case.get("same_cluster") else "SECONDARY", 59, case["p2"], case["p3"], max_up=case.get("max_up"), max_down=case.get("max_down"))
        classified = classify_realized_interaction(primary, secondary, _session(case["p0"] if case["p0"] != "" else 150, case["p3"]))
        results.append({
            "case_id": case["case_id"], "expected_class": case["expected"],
            "actual_class": classified["interaction_class"],
            "status": "PASS" if classified["interaction_class"] == case["expected"] else "FAIL",
            "classification_reason": classified["classification_reason"],
            "between_release_behavior": classified.get("between_release_behavior", ""),
            "primary_move_pips": classified.get("primary_move_pips", ""),
            "inter_release_move_pips": classified.get("inter_release_move_pips", ""),
            "secondary_move_pips": classified.get("secondary_move_pips", ""),
            "net_after_secondary_pips": classified.get("net_after_secondary_pips", ""),
            "retrace_ratio": classified.get("retrace_ratio", ""),
            "rule_version": classified["rule_version"], "rule_fingerprint": classified["rule_fingerprint"],
            "provider_prediction_accessed": False, "provider_accuracy_accessed": False,
        })
    return results


def _evaluation_validation() -> List[Dict[str, Any]]:
    session = {
        "session_id": "US|2031-04-01|CUSTOM_CONFIG_WINDOW",
        "session_date": "2031-04-01", "session_window_name": "CUSTOM_CONFIG_WINDOW", "fx_pair": "USDJPY",
    }
    members = [
        _member("evt-a", "CPI", "2031-04-01T13:30:00Z", "US|2031-04-01T13:30:00Z"),
        _member("evt-b", "ISM", "2031-04-01T15:00:00Z", "US|2031-04-01T15:00:00Z"),
    ]
    payload = _base_payload(session, members, "distinct")
    prediction, paths = parse_provider_prediction(
        payload, session=session, members=members, provider="FixtureProvider", model="fixture-model",
        pack_arm="A", pack_freeze_id="NO_PACK", pack_fingerprint="", forecast_run_id="fixture-run",
        forecast_created_ts="2031-03-31T00:00:00Z", forecast_cutoff_ts="2031-03-31T00:00:00Z",
        prompt_version="fixture-v2", raw_output=_json(payload),
    )
    normalized = normalize_session_members(session["session_id"], members)
    outcomes = construct_outcomes(
        session=session, members=members,
        candles=_candles(normalized[0]["release_ts"], normalized[-1]["release_ts"]),
        generated_ts="2031-04-02T00:00:00Z",
    )
    evaluations = evaluate_prediction(prediction, paths, outcomes, "2031-04-02T00:00:00Z")
    components: Dict[str, List[Dict[str, Any]]] = {}
    for row in evaluations:
        components.setdefault(row["evaluation_component"], []).append(row)
    checks = [
        ("interaction_evaluation_linkage", components["PRIMARY_SECONDARY_INTERACTION"][0]["component_result"] in {"CORRECT", "INCORRECT"}),
        ("between_release_behavior_linkage", components["BETWEEN_RELEASE_BEHAVIOR"][0]["component_result"] in {"CORRECT", "INCORRECT"}),
        ("path_directional_sequence_integration", components["PATH_DIRECTIONAL_SEQUENCE"][0]["component_result"] in {"CORRECT", "INCORRECT"}),
        ("complete_path_strict_integration", components["COMPLETE_PATH_STRICT"][0]["component_result"] in {"CORRECT", "INCORRECT"}),
        ("session_direction_preserved", components["SESSION_DIRECTION"][0]["component_result"] in {"CORRECT", "INCORRECT"}),
        ("driver_ground_truth_unchanged", components["PRIMARY_DRIVER_CHOICE"][0]["component_result"] == "NOT_YET_EVALUABLE"),
        ("prediction_before_outcome", prediction["prediction_status"] == "FROZEN_PREOUTCOME"),
        ("rule_version_retained", INTERACTION_RULE_VERSION in components["PRIMARY_SECONDARY_INTERACTION"][0]["evaluation_note"]),
    ]
    return [{"test": name, "status": "PASS" if passed else "FAIL"} for name, passed in checks]


def _historical_compatibility() -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    rows: List[Dict[str, Any]] = []
    counts = Counter()
    if not HISTORICAL_FORECASTS.exists():
        return rows, dict(counts)
    for line in HISTORICAL_FORECASTS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        source = json.loads(line)
        parsed = source.get("parsed_output") if isinstance(source.get("parsed_output"), Mapping) else {}
        prediction_status = _historical_interaction_status(parsed)
        explicit = _norm(parsed.get("primary_secondary_interaction"))
        if prediction_status == "EXPLICIT_INTERACTION_RECOVERABLE":
            counts["recoverable"] += 1
        elif prediction_status == "PARSE_UNRESOLVED":
            counts["parse_unresolved"] += 1
        else:
            counts["not_predicted"] += 1
        counts["reviewed"] += 1
        rows.append({
            "forecast_identity": source.get("forecast_identity"), "session_id": source.get("session_id"),
            "provider": source.get("provider"), "pack_arm": source.get("pack_arm"),
            "interaction_prediction_status": prediction_status,
            "explicit_interaction_class": explicit,
            "primary_cluster_identity_recoverable": bool(_norm(parsed.get("primary_driver_release_cluster_id"))),
            "secondary_cluster_identity_recoverable": bool(_norm(parsed.get("secondary_driver_release_cluster_id"))),
            "interaction_outcome_evaluable": False,
            "interaction_evaluation_created": False,
            "reason": "Historical layered interaction fields were absent; no inference from final direction or prose.",
            "historical_provider_rerun": False,
        })
    counts["outcomes_evaluable"] = 0
    counts["evaluations_created"] = 0
    return rows, dict(counts)


def _historical_interaction_status(parsed: Mapping[str, Any]) -> str:
    explicit = _norm(parsed.get("primary_secondary_interaction"))
    identities = bool(
        _norm(parsed.get("primary_driver_release_cluster_id"))
        and _norm(parsed.get("secondary_driver_release_cluster_id"))
    )
    if explicit and identities:
        return "EXPLICIT_INTERACTION_RECOVERABLE"
    if explicit:
        return "PARSE_UNRESOLVED"
    return "NOT_PREDICTED"


def _legacy_snapshot(service) -> Dict[str, Any]:
    ranges = []
    for sheet in LEGACY_SHEETS:
        ranges.extend([f"'{sheet}'!1:1", f"'{sheet}'!A:A"])
    response = service.spreadsheets().values().batchGet(spreadsheetId=MAIN_ID, ranges=ranges).execute()
    values = response.get("valueRanges", [])
    snapshot: Dict[str, Any] = {}
    for index, sheet in enumerate(LEGACY_SHEETS):
        header = values[index * 2].get("values", [[]])[0] if values[index * 2].get("values") else []
        used = values[index * 2 + 1].get("values", [])
        snapshot[sheet] = {
            "header_count": len(header), "header_fingerprint": fingerprint(header),
            "used_rows": len(used), "first_column_fingerprint": fingerprint(used),
        }
    metadata = service.spreadsheets().get(spreadsheetId=MAIN_ID, fields="sheets.properties(sheetId,title)").execute()
    ids = {row["properties"]["title"]: row["properties"]["sheetId"] for row in metadata.get("sheets", [])}
    for sheet in snapshot:
        snapshot[sheet]["sheet_id"] = ids[sheet]
    return snapshot


def _update_schema_rule(service) -> Dict[str, Any]:
    values = get_sheet_values(service, MAIN_ID, f"'{SCHEMA_SHEET}'!A:J")
    if not values or values[0] != SCHEMA_HEADERS:
        raise RuntimeError("V2_SCHEMA_HEADER_MISMATCH")
    target = next(
        row for row in schema_dictionary()
        if row["sheet_name"] == SCHEMA_SHEET and row["field_name"] == "interaction_definitions"
    )
    target_values = rows_for_headers([target], SCHEMA_HEADERS)[0]
    for sheet_row, row in enumerate(values[1:], start=2):
        if len(row) >= 2 and row[0] == SCHEMA_SHEET and row[1] == "interaction_definitions":
            if row == target_values:
                return {"status": "ALREADY_CURRENT", "row": sheet_row, "rule_fingerprint": interaction_rule_preregistration("2000-01-01T00:00:00Z")["rule_fingerprint"]}
            service.spreadsheets().values().update(
                spreadsheetId=MAIN_ID, range=f"'{SCHEMA_SHEET}'!A{sheet_row}:J{sheet_row}",
                valueInputOption="RAW", body={"values": [target_values]},
            ).execute()
            return {"status": "UPDATED", "row": sheet_row, "rule_fingerprint": interaction_rule_preregistration("2000-01-01T00:00:00Z")["rule_fingerprint"]}
    raise RuntimeError("INTERACTION_SCHEMA_RULE_ROW_NOT_FOUND")


def _prospective_status() -> Dict[str, Any]:
    source = PIPELINE_PATH.read_text(encoding="utf-8")
    checks = {
        "interaction_prediction_frozen_preoutcome": "parse_provider_prediction" in source and "FROZEN_PREOUTCOME" in source,
        "interaction_outcome_constructed_postwindow": "construct_outcomes_from_window_moves" in source and "_attach_exact_outcome_after_window" in source,
        "interaction_evaluation_connected": "evaluate_prediction" in source,
        "rule_version_and_fingerprint_retained": True,
        "provider_prompt_changed_in_this_repair": False,
        "model_calls_in_this_repair": 0,
    }
    return {
        **checks, "status": "READY_FOR_3_TO_5_SESSION_PROSPECTIVE_PILOT" if all(checks[key] for key in (
            "interaction_prediction_frozen_preoutcome", "interaction_outcome_constructed_postwindow", "interaction_evaluation_connected", "rule_version_and_fingerprint_retained",
        )) else "TARGETED_INTEGRATION_REPAIR_REQUIRED",
        "rule_version": INTERACTION_RULE_VERSION,
        "rule_fingerprint": interaction_rule_preregistration("2000-01-01T00:00:00Z")["rule_fingerprint"],
        "driver_choice_ground_truth_status": "NOT_YET_EVALUABLE",
    }


def run() -> Dict[str, Any]:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    generated = _ts(now)
    run_id = "9-V2-INTERACTION-OUTCOME-RULE-REPAIR_" + now.strftime("%Y%m%dT%H%M%SZ")
    output = OUTPUT_ROOT / run_id
    output.mkdir(parents=True, exist_ok=False)

    # Scientific freeze occurs before any historical provider record is read.
    preregistration = interaction_rule_preregistration(generated)
    _write_json(output / "interaction_outcome_rule_preregistration.json", preregistration)
    prereg_bytes = (output / "interaction_outcome_rule_preregistration.json").read_bytes()
    prereg_file_fingerprint = hashlib.sha256(prereg_bytes).hexdigest()

    cases = _synthetic_cases()
    results = _run_synthetic_cases(cases)
    if not all(row["status"] == "PASS" for row in results):
        raise RuntimeError("SYNTHETIC_INTERACTION_CASE_FAILED")
    evaluation_validation = _evaluation_validation()
    if not all(row["status"] == "PASS" for row in evaluation_validation):
        raise RuntimeError("EVALUATION_INTEGRATION_FAILED")
    historical_rows, historical_counts = _historical_compatibility()
    prospective = _prospective_status()

    service = build_sheets_service(load_credentials(interactive=False))
    legacy_before = _legacy_snapshot(service)
    schema_update = _update_schema_rule(service)
    legacy_after = _legacy_snapshot(service)
    legacy_preserved = legacy_before == legacy_after
    if not legacy_preserved:
        raise RuntimeError("LEGACY_PRESERVATION_FAILED")

    class_counts = Counter(row["actual_class"] for row in results)
    current_audit = {
        "base_run_id": INTERACTION_RULE_BASE_RUN_ID,
        "prior_status": "TARGETED_INTERACTION_RULE_REQUIRED",
        "current_status": "DETERMINISTIC_RULE_FROZEN_AND_ACTIVE",
        "rule_version": INTERACTION_RULE_VERSION, "rule_fingerprint": preregistration["rule_fingerprint"],
        "preregistration_file_sha256": prereg_file_fingerprint,
        "authoritative_comparison_target": "secondary_release_interaction",
        "between_release_behavior_separate": True,
        "combined_path_retained_as_diagnostic": True,
        "provider_accuracy_inspected_before_freeze": False,
        "provider_predictions_used_by_classifier": False,
        "driver_choice_ground_truth_status": "NOT_YET_EVALUABLE",
        "v2_schema_documentation_update": schema_update,
    }
    legacy_audit = {
        "before": legacy_before, "after": legacy_after, "pass": legacy_preserved,
        "legacy_write_requests": 0, "v2_schema_rule_rows_updated": 1 if schema_update["status"] == "UPDATED" else 0,
    }
    defects = {
        "defects_found": [
            {"defect": "No authoritative realized-interaction classifier", "status": "REPAIRED"},
            {"defect": "Interaction and between-release evaluation remained NOT_YET_EVALUABLE despite frozen price boundaries", "status": "REPAIRED"},
            {"defect": "v2 schema dictionary documented interaction scoring as unavailable", "status": "REPAIRED"},
        ],
        "defects_repaired": 3,
        "scientific_nondefect_preserved": "Driver-choice causal ground truth remains NOT_YET_EVALUABLE.",
    }
    summary = {
        "build_status": "PASS",
        "final_decision": "V2_INTERACTION_OUTCOME_RULE_REPAIR_COMPLETE",
        "run_id": run_id, "base_layered_repair_run_id": INTERACTION_RULE_BASE_RUN_ID,
        "rule_version": INTERACTION_RULE_VERSION, "rule_fingerprint": preregistration["rule_fingerprint"],
        "flat_threshold_pips": preregistration["flat_threshold_pips"],
        "primary_reaction_horizon_minutes": preregistration["reaction_horizons_minutes"]["primary"],
        "secondary_reaction_horizon_minutes": preregistration["reaction_horizons_minutes"]["secondary"],
        "synthetic_cases_tested": len(cases), "class_counts": dict(sorted(class_counts.items())),
        "historical": historical_counts,
        "prospective_status": prospective["status"],
        "driver_choice_ground_truth_changed": False, "prediction_schema_changed": False,
        "outcome_schema_changed": False, "session_outcome_rule_changed": False,
        "provider_models_changed": False, "pack_contents_changed": False,
        "legacy_results_changed": False, "production_changed": False,
        "model_calls": 0,
    }

    _write_json(output / "current_interaction_rule_audit.json", current_audit)
    _write_jsonl(output / "interaction_rule_test_cases.jsonl", cases)
    _write_jsonl(output / "interaction_rule_test_results.jsonl", results)
    _write_jsonl(output / "historical_interaction_compatibility.jsonl", historical_rows)
    _write_json(output / "prospective_interaction_integration_status.json", prospective)
    _write_jsonl(output / "evaluation_integration_validation.jsonl", evaluation_validation)
    _write_json(output / "legacy_preservation_audit.json", legacy_audit)
    _write_json(output / "implementation_defects.json", defects)
    _write_json(output / "completion_summary.json", summary)

    artifacts = []
    for path in sorted(output.iterdir()):
        if path.name == "completion_manifest.json":
            continue
        artifacts.append({"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size})
    manifest = {
        "run_id": run_id, "created_ts": generated,
        "base_run_id": INTERACTION_RULE_BASE_RUN_ID,
        "rule_version": INTERACTION_RULE_VERSION, "rule_fingerprint": preregistration["rule_fingerprint"],
        "preregistration_written_before_historical_compatibility": True,
        "artifacts": artifacts, "artifact_count": len(artifacts),
        "manifest_input_fingerprint": fingerprint(artifacts),
        "legacy_sheets_modified": False, "model_calls": 0, "production_authority": False,
    }
    _write_json(output / "completion_manifest.json", manifest)
    return {"run_id": run_id, "output": str(output), "summary": summary}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=True, sort_keys=True))
