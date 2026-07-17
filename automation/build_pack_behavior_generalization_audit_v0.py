import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.build_market_sessions_shadow_v0 import (
    DIAGNOSTICS_SPREADSHEET_ID,
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


SCHEMA_VERSION = "presignal_v2_behavior_generalization_audit_0.1"
GENERALIZATION_VERSION = "behavior_generalization_audit_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-4Y"
REGISTRY_CATEGORY = "PRESIGNAL_V2_BEHAVIOR_PATTERN_GENERALIZATION_AUDIT"
REGISTRY_OWNER_MODULE = "market_state"

PILOT_TRANSITIONS_SHEET = "Pack_Exposure_Reasoning_Transitions"
PILOT_FIELD_SHEET = "Pack_Exposure_Field_Influence_Audit"
PILOT_NOSIGNAL_SHEET = "Pack_Exposure_NoSignal_Confidence_Audit"
PILOT_INVALID_SHEET = "Pack_Exposure_Invalid_Output_Audit"
PILOT_SUMMARY_SHEET = "Pack_Exposure_Behavior_Compare_Summary"

TIER1_RUNS_SHEET = "Pack_Behavior_Discovery_Runs"
TIER1_TRANSITIONS_SHEET = "Pack_Behavior_Discovery_Transitions"
TIER1_FIELD_SHEET = "Pack_Behavior_Discovery_Field_Influence"
TIER1_NOSIGNAL_SHEET = "Pack_Behavior_Discovery_NoSignal"
TIER1_INVALID_SHEET = "Pack_Behavior_Discovery_Invalid_Output"
TIER1_SUMMARY_SHEET = "Pack_Behavior_Discovery_Run_Summary"

OUTPUT_GENERALIZATION_SHEET = "Pack_Behavior_Generalization_Audit"
OUTPUT_PROVIDER_SHEET = "Pack_Behavior_Provider_Consistency_Audit"
OUTPUT_TRANSITION_SHEET = "Pack_Behavior_Transition_Reproducibility_Audit"
OUTPUT_FIELD_SHEET = "Pack_Behavior_Field_Stability_Audit"
OUTPUT_NOSIGNAL_SHEET = "Pack_Behavior_NoSignal_Stability_Audit"
OUTPUT_INVALID_SHEET = "Pack_Behavior_Invalid_Output_Generalization_Audit"
OUTPUT_HYPOTHESES_SHEET = "Pack_Behavior_Generalization_Hypotheses"
OUTPUT_SUMMARY_SHEET = "Pack_Behavior_Generalization_Summary"

PROVIDERS = ["OpenAI", "Gemini", "Anthropic"]
PACK_LEVELS = ["A", "B", "C", "D", "E"]
TRANSITIONS = ["A_to_B", "B_to_C", "C_to_D", "D_to_E", "A_to_D", "A_to_E"]
PATTERN_FAMILIES = [
    "provider_sensitivity",
    "pack_transition_value",
    "field_influence",
    "field_family_influence",
    "no_signal_behavior",
    "confidence_behavior",
    "causal_chain_behavior",
    "invalid_output_behavior",
]

GENERALIZATION_HEADERS = [
    "generated_ts",
    "schema_version",
    "generalization_audit_version",
    "generalization_run_id",
    "pattern_id",
    "pattern_family",
    "pattern_name",
    "pattern_description",
    "evidence_scope",
    "sessions_observed",
    "sessions_with_pattern",
    "providers_observed",
    "providers_with_pattern",
    "pack_transitions_observed",
    "pack_transitions_with_pattern",
    "valid_observation_count",
    "invalid_or_partial_count",
    "recurrence_rate",
    "cross_session_recurrence",
    "cross_provider_recurrence",
    "cross_transition_recurrence",
    "generalization_status",
    "confidence_label",
    "evidence_sheets",
    "interpretation_allowed",
    "interpretation_forbidden",
    "notes",
]

PROVIDER_HEADERS = [
    "generated_ts",
    "schema_version",
    "generalization_audit_version",
    "generalization_run_id",
    "provider",
    "pattern_family",
    "sessions_available",
    "sessions_valid",
    "valid_transition_count",
    "invalid_transition_count",
    "direction_change_count",
    "confidence_change_count",
    "no_signal_change_count",
    "causal_chain_change_count",
    "reasoning_change_count",
    "field_used_count",
    "field_changed_reasoning_count",
    "mean_transition_complexity",
    "max_transition_complexity",
    "sensitivity_classification",
    "consistency_status",
    "invalid_output_impact",
    "interpretation",
    "notes",
]

TRANSITION_HEADERS = [
    "generated_ts",
    "schema_version",
    "generalization_audit_version",
    "generalization_run_id",
    "pack_transition",
    "sessions_available",
    "sessions_with_valid_transition",
    "providers_available",
    "providers_with_valid_transition",
    "valid_transition_count",
    "invalid_transition_count",
    "direction_change_count",
    "confidence_change_count",
    "no_signal_change_count",
    "causal_chain_change_count",
    "information_used_change_count",
    "missing_information_reduction_count",
    "mean_transition_complexity",
    "max_transition_complexity",
    "behavioral_value_classification",
    "reproducibility_status",
    "invalid_output_impact",
    "interpretation",
    "notes",
]

FIELD_HEADERS = [
    "generated_ts",
    "schema_version",
    "generalization_audit_version",
    "generalization_run_id",
    "candidate_family",
    "candidate_field",
    "sessions_available",
    "sessions_field_available",
    "sessions_field_used",
    "sessions_field_changed_reasoning",
    "sessions_field_discarded",
    "sessions_field_no_effect",
    "valid_field_observation_count",
    "invalid_field_observation_count",
    "field_used_count",
    "field_changed_reasoning_count",
    "field_discarded_count",
    "field_no_effect_count",
    "available_not_mentioned_count",
    "used_rate",
    "changed_reasoning_rate",
    "discarded_rate",
    "no_effect_rate",
    "stability_status",
    "field_behavior_interpretation",
    "notes",
]

NOSIGNAL_HEADERS = [
    "generated_ts",
    "schema_version",
    "generalization_audit_version",
    "generalization_run_id",
    "provider",
    "pack_transition",
    "sessions_available",
    "valid_transition_count",
    "invalid_transition_count",
    "no_signal_change_count",
    "no_signal_from_true_to_false_count",
    "no_signal_from_false_to_true_count",
    "no_signal_stable_true_count",
    "no_signal_stable_false_count",
    "confidence_change_count",
    "mean_confidence_delta",
    "max_confidence_delta_abs",
    "stability_status",
    "interpretation",
    "notes",
]

INVALID_HEADERS = [
    "generated_ts",
    "schema_version",
    "generalization_audit_version",
    "generalization_run_id",
    "provider",
    "pack_level",
    "sessions_attempted",
    "valid_output_count",
    "invalid_output_count",
    "invalid_output_rate",
    "invalid_reason_counts",
    "malformed_or_truncated_count",
    "schema_validation_failure_count",
    "provider_error_count",
    "raw_archive_missing_count",
    "invalid_pattern_status",
    "tier2_design_implication",
    "notes",
]

HYPOTHESIS_HEADERS = [
    "generated_ts",
    "schema_version",
    "generalization_audit_version",
    "generalization_run_id",
    "hypothesis_id",
    "hypothesis_name",
    "hypothesis_type",
    "hypothesis_statement",
    "supporting_pattern_ids",
    "supporting_evidence_summary",
    "sessions_supporting",
    "providers_supporting",
    "pack_transitions_supporting",
    "fields_or_families_involved",
    "current_evidence_status",
    "tier2_test_priority",
    "tier2_test_design_hint",
    "accuracy_excluded",
    "production_excluded",
    "notes",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "schema_version",
    "generalization_audit_version",
    "generalization_run_id",
    "build_status",
    "final_interpretation",
    "pilot_sessions_included",
    "tier1_sessions_included",
    "total_sessions_included",
    "providers_included",
    "pack_levels_included",
    "generalization_patterns_identified",
    "candidate_patterns_identified",
    "underdetermined_patterns_identified",
    "invalid_output_limited_patterns_identified",
    "hypotheses_defined",
    "high_priority_hypotheses",
    "medium_priority_hypotheses",
    "hold_hypotheses",
    "strongest_provider_pattern",
    "strongest_transition_pattern",
    "strongest_field_family_pattern",
    "strongest_no_signal_pattern",
    "strongest_invalid_output_pattern",
    "accuracy_evaluation_count",
    "provider_call_count",
    "forecast_generation_count",
    "provider_rerun_count",
    "production_behavior_change_count",
    "ready_for_tier2_design",
    "ready_for_tier2_execution",
    "ready_for_accuracy_evaluation",
    "ready_for_production",
    "recommended_next_step",
    "notes",
]


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _run_id(generated_ts: str) -> str:
    stamp = generated_ts.replace("-", "").replace(":", "").replace("+00:00", "Z").replace(".", "")
    return f"pack_behavior_generalization_audit_v0_{stamp}"


def _sheet_titles(service, spreadsheet_id: str) -> Set[str]:
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    return {sheet["properties"]["title"] for sheet in meta.get("sheets", [])}


def _safe_rows(service, titles: Set[str], sheet_name: str, missing: List[str]) -> List[Dict[str, Any]]:
    if sheet_name not in titles:
        missing.append(sheet_name)
        return []
    return _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name)


