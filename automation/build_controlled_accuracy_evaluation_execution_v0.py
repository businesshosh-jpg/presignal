import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.build_market_sessions_shadow_v0 import (
    DIAGNOSTICS_SPREADSHEET_ID,
    MAIN_SPREADSHEET_ID,
    PROJECT_OVERVIEWS_SPREADSHEET_ID,
    REGISTRY_HEADERS,
    REGISTRY_SHEET,
    _column_letter,
    _ensure_sheet,
    _norm,
    _sheet_to_rows,
    _write_rows,
)
from automation.build_session_information_requests_v0 import _iso_now, _truncate_text
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials


SCHEMA_VERSION = "presignal_v2_controlled_accuracy_evaluation_execution_dry_run_0.1"
EXECUTION_BUILDER_VERSION = "controlled_accuracy_evaluation_execution_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-5D"
REGISTRY_CATEGORY = "PRESIGNAL_V2_CONTROLLED_ACCURACY_EVALUATION_EXECUTION_DRY_RUN"
REGISTRY_OWNER_MODULE = "market_state"

INPUT_DESIGN_SHEETS = [
    "Controlled_Accuracy_Evaluation_Design",
    "Controlled_Accuracy_Experiment_Schema",
    "Controlled_Accuracy_Row_Eligibility_Rules",
    "Controlled_Accuracy_Outcome_Matching_Design",
    "Controlled_Accuracy_Metric_Logic",
    "Controlled_Accuracy_Comparison_Logic",
    "Controlled_Accuracy_Invalid_Output_Handling",
    "Controlled_Accuracy_Governance_Check",
    "Controlled_Accuracy_Execution_Readiness",
    "Controlled_Accuracy_Design_Summary",
]

TIER2_INPUT_SHEETS = [
    "Pack_Behavior_Tier2_Runs",
    "Pack_Behavior_Tier2_Forecasts",
    "Pack_Behavior_Tier2_Metadata",
    "Pack_Behavior_Tier2_Behavior",
    "Pack_Behavior_Tier2_Raw_Response_Archive",
    "Pack_Behavior_Tier2_Transitions",
    "Pack_Behavior_Tier2_Field_Influence",
    "Pack_Behavior_Tier2_NoSignal",
    "Pack_Behavior_Tier2_Invalid_Output",
    "Pack_Behavior_Tier2_Run_Summary",
]

OUTCOME_REFERENCE_SHEETS = [
    "Outcome_Ledger",
    "Evaluation_Rows",
    "Evaluation_Summary",
    "Evaluation_BatchCompare",
    "Evaluation_Scenario",
    "Session_Evaluation",
    "Session_vs_Event_Baseline_Compare",
]

OUTPUT_DRY_RUN = "Controlled_Accuracy_Eval_Dry_Run"
OUTPUT_ELIGIBLE = "Controlled_Accuracy_Eligible_Row_Preview"
OUTPUT_OUTCOME = "Controlled_Accuracy_Outcome_Match_Preview"
OUTPUT_PAIR = "Controlled_Accuracy_Comparison_Pair_Preview"
OUTPUT_METRIC = "Controlled_Accuracy_Metric_Row_Preview"
OUTPUT_INVALID = "Controlled_Accuracy_Invalid_Row_Audit"
OUTPUT_GOVERNANCE = "Controlled_Accuracy_Execution_Governance_Audit"
OUTPUT_SUMMARY = "Controlled_Accuracy_Execution_Dry_Run_Summary"

OUTPUT_SHEETS = [
    OUTPUT_DRY_RUN,
    OUTPUT_ELIGIBLE,
    OUTPUT_OUTCOME,
    OUTPUT_PAIR,
    OUTPUT_METRIC,
    OUTPUT_INVALID,
    OUTPUT_GOVERNANCE,
    OUTPUT_SUMMARY,
]

DRY_RUN_HEADERS = [
    "generated_ts",
    "schema_version",
    "execution_builder_version",
    "dry_run_id",
    "experiment_id",
    "accuracy_hypothesis_id",
    "source_behavior_hypothesis_id",
    "dry_run_status",
    "forecast_source_sheet",
    "outcome_source_sheet",
    "eligible_rows_found",
    "invalid_rows_excluded",
    "outcome_matches_found",
    "outcome_matches_missing",
    "comparison_pairs_planned",
    "metric_rows_planned",
    "accuracy_calculation_performed",
    "direction_correctness_calculated",
    "overall_ok_calculated",
    "final_result_written",
    "notes",
]

ELIGIBLE_HEADERS = [
    "generated_ts",
    "schema_version",
    "execution_builder_version",
    "dry_run_id",
    "experiment_id",
    "session_id",
    "provider",
    "pack_level",
    "forecast_row_key",
    "source_sheet",
    "output_valid",
    "raw_archive_present",
    "eligible_for_future_evaluation",
    "eligibility_status",
    "eligibility_reason",
    "exclusion_reason",
    "would_be_in_accuracy_denominator",
    "accuracy_calculation_performed",
    "notes",
]

OUTCOME_HEADERS = [
    "generated_ts",
    "schema_version",
    "execution_builder_version",
    "dry_run_id",
    "experiment_id",
    "session_id",
    "provider",
    "pack_level",
    "forecast_row_key",
    "outcome_source_sheet",
    "outcome_match_status",
    "outcome_match_key",
    "matched_outcome_row_reference",
    "required_outcome_fields_present",
    "missing_outcome_fields",
    "market_reaction_window",
    "direction_label_available",
    "realized_pips_available",
    "outcome_values_read",
    "direction_correctness_calculated",
    "notes",
]

PAIR_HEADERS = [
    "generated_ts",
    "schema_version",
    "execution_builder_version",
    "dry_run_id",
    "experiment_id",
    "comparison_id",
    "session_id",
    "provider",
    "baseline_pack_level",
    "treatment_pack_level",
    "baseline_forecast_row_key",
    "treatment_forecast_row_key",
    "baseline_eligible",
    "treatment_eligible",
    "pair_status",
    "invalid_pair_reason",
    "planned_primary_metric",
    "planned_secondary_metrics",
    "accuracy_delta_calculated",
    "notes",
]

METRIC_HEADERS = [
    "generated_ts",
    "schema_version",
    "execution_builder_version",
    "dry_run_id",
    "experiment_id",
    "metric_id",
    "metric_name",
    "comparison_id",
    "planned_denominator_count",
    "planned_exclusion_count",
    "minimum_sample_warning",
    "metric_formula_reference",
    "metric_calculation_status",
    "metric_value_calculated",
    "notes",
]

INVALID_HEADERS = [
    "generated_ts",
    "schema_version",
    "execution_builder_version",
    "dry_run_id",
    "experiment_id",
    "session_id",
    "provider",
    "pack_level",
    "forecast_row_key",
    "invalid_case_type",
    "source_detection_sheet",
    "raw_archive_present",
    "excluded_from_future_accuracy",
    "would_count_in_invalid_output_rate",
    "rerun_allowed",
    "inference_allowed",
    "notes",
]

GOVERNANCE_HEADERS = [
    "generated_ts",
    "schema_version",
    "execution_builder_version",
    "dry_run_id",
    "check_id",
    "check_name",
    "expected_value",
    "actual_value",
    "status",
    "notes",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "schema_version",
    "execution_builder_version",
    "dry_run_id",
    "build_status",
    "final_interpretation",
    "experiments_previewed",
    "eligible_rows_found",
    "invalid_rows_excluded",
    "outcome_matches_found",
    "outcome_matches_missing",
    "comparison_pairs_planned",
    "metric_rows_planned",
    "outcome_matching_preview_status",
    "minimum_sample_warning_count",
    "invalid_output_rate_preview",
    "provider_calls_performed",
    "forecast_generation_performed",
    "accuracy_evaluation_performed",
    "direction_correctness_calculated",
    "overall_ok_calculated",
    "accuracy_delta_calculated",
    "metric_values_calculated",
    "evaluation_result_rows_written",
    "evaluation_rows_written",
    "outcome_ledger_written",
    "production_behavior_change_count",
    "ready_for_phase9a5e_execution_approval",
    "ready_for_accuracy_evaluation",
    "ready_for_production",
    "recommended_next_step",
    "notes",
]

HEADERS_BY_SHEET = {
    OUTPUT_DRY_RUN: DRY_RUN_HEADERS,
    OUTPUT_ELIGIBLE: ELIGIBLE_HEADERS,
    OUTPUT_OUTCOME: OUTCOME_HEADERS,
    OUTPUT_PAIR: PAIR_HEADERS,
    OUTPUT_METRIC: METRIC_HEADERS,
    OUTPUT_INVALID: INVALID_HEADERS,
    OUTPUT_GOVERNANCE: GOVERNANCE_HEADERS,
    OUTPUT_SUMMARY: SUMMARY_HEADERS,
}

REQUIRED_OUTCOME_FIELD_ALIASES = {
    "direction_label": ["outcome_direction_proxy", "mr_real_dir", "session_realized_direction"],
    "realized_pips": ["realized_pips", "session_realized_pips"],
}


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _bool(value: Any) -> bool:
    return _upper(value) in {"TRUE", "YES", "1", "Y"}


def _base(generated_ts: str, dry_run_id: str) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "execution_builder_version": EXECUTION_BUILDER_VERSION,
        "dry_run_id": dry_run_id,
    }


def _run_id(generated_ts: str) -> str:
    compact = generated_ts.replace("-", "").replace(":", "").replace("Z", "Z")
    return f"controlled_accuracy_eval_dry_run_v0_{compact}"


def _sheet_titles(service, spreadsheet_id: str) -> Set[str]:
    metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    return {sheet["properties"]["title"] for sheet in metadata.get("sheets", [])}


def _safe_rows(
    service,
    spreadsheet_id: str,
    titles: Set[str],
    sheet_name: str,
    missing: List[str],
    required: bool = False,
) -> List[Dict[str, Any]]:
    if sheet_name not in titles:
        missing.append(sheet_name)
        if required:
            return []
        return []
    try:
        return _sheet_to_rows(service, spreadsheet_id, sheet_name)
    except Exception:
        missing.append(sheet_name)
        return []


def _extract_pack(value: Any) -> str:
    match = re.search(r"\bPack\s+([A-E])\b", _norm(value), flags=re.IGNORECASE)
    if match:
        return match.group(1).upper()
    raw = _upper(value)
    if raw in {"A", "B", "C", "D", "E"}:
        return raw
    return ""


def _split_pipe(value: Any) -> List[str]:
    return [_norm(part) for part in _norm(value).split("|") if _norm(part)]


def _forecast_row_key(row: Dict[str, Any]) -> str:
    archive_key = _norm(row.get("raw_response_archive_key"))
    if archive_key:
        return archive_key
    return "|".join(
        [
            _norm(row.get("execution_run_id")) or _norm(row.get("discovery_run_id")),
            _norm(row.get("session_id")),
            _norm(row.get("provider")),
            _norm(row.get("pack_level")),
            _norm(row.get("prompt_hash")),
        ]
    )


def _session_date(session_id: str, fallback: Any = "") -> str:
    parts = _norm(session_id).split("|")
    if len(parts) >= 2 and re.match(r"\d{4}-\d{2}-\d{2}", parts[1]):
        return parts[1]
    return _norm(fallback)


def _session_country(session_id: str, fallback: Any = "") -> str:
    parts = _norm(session_id).split("|")
    if parts:
        return parts[0]
    return _norm(fallback)


def _experiment_scope(experiment: Dict[str, Any]) -> Tuple[Set[str], Set[str]]:
    experiment_id = _norm(experiment.get("experiment_id"))
    provider_scope = _norm(experiment.get("provider_scope"))
    pack_scope = _norm(experiment.get("pack_scope"))
    providers = {"OpenAI", "Gemini", "Anthropic"}
    if experiment_id == "ACC_EXP_OPENAI_STABLE_CAUSAL_REWRITE_TESTBED" or "OpenAI" in provider_scope and "Gemini" not in provider_scope:
        providers = {"OpenAI"}
    packs = {_extract_pack(part) for part in _split_pipe(pack_scope)}
    packs = {pack for pack in packs if pack}
    if not packs:
        if experiment_id == "ACC_EXP_PACK_B_TARGET_STATE_SIGNAL_DISCIPLINE":
            packs = {"A", "B"}
        elif experiment_id == "ACC_EXP_OPENAI_STABLE_CAUSAL_REWRITE_TESTBED":
            packs = {"A", "B", "D"}
        else:
            packs = {"A", "B", "D", "E"}
    return providers, packs


def _valid_output(row: Dict[str, Any]) -> bool:
    return _bool(row.get("json_parse_success")) and _bool(row.get("json_validation_success")) and _upper(row.get("status")) not in {
        "PROVIDER_ERROR",
        "ERROR",
        "FAILED",
    }