def _float(value: Any) -> Optional[float]:
    try:
        text = _norm(value)
        return float(text) if text else None
    except Exception:
        return None


def _material_confidence_changed(row: Dict[str, Any]) -> bool:
    value = _float(row.get("confidence_delta"))
    return value is not None and abs(value) >= 10


def _is_valid_transition(row: Dict[str, Any]) -> bool:
    return _upper(row.get("transition_status")) == "PASS"


def _direction_changed(row: Dict[str, Any]) -> bool:
    value = _upper(row.get("direction_transition"))
    return value not in {"", "UNCHANGED", "UNKNOWN"}


def _reasoning_changed(row: Dict[str, Any]) -> bool:
    return any(
        _upper(row.get(field)) in {"CHANGED", "REDUCED"}
        for field in [
            "primary_driver_transition",
            "secondary_driver_transition",
            "used_information_transition",
            "ignored_information_transition",
            "missing_information_transition",
            "causal_chain_transition",
        ]
    )


def _status_from_sessions(sessions_with_pattern: int, valid_observations: int, invalid: int = 0) -> str:
    if invalid and invalid >= valid_observations and valid_observations < 5:
        return "INVALID_OUTPUT_LIMITED"
    if sessions_with_pattern <= 0 or valid_observations <= 0:
        return "UNDERDETERMINED"
    if sessions_with_pattern == 1:
        return "SINGLE_SESSION_ONLY"
    if sessions_with_pattern >= 3 and valid_observations >= 5:
        return "CANDIDATE_PATTERN"
    if sessions_with_pattern >= 2:
        return "REPEATED"
    return "OBSERVED"


def _confidence_label(status: str, recurrence_rate: float) -> str:
    if status in {"CANDIDATE_PATTERN"} and recurrence_rate >= 0.5:
        return "MEDIUM"
    if status in {"REPEATED", "OBSERVED"}:
        return "LOW_TO_MEDIUM"
    if status == "INVALID_OUTPUT_LIMITED":
        return "INVALID_OUTPUT_LIMITED"
    return "LOW"