def _raw_archive_keys(raw_rows: Iterable[Dict[str, Any]]) -> Set[str]:
    return {_norm(row.get("raw_response_archive_key")) for row in raw_rows if _norm(row.get("raw_response_archive_key"))}


def _source_headers(rows: Sequence[Dict[str, Any]]) -> Set[str]:
    if not rows:
        return set()
    return {key for key in rows[0].keys() if not key.startswith("__")}


def _outcome_indexes(
    main_refs: Dict[str, List[Dict[str, Any]]],
    diag_refs: Dict[str, List[Dict[str, Any]]],
) -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]]]:
    sources = [
        ("Evaluation_Rows", main_refs.get("Evaluation_Rows", [])),
        ("Outcome_Ledger", main_refs.get("Outcome_Ledger", [])),
        ("Session_Evaluation", diag_refs.get("Session_Evaluation", [])),
        ("Session_vs_Event_Baseline_Compare", diag_refs.get("Session_vs_Event_Baseline_Compare", [])),
    ]
    selected_name = ""
    selected_rows: List[Dict[str, Any]] = []
    for name, rows in sources:
        if rows:
            selected_name = name
            selected_rows = rows
            break
    headers = _source_headers(selected_rows)
    direction_field = next((field for field in REQUIRED_OUTCOME_FIELD_ALIASES["direction_label"] if field in headers), "")
    pips_field = next((field for field in REQUIRED_OUTCOME_FIELD_ALIASES["realized_pips"] if field in headers), "")
    required_fields_present = bool(direction_field and pips_field)
    missing_fields = []
    if not direction_field:
        missing_fields.append("direction_label")
    if not pips_field:
        missing_fields.append("realized_pips")

    date_country_counts: Counter[str] = Counter()
    session_counts: Counter[str] = Counter()
    row_ref_by_key: Dict[str, str] = {}
    for row in selected_rows:
        session_id = _norm(row.get("session_id"))
        country = _norm(row.get("country"))
        release_date = _norm(row.get("release_date")) or _session_date(session_id)
        if session_id:
            session_counts[session_id] += 1
            row_ref_by_key.setdefault(session_id, f"{selected_name}!row={row.get('__source_row_number__', '')}")
        if release_date and country:
            key = f"{country}|{release_date}"
            date_country_counts[key] += 1
            row_ref_by_key.setdefault(key, f"{selected_name}!date_country_key={key}")

    metadata = {
        "source_sheet": selected_name,
        "source_available": bool(selected_name),
        "headers": headers,
        "required_fields_present": required_fields_present,
        "missing_fields": missing_fields,
        "direction_label_available": bool(direction_field),
        "realized_pips_available": bool(pips_field),
    }
    indexes = {
        "date_country_counts": dict(date_country_counts),
        "session_counts": dict(session_counts),
        "row_ref_by_key": row_ref_by_key,
    }
    return metadata, indexes