def _combine_transitions(pilot_rows: Sequence[Dict[str, Any]], tier1_rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for source, source_rows in [("pilot", pilot_rows), ("tier1", tier1_rows)]:
        for row in source_rows:
            out = dict(row)
            out["evidence_scope"] = source
            rows.append(out)
    return rows


def _combine_field_rows(pilot_rows: Sequence[Dict[str, Any]], tier1_rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for source, source_rows in [("pilot", pilot_rows), ("tier1", tier1_rows)]:
        for row in source_rows:
            out = dict(row)
            out["evidence_scope"] = source
            rows.append(out)
    return rows


def _combine_invalid_rows(pilot_rows: Sequence[Dict[str, Any]], tier1_rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for source, source_rows in [("pilot", pilot_rows), ("tier1", tier1_rows)]:
        for row in source_rows:
            out = dict(row)
            out["evidence_scope"] = source
            rows.append(out)
    return rows


def _sessions(rows: Iterable[Dict[str, Any]]) -> Set[str]:
    return {_norm(row.get("session_id")) for row in rows if _norm(row.get("session_id"))}


def _fmt_rate(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return ""
    return f"{numerator / denominator:.3f}"


def _fmt_mean(values: Sequence[float]) -> str:
    return f"{mean(values):.2f}" if values else ""


def _transition_metrics(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    valid = [row for row in rows if _is_valid_transition(row)]
    invalid = [row for row in rows if not _is_valid_transition(row)]
    complexities = [_float(row.get("transition_complexity_score")) for row in valid]
    complexities = [value for value in complexities if value is not None]
    return {
        "valid": valid,
        "invalid": invalid,
        "valid_count": len(valid),
        "invalid_count": len(invalid),
        "sessions": _sessions(rows),
        "valid_sessions": _sessions(valid),
        "providers": {_norm(row.get("provider")) for row in rows if _norm(row.get("provider"))},
        "valid_providers": {_norm(row.get("provider")) for row in valid if _norm(row.get("provider"))},
        "direction": sum(1 for row in valid if _direction_changed(row)),
        "confidence": sum(1 for row in valid if _material_confidence_changed(row)),
        "no_signal": sum(1 for row in valid if _upper(row.get("no_signal_transition")) == "CHANGED"),
        "causal": sum(1 for row in valid if _upper(row.get("causal_chain_transition")) == "CHANGED"),
        "info_used": sum(1 for row in valid if _upper(row.get("used_information_transition")) == "CHANGED"),
        "missing_reduced": sum(1 for row in valid if _upper(row.get("missing_information_transition")) == "REDUCED"),
        "reasoning": sum(1 for row in valid if _reasoning_changed(row)),
        "mean_complexity": _fmt_mean(complexities),
        "max_complexity": f"{max(complexities):.0f}" if complexities else "",
    }


def _classify_provider(metrics: Dict[str, Any]) -> str:
    valid = metrics["valid_count"]
    invalid = metrics["invalid_count"]
    if valid == 0 or invalid > valid:
        return "UNDETERMINED_DUE_INVALID_OUTPUTS"
    score = metrics["direction"] + metrics["confidence"] + metrics["no_signal"] + metrics["causal"]
    rate = score / max(valid, 1)
    if rate >= 1.5:
        return "HIGH_PACK_SENSITIVITY"
    if rate >= 0.75:
        return "MODERATE_PACK_SENSITIVITY"
    return "LOW_PACK_SENSITIVITY"


def _provider_consistency(metrics: Dict[str, Any]) -> str:
    if metrics["invalid_count"] > metrics["valid_count"]:
        return "INVALID_OUTPUT_LIMITED"
    if len(metrics["valid_sessions"]) >= 3 and metrics["reasoning"] >= len(metrics["valid_sessions"]):
        return "CONSISTENT_ACROSS_SESSIONS"
    if len(metrics["valid_sessions"]) >= 2:
        return "MIXED_ACROSS_SESSIONS"
    if len(metrics["valid_sessions"]) == 1:
        return "SESSION_SPECIFIC"
    return "UNDERDETERMINED"


def _behavioral_value(metrics: Dict[str, Any]) -> str:
    valid = metrics["valid_count"]
    if valid == 0:
        return "UNDETERMINED"
    score = metrics["direction"] + metrics["confidence"] + metrics["no_signal"] + metrics["causal"]
    rate = score / max(valid, 1)
    if rate >= 1.8:
        return "HIGH_BEHAVIORAL_VALUE"
    if rate >= 1.0:
        return "MODERATE_BEHAVIORAL_VALUE"
    return "LOW_BEHAVIORAL_VALUE"


def _transition_repro(metrics: Dict[str, Any]) -> str:
    if metrics["invalid_count"] > metrics["valid_count"]:
        return "INVALID_OUTPUT_LIMITED"
    sessions = len(metrics["valid_sessions"])
    if sessions >= 3 and metrics["causal"] >= max(3, sessions):
        return "REPEATED_STRONG"
    if sessions >= 2 and metrics["causal"] >= 2:
        return "REPEATED_MODERATE"
    if metrics["valid_count"] > 0:
        return "REPEATED_WEAK"
    return "UNDERDETERMINED"


def _field_stability(rows: Sequence[Dict[str, Any]]) -> str:
    valid = [row for row in rows if _upper(row.get("influence_status")) != "INVALID_OUTPUT"]
    invalid = len(rows) - len(valid)
    if not rows:
        return "FIELD_NOT_AVAILABLE"
    if invalid >= len(valid) and len(valid) < 3:
        return "INVALID_OUTPUT_LIMITED"
    counts = Counter(_upper(row.get("influence_status")) for row in valid)
    if counts["USED_AND_CHANGED_REASONING"] >= 2:
        return "REPEATED_CHANGED_REASONING"
    if counts["USED_NO_CLEAR_CHANGE"] + counts["USED_AND_CHANGED_REASONING"] >= 3:
        return "REPEATED_USED"
    if counts["EXPLICITLY_DISCARDED"] >= 2:
        return "REPEATED_DISCARDED"
    if counts["EXPLICITLY_NO_EFFECT"] >= 2:
        return "REPEATED_NO_EFFECT"
    if counts["AVAILABLE_NOT_MENTIONED"] >= 3:
        return "AVAILABLE_NOT_REPEATED"
    return "MIXED_FIELD_BEHAVIOR" if valid else "UNDERDETERMINED"


def _invalid_pattern_status(invalid_count: int, attempted: int, malformed: int, provider_error: int) -> str:
    if attempted <= 0:
        return "UNDERDETERMINED"
    rate = invalid_count / attempted
    if invalid_count == 0:
        return "NO_INVALID_PATTERN"
    if rate >= 0.5 and malformed >= 2:
        return "PROVIDER_PACK_RISK"
    if rate > 0.2:
        return "REPEATED_INVALID_PATTERN"
    if provider_error:
        return "LOW_INVALID_RATE"
    return "LOW_INVALID_RATE"


def _generalization_row(
    generated_ts: str,
    run_id: str,
    pattern_id: str,
    family: str,
    name: str,
    description: str,
    sessions_observed: Set[str],
    sessions_with_pattern: Set[str],
    providers_observed: Set[str],
    providers_with_pattern: Set[str],
    transitions_observed: Set[str],
    transitions_with_pattern: Set[str],
    valid_count: int,
    invalid_count: int,
    evidence_sheets: str,
    notes: str = "",
    forced_status: str = "",
) -> Dict[str, Any]:
    denom = valid_count + invalid_count
    recurrence_rate = valid_count / denom if denom else 0
    status = forced_status or _status_from_sessions(len(sessions_with_pattern), valid_count, invalid_count)
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "generalization_audit_version": GENERALIZATION_VERSION,
        "generalization_run_id": run_id,
        "pattern_id": pattern_id,
        "pattern_family": family,
        "pattern_name": name,
        "pattern_description": description,
        "evidence_scope": "pilot_plus_tier1",
        "sessions_observed": "|".join(sorted(sessions_observed)),
        "sessions_with_pattern": "|".join(sorted(sessions_with_pattern)),
        "providers_observed": "|".join(sorted(providers_observed)),
        "providers_with_pattern": "|".join(sorted(providers_with_pattern)),
        "pack_transitions_observed": "|".join(sorted(transitions_observed)),
        "pack_transitions_with_pattern": "|".join(sorted(transitions_with_pattern)),
        "valid_observation_count": valid_count,
        "invalid_or_partial_count": invalid_count,
        "recurrence_rate": f"{recurrence_rate:.3f}" if denom else "",
        "cross_session_recurrence": "TRUE" if len(sessions_with_pattern) >= 2 else "FALSE",
        "cross_provider_recurrence": "TRUE" if len(providers_with_pattern) >= 2 else "FALSE",
        "cross_transition_recurrence": "TRUE" if len(transitions_with_pattern) >= 2 else "FALSE",
        "generalization_status": status,
        "confidence_label": _confidence_label(status, recurrence_rate),
        "evidence_sheets": evidence_sheets,
        "interpretation_allowed": "Candidate behavior pattern for Tier 2 design; behavior-only interpretation.",
        "interpretation_forbidden": "No accuracy, provider ranking, pack ranking, production, routing, or statistical-stability claim.",
        "notes": _truncate_text(notes, 500),
    }


def _hypothesis_row(
    generated_ts: str,
    run_id: str,
    hypothesis_id: str,
    name: str,
    htype: str,
    statement: str,
    pattern_ids: Sequence[str],
    evidence: str,
    sessions: Iterable[str],
    providers: Iterable[str],
    transitions: Iterable[str],
    fields: Iterable[str],
    status: str,
    priority: str,
    design_hint: str,
    notes: str = "",
) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "generalization_audit_version": GENERALIZATION_VERSION,
        "generalization_run_id": run_id,
        "hypothesis_id": hypothesis_id,
        "hypothesis_name": name,
        "hypothesis_type": htype,
        "hypothesis_statement": statement,
        "supporting_pattern_ids": "|".join(pattern_ids),
        "supporting_evidence_summary": _truncate_text(evidence, 500),
        "sessions_supporting": "|".join(sorted(set(sessions))),
        "providers_supporting": "|".join(sorted(set(providers))),
        "pack_transitions_supporting": "|".join(sorted(set(transitions))),
        "fields_or_families_involved": "|".join(sorted(set(fields))),
        "current_evidence_status": status,
        "tier2_test_priority": priority,
        "tier2_test_design_hint": design_hint,
        "accuracy_excluded": "TRUE",
        "production_excluded": "TRUE",
        "notes": _truncate_text(notes, 500),
    }


def _upsert_registry_rows(service) -> Dict[str, int]:
    headers = _ensure_sheet(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET, REGISTRY_HEADERS)
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_upper(row.get("logical_sheet_id")): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_upper(row.get("logical_sheet_id")): row for row in rows}
    registry_rows = [
        ("PACK_BEHAVIOR_GENERALIZATION_AUDIT", OUTPUT_GENERALIZATION_SHEET, "behavior_generalization_audit"),
        ("PACK_BEHAVIOR_PROVIDER_CONSISTENCY_AUDIT", OUTPUT_PROVIDER_SHEET, "behavior_provider_consistency_audit"),
        ("PACK_BEHAVIOR_TRANSITION_REPRODUCIBILITY_AUDIT", OUTPUT_TRANSITION_SHEET, "behavior_transition_reproducibility_audit"),
        ("PACK_BEHAVIOR_FIELD_STABILITY_AUDIT", OUTPUT_FIELD_SHEET, "behavior_field_stability_audit"),
        ("PACK_BEHAVIOR_NOSIGNAL_STABILITY_AUDIT", OUTPUT_NOSIGNAL_SHEET, "behavior_no_signal_stability_audit"),
        ("PACK_BEHAVIOR_INVALID_OUTPUT_GENERALIZATION_AUDIT", OUTPUT_INVALID_SHEET, "behavior_invalid_output_generalization_audit"),
        ("PACK_BEHAVIOR_GENERALIZATION_HYPOTHESES", OUTPUT_HYPOTHESES_SHEET, "behavior_generalization_hypotheses"),
        ("PACK_BEHAVIOR_GENERALIZATION_SUMMARY", OUTPUT_SUMMARY_SHEET, "behavior_generalization_summary"),
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
            "notes": "Phase 9A-4Y behavior generalization audit; behavior-only, no accuracy evaluation.",
            "registry_created_ts": _norm(existing.get("registry_created_ts")) or now,
            "registry_last_verified_ts": now,
            "registry_migration_ts": _norm(existing.get("registry_migration_ts")),
            "registry_rename_ts": _norm(existing.get("registry_rename_ts")),
        }
        values = [merged.get(header, "") for header in headers]
        row_number = by_id.get(key)
        if not row_number:
            appended += 1
            row_number = len(rows) + appended + 1
        updates.append({"range": f"'{REGISTRY_SHEET}'!A{row_number}:{_column_letter(len(headers))}{row_number}", "values": [values]})
    if updates:
        batch_update_values(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, updates)
    return {"updated": len(registry_rows) - appended, "appended": appended}


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build PreSignal v2.0 Phase 9A-4Y behavior generalization audit.")
    return parser.parse_args(argv)


def build_pack_behavior_generalization_audit_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    args = args or _parse_args()
    generated_ts = _iso_now()
    run_id = _run_id(generated_ts)
    service = build_sheets_service(load_credentials())
    titles = _sheet_titles(service, DIAGNOSTICS_SPREADSHEET_ID)
    missing: List[str] = []

    pilot_transitions = _safe_rows(service, titles, PILOT_TRANSITIONS_SHEET, missing)
    pilot_fields = _safe_rows(service, titles, PILOT_FIELD_SHEET, missing)
    pilot_no_signal = _safe_rows(service, titles, PILOT_NOSIGNAL_SHEET, missing)
    pilot_invalid = _safe_rows(service, titles, PILOT_INVALID_SHEET, missing)
    pilot_summary = _safe_rows(service, titles, PILOT_SUMMARY_SHEET, missing)
    tier1_runs = _safe_rows(service, titles, TIER1_RUNS_SHEET, missing)
    tier1_transitions = _safe_rows(service, titles, TIER1_TRANSITIONS_SHEET, missing)
    tier1_fields = _safe_rows(service, titles, TIER1_FIELD_SHEET, missing)
    tier1_no_signal = _safe_rows(service, titles, TIER1_NOSIGNAL_SHEET, missing)
    tier1_invalid = _safe_rows(service, titles, TIER1_INVALID_SHEET, missing)
    tier1_summary = _safe_rows(service, titles, TIER1_SUMMARY_SHEET, missing)

    if not pilot_transitions and not tier1_transitions:
        raise RuntimeError("Both pilot and Tier 1 behavior outputs are missing; cannot build generalization audit.")

    transitions = _combine_transitions(pilot_transitions, tier1_transitions)
    field_rows_all = _combine_field_rows(pilot_fields, tier1_fields)
    invalid_rows_all = _combine_invalid_rows(pilot_invalid, tier1_invalid)
    all_sessions = _sessions(transitions)
    pilot_sessions = _sessions(pilot_transitions)
    tier1_sessions = _sessions(tier1_transitions) or {_norm(row.get("session_id")) for row in tier1_runs if _norm(row.get("session_id"))}
    providers_observed = {_norm(row.get("provider")) for row in transitions if _norm(row.get("provider"))}
    transitions_observed = {_norm(row.get("transition")) for row in transitions if _norm(row.get("transition"))}

    provider_rows: List[Dict[str, Any]] = []
    provider_metrics_by_provider: Dict[str, Dict[str, Any]] = {}
    field_by_provider = defaultdict(list)
    for row in field_rows_all:
        field_by_provider[_norm(row.get("provider"))].append(row)
    for provider in PROVIDERS:
        rows = [row for row in transitions if _norm(row.get("provider")) == provider]
        metrics = _transition_metrics(rows)
        provider_metrics_by_provider[provider] = metrics
        field_valid = [row for row in field_by_provider[provider] if _upper(row.get("influence_status")) != "INVALID_OUTPUT"]
        field_used = sum(1 for row in field_valid if _upper(row.get("influence_status")) in {"USED_AND_CHANGED_REASONING", "USED_NO_CLEAR_CHANGE"})
        field_changed = sum(1 for row in field_valid if _upper(row.get("influence_status")) == "USED_AND_CHANGED_REASONING")
        classification = _classify_provider(metrics)
        consistency = _provider_consistency(metrics)
        invalid_impact = "HIGH" if metrics["invalid_count"] > metrics["valid_count"] else ("MEDIUM" if metrics["invalid_count"] else "LOW")
        for family in PATTERN_FAMILIES:
            provider_rows.append(
                {
                    "generated_ts": generated_ts,
                    "schema_version": SCHEMA_VERSION,
                    "generalization_audit_version": GENERALIZATION_VERSION,
                    "generalization_run_id": run_id,
                    "provider": provider,
                    "pattern_family": family,
                    "sessions_available": len(metrics["sessions"]),
                    "sessions_valid": len(metrics["valid_sessions"]),
                    "valid_transition_count": metrics["valid_count"],
                    "invalid_transition_count": metrics["invalid_count"],
                    "direction_change_count": metrics["direction"],
                    "confidence_change_count": metrics["confidence"],
                    "no_signal_change_count": metrics["no_signal"],
                    "causal_chain_change_count": metrics["causal"],
                    "reasoning_change_count": metrics["reasoning"],
                    "field_used_count": field_used,
                    "field_changed_reasoning_count": field_changed,
                    "mean_transition_complexity": metrics["mean_complexity"],
                    "max_transition_complexity": metrics["max_complexity"],
                    "sensitivity_classification": classification,
                    "consistency_status": consistency,
                    "invalid_output_impact": invalid_impact,
                    "interpretation": f"{provider} shows {classification.lower()} for {family}; behavior-only, no accuracy interpretation.",
                    "notes": "Same provider-level counts repeated across pattern families to support family-specific downstream grouping.",
                }
            )

    transition_rows_out: List[Dict[str, Any]] = []
    transition_metrics_by_name: Dict[str, Dict[str, Any]] = {}
    for transition in TRANSITIONS:
        rows = [row for row in transitions if _norm(row.get("transition")) == transition]
        metrics = _transition_metrics(rows)
        transition_metrics_by_name[transition] = metrics
        value = _behavioral_value(metrics)
        repro = _transition_repro(metrics)
        invalid_impact = "HIGH" if metrics["invalid_count"] > metrics["valid_count"] else ("MEDIUM" if metrics["invalid_count"] else "LOW")
        transition_rows_out.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "generalization_audit_version": GENERALIZATION_VERSION,
                "generalization_run_id": run_id,
                "pack_transition": transition,
                "sessions_available": len(metrics["sessions"]),
                "sessions_with_valid_transition": len(metrics["valid_sessions"]),
                "providers_available": len(metrics["providers"]),
                "providers_with_valid_transition": len(metrics["valid_providers"]),
                "valid_transition_count": metrics["valid_count"],
                "invalid_transition_count": metrics["invalid_count"],
                "direction_change_count": metrics["direction"],
                "confidence_change_count": metrics["confidence"],
                "no_signal_change_count": metrics["no_signal"],
                "causal_chain_change_count": metrics["causal"],
                "information_used_change_count": metrics["info_used"],
                "missing_information_reduction_count": metrics["missing_reduced"],
                "mean_transition_complexity": metrics["mean_complexity"],
                "max_transition_complexity": metrics["max_complexity"],
                "behavioral_value_classification": value,
                "reproducibility_status": repro,
                "invalid_output_impact": invalid_impact,
                "interpretation": f"{transition} shows {value.lower()} and {repro.lower()} across pilot plus Tier 1.",
                "notes": "D_to_E should be interpreted cautiously because Pack E may duplicate Pack D under Feature Freeze.",
            }
        )

    field_rows_out: List[Dict[str, Any]] = []
    field_groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in field_rows_all:
        field_groups[(_norm(row.get("candidate_family")), _norm(row.get("candidate_field")))].append(row)
    for (family, field), rows in sorted(field_groups.items()):
        if not field:
            continue
        valid = [row for row in rows if _upper(row.get("influence_status")) != "INVALID_OUTPUT"]
        invalid = len(rows) - len(valid)
        counts = Counter(_upper(row.get("influence_status")) for row in valid)
        used = counts["USED_AND_CHANGED_REASONING"] + counts["USED_NO_CLEAR_CHANGE"]
        changed = counts["USED_AND_CHANGED_REASONING"]
        discarded = counts["EXPLICITLY_DISCARDED"]
        no_effect = counts["EXPLICITLY_NO_EFFECT"]
        available_not_mentioned = counts["AVAILABLE_NOT_MENTIONED"]
        valid_count = len(valid)
        status = _field_stability(rows)
        field_rows_out.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "generalization_audit_version": GENERALIZATION_VERSION,
                "generalization_run_id": run_id,
                "candidate_family": family,
                "candidate_field": field,
                "sessions_available": len(all_sessions),
                "sessions_field_available": len(_sessions(rows)),
                "sessions_field_used": len(_sessions([row for row in valid if _upper(row.get("influence_status")) in {"USED_AND_CHANGED_REASONING", "USED_NO_CLEAR_CHANGE"}])),
                "sessions_field_changed_reasoning": len(_sessions([row for row in valid if _upper(row.get("influence_status")) == "USED_AND_CHANGED_REASONING"])),
                "sessions_field_discarded": len(_sessions([row for row in valid if _upper(row.get("influence_status")) == "EXPLICITLY_DISCARDED"])),
                "sessions_field_no_effect": len(_sessions([row for row in valid if _upper(row.get("influence_status")) == "EXPLICITLY_NO_EFFECT"])),
                "valid_field_observation_count": valid_count,
                "invalid_field_observation_count": invalid,
                "field_used_count": used,
                "field_changed_reasoning_count": changed,
                "field_discarded_count": discarded,
                "field_no_effect_count": no_effect,
                "available_not_mentioned_count": available_not_mentioned,
                "used_rate": _fmt_rate(used, valid_count),
                "changed_reasoning_rate": _fmt_rate(changed, valid_count),
                "discarded_rate": _fmt_rate(discarded, valid_count),
                "no_effect_rate": _fmt_rate(no_effect, valid_count),
                "stability_status": status,
                "field_behavior_interpretation": f"{field} is {status.lower()} within {family}; exact-field matching is conservative.",
                "notes": "Family-level influence may be undercounted when providers mention broad concepts instead of exact field names.",
            }
        )

    no_signal_rows_out: List[Dict[str, Any]] = []
    for provider in PROVIDERS:
        for transition in TRANSITIONS:
            rows = [row for row in transitions if _norm(row.get("provider")) == provider and _norm(row.get("transition")) == transition]
            valid = [row for row in rows if _is_valid_transition(row)]
            invalid = len(rows) - len(valid)
            deltas = [_float(row.get("confidence_delta")) for row in valid]
            deltas = [value for value in deltas if value is not None]
            ns_changed = [row for row in valid if _upper(row.get("no_signal_transition")) == "CHANGED"]
            true_to_false = sum(1 for row in ns_changed if _upper(row.get("no_signal_from")) == "TRUE" and _upper(row.get("no_signal_to")) == "FALSE")
            false_to_true = sum(1 for row in ns_changed if _upper(row.get("no_signal_from")) == "FALSE" and _upper(row.get("no_signal_to")) == "TRUE")
            stable_true = sum(1 for row in valid if _upper(row.get("no_signal_from")) == "TRUE" and _upper(row.get("no_signal_to")) == "TRUE")
            stable_false = sum(1 for row in valid if _upper(row.get("no_signal_from")) == "FALSE" and _upper(row.get("no_signal_to")) == "FALSE")
            if invalid > len(valid):
                status = "INVALID_OUTPUT_LIMITED"
            elif true_to_false > false_to_true and true_to_false:
                status = "NO_SIGNAL_REDUCED_BY_PACK"
            elif false_to_true > true_to_false and false_to_true:
                status = "NO_SIGNAL_INCREASED_BY_PACK"
            elif true_to_false or false_to_true:
                status = "MIXED_NO_SIGNAL_BEHAVIOR"
            elif stable_true or stable_false:
                status = "NO_SIGNAL_STABLE"
            else:
                status = "UNDERDETERMINED"
            no_signal_rows_out.append(
                {
                    "generated_ts": generated_ts,
                    "schema_version": SCHEMA_VERSION,
                    "generalization_audit_version": GENERALIZATION_VERSION,
                    "generalization_run_id": run_id,
                    "provider": provider,
                    "pack_transition": transition,
                    "sessions_available": len(_sessions(rows)),
                    "valid_transition_count": len(valid),
                    "invalid_transition_count": invalid,
                    "no_signal_change_count": len(ns_changed),
                    "no_signal_from_true_to_false_count": true_to_false,
                    "no_signal_from_false_to_true_count": false_to_true,
                    "no_signal_stable_true_count": stable_true,
                    "no_signal_stable_false_count": stable_false,
                    "confidence_change_count": sum(1 for value in deltas if abs(value) >= 10),
                    "mean_confidence_delta": _fmt_mean(deltas),
                    "max_confidence_delta_abs": f"{max([abs(value) for value in deltas]):.2f}" if deltas else "",
                    "stability_status": status,
                    "interpretation": f"{provider} {transition} no-signal status: {status}.",
                    "notes": "No-signal behavior is behavior evidence only; not accuracy.",
                }
            )

    invalid_rows_out: List[Dict[str, Any]] = []
    invalid_by_key = defaultdict(list)
    for row in invalid_rows_all:
        invalid_by_key[(_norm(row.get("provider")), _norm(row.get("pack_level")))].append(row)
    valid_output_counts = Counter()
    for row in field_rows_all:
        provider = _norm(row.get("provider"))
        pack = _norm(row.get("pack_level"))
        if _upper(row.get("influence_status")) != "INVALID_OUTPUT":
            valid_output_counts[(provider, pack, _norm(row.get("session_id")))] = 1
    for provider in PROVIDERS:
        for pack in PACK_LEVELS:
            invalid_rows = invalid_by_key.get((provider, pack), [])
            sessions_attempted = len(all_sessions)
            invalid_count = len(invalid_rows)
            valid_count = len({key[2] for key in valid_output_counts if key[0] == provider and key[1] == pack})
            reason_counts = Counter(_norm(row.get("invalid_reason")) for row in invalid_rows)
            malformed = sum(count for reason, count in reason_counts.items() if "MALFORMED" in reason.upper() or "TRUNCATED" in reason.upper())
            schema_fail = sum(count for reason, count in reason_counts.items() if "MISSING_REQUIRED_FIELD" in reason.upper() or "SCHEMA" in reason.upper())
            provider_error = sum(count for reason, count in reason_counts.items() if "PROVIDER_ERROR" in reason.upper() or "503" in reason.upper() or "TIMEOUT" in reason.upper())
            raw_missing = sum(1 for row in invalid_rows if _upper(row.get("raw_response_archived")) == "FALSE")
            status = _invalid_pattern_status(invalid_count, max(sessions_attempted, invalid_count + valid_count), malformed, provider_error)
            invalid_rows_out.append(
                {
                    "generated_ts": generated_ts,
                    "schema_version": SCHEMA_VERSION,
                    "generalization_audit_version": GENERALIZATION_VERSION,
                    "generalization_run_id": run_id,
                    "provider": provider,
                    "pack_level": pack,
                    "sessions_attempted": sessions_attempted,
                    "valid_output_count": valid_count,
                    "invalid_output_count": invalid_count,
                    "invalid_output_rate": _fmt_rate(invalid_count, max(sessions_attempted, invalid_count + valid_count)),
                    "invalid_reason_counts": json.dumps(reason_counts, ensure_ascii=True),
                    "malformed_or_truncated_count": malformed,
                    "schema_validation_failure_count": schema_fail,
                    "provider_error_count": provider_error,
                    "raw_archive_missing_count": raw_missing,
                    "invalid_pattern_status": status,
                    "tier2_design_implication": "Monitor provider/pack output risk; do not silently rerun or impute.",
                    "notes": "Anthropic D/E truncation, Gemini transient provider error, and OpenAI missing status are reviewed as behavior infrastructure risks.",
                }
            )

    # Pattern rows.
    valid_transitions = [row for row in transitions if _is_valid_transition(row)]
    generalization_rows: List[Dict[str, Any]] = []
    pattern_index: Dict[str, Dict[str, Any]] = {}

    def add_pattern(row: Dict[str, Any]) -> None:
        generalization_rows.append(row)
        pattern_index[row["pattern_id"]] = row

    high_provider = max(PROVIDERS, key=lambda provider: provider_metrics_by_provider.get(provider, {}).get("direction", 0) + provider_metrics_by_provider.get(provider, {}).get("confidence", 0) + provider_metrics_by_provider.get(provider, {}).get("no_signal", 0) + provider_metrics_by_provider.get(provider, {}).get("causal", 0))
    high_provider_metrics = provider_metrics_by_provider[high_provider]
    add_pattern(
        _generalization_row(
            generated_ts,
            run_id,
            "PATTERN_PROVIDER_GEMINI_SENSITIVITY",
            "provider_sensitivity",
            "Gemini high pack sensitivity",
            "Gemini repeatedly changes direction, confidence, no-signal, and causal chains under pack exposure.",
            all_sessions,
            high_provider_metrics["valid_sessions"],
            providers_observed,
            {high_provider},
            transitions_observed,
            {_norm(row.get("transition")) for row in high_provider_metrics["valid"] if _reasoning_changed(row)},
            high_provider_metrics["valid_count"],
            high_provider_metrics["invalid_count"],
            f"{PILOT_TRANSITIONS_SHEET}|{TIER1_TRANSITIONS_SHEET}",
            "Highest provider sensitivity by transition counts; provider quality is not inferred.",
        )
    )

    openai_metrics = provider_metrics_by_provider.get("OpenAI", {})
    add_pattern(
        _generalization_row(
            generated_ts,
            run_id,
            "PATTERN_PROVIDER_OPENAI_CAUSAL_STABLE_CONFIDENCE",
            "provider_sensitivity",
            "OpenAI causal-chain change with stable confidence/no-signal",
            "OpenAI repeatedly rewrites causal chains while confidence and no-signal state remain comparatively stable.",
            all_sessions,
            openai_metrics.get("valid_sessions", set()),
            providers_observed,
            {"OpenAI"},
            transitions_observed,
            {_norm(row.get("transition")) for row in openai_metrics.get("valid", []) if _upper(row.get("causal_chain_transition")) == "CHANGED"},
            openai_metrics.get("valid_count", 0),
            openai_metrics.get("invalid_count", 0),
            f"{PILOT_TRANSITIONS_SHEET}|{TIER1_TRANSITIONS_SHEET}",
            "Behavioral consistency only; no correctness claim.",
        )
    )

    a_to_b = transition_metrics_by_name["A_to_B"]
    add_pattern(
        _generalization_row(
            generated_ts,
            run_id,
            "PATTERN_TRANSITION_A_TO_B_TARGET_STATE_ACTIVE",
            "pack_transition_value",
            "A_to_B target-state exposure is behaviorally active",
            "Adding USDJPY target-state fields repeatedly produces large behavior transitions.",
            all_sessions,
            a_to_b["valid_sessions"],
            providers_observed,
            a_to_b["valid_providers"],
            transitions_observed,
            {"A_to_B"},
            a_to_b["valid_count"],
            a_to_b["invalid_count"],
            f"{PILOT_TRANSITIONS_SHEET}|{TIER1_TRANSITIONS_SHEET}",
            "Strong early repeated signal; requires Tier 2 confirmation.",
        )
    )

    a_to_d = transition_metrics_by_name["A_to_D"]
    add_pattern(
        _generalization_row(
            generated_ts,
            run_id,
            "PATTERN_TRANSITION_A_TO_D_BROAD_CONTEXT_ACTIVE",
            "pack_transition_value",
            "A_to_D broad deterministic context is behaviorally active",
            "Moving from no-pack to target+calendar+rates/dollar context repeatedly changes reasoning.",
            all_sessions,
            a_to_d["valid_sessions"],
            providers_observed,
            a_to_d["valid_providers"],
            transitions_observed,
            {"A_to_D"},
            a_to_d["valid_count"],
            a_to_d["invalid_count"],
            f"{PILOT_TRANSITIONS_SHEET}|{TIER1_TRANSITIONS_SHEET}",
            "Broad deterministic pack transition is active; no accuracy claim.",
        )
    )

    d_to_e = transition_metrics_by_name["D_to_E"]
    add_pattern(
        _generalization_row(
            generated_ts,
            run_id,
            "PATTERN_TRANSITION_D_TO_E_POTENTIAL_REDUNDANCY",
            "pack_redundancy",
            "Pack E may be behaviorally redundant with Pack D",
            "D_to_E shows lower distinct directional/no-signal movement and may duplicate D under Feature Freeze.",
            all_sessions,
            d_to_e["valid_sessions"],
            providers_observed,
            d_to_e["valid_providers"],
            transitions_observed,
            {"D_to_E"},
            d_to_e["valid_count"],
            d_to_e["invalid_count"],
            f"{PILOT_TRANSITIONS_SHEET}|{TIER1_TRANSITIONS_SHEET}",
            "Potential redundancy only; do not remove any pack level.",
        )
    )

    family_counts = defaultdict(lambda: Counter())
    family_sessions = defaultdict(set)
    for row in field_rows_all:
        family = _norm(row.get("candidate_family")) or "UNKNOWN"
        status = _upper(row.get("influence_status"))
        family_counts[family][status] += 1
        if status in {"USED_AND_CHANGED_REASONING", "USED_NO_CLEAR_CHANGE"}:
            family_sessions[family].add(_norm(row.get("session_id")))
    for family in ["usdjpy_trend", "upcoming_larger_events", "dxy", "treasury_yields"]:
        counts = family_counts[family]
        valid_count = sum(count for status, count in counts.items() if status != "INVALID_OUTPUT")
        invalid_count = counts["INVALID_OUTPUT"]
        used = counts["USED_AND_CHANGED_REASONING"] + counts["USED_NO_CLEAR_CHANGE"]
        changed = counts["USED_AND_CHANGED_REASONING"]
        if family == "usdjpy_trend":
            pattern_id = "PATTERN_FIELD_FAMILY_USDJPY_TREND_REPEATED"
            name = "USDJPY trend fields repeatedly influence reasoning"
            description = "USDJPY trend is the strongest repeated field family by use and changed-reasoning evidence."
        elif family == "dxy":
            pattern_id = "PATTERN_FIELD_FAMILY_DXY_ACTIVE_LESS_THAN_USDJPY"
            name = "DXY fields are behaviorally active but secondary to USDJPY trend"
            description = "DXY fields are used and sometimes change reasoning, but less frequently than USDJPY trend."
        elif family == "treasury_yields":
            pattern_id = "PATTERN_FIELD_FAMILY_TREASURY_UNDERDETERMINED"
            name = "Treasury fields are available but often not mentioned"
            description = "Treasury fields need more evidence before being treated as a behavior-moving family."
        else:
            pattern_id = "PATTERN_FIELD_FAMILY_CALENDAR_MIXED"
            name = "Upcoming-event fields produce mixed behavior"
            description = "Calendar fields are used, discarded, and no-effect across providers, suggesting differentiating behavioral value."
        add_pattern(
            _generalization_row(
                generated_ts,
                run_id,
                pattern_id,
                "field_family_influence",
                name,
                description,
                all_sessions,
                family_sessions[family],
                providers_observed,
                {_norm(row.get("provider")) for row in field_rows_all if _norm(row.get("candidate_family")) == family and _upper(row.get("influence_status")) in {"USED_AND_CHANGED_REASONING", "USED_NO_CLEAR_CHANGE"}},
                transitions_observed,
                transitions_observed if used else set(),
                used + changed,
                invalid_count,
                f"{PILOT_FIELD_SHEET}|{TIER1_FIELD_SHEET}",
                f"used_count={used}; changed_reasoning_count={changed}; exact-field matching may undercount family influence.",
                forced_status="UNDERDETERMINED" if family == "treasury_yields" and used < 10 else "",
            )
        )

    no_signal_change_sessions = _sessions([row for row in valid_transitions if _upper(row.get("no_signal_transition")) == "CHANGED"])
    no_signal_providers = {_norm(row.get("provider")) for row in valid_transitions if _upper(row.get("no_signal_transition")) == "CHANGED"}
    add_pattern(
        _generalization_row(
            generated_ts,
            run_id,
            "PATTERN_NOSIGNAL_CONTEXT_SENSITIVITY",
            "no_signal_behavior",
            "No-signal behavior changes with richer context",
            "No-signal state changes repeat across sessions and providers, especially with broader pack transitions.",
            all_sessions,
            no_signal_change_sessions,
            providers_observed,
            no_signal_providers,
            transitions_observed,
            {_norm(row.get("transition")) for row in valid_transitions if _upper(row.get("no_signal_transition")) == "CHANGED"},
            sum(1 for row in valid_transitions if _upper(row.get("no_signal_transition")) == "CHANGED"),
            sum(1 for row in transitions if not _is_valid_transition(row)),
            f"{PILOT_TRANSITIONS_SHEET}|{TIER1_TRANSITIONS_SHEET}",
            "Behavior-only no-signal sensitivity; do not infer correctness.",
        )
    )

    invalid_anthropic_de = [
        row
        for row in invalid_rows_all
        if _norm(row.get("provider")) == "Anthropic" and _norm(row.get("pack_level")) in {"D", "E"}
    ]
    add_pattern(
        _generalization_row(
            generated_ts,
            run_id,
            "PATTERN_INVALID_ANTHROPIC_D_E_TRUNCATION",
            "invalid_output_behavior",
            "Anthropic D/E output truncation risk",
            "Anthropic D/E invalid outputs recur across pilot and Tier 1, limiting interpretation for those cells.",
            all_sessions,
            _sessions(invalid_anthropic_de),
            providers_observed,
            {"Anthropic"},
            transitions_observed,
            {"C_to_D", "D_to_E", "A_to_D", "A_to_E"},
            len(invalid_anthropic_de),
            len(invalid_anthropic_de),
            f"{PILOT_INVALID_SHEET}|{TIER1_INVALID_SHEET}",
            "Tier 2 design should monitor and isolate this risk without silent retries.",
            forced_status="INVALID_OUTPUT_LIMITED",
        )
    )

    hypotheses: List[Dict[str, Any]] = []
    hypotheses.append(
        _hypothesis_row(
            generated_ts,
            run_id,
            "HYP_USDJPY_TREND_REASONING",
            "USDJPY trend fields repeatedly change provider reasoning",
            "field_family_influence",
            "USDJPY trend fields are expected to remain the most behaviorally active Lane A family in Tier 2.",
            ["PATTERN_FIELD_FAMILY_USDJPY_TREND_REPEATED", "PATTERN_TRANSITION_A_TO_B_TARGET_STATE_ACTIVE"],
            "USDJPY trend family has repeated use and changed-reasoning evidence across pilot plus Tier 1.",
            family_sessions["usdjpy_trend"],
            providers_observed,
            ["A_to_B", "A_to_D", "A_to_E"],
            ["usdjpy_trend"],
            "CANDIDATE_PATTERN",
            "HIGH",
            "Track exact-field and family-level mentions for USDJPY trend across 5-10 more sessions.",
        )
    )
    hypotheses.append(
        _hypothesis_row(
            generated_ts,
            run_id,
            "HYP_A_TO_B_TARGET_STATE_VALUE",
            "A_to_B target-state exposure repeatedly creates large behavior transitions",
            "pack_transition_value",
            "Adding target-state context should repeatedly change provider reasoning, direction, confidence, or no-signal behavior.",
            ["PATTERN_TRANSITION_A_TO_B_TARGET_STATE_ACTIVE"],
            "A_to_B has repeated high transition complexity and behavior movement.",
            a_to_b["valid_sessions"],
            a_to_b["valid_providers"],
            ["A_to_B"],
            ["usdjpy_trend"],
            "CANDIDATE_PATTERN",
            "HIGH",
            "Preserve A_to_B as a primary Tier 2 transition of interest.",
        )
    )
    hypotheses.append(
        _hypothesis_row(
            generated_ts,
            run_id,
            "HYP_GEMINI_HIGH_SENSITIVITY",
            "Gemini is highly sensitive to added deterministic pack context",
            "provider_sensitivity",
            "Gemini should continue to show high direction/confidence/no-signal movement under pack exposure.",
            ["PATTERN_PROVIDER_GEMINI_SENSITIVITY", "PATTERN_NOSIGNAL_CONTEXT_SENSITIVITY"],
            "Gemini has the strongest aggregate transition movement in current behavior evidence.",
            high_provider_metrics["valid_sessions"],
            ["Gemini"],
            transitions_observed,
            ["usdjpy_trend", "upcoming_larger_events", "dxy", "treasury_yields"],
            "CANDIDATE_PATTERN",
            "HIGH",
            "Tier 2 should monitor Gemini sensitivity without treating it as accuracy or provider quality.",
        )
    )
    hypotheses.append(
        _hypothesis_row(
            generated_ts,
            run_id,
            "HYP_OPENAI_CAUSAL_STABLE",
            "OpenAI rewrites causal chains while remaining confidence/no-signal stable",
            "provider_sensitivity",
            "OpenAI may incorporate pack context primarily through causal-chain restatement rather than no-signal movement.",
            ["PATTERN_PROVIDER_OPENAI_CAUSAL_STABLE_CONFIDENCE"],
            "OpenAI repeatedly changes causal chains but shows relatively stable confidence/no-signal behavior.",
            openai_metrics.get("valid_sessions", set()),
            ["OpenAI"],
            transitions_observed,
            ["all Lane A families"],
            "REPEATED",
            "MEDIUM",
            "Tier 2 should compare causal-chain movement separately from direction and confidence movement.",
        )
    )
    hypotheses.append(
        _hypothesis_row(
            generated_ts,
            run_id,
            "HYP_PACK_E_REDUNDANCY",
            "Pack E may be behaviorally redundant with Pack D",
            "pack_redundancy",
            "Under Feature Freeze, Pack E may add little distinct behavior beyond Pack D.",
            ["PATTERN_TRANSITION_D_TO_E_POTENTIAL_REDUNDANCY"],
            "D_to_E shows lower distinct movement than A_to_B or A_to_D, but invalid outputs limit certainty.",
            d_to_e["valid_sessions"],
            d_to_e["valid_providers"],
            ["D_to_E"],
            ["full Lane A deterministic core"],
            "REPEATED",
            "MEDIUM",
            "Tier 2 should keep Pack E but explicitly test D/E redundancy; do not remove any level yet.",
        )
    )
    hypotheses.append(
        _hypothesis_row(
            generated_ts,
            run_id,
            "HYP_ANTHROPIC_DE_INVALID_RISK",
            "Anthropic D/E outputs are invalid-output-limited",
            "invalid_output_behavior",
            "Anthropic D/E cells require monitoring because truncation recurs and can limit transition comparisons.",
            ["PATTERN_INVALID_ANTHROPIC_D_E_TRUNCATION"],
            "Anthropic D/E malformed/truncated outputs recur across current evidence.",
            _sessions(invalid_anthropic_de),
            ["Anthropic"],
            ["C_to_D", "D_to_E", "A_to_D", "A_to_E"],
            ["Pack D", "Pack E"],
            "INVALID_OUTPUT_LIMITED",
            "HOLD",
            "Tier 2 design should include explicit invalid-output monitoring; no silent reruns or repair.",
        )
    )
    hypotheses.append(
        _hypothesis_row(
            generated_ts,
            run_id,
            "HYP_TREASURY_UNDERDETERMINED",
            "Treasury fields are available but often not mentioned",
            "field_family_influence",
            "Treasury fields may be behaviorally weaker or under-attributed; more sessions are needed before treating the family as behavior-moving.",
            ["PATTERN_FIELD_FAMILY_TREASURY_UNDERDETERMINED"],
            "Treasury fields appear less often in explicit field influence than USDJPY trend and DXY.",
            family_sessions["treasury_yields"],
            providers_observed,
            ["C_to_D", "A_to_D", "A_to_E"],
            ["treasury_yields"],
            "UNDERDETERMINED",
            "MEDIUM",
            "Tier 2 should preserve Treasury fields but evaluate family-level mentions conservatively.",
        )
    )

    candidate_patterns = sum(1 for row in generalization_rows if row["generalization_status"] == "CANDIDATE_PATTERN")
    underdetermined_patterns = sum(1 for row in generalization_rows if row["generalization_status"] == "UNDERDETERMINED")
    invalid_limited = sum(1 for row in generalization_rows if row["generalization_status"] == "INVALID_OUTPUT_LIMITED")
    high_hypotheses = sum(1 for row in hypotheses if row["tier2_test_priority"] == "HIGH")
    medium_hypotheses = sum(1 for row in hypotheses if row["tier2_test_priority"] == "MEDIUM")
    hold_hypotheses = sum(1 for row in hypotheses if row["tier2_test_priority"] == "HOLD")

    strongest_transition = max(transition_rows_out, key=lambda row: _float(row.get("mean_transition_complexity")) or 0)["pack_transition"] if transition_rows_out else ""
    family_used_counts = {
        family: family_counts[family]["USED_AND_CHANGED_REASONING"] + family_counts[family]["USED_NO_CLEAR_CHANGE"]
        for family in family_counts
    }
    strongest_family = max(family_used_counts, key=family_used_counts.get) if family_used_counts else ""
    strongest_no_signal = max(no_signal_rows_out, key=lambda row: int(row.get("no_signal_change_count") or 0)) if no_signal_rows_out else {}
    strongest_invalid = max(invalid_rows_out, key=lambda row: int(row.get("invalid_output_count") or 0)) if invalid_rows_out else {}

    summary = {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "generalization_audit_version": GENERALIZATION_VERSION,
        "generalization_run_id": run_id,
        "build_status": "PASS_WITH_WARNINGS" if invalid_limited else "PASS",
        "final_interpretation": "BEHAVIOR_PATTERN_GENERALIZATION_AUDIT_READY_WITH_WARNINGS" if invalid_limited else "BEHAVIOR_PATTERN_GENERALIZATION_AUDIT_READY",
        "pilot_sessions_included": len(pilot_sessions),
        "tier1_sessions_included": len(tier1_sessions),
        "total_sessions_included": len(all_sessions),
        "providers_included": "|".join(sorted(providers_observed)),
        "pack_levels_included": "|".join(PACK_LEVELS),
        "generalization_patterns_identified": len(generalization_rows),
        "candidate_patterns_identified": candidate_patterns,
        "underdetermined_patterns_identified": underdetermined_patterns,
        "invalid_output_limited_patterns_identified": invalid_limited,
        "hypotheses_defined": len(hypotheses),
        "high_priority_hypotheses": high_hypotheses,
        "medium_priority_hypotheses": medium_hypotheses,
        "hold_hypotheses": hold_hypotheses,
        "strongest_provider_pattern": "Gemini high pack sensitivity",
        "strongest_transition_pattern": strongest_transition,
        "strongest_field_family_pattern": strongest_family,
        "strongest_no_signal_pattern": f"{strongest_no_signal.get('provider', '')}:{strongest_no_signal.get('pack_transition', '')}",
        "strongest_invalid_output_pattern": f"{strongest_invalid.get('provider', '')}:{strongest_invalid.get('pack_level', '')}",
        "accuracy_evaluation_count": 0,
        "provider_call_count": 0,
        "forecast_generation_count": 0,
        "provider_rerun_count": 0,
        "production_behavior_change_count": 0,
        "ready_for_tier2_design": "TRUE",
        "ready_for_tier2_execution": "FALSE",
        "ready_for_accuracy_evaluation": "FALSE",
        "ready_for_production": "FALSE",
        "recommended_next_step": "PROCEED_TO_PHASE9A4Z_TIER2_EXPANSION_DESIGN",
        "notes": _truncate_text(json.dumps({"missing_optional_or_input_sheets": missing}, ensure_ascii=True), 500),
    }

    for sheet, headers, rows in [
        (OUTPUT_GENERALIZATION_SHEET, GENERALIZATION_HEADERS, generalization_rows),
        (OUTPUT_PROVIDER_SHEET, PROVIDER_HEADERS, provider_rows),
        (OUTPUT_TRANSITION_SHEET, TRANSITION_HEADERS, transition_rows_out),
        (OUTPUT_FIELD_SHEET, FIELD_HEADERS, field_rows_out),
        (OUTPUT_NOSIGNAL_SHEET, NOSIGNAL_HEADERS, no_signal_rows_out),
        (OUTPUT_INVALID_SHEET, INVALID_HEADERS, invalid_rows_out),
        (OUTPUT_HYPOTHESES_SHEET, HYPOTHESIS_HEADERS, hypotheses),
        (OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS, [summary]),
    ]:
        sheet_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, sheet, headers)
        _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet, sheet_headers, rows)
    registry = _upsert_registry_rows(service)
    return {
        "build_status": summary["build_status"],
        "final_interpretation": summary["final_interpretation"],
        "generalization_run_id": run_id,
        "pilot_sessions_included": len(pilot_sessions),
        "tier1_sessions_included": len(tier1_sessions),
        "total_sessions_included": len(all_sessions),
        "generalization_patterns_identified": len(generalization_rows),
        "candidate_patterns_identified": candidate_patterns,
        "underdetermined_patterns_identified": underdetermined_patterns,
        "invalid_output_limited_patterns_identified": invalid_limited,
        "hypotheses_defined": len(hypotheses),
        "high_priority_hypotheses": high_hypotheses,
        "medium_priority_hypotheses": medium_hypotheses,
        "hold_hypotheses": hold_hypotheses,
        "strongest_provider_pattern": summary["strongest_provider_pattern"],
        "strongest_transition_pattern": strongest_transition,
        "strongest_field_family_pattern": strongest_family,
        "strongest_no_signal_pattern": summary["strongest_no_signal_pattern"],
        "strongest_invalid_output_pattern": summary["strongest_invalid_output_pattern"],
        "accuracy_evaluation_count": 0,
        "provider_call_count": 0,
        "forecast_generation_count": 0,
        "provider_rerun_count": 0,
        "production_behavior_change_count": 0,
        "ready_for_tier2_design": True,
        "ready_for_tier2_execution": False,
        "ready_for_accuracy_evaluation": False,
        "ready_for_production": False,
        "recommended_next_step": summary["recommended_next_step"],
        "sheets_written": {
            OUTPUT_GENERALIZATION_SHEET: len(generalization_rows),
            OUTPUT_PROVIDER_SHEET: len(provider_rows),
            OUTPUT_TRANSITION_SHEET: len(transition_rows_out),
            OUTPUT_FIELD_SHEET: len(field_rows_out),
            OUTPUT_NOSIGNAL_SHEET: len(no_signal_rows_out),
            OUTPUT_INVALID_SHEET: len(invalid_rows_out),
            OUTPUT_HYPOTHESES_SHEET: len(hypotheses),
            OUTPUT_SUMMARY_SHEET: 1,
        },
        "registry": registry,
    }


def main() -> None:
    result = build_pack_behavior_generalization_audit_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