def _outcome_preview_for_row(row: Dict[str, Any], outcome_meta: Dict[str, Any], outcome_indexes: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    session_id = _norm(row.get("session_id"))
    date_key = f"{_session_country(session_id, row.get('country'))}|{_session_date(session_id, row.get('session_date'))}"
    session_counts = outcome_indexes.get("session_counts", {})
    date_counts = outcome_indexes.get("date_country_counts", {})
    row_refs = outcome_indexes.get("row_ref_by_key", {})
    matched = False
    match_key = ""
    reference = ""
    if session_counts.get(session_id, 0) > 0:
        matched = True
        match_key = session_id
        reference = row_refs.get(session_id, "")
    elif date_counts.get(date_key, 0) > 0:
        matched = True
        match_key = date_key
        reference = f"{outcome_meta.get('source_sheet')} date_country_match_count={date_counts.get(date_key)}; values suppressed"
    if not outcome_meta.get("source_available"):
        status = "BLOCKED_MISSING_OUTCOME_SOURCE"
    elif not outcome_meta.get("required_fields_present"):
        status = "NEEDS_REVIEW_MISSING_REQUIRED_OUTCOME_FIELDS"
    elif matched:
        status = "MATCH_AVAILABLE_VALUES_SUPPRESSED"
    else:
        status = "NO_MATCHING_OUTCOME_ROW"
    return {
        "outcome_source_sheet": outcome_meta.get("source_sheet") or "MISSING_OUTCOME_SOURCE",
        "outcome_match_status": status,
        "outcome_match_key": match_key,
        "matched_outcome_row_reference": reference,
        "required_outcome_fields_present": "TRUE" if outcome_meta.get("required_fields_present") else "FALSE",
        "missing_outcome_fields": "|".join(outcome_meta.get("missing_fields", [])),
        "market_reaction_window": "planned_future_evaluation_window; not executed",
        "direction_label_available": "TRUE" if outcome_meta.get("direction_label_available") else "FALSE",
        "realized_pips_available": "TRUE" if outcome_meta.get("realized_pips_available") else "FALSE",
        "matched": matched and bool(outcome_meta.get("required_fields_present")),
    }


def _eligibility_status(
    row: Dict[str, Any],
    providers: Set[str],
    packs: Set[str],
    raw_keys: Set[str],
    outcome_match: Dict[str, Any],
) -> Tuple[str, str, str, bool, bool, bool]:
    provider = _norm(row.get("provider"))
    pack = _upper(row.get("pack_level"))
    row_key = _forecast_row_key(row)
    raw_present = _norm(row.get("raw_response_archive_key")) in raw_keys
    output_valid = _valid_output(row)
    required_missing = [field for field in ["session_id", "provider", "pack_level"] if not _norm(row.get(field))]
    if provider not in providers:
        return (
            "EXCLUDED_OUT_OF_SCOPE_PROVIDER",
            "Provider outside experiment scope.",
            f"provider={provider}",
            False,
            output_valid,
            raw_present,
        )
    if pack not in packs:
        return (
            "EXCLUDED_OUT_OF_SCOPE_PACK",
            "Pack level outside experiment scope.",
            f"pack_level={pack}",
            False,
            output_valid,
            raw_present,
        )
    if required_missing:
        return (
            "EXCLUDED_MISSING_REQUIRED_FIELD",
            "Missing required forecast identity field.",
            "|".join(required_missing),
            False,
            output_valid,
            raw_present,
        )
    if not raw_present:
        return (
            "EXCLUDED_MISSING_RAW_ARCHIVE",
            "Raw response archive key not present in archive sheet.",
            row_key,
            False,
            output_valid,
            raw_present,
        )
    if not output_valid:
        status = "EXCLUDED_PROVIDER_FAILURE" if _upper(row.get("status")) in {"PROVIDER_ERROR", "ERROR", "FAILED"} else "EXCLUDED_INVALID_OUTPUT"
        return (
            status,
            "Invalid provider output is excluded from future accuracy denominator.",
            _norm(row.get("error_message")) or "json_parse_or_validation_failure",
            False,
            output_valid,
            raw_present,
        )
    if not outcome_match.get("matched"):
        return (
            "EXCLUDED_NO_MATCHING_OUTCOME",
            "No safe outcome match is available for future scoring.",
            _norm(outcome_match.get("outcome_match_status")),
            False,
            output_valid,
            raw_present,
        )
    return ("ELIGIBLE", "Valid scoped row with raw archive and previewable outcome match.", "", True, output_valid, raw_present)


def _build_eligible_and_outcome_rows(
    generated_ts: str,
    dry_run_id: str,
    experiments: Sequence[Dict[str, Any]],
    forecasts: Sequence[Dict[str, Any]],
    raw_keys: Set[str],
    outcome_meta: Dict[str, Any],
    outcome_indexes: Dict[str, Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[Tuple[str, str], Dict[str, Any]]]:
    eligible_rows: List[Dict[str, Any]] = []
    outcome_rows: List[Dict[str, Any]] = []
    preview_by_experiment_key: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for experiment in experiments:
        experiment_id = _norm(experiment.get("experiment_id"))
        providers, packs = _experiment_scope(experiment)
        for forecast in forecasts:
            row_key = _forecast_row_key(forecast)
            outcome_preview = _outcome_preview_for_row(forecast, outcome_meta, outcome_indexes)
            status, reason, exclusion, eligible, output_valid, raw_present = _eligibility_status(
                forecast, providers, packs, raw_keys, outcome_preview
            )
            base = _base(generated_ts, dry_run_id)
            common = {
                "experiment_id": experiment_id,
                "session_id": _norm(forecast.get("session_id")),
                "provider": _norm(forecast.get("provider")),
                "pack_level": _upper(forecast.get("pack_level")),
                "forecast_row_key": row_key,
            }
            eligible_row = dict(base)
            eligible_row.update(
                {
                    **common,
                    "source_sheet": "Pack_Behavior_Tier2_Forecasts",
                    "output_valid": "TRUE" if output_valid else "FALSE",
                    "raw_archive_present": "TRUE" if raw_present else "FALSE",
                    "eligible_for_future_evaluation": "TRUE" if eligible else "FALSE",
                    "eligibility_status": status,
                    "eligibility_reason": reason,
                    "exclusion_reason": exclusion,
                    "would_be_in_accuracy_denominator": "TRUE" if eligible else "FALSE",
                    "accuracy_calculation_performed": "FALSE",
                    "notes": "Dry-run preview only; no correctness or metric value calculated.",
                }
            )
            eligible_rows.append(eligible_row)
            preview_by_experiment_key[(experiment_id, row_key)] = eligible_row
            if status in {"ELIGIBLE", "EXCLUDED_NO_MATCHING_OUTCOME"}:
                outcome_row = dict(base)
                outcome_row.update(
                    {
                        **common,
                        "outcome_source_sheet": outcome_preview.get("outcome_source_sheet"),
                        "outcome_match_status": outcome_preview.get("outcome_match_status"),
                        "outcome_match_key": outcome_preview.get("outcome_match_key"),
                        "matched_outcome_row_reference": outcome_preview.get("matched_outcome_row_reference"),
                        "required_outcome_fields_present": outcome_preview.get("required_outcome_fields_present"),
                        "missing_outcome_fields": outcome_preview.get("missing_outcome_fields"),
                        "market_reaction_window": outcome_preview.get("market_reaction_window"),
                        "direction_label_available": outcome_preview.get("direction_label_available"),
                        "realized_pips_available": outcome_preview.get("realized_pips_available"),
                        "outcome_values_read": "FALSE",
                        "direction_correctness_calculated": "FALSE",
                        "notes": "Outcome values suppressed; this row previews match availability only.",
                    }
                )
                outcome_rows.append(outcome_row)
    return eligible_rows, outcome_rows, preview_by_experiment_key


def _forecast_lookup(forecasts: Sequence[Dict[str, Any]]) -> Dict[Tuple[str, str, str], Dict[str, Any]]:
    lookup: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for row in forecasts:
        lookup[(_norm(row.get("session_id")), _norm(row.get("provider")), _upper(row.get("pack_level")))] = row
    return lookup


def _providers_for_comparison(comparison: Dict[str, Any], forecasts: Sequence[Dict[str, Any]]) -> List[str]:
    scope = _norm(comparison.get("provider_scope"))
    providers = sorted({_norm(row.get("provider")) for row in forecasts if _norm(row.get("provider"))})
    if scope == "OpenAI":
        return ["OpenAI"]
    scoped = [provider for provider in providers if provider in {"OpenAI", "Gemini", "Anthropic"}]
    return scoped or providers


def _metric_list(comparison: Dict[str, Any]) -> List[str]:
    metrics: List[str] = []
    for value in [_norm(comparison.get("primary_metric")), _norm(comparison.get("secondary_metrics"))]:
        for metric in _split_pipe(value):
            if metric and metric not in metrics:
                metrics.append(metric)
    return metrics


def _build_pair_rows(
    generated_ts: str,
    dry_run_id: str,
    comparisons: Sequence[Dict[str, Any]],
    forecasts: Sequence[Dict[str, Any]],
    eligible_by_key: Dict[Tuple[str, str], Dict[str, Any]],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    lookup = _forecast_lookup(forecasts)
    sessions = sorted({_norm(row.get("session_id")) for row in forecasts if _norm(row.get("session_id"))})
    for comparison in comparisons:
        experiment_id = _norm(comparison.get("experiment_id"))
        comparison_id = _norm(comparison.get("comparison_id"))
        baseline_pack = _extract_pack(comparison.get("baseline_group"))
        treatment_pack = _extract_pack(comparison.get("treatment_group"))
        if not baseline_pack or not treatment_pack:
            continue
        providers = _providers_for_comparison(comparison, forecasts)
        for session_id in sessions:
            for provider in providers:
                baseline = lookup.get((session_id, provider, baseline_pack), {})
                treatment = lookup.get((session_id, provider, treatment_pack), {})
                baseline_key = _forecast_row_key(baseline) if baseline else ""
                treatment_key = _forecast_row_key(treatment) if treatment else ""
                baseline_preview = eligible_by_key.get((experiment_id, baseline_key), {})
                treatment_preview = eligible_by_key.get((experiment_id, treatment_key), {})
                baseline_eligible = _bool(baseline_preview.get("eligible_for_future_evaluation"))
                treatment_eligible = _bool(treatment_preview.get("eligible_for_future_evaluation"))
                invalid_reason = ""
                if not baseline:
                    status = "PAIR_BLOCKED_BASELINE_INVALID"
                    invalid_reason = "missing baseline forecast row"
                elif not treatment:
                    status = "PAIR_BLOCKED_TREATMENT_INVALID"
                    invalid_reason = "missing treatment forecast row"
                elif baseline_preview.get("eligibility_status") == "EXCLUDED_NO_MATCHING_OUTCOME" or treatment_preview.get("eligibility_status") == "EXCLUDED_NO_MATCHING_OUTCOME":
                    status = "PAIR_BLOCKED_MISSING_OUTCOME"
                    invalid_reason = "baseline or treatment lacks safe outcome match"
                elif not baseline_eligible:
                    status = "PAIR_BLOCKED_BASELINE_INVALID"
                    invalid_reason = _norm(baseline_preview.get("eligibility_status"))
                elif not treatment_eligible:
                    status = "PAIR_BLOCKED_TREATMENT_INVALID"
                    invalid_reason = _norm(treatment_preview.get("eligibility_status"))
                else:
                    status = "PAIR_READY_FOR_FUTURE_EVALUATION"
                row = _base(generated_ts, dry_run_id)
                row.update(
                    {
                        "experiment_id": experiment_id,
                        "comparison_id": comparison_id,
                        "session_id": session_id,
                        "provider": provider,
                        "baseline_pack_level": baseline_pack,
                        "treatment_pack_level": treatment_pack,
                        "baseline_forecast_row_key": baseline_key,
                        "treatment_forecast_row_key": treatment_key,
                        "baseline_eligible": "TRUE" if baseline_eligible else "FALSE",
                        "treatment_eligible": "TRUE" if treatment_eligible else "FALSE",
                        "pair_status": status,
                        "invalid_pair_reason": invalid_reason,
                        "planned_primary_metric": _norm(comparison.get("primary_metric")),
                        "planned_secondary_metrics": _norm(comparison.get("secondary_metrics")),
                        "accuracy_delta_calculated": "FALSE",
                        "notes": "Pair preview only; no baseline/treatment result compared.",
                    }
                )
                rows.append(row)
    return rows


def _build_metric_rows(
    generated_ts: str,
    dry_run_id: str,
    comparisons: Sequence[Dict[str, Any]],
    metric_logic: Sequence[Dict[str, Any]],
    pair_rows: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    metric_by_name = {_norm(row.get("metric_name")) or _norm(row.get("metric_id")): row for row in metric_logic}
    pair_counts: Dict[str, Counter[str]] = defaultdict(Counter)
    for pair in pair_rows:
        comparison_id = _norm(pair.get("comparison_id"))
        if _norm(pair.get("pair_status")) == "PAIR_READY_FOR_FUTURE_EVALUATION":
            pair_counts[comparison_id]["ready"] += 1
        else:
            pair_counts[comparison_id]["excluded"] += 1
    rows: List[Dict[str, Any]] = []
    for comparison in comparisons:
        comparison_id = _norm(comparison.get("comparison_id"))
        experiment_id = _norm(comparison.get("experiment_id"))
        for metric_name in _metric_list(comparison):
            logic = metric_by_name.get(metric_name, {})
            denominator = pair_counts[comparison_id]["ready"]
            minimum_warning = "TRUE" if denominator < 10 else "FALSE"
            row = _base(generated_ts, dry_run_id)
            row.update(
                {
                    "experiment_id": experiment_id,
                    "metric_id": _norm(logic.get("metric_id")) or f"PLANNED_{metric_name.upper()}",
                    "metric_name": metric_name,
                    "comparison_id": comparison_id,
                    "planned_denominator_count": denominator,
                    "planned_exclusion_count": pair_counts[comparison_id]["excluded"],
                    "minimum_sample_warning": minimum_warning,
                    "metric_formula_reference": _truncate_text(_norm(logic.get("calculation_formula_pseudocode")) or "defined in Controlled_Accuracy_Metric_Logic", 500),
                    "metric_calculation_status": "PLANNED_ONLY",
                    "metric_value_calculated": "FALSE",
                    "notes": "Metric row preview only; no metric value calculated.",
                }
            )
            rows.append(row)
    return rows


def _invalid_case_type(eligible_row: Dict[str, Any]) -> str:
    status = _norm(eligible_row.get("eligibility_status"))
    if status == "EXCLUDED_PROVIDER_FAILURE":
        return "provider_503_or_provider_failure"
    if status == "EXCLUDED_INVALID_OUTPUT":
        return "schema_failure_or_malformed_json"
    if status == "EXCLUDED_MISSING_RAW_ARCHIVE":
        return "missing_raw_archive"
    if status == "EXCLUDED_MISSING_REQUIRED_FIELD":
        return "missing_forecast_identity_field"
    if status == "EXCLUDED_NO_MATCHING_OUTCOME":
        return "missing_outcome"
    return status.lower() or "excluded_row"


def _build_invalid_rows(generated_ts: str, dry_run_id: str, eligible_rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    audited_statuses = {
        "EXCLUDED_INVALID_OUTPUT",
        "EXCLUDED_PROVIDER_FAILURE",
        "EXCLUDED_MISSING_RAW_ARCHIVE",
        "EXCLUDED_MISSING_REQUIRED_FIELD",
        "EXCLUDED_NO_MATCHING_OUTCOME",
    }
    seen: Set[Tuple[str, str, str]] = set()
    for candidate in eligible_rows:
        status = _norm(candidate.get("eligibility_status"))
        if status not in audited_statuses:
            continue
        key = (_norm(candidate.get("experiment_id")), _norm(candidate.get("forecast_row_key")), status)
        if key in seen:
            continue
        seen.add(key)
        row = _base(generated_ts, dry_run_id)
        row.update(
            {
                "experiment_id": _norm(candidate.get("experiment_id")),
                "session_id": _norm(candidate.get("session_id")),
                "provider": _norm(candidate.get("provider")),
                "pack_level": _norm(candidate.get("pack_level")),
                "forecast_row_key": _norm(candidate.get("forecast_row_key")),
                "invalid_case_type": _invalid_case_type(candidate),
                "source_detection_sheet": "Controlled_Accuracy_Eligible_Row_Preview",
                "raw_archive_present": _norm(candidate.get("raw_archive_present")),
                "excluded_from_future_accuracy": "TRUE",
                "would_count_in_invalid_output_rate": "TRUE" if status in {"EXCLUDED_INVALID_OUTPUT", "EXCLUDED_PROVIDER_FAILURE"} else "FALSE",
                "rerun_allowed": "FALSE",
                "inference_allowed": "FALSE",
                "notes": _truncate_text(_norm(candidate.get("exclusion_reason")) or "Excluded by dry-run eligibility preview.", 500),
            }
        )
        rows.append(row)
    return rows


def _build_governance_rows(generated_ts: str, dry_run_id: str) -> List[Dict[str, Any]]:
    checks = [
        ("GOV_PROVIDER_CALLS", "provider_calls_performed", "0", "0"),
        ("GOV_FORECAST_GENERATION", "forecast_generation_performed", "0", "0"),
        ("GOV_ACCURACY_EVAL", "accuracy_evaluation_performed", "0", "0"),
        ("GOV_DIRECTION_CORRECTNESS", "direction_correctness_calculated", "0", "0"),
        ("GOV_OVERALL_OK", "overall_ok_calculated", "0", "0"),
        ("GOV_ACCURACY_DELTA", "accuracy_delta_calculated", "0", "0"),
        ("GOV_METRIC_VALUES", "metric_values_calculated", "0", "0"),
        ("GOV_EVAL_RESULT_ROWS", "evaluation_result_rows_written", "0", "0"),
        ("GOV_EVAL_ROWS", "evaluation_rows_written", "0", "0"),
        ("GOV_OUTCOME_LEDGER", "outcome_ledger_written", "0", "0"),
        ("GOV_PRODUCTION_WRITES", "production_writes", "0", "0"),
        ("GOV_ROUTING", "routing_changes", "FALSE", "FALSE"),
        ("GOV_WEIGHTING", "weighting_changes", "FALSE", "FALSE"),
        ("GOV_CALIBRATION", "calibration_changes", "FALSE", "FALSE"),
        ("GOV_ENSEMBLE", "ensemble_changes", "FALSE", "FALSE"),
    ]
    rows: List[Dict[str, Any]] = []
    for check_id, name, expected, actual in checks:
        row = _base(generated_ts, dry_run_id)
        row.update(
            {
                "check_id": check_id,
                "check_name": name,
                "expected_value": expected,
                "actual_value": actual,
                "status": "PASS" if expected == actual else "FAIL",
                "notes": "Dry-run governance check; no scoring or production write occurred.",
            }
        )
        rows.append(row)
    return rows


def _build_dry_run_rows(
    generated_ts: str,
    dry_run_id: str,
    experiments: Sequence[Dict[str, Any]],
    eligible_rows: Sequence[Dict[str, Any]],
    outcome_rows: Sequence[Dict[str, Any]],
    pair_rows: Sequence[Dict[str, Any]],
    metric_rows: Sequence[Dict[str, Any]],
    outcome_status: str,
) -> List[Dict[str, Any]]:
    grouped_eligible: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    grouped_outcome: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    grouped_pairs: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    grouped_metrics: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in eligible_rows:
        grouped_eligible[_norm(row.get("experiment_id"))].append(row)
    for row in outcome_rows:
        grouped_outcome[_norm(row.get("experiment_id"))].append(row)
    for row in pair_rows:
        grouped_pairs[_norm(row.get("experiment_id"))].append(row)
    for row in metric_rows:
        grouped_metrics[_norm(row.get("experiment_id"))].append(row)

    rows: List[Dict[str, Any]] = []
    for experiment in experiments:
        experiment_id = _norm(experiment.get("experiment_id"))
        exp_eligible = grouped_eligible[experiment_id]
        exp_outcome = grouped_outcome[experiment_id]
        exp_pairs = grouped_pairs[experiment_id]
        exp_metrics = grouped_metrics[experiment_id]
        eligible_count = sum(1 for row in exp_eligible if _bool(row.get("eligible_for_future_evaluation")))
        invalid_count = sum(1 for row in exp_eligible if _norm(row.get("eligibility_status")) in {"EXCLUDED_INVALID_OUTPUT", "EXCLUDED_PROVIDER_FAILURE"})
        outcome_found = sum(1 for row in exp_outcome if _norm(row.get("outcome_match_status")) == "MATCH_AVAILABLE_VALUES_SUPPRESSED")
        outcome_missing = sum(1 for row in exp_outcome if _norm(row.get("outcome_match_status")) != "MATCH_AVAILABLE_VALUES_SUPPRESSED")
        dry_status = "PREVIEW_READY"
        if outcome_status != "MATCH_PREVIEW_AVAILABLE":
            dry_status = outcome_status
        row = _base(generated_ts, dry_run_id)
        row.update(
            {
                "experiment_id": experiment_id,
                "accuracy_hypothesis_id": _norm(experiment.get("accuracy_hypothesis_id")),
                "source_behavior_hypothesis_id": _norm(experiment.get("source_behavior_hypothesis_id")),
                "dry_run_status": dry_status,
                "forecast_source_sheet": "Pack_Behavior_Tier2_Forecasts",
                "outcome_source_sheet": _norm(experiment.get("outcome_source_sheet")),
                "eligible_rows_found": eligible_count,
                "invalid_rows_excluded": invalid_count,
                "outcome_matches_found": outcome_found,
                "outcome_matches_missing": outcome_missing,
                "comparison_pairs_planned": len(exp_pairs),
                "metric_rows_planned": len(exp_metrics),
                "accuracy_calculation_performed": "FALSE",
                "direction_correctness_calculated": "FALSE",
                "overall_ok_calculated": "FALSE",
                "final_result_written": "FALSE",
                "notes": "Dry-run only; values are eligibility and planning previews, not accuracy results.",
            }
        )
        rows.append(row)
    return rows


def _upsert_registry_rows(service) -> Dict[str, int]:
    headers = _ensure_sheet(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET, REGISTRY_HEADERS)
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_upper(row.get("logical_sheet_id")): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_upper(row.get("logical_sheet_id")): row for row in rows}
    registry_rows = [
        ("CONTROLLED_ACCURACY_EVAL_DRY_RUN", OUTPUT_DRY_RUN, "controlled_accuracy_eval_dry_run"),
        ("CONTROLLED_ACCURACY_ELIGIBLE_ROW_PREVIEW", OUTPUT_ELIGIBLE, "controlled_accuracy_eligible_row_preview"),
        ("CONTROLLED_ACCURACY_OUTCOME_MATCH_PREVIEW", OUTPUT_OUTCOME, "controlled_accuracy_outcome_match_preview"),
        ("CONTROLLED_ACCURACY_COMPARISON_PAIR_PREVIEW", OUTPUT_PAIR, "controlled_accuracy_comparison_pair_preview"),
        ("CONTROLLED_ACCURACY_METRIC_ROW_PREVIEW", OUTPUT_METRIC, "controlled_accuracy_metric_row_preview"),
        ("CONTROLLED_ACCURACY_INVALID_ROW_AUDIT", OUTPUT_INVALID, "controlled_accuracy_invalid_row_audit"),
        ("CONTROLLED_ACCURACY_EXECUTION_GOVERNANCE_AUDIT", OUTPUT_GOVERNANCE, "controlled_accuracy_execution_governance_audit"),
        ("CONTROLLED_ACCURACY_EXECUTION_DRY_RUN_SUMMARY", OUTPUT_SUMMARY, "controlled_accuracy_execution_dry_run_summary"),
    ]
    updates: List[Dict[str, Any]] = []
    appended = 0
    for logical_id, sheet_name, role in registry_rows:
        key = _upper(logical_id)
        existing = existing_by_id.get(key, {})
        merged = {
            "logical_sheet_id": logical_id,
            "physical_sheet_name": sheet_name,
            "sheet_role": role,
            "workbook": "DIAGNOSTICS",
            "workbook_location": "DIAGNOSTICS",
            "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
            "category": REGISTRY_CATEGORY,
            "lifecycle": "active_shadow",
            "lifecycle_state": "ACTIVE",
            "owner_module": REGISTRY_OWNER_MODULE,
            "participates_in_rebuild": "TRUE",
            "read_only": "FALSE",
            "allow_creation": "TRUE",
            "created_phase": PHASE_LABEL,
            "notes": "Phase 9A-5D controlled accuracy evaluator dry-run preview; no accuracy results.",
            "registry_created_ts": _norm(existing.get("registry_created_ts")) or now,
            "registry_last_verified_ts": now,
            "registry_migration_ts": _norm(existing.get("registry_migration_ts")),
            "registry_rename_ts": _norm(existing.get("registry_rename_ts")),
        }
        values = [merged.get(header, "") for header in headers]
        if key in by_id:
            row_number = by_id[key]
        else:
            appended += 1
            row_number = len(rows) + appended + 1
        updates.append({"range": f"'{REGISTRY_SHEET}'!A{row_number}:{_column_letter(len(headers))}{row_number}", "values": [values]})
    if updates:
        batch_update_values(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, updates)
    return {"updated": len(registry_rows) - appended, "appended": appended}


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build PreSignal v2.0 Phase 9A-5D controlled accuracy evaluator dry-run.")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Run preview mode only. This is the default and only supported mode.")
    parser.add_argument("--execute-evaluation", action="store_true", help="Reserved future flag. Not supported in Phase 9A-5D.")
    return parser.parse_args(argv)


def build_controlled_accuracy_evaluation_execution_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    args = args or _parse_args()
    if args.execute_evaluation:
        raise RuntimeError("Phase 9A-5D supports dry-run preview only. Do not execute final accuracy evaluation.")

    generated_ts = _iso_now()
    dry_run_id = _run_id(generated_ts)
    service = build_sheets_service(load_credentials())
    diag_titles = _sheet_titles(service, DIAGNOSTICS_SPREADSHEET_ID)
    main_titles = _sheet_titles(service, MAIN_SPREADSHEET_ID)

    missing_required: List[str] = []
    missing_optional: List[str] = []
    design_inputs = {
        sheet: _safe_rows(service, DIAGNOSTICS_SPREADSHEET_ID, diag_titles, sheet, missing_required, required=True)
        for sheet in INPUT_DESIGN_SHEETS
    }
    tier2_inputs = {
        sheet: _safe_rows(service, DIAGNOSTICS_SPREADSHEET_ID, diag_titles, sheet, missing_required, required=True)
        for sheet in TIER2_INPUT_SHEETS
    }
    diag_refs = {
        sheet: _safe_rows(service, DIAGNOSTICS_SPREADSHEET_ID, diag_titles, sheet, missing_optional)
        for sheet in OUTCOME_REFERENCE_SHEETS
    }
    main_refs = {
        sheet: _safe_rows(service, MAIN_SPREADSHEET_ID, main_titles, sheet, missing_optional)
        for sheet in OUTCOME_REFERENCE_SHEETS
    }
    if missing_required:
        raise RuntimeError(f"Missing required Phase 9A-5D inputs: {sorted(set(missing_required))}")

    design_summary = design_inputs["Controlled_Accuracy_Design_Summary"][-1] if design_inputs["Controlled_Accuracy_Design_Summary"] else {}
    if not _bool(design_summary.get("ready_for_phase9a5d_execution_builder")):
        raise RuntimeError("Phase 9A-5C design is not ready for Phase 9A-5D execution builder.")

    experiments = design_inputs["Controlled_Accuracy_Experiment_Schema"]
    comparisons = design_inputs["Controlled_Accuracy_Comparison_Logic"]
    metric_logic = design_inputs["Controlled_Accuracy_Metric_Logic"]
    forecasts = tier2_inputs["Pack_Behavior_Tier2_Forecasts"]
    raw_rows = tier2_inputs["Pack_Behavior_Tier2_Raw_Response_Archive"]
    raw_keys = _raw_archive_keys(raw_rows)

    outcome_meta, outcome_indexes = _outcome_indexes(main_refs, diag_refs)
    if not outcome_meta.get("source_available"):
        outcome_status = "BLOCKED_MISSING_OUTCOME_SOURCE"
    elif not outcome_meta.get("required_fields_present"):
        outcome_status = "NEEDS_REVIEW_MISSING_OUTCOME_FIELDS"
    else:
        outcome_status = "MATCH_PREVIEW_AVAILABLE"

    eligible_rows, outcome_rows, eligible_by_key = _build_eligible_and_outcome_rows(
        generated_ts, dry_run_id, experiments, forecasts, raw_keys, outcome_meta, outcome_indexes
    )
    pair_rows = _build_pair_rows(generated_ts, dry_run_id, comparisons, forecasts, eligible_by_key)
    metric_rows = _build_metric_rows(generated_ts, dry_run_id, comparisons, metric_logic, pair_rows)
    invalid_rows = _build_invalid_rows(generated_ts, dry_run_id, eligible_rows)
    governance_rows = _build_governance_rows(generated_ts, dry_run_id)
    dry_run_rows = _build_dry_run_rows(
        generated_ts, dry_run_id, experiments, eligible_rows, outcome_rows, pair_rows, metric_rows, outcome_status
    )

    governance_failed = any(_norm(row.get("status")) != "PASS" for row in governance_rows)
    outcome_matches_found = sum(1 for row in outcome_rows if _norm(row.get("outcome_match_status")) == "MATCH_AVAILABLE_VALUES_SUPPRESSED")
    outcome_matches_missing = sum(1 for row in outcome_rows if _norm(row.get("outcome_match_status")) != "MATCH_AVAILABLE_VALUES_SUPPRESSED")
    eligible_count = sum(1 for row in eligible_rows if _bool(row.get("eligible_for_future_evaluation")))
    invalid_unique_keys = {
        _norm(row.get("forecast_row_key"))
        for row in eligible_rows
        if _norm(row.get("eligibility_status")) in {"EXCLUDED_INVALID_OUTPUT", "EXCLUDED_PROVIDER_FAILURE"}
    }
    invalid_output_rate_preview = round(len(invalid_unique_keys) / len(forecasts), 6) if forecasts else 0
    minimum_sample_warning_count = sum(1 for row in metric_rows if _bool(row.get("minimum_sample_warning")))

    ready_for_approval = (
        not governance_failed
        and outcome_status == "MATCH_PREVIEW_AVAILABLE"
        and outcome_matches_found > 0
        and eligible_count > 0
    )
    build_status = "PASS_WITH_WARNINGS" if ready_for_approval else "PASS_WITH_WARNINGS"
    final_interpretation = (
        "CONTROLLED_ACCURACY_EXECUTION_BUILDER_DRY_RUN_READY_WITH_WARNINGS"
        if ready_for_approval
        else "CONTROLLED_ACCURACY_EXECUTION_BUILDER_DRY_RUN_NEEDS_REVIEW"
    )
    recommended_next_step = (
        "PROCEED_TO_PHASE9A5E_ACCURACY_EXECUTION_APPROVAL"
        if ready_for_approval
        else "RUN_PHASE9A5D_DRY_RUN_REPAIR"
    )

    summary_row = _base(generated_ts, dry_run_id)
    summary_row.update(
        {
            "build_status": build_status,
            "final_interpretation": final_interpretation,
            "experiments_previewed": len(experiments),
            "eligible_rows_found": eligible_count,
            "invalid_rows_excluded": len(invalid_unique_keys),
            "outcome_matches_found": outcome_matches_found,
            "outcome_matches_missing": outcome_matches_missing,
            "comparison_pairs_planned": len(pair_rows),
            "metric_rows_planned": len(metric_rows),
            "outcome_matching_preview_status": outcome_status,
            "minimum_sample_warning_count": minimum_sample_warning_count,
            "invalid_output_rate_preview": invalid_output_rate_preview,
            "provider_calls_performed": 0,
            "forecast_generation_performed": 0,
            "accuracy_evaluation_performed": 0,
            "direction_correctness_calculated": 0,
            "overall_ok_calculated": 0,
            "accuracy_delta_calculated": 0,
            "metric_values_calculated": 0,
            "evaluation_result_rows_written": 0,
            "evaluation_rows_written": 0,
            "outcome_ledger_written": 0,
            "production_behavior_change_count": 0,
            "ready_for_phase9a5e_execution_approval": "TRUE" if ready_for_approval else "FALSE",
            "ready_for_accuracy_evaluation": "FALSE",
            "ready_for_production": "FALSE",
            "recommended_next_step": recommended_next_step,
            "notes": json.dumps(
                {
                    "dry_run_only": True,
                    "outcome_source_used_for_preview": outcome_meta.get("source_sheet"),
                    "missing_optional_references": sorted(set(missing_optional)),
                    "outcome_values_written": False,
                    "metric_values_calculated": False,
                    "comparison_results_calculated": False,
                },
                sort_keys=True,
            ),
        }
    )
    summary_rows = [summary_row]

    outputs = [
        (OUTPUT_DRY_RUN, DRY_RUN_HEADERS, dry_run_rows),
        (OUTPUT_ELIGIBLE, ELIGIBLE_HEADERS, eligible_rows),
        (OUTPUT_OUTCOME, OUTCOME_HEADERS, outcome_rows),
        (OUTPUT_PAIR, PAIR_HEADERS, pair_rows),
        (OUTPUT_METRIC, METRIC_HEADERS, metric_rows),
        (OUTPUT_INVALID, INVALID_HEADERS, invalid_rows),
        (OUTPUT_GOVERNANCE, GOVERNANCE_HEADERS, governance_rows),
        (OUTPUT_SUMMARY, SUMMARY_HEADERS, summary_rows),
    ]

    for sheet_name, required_headers, rows in outputs:
        headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, required_headers)
        _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, headers, rows)

    registry = _upsert_registry_rows(service)

    return {
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "file_created": "automation/build_controlled_accuracy_evaluation_execution_v0.py",
        "sheets_written": {sheet_name: len(rows) for sheet_name, _, rows in outputs},
        "experiments_previewed": len(experiments),
        "eligible_rows_found": eligible_count,
        "invalid_rows_excluded": len(invalid_unique_keys),
        "outcome_matches_found": outcome_matches_found,
        "outcome_matches_missing": outcome_matches_missing,
        "comparison_pairs_planned": len(pair_rows),
        "metric_rows_planned": len(metric_rows),
        "outcome_matching_preview_status": outcome_status,
        "minimum_sample_warning_count": minimum_sample_warning_count,
        "invalid_output_rate_preview": invalid_output_rate_preview,
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "accuracy_evaluation_performed": 0,
        "direction_correctness_calculated": 0,
        "overall_ok_calculated": 0,
        "accuracy_delta_calculated": 0,
        "metric_values_calculated": 0,
        "evaluation_result_rows_written": 0,
        "evaluation_rows_written": 0,
        "outcome_ledger_written": 0,
        "production_behavior_change_count": 0,
        "ready_for_phase9a5e_execution_approval": ready_for_approval,
        "ready_for_accuracy_evaluation": False,
        "ready_for_production": False,
        "recommended_next_step": recommended_next_step,
        "registry": registry,
    }


def main() -> None:
    result = build_controlled_accuracy_evaluation_execution_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
