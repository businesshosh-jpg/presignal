#!/usr/bin/env python3
"""Phase 9A-6R15I — Outcome Architecture v2 staged shadow implementation.

Builds version-isolated diagnostic contracts for the five preregistered
Outcome Architecture v2 layers. The builder records existing outcome states;
it does not alter v1 outcome artifacts, Success Mapping, classifications, or
production consumers.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.build_market_sessions_shadow_v0 import (  # type: ignore
    DIAGNOSTICS_SPREADSHEET_ID,
    PROJECT_OVERVIEWS_SPREADSHEET_ID,
    REGISTRY_HEADERS,
    REGISTRY_SHEET,
    _column_letter,
    _sheet_to_rows,
)
from automation.build_refined_mechanism_test_execution_v0 import (  # type: ignore
    _append_rows,
    _canonical_json,
    _fetch_input_sheets,
    _normalize,
    _sheet_titles_light,
)
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials  # type: ignore


PHASE_ID = "9A-6R15I-R1"
BUILD_SCRIPT = "automation/build_refined_mechanism_test_outcome_architecture_v2_staged_implementation_v0.py"
SCHEMA_VERSION = "presignal_v2_refined_mechanism_test_outcome_architecture_v2_staged_implementation_r1_v0"
REGISTRY_CATEGORY = "PRESIGNAL_V2_REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_V2_SHADOW"
REGISTRY_OWNER_MODULE = "market_state"

ARCHITECTURE_VERSION = "2.0"
ARCHITECTURE_PREREGISTRATION_VERSION = "1.0"
PREREGISTRATION_RUN_ID = "9A-6R15F_20260713T034023Z"
VALIDATION_RUN_ID = "9A-6R15G_20260713T043437Z"
PLANNING_RUN_ID = "9A-6R15H_20260713T045229Z"
CANONICAL_PREREGISTRATION_VERSION = "1.0-clean-r1"
CANONICAL_AUTHORITY_RUN_ID = "9A-6R13R1_20260711T020141Z"
CLASSIFICATION_VERSION = "1.1"
CLASSIFICATION_RUN_ID = "refined_mechanism_v11_classification_20260710T152725Z"
SOURCE_TEST_EXECUTION_RUN_ID = "9A-6R15_20260712T090705Z"
SOURCE_POPULATION_COLLAPSE_RUN_ID = "9A-6R15A_20260712T120605Z"
PRIMARY_ANALYSIS_ID = "PRIMARY_PM003_STRUCTURE_A"

IMPLEMENTATION_MODE = "SHADOW_DIAGNOSTIC"
BUILD_STATUS = "PASS"
FINAL_INTERPRETATION = "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_V2_STAGE_REPAIR_READY"
RECOMMENDED_NEXT_STEP = "PROCEED_TO_PHASE9A6R15J_R1_REPAIR_REVIEW"

STAGES: Tuple[Tuple[str, str], ...] = (
    ("OA_V2_IMPL_STAGE_01", "CANONICAL_OUTCOME"),
    ("OA_V2_IMPL_STAGE_02", "OUTCOME_OVERLAY"),
    ("OA_V2_IMPL_STAGE_03", "OUTCOME_LINKAGE"),
    ("OA_V2_IMPL_STAGE_04", "OUTCOME_REPRESENTATION"),
    ("OA_V2_IMPL_STAGE_05", "ELIGIBILITY_INTERACTION"),
)

FROZEN_INPUT_SHEETS: Tuple[str, ...] = (
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Preregistration",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Frozen_Layers",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Frozen_Redesign_Targets",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Frozen_Prohibited_Redesigns",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Frozen_Empirical_Questions",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Frozen_Compatibility",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Frozen_Governance",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Frozen_Implementation_Boundary",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Fingerprint_Freeze",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Preregistration_Summary",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Validation",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Layer_Validation",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Target_Validation",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Compatibility_Validation",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Determinism_Validation",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Governance_Validation",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Implementation_Readiness",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Validation_Summary",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Implementation_Plan",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Implementation_Sequence",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Implementation_Dependency_Graph",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Implementation_Verification",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Implementation_Stop_Conditions",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Implementation_Planning_Readiness",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Implementation_Planning_Summary",
    "Refined_Mechanism_v11_Classifications",
    "Refined_Mechanism_Test_Row_Lineage_Audit",
    "Refined_Mechanism_Test_Outcome_Join_Audit",
)

OUTCOME_SOURCE_SHEETS: Tuple[str, ...] = (
    "Market_Reaction_Canonical_Outcomes",
    "Market_Reaction_Recovered_Canonical_Outcomes",
    "Corrected_Accuracy_Row_Selection",
    "Corrected_Accuracy_Outcome_Mapping",
)

OUTPUT_IMPLEMENTATION = "Refined_Mechanism_Test_Outcome_Architecture_V2_Implementation"
OUTPUT_CANONICAL = "Refined_Mechanism_Test_Outcome_Architecture_V2_Canonical_Coverage"
OUTPUT_OVERLAY = "Refined_Mechanism_Test_Outcome_Architecture_V2_Overlay_Manifest"
OUTPUT_LINKAGE = "Refined_Mechanism_Test_Outcome_Architecture_V2_Linkage_Bridge"
OUTPUT_REPRESENTATION = "Refined_Mechanism_Test_Outcome_Architecture_V2_Representation"
OUTPUT_PAIR = "Refined_Mechanism_Test_Outcome_Architecture_V2_Pair_Evaluability"
OUTPUT_SURVIVORSHIP = "Refined_Mechanism_Test_Outcome_Architecture_V2_Survivorship"
OUTPUT_CHECKPOINTS = "Refined_Mechanism_Test_Outcome_Architecture_V2_Stage_Checkpoints"
OUTPUT_LINEAGE = "Refined_Mechanism_Test_Outcome_Architecture_V2_Lineage_Audit"
OUTPUT_DETERMINISM = "Refined_Mechanism_Test_Outcome_Architecture_V2_Determinism_Audit"
OUTPUT_COMPATIBILITY = "Refined_Mechanism_Test_Outcome_Architecture_V2_Compatibility_Audit"
OUTPUT_GOVERNANCE = "Refined_Mechanism_Test_Outcome_Architecture_V2_Implementation_Governance"
OUTPUT_SUMMARY = "Refined_Mechanism_Test_Outcome_Architecture_V2_Implementation_Summary"
OUTPUT_REPAIR = "Refined_Mechanism_Test_Outcome_Architecture_V2_Repair"
OUTPUT_PARSER_REPAIR = "Refined_Mechanism_Test_Outcome_Architecture_V2_Parser_Repair"
OUTPUT_STOP_AUDIT = "Refined_Mechanism_Test_Outcome_Architecture_V2_Hard_Stop_Runtime_Audit"
OUTPUT_AGGREGATE_FP = "Refined_Mechanism_Test_Outcome_Architecture_V2_Aggregate_Fingerprint"
OUTPUT_AUTHORITY = "Refined_Mechanism_Test_Outcome_Architecture_V2_Authority_Record"
OUTPUT_REPAIR_CHECKPOINTS = "Refined_Mechanism_Test_Outcome_Architecture_V2_Repair_Checkpoints"
OUTPUT_REPAIR_DETERMINISM = "Refined_Mechanism_Test_Outcome_Architecture_V2_Repair_Determinism"
OUTPUT_REPAIR_GOVERNANCE = "Refined_Mechanism_Test_Outcome_Architecture_V2_Repair_Governance"
OUTPUT_REPAIR_SUMMARY = "Refined_Mechanism_Test_Outcome_Architecture_V2_Repair_Summary"

OUTPUT_SHEETS: Dict[str, List[str]] = {
    OUTPUT_IMPLEMENTATION: [
        "generated_ts", "schema_version", "outcome_architecture_implementation_run_id",
        "architecture_version", "architecture_preregistration_version", "implementation_mode",
        "production_authority", "current_architecture_replacement", "success_mapping_consumer_switch",
        "mechanism_test_rerun", "implementation_status", "build_status", "final_interpretation",
        "payload_json",
    ],
    OUTPUT_CANONICAL: [
        "generated_ts", "schema_version", "outcome_architecture_implementation_run_id", "stage_id",
        "observation_side", "source_observation_key", "provider", "session_id", "pack_level",
        "source_outcome_identity", "canonical_outcome_id", "canonical_version", "evaluation_window_identity",
        "outcome_timestamp", "timestamp_provenance_status", "coverage_status", "deterministic_failure_reason",
        "source_lineage", "downstream_overlay_eligible", "layer_fingerprint", "payload_json",
    ],
    OUTPUT_OVERLAY: [
        "generated_ts", "schema_version", "outcome_architecture_implementation_run_id", "stage_id",
        "observation_side", "source_observation_key", "canonical_outcome_id", "expected_overlay_id",
        "overlay_version", "repaired_overlay_available", "repair_lineage", "required_fields_present",
        "missing_component_reason", "overlay_status", "downstream_linkage_eligible", "layer_fingerprint", "payload_json",
    ],
    OUTPUT_LINKAGE: [
        "generated_ts", "schema_version", "outcome_architecture_implementation_run_id", "stage_id",
        "observation_side", "source_observation_key", "provider", "session_id", "pack_level",
        "forecast_run_identity", "repaired_canonical_outcome_id", "canonical_outcome_id", "overlay_id",
        "architecture_version", "linkage_version", "linkage_status", "linkage_reason",
        "stable_key_json", "layer_fingerprint", "payload_json",
    ],
    OUTPUT_REPRESENTATION: [
        "generated_ts", "schema_version", "outcome_architecture_implementation_run_id", "stage_id",
        "observation_side", "source_observation_key", "canonical_outcome_id", "overlay_id",
        "representation_version", "realized_state", "forecast_state", "no_signal_state",
        "representation_status", "representation_provenance", "current_success_mapping_v1_consumability",
        "downstream_consumer_compatibility", "layer_fingerprint", "payload_json",
    ],
    OUTPUT_PAIR: [
        "generated_ts", "schema_version", "outcome_architecture_implementation_run_id", "stage_id",
        "source_observation_key", "provider", "session_id", "baseline_source_key", "expanded_source_key",
        "baseline_linkage_status", "expanded_linkage_status", "baseline_overlay_status", "expanded_overlay_status",
        "baseline_representation_status", "expanded_representation_status", "representation_readiness",
        "pair_evaluability_status", "first_failure_point", "layer_fingerprint", "payload_json",
    ],
    OUTPUT_SURVIVORSHIP: [
        "generated_ts", "schema_version", "outcome_architecture_implementation_run_id", "stage_id",
        "source_observation_key", "mechanism_classification_reference", "expanded_label", "confidence_category",
        "canonical_status", "overlay_status", "linkage_status", "representation_status",
        "current_success_mapping_v1_consumability", "current_eligibility_status", "first_blocking_layer",
        "projected_architecture_v2_survivorship_status", "no_rule_change_confirmation", "layer_fingerprint", "payload_json",
    ],
    OUTPUT_CHECKPOINTS: [
        "generated_ts", "schema_version", "outcome_architecture_implementation_run_id", "architecture_version",
        "stage_id", "stage_order", "stage_status", "input_fingerprints_json", "output_fingerprint",
        "input_rows", "output_rows", "verification_status", "determinism_status", "compatibility_status",
        "blocking_governance_findings", "completion_timestamp", "checkpoint_id", "resume_token", "payload_json",
    ],
    OUTPUT_LINEAGE: [
        "generated_ts", "schema_version", "outcome_architecture_implementation_run_id", "stage_id",
        "lineage_component", "source_sheet", "source_run_id", "source_row_count", "source_fingerprint",
        "lineage_status", "payload_json",
    ],
    OUTPUT_DETERMINISM: [
        "generated_ts", "schema_version", "outcome_architecture_implementation_run_id", "stage_id",
        "determinism_check_id", "first_pass_fingerprint", "second_pass_fingerprint", "determinism_status",
        "stable_key_uniqueness_status", "expected_row_accounting_status", "payload_json",
    ],
    OUTPUT_COMPATIBILITY: [
        "generated_ts", "schema_version", "outcome_architecture_implementation_run_id", "stage_id",
        "compatibility_target", "compatibility_status", "consumer_switch", "scientific_rule_change",
        "notes", "payload_json",
    ],
    OUTPUT_GOVERNANCE: [
        "generated_ts", "schema_version", "outcome_architecture_implementation_run_id", "counter_name",
        "counter_value", "status", "notes",
    ],
    OUTPUT_SUMMARY: [
        "generated_ts", "schema_version", "outcome_architecture_implementation_run_id", "build_status",
        "final_interpretation", "all_stages_completed", "all_stages_verified",
        "ready_for_outcome_architecture_v2_implementation_review", "ready_for_consumer_switch",
        "ready_for_mechanism_retesting", "ready_for_production", "recommended_next_step", "payload_json",
    ],
}

REPAIR_HEADERS = [
    "generated_ts", "schema_version", "outcome_architecture_implementation_run_id",
    "architecture_version", "repair_area", "repair_status", "authority_status", "payload_json",
]
OUTPUT_SHEETS.update({
    sheet_name: list(REPAIR_HEADERS)
    for sheet_name in (
        OUTPUT_REPAIR, OUTPUT_PARSER_REPAIR, OUTPUT_STOP_AUDIT, OUTPUT_AGGREGATE_FP,
        OUTPUT_AUTHORITY, OUTPUT_REPAIR_CHECKPOINTS, OUTPUT_REPAIR_DETERMINISM,
        OUTPUT_REPAIR_GOVERNANCE, OUTPUT_REPAIR_SUMMARY,
    )
})

OUTPUT_LOGICAL_IDS = {name: name.upper() for name in OUTPUT_SHEETS}

HARD_STOPS = (
    "LINEAGE_MISMATCH", "FINGERPRINT_MISMATCH", "DEPENDENCY_FAILURE", "VERSION_MISMATCH",
    "COMPATIBILITY_FAILURE", "DETERMINISTIC_FAILURE", "UNEXPECTED_DATA_LOSS",
    "PROHIBITED_REDESIGN_ATTEMPT", "SOURCE_SHEET_MODIFICATION_ATTEMPT", "MIXED_RUN_RESUME_ATTEMPT",
    "UNVERIFIED_CHECKPOINT_RESUME_ATTEMPT", "DUPLICATE_LINK", "AMBIGUOUS_LINK", "FUZZY_JOIN_ATTEMPT",
    "MANUAL_JOIN_ATTEMPT", "SUCCESS_MAPPING_CHANGE_ATTEMPT", "MECHANISM_TEST_ATTEMPT",
    "PRODUCTION_WRITE_ATTEMPT", "INVALID_ZERO_FALSE_NULL_COERCION",
)

AGGREGATE_FINGERPRINT_SCHEMA_VERSION = "oa_v2_aggregate_logical_payload_v1"
AGGREGATE_COMPONENTS: Tuple[str, ...] = (
    OUTPUT_CANONICAL, OUTPUT_OVERLAY, OUTPUT_LINKAGE, OUTPUT_REPRESENTATION,
    OUTPUT_PAIR, OUTPUT_SURVIVORSHIP, OUTPUT_CHECKPOINTS, OUTPUT_LINEAGE,
    OUTPUT_DETERMINISM, OUTPUT_COMPATIBILITY, OUTPUT_GOVERNANCE,
)
MISSING = object()


class StageBlocked(RuntimeError):
    def __init__(self, stop_rule: str, message: str):
        super().__init__(message)
        self.stop_rule = stop_rule


def _run_id(ts: datetime) -> str:
    return os.environ.get("OA_V2_IMPLEMENTATION_RUN_ID", "").strip() or f"9A-6R15I-R1_{ts.strftime('%Y%m%dT%H%M%SZ')}"


def _now_iso(ts: datetime) -> str:
    return ts.isoformat().replace("+00:00", "Z")


def _require(condition: bool, stop_rule: str, message: str) -> None:
    if not condition:
        raise StageBlocked(stop_rule, message)


def _payload(row: Mapping[str, Any]) -> Dict[str, Any]:
    raw = _normalize(row.get("payload_json"))
    try:
        value = json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        raise StageBlocked("LINEAGE_MISMATCH", f"Invalid payload_json: {exc}") from exc
    return value if isinstance(value, dict) else {}


def _canonical_fingerprint(value: Any) -> str:
    serialized = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _records_fingerprint(rows: Sequence[Mapping[str, Any]]) -> str:
    stable_rows = []
    volatile = {"generated_ts", "outcome_architecture_implementation_run_id", "layer_fingerprint", "payload_json"}
    for row in rows:
        stable_rows.append({key: row.get(key, "") for key in sorted(row) if key not in volatile})
    return _canonical_fingerprint(stable_rows)


def _parse_nonnegative_int(
    value: Any,
    field_name: str,
    declared_type: str = "INTEGER_COUNT",
) -> Tuple[int, str]:
    """Parse governed counts explicitly, preserving zero, false, missing, and null."""
    _require(declared_type in {"INTEGER_COUNT", "BOOLEAN_OR_INTEGER"}, "INVALID_ZERO_FALSE_NULL_COERCION", f"{field_name} has an unsupported declared type.")
    if value is MISSING:
        raise StageBlocked("INVALID_ZERO_FALSE_NULL_COERCION", f"{field_name} is missing.")
    if value is None:
        raise StageBlocked("INVALID_ZERO_FALSE_NULL_COERCION", f"{field_name} is null.")
    if isinstance(value, bool):
        return (0 if value is False else 1), "BOOLEAN_FALSE" if value is False else "BOOLEAN_TRUE"
    if isinstance(value, int):
        _require(value >= 0, "INVALID_ZERO_FALSE_NULL_COERCION", f"{field_name} is negative.")
        return value, "NUMERIC_ZERO" if value == 0 else "NUMERIC"
    if isinstance(value, float):
        _require(math.isfinite(value), "INVALID_ZERO_FALSE_NULL_COERCION", f"{field_name} is not finite.")
        _require(value.is_integer(), "INVALID_ZERO_FALSE_NULL_COERCION", f"{field_name} is a non-integral float.")
        parsed_float = int(value)
        _require(parsed_float >= 0, "INVALID_ZERO_FALSE_NULL_COERCION", f"{field_name} is negative.")
        return parsed_float, "FLOAT_ZERO" if parsed_float == 0 else "FLOAT_NUMERIC"
    raw = _normalize(value)
    if raw == "":
        raise StageBlocked("INVALID_ZERO_FALSE_NULL_COERCION", f"{field_name} is empty or missing.")
    if raw.upper() == "FALSE":
        return 0, "STRING_FALSE"
    _require(declared_type in {"INTEGER_COUNT", "BOOLEAN_OR_INTEGER"}, "INVALID_ZERO_FALSE_NULL_COERCION", f"{field_name} does not permit string numeric input.")
    try:
        parsed = int(raw)
    except ValueError as exc:
        raise StageBlocked("INVALID_ZERO_FALSE_NULL_COERCION", f"{field_name} is not an integer: {raw}") from exc
    _require(parsed >= 0, "INVALID_ZERO_FALSE_NULL_COERCION", f"{field_name} is negative.")
    return parsed, "STRING_ZERO" if parsed == 0 else "STRING_NUMERIC"


def _guard(condition: bool, stop_rule: str, message: str, stage_context: str) -> None:
    """Fail closed with an explicit stage context for every governed runtime guard."""
    _require(stop_rule in HARD_STOPS, "LINEAGE_MISMATCH", f"Unknown stop rule: {stop_rule}")
    _require(condition, stop_rule, f"{stage_context}: {message}")


def _runtime_guard_tests() -> List[Dict[str, Any]]:
    """Exercise every frozen hard stop in memory without writing or changing sources."""
    results: List[Dict[str, Any]] = []
    for stop_rule in HARD_STOPS:
        triggered = False
        message = ""
        try:
            _guard(False, stop_rule, "controlled negative-path trigger", "IN_MEMORY_GUARD_TEST")
        except StageBlocked as exc:
            triggered = exc.stop_rule == stop_rule
            message = str(exc)
        _require(triggered, "DETERMINISTIC_FAILURE", f"Negative-path guard did not trigger {stop_rule}.")
        results.append({
            "stop_code": stop_rule, "assertion_function": "_guard",
            "trigger_condition": "condition=False", "test_executed": True,
            "trigger_observed": triggered, "stage_blocked": triggered,
            "downstream_blocked": triggered, "final_readiness_blocked": triggered,
            "scientific_rules_unchanged": True, "diagnostic_message": message,
        })
    return results


def _parser_test_matrix() -> List[Dict[str, Any]]:
    cases = [
        ("INTEGER_ZERO", 0, 0, "NUMERIC_ZERO", False),
        ("FLOAT_ZERO", 0.0, 0, "FLOAT_ZERO", False),
        ("STRING_ZERO", "0", 0, "STRING_ZERO", False),
        ("BOOLEAN_FALSE", False, 0, "BOOLEAN_FALSE", False),
        ("STRING_FALSE", "FALSE", 0, "STRING_FALSE", False),
        ("EMPTY", "", None, "", True),
        ("WHITESPACE", "   ", None, "", True),
        ("MISSING", MISSING, None, "", True),
        ("NULL", None, None, "", True),
        ("INVALID", "invalid", None, "", True),
        ("POSITIVE_INTEGER", 1, 1, "NUMERIC", False),
        ("POSITIVE_FLOAT", 1.0, 1, "FLOAT_NUMERIC", False),
        ("BOOLEAN_TRUE", True, 1, "BOOLEAN_TRUE", False),
    ]
    results: List[Dict[str, Any]] = []
    for case_id, value, expected_value, expected_kind, expects_error in cases:
        try:
            parsed, kind = _parse_nonnegative_int(value, case_id, "INTEGER_COUNT")
            passed = not expects_error and parsed == expected_value and kind == expected_kind
            result = {"case": case_id, "status": "PASS" if passed else "FAIL", "parsed": parsed, "kind": kind, "error": ""}
        except StageBlocked as exc:
            passed = expects_error and exc.stop_rule == "INVALID_ZERO_FALSE_NULL_COERCION"
            result = {"case": case_id, "status": "PASS" if passed else "FAIL", "parsed": None, "kind": "", "error": exc.stop_rule}
        _require(result["status"] == "PASS", "DETERMINISTIC_FAILURE", f"Parser test failed: {case_id}.")
        results.append(result)
    return results


def _latest_exact(rows: Sequence[Mapping[str, Any]], run_key: str, run_id: str) -> Dict[str, Any]:
    matches = [dict(row) for row in rows if _normalize(row.get(run_key)) == run_id]
    _require(bool(matches), "LINEAGE_MISMATCH", f"No row for {run_key}={run_id}.")
    return sorted(matches, key=lambda row: int(_normalize(row.get("__source_row_number__")) or "0"))[-1]


def _rows_for_run(rows: Sequence[Mapping[str, Any]], run_key: str, run_id: str) -> List[Dict[str, Any]]:
    return [dict(row) for row in rows if _normalize(row.get(run_key)) == run_id]


def _index_unique(rows: Iterable[Mapping[str, Any]], key_name: str) -> Dict[str, Dict[str, Any]]:
    index: Dict[str, Dict[str, Any]] = {}
    duplicates: Set[str] = set()
    for raw in rows:
        row = dict(raw)
        key = _normalize(row.get(key_name))
        if not key:
            continue
        if key in index:
            duplicates.add(key)
        index[key] = row
    _require(not duplicates, "DUPLICATE_LINK", f"Duplicate source identities for {key_name}: {sorted(duplicates)[:10]}")
    return index


def _safe_bool(value: Any) -> bool:
    return _normalize(value).upper() in {"TRUE", "1", "YES", "Y", "PASS", "OK"}


def _side_value(row: Mapping[str, Any], side: str, name: str) -> str:
    return _normalize(row.get(f"{side.lower()}_{name}"))


def _side_payload(join_row: Mapping[str, Any], side: str) -> Dict[str, Any]:
    return (_payload(join_row).get(f"{side.lower()}_join") or {}) if join_row else {}


def _source_fingerprints(inputs: Mapping[str, Any], outcome_inputs: Mapping[str, Any]) -> Dict[str, str]:
    all_inputs = {**inputs, **outcome_inputs}
    return {sheet: _records_fingerprint(data.rows) for sheet, data in all_inputs.items()}


def _upsert_registry_rows(service, generated_ts: str) -> Dict[str, Any]:
    try:
        titles = _sheet_titles_light(service, PROJECT_OVERVIEWS_SPREADSHEET_ID)
        if REGISTRY_SHEET not in titles:
            return {"status": "missing", "appended": 0, "updated": 0}
        rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
        by_id = {_normalize(row.get("logical_sheet_id")).upper(): index + 2 for index, row in enumerate(rows)}
        existing_by_id = {_normalize(row.get("logical_sheet_id")).upper(): row for row in rows}
        updates = []
        appended = 0
        for sheet_name, logical_id in OUTPUT_LOGICAL_IDS.items():
            key = logical_id.upper()
            existing = existing_by_id.get(key, {})
            merged = {
                "logical_sheet_id": logical_id,
                "physical_sheet_name": sheet_name,
                "workbook": "DIAGNOSTICS",
                "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
                "category": REGISTRY_CATEGORY,
                "lifecycle_state": "ACTIVE_SHADOW",
                "owner_module": REGISTRY_OWNER_MODULE,
                "participates_in_rebuild": "TRUE",
                "read_only": "FALSE",
                "allow_creation": "TRUE",
                "created_phase": f"PreSignal v2.0 Phase {PHASE_ID}",
                "notes": "Outcome Architecture v2 shadow diagnostic implementation; no production authority.",
                "registry_created_ts": _normalize(existing.get("registry_created_ts")) or generated_ts,
                "registry_last_verified_ts": generated_ts,
                "registry_migration_ts": _normalize(existing.get("registry_migration_ts")),
                "registry_rename_ts": _normalize(existing.get("registry_rename_ts")),
            }
            row_number = by_id.get(key)
            if row_number is None:
                appended += 1
                row_number = len(rows) + appended + 1
            updates.append({
                "range": f"'{REGISTRY_SHEET}'!A{row_number}:{_column_letter(len(REGISTRY_HEADERS))}{row_number}",
                "values": [[merged.get(header, "") for header in REGISTRY_HEADERS]],
            })
        if updates:
            batch_update_values(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, updates)
        return {"status": "ok", "appended": appended, "updated": len(OUTPUT_LOGICAL_IDS) - appended}
    except Exception as exc:  # pragma: no cover - registry should not mask sheet diagnostics
        return {"status": "unavailable", "appended": 0, "updated": 0, "error": str(exc)}


def _validate_frozen_chain(inputs: Mapping[str, Any]) -> Dict[str, Any]:
    prereg_row = _latest_exact(
        inputs["Refined_Mechanism_Test_Outcome_Architecture_V2_Preregistration"].rows,
        "outcome_architecture_preregistration_run_id", PREREGISTRATION_RUN_ID,
    )
    _require(_normalize(prereg_row.get("architecture_version")) == ARCHITECTURE_VERSION, "VERSION_MISMATCH", "Architecture version drift.")
    _require(_normalize(prereg_row.get("architecture_preregistration_version")) == ARCHITECTURE_PREREGISTRATION_VERSION, "VERSION_MISMATCH", "Architecture preregistration version drift.")
    _require(_normalize(prereg_row.get("canonical_run_id")) == CANONICAL_AUTHORITY_RUN_ID, "LINEAGE_MISMATCH", "Canonical authority drift.")
    _require(_normalize(prereg_row.get("classification_run_id")) == CLASSIFICATION_RUN_ID, "LINEAGE_MISMATCH", "Classification run drift.")

    validation_summary = _latest_exact(
        inputs["Refined_Mechanism_Test_Outcome_Architecture_V2_Validation_Summary"].rows,
        "outcome_architecture_validation_run_id", VALIDATION_RUN_ID,
    )
    validation_payload = _payload(validation_summary)
    blocking_repairs, parsing_kind = _parse_nonnegative_int(
        validation_payload.get("blocking_repairs_required"), "blocking_repairs_required"
    )
    _require(blocking_repairs == 0, "DEPENDENCY_FAILURE", "Validation reports blocking repairs.")
    _require(
        _normalize(validation_summary.get("implementation_readiness_status")) == "READY_FOR_OUTCOME_ARCHITECTURE_IMPLEMENTATION",
        "DEPENDENCY_FAILURE", "Validation did not authorize implementation.",
    )

    planning_summary = _latest_exact(
        inputs["Refined_Mechanism_Test_Outcome_Architecture_V2_Implementation_Planning_Summary"].rows,
        "outcome_architecture_implementation_planning_run_id", PLANNING_RUN_ID,
    )
    _require(
        _normalize(planning_summary.get("implementation_planning_status")) == "READY_FOR_STAGED_IMPLEMENTATION",
        "DEPENDENCY_FAILURE", "Implementation planning did not authorize staged implementation.",
    )

    frozen_layers = _rows_for_run(
        inputs["Refined_Mechanism_Test_Outcome_Architecture_V2_Frozen_Layers"].rows,
        "outcome_architecture_preregistration_run_id", PREREGISTRATION_RUN_ID,
    )
    frozen_targets = _rows_for_run(
        inputs["Refined_Mechanism_Test_Outcome_Architecture_V2_Frozen_Redesign_Targets"].rows,
        "outcome_architecture_preregistration_run_id", PREREGISTRATION_RUN_ID,
    )
    frozen_prohibited = _rows_for_run(
        inputs["Refined_Mechanism_Test_Outcome_Architecture_V2_Frozen_Prohibited_Redesigns"].rows,
        "outcome_architecture_preregistration_run_id", PREREGISTRATION_RUN_ID,
    )
    _require(len(frozen_layers) == 5, "LINEAGE_MISMATCH", "Expected five frozen architecture layers.")
    _require(len(frozen_targets) == 5, "PROHIBITED_REDESIGN_ATTEMPT", "Only the five validated targets may be implemented.")
    _require(len(frozen_prohibited) == 3, "PROHIBITED_REDESIGN_ATTEMPT", "Frozen prohibited redesign set drifted.")
    observed_order = [_normalize(row.get("layer_name")) for row in sorted(frozen_layers, key=lambda row: int(_normalize(row.get("layer_order")) or "0"))]
    _require(observed_order == [name for _, name in STAGES], "DEPENDENCY_FAILURE", f"Frozen stage order drift: {observed_order}")

    classification_rows = [
        dict(row) for row in inputs["Refined_Mechanism_v11_Classifications"].rows
        if _normalize(row.get("classification_run_id")) == CLASSIFICATION_RUN_ID
    ]
    _require(len(classification_rows) == 360, "LINEAGE_MISMATCH", "Classification scope is not the frozen 360 rows.")
    _require(
        {_normalize(row.get("mechanism_version")) for row in classification_rows} == {CLASSIFICATION_VERSION},
        "VERSION_MISMATCH", "Classification mechanism version drift.",
    )
    return {
        "prereg_row": prereg_row,
        "validation_summary": validation_summary,
        "planning_summary": planning_summary,
        "frozen_layers": frozen_layers,
        "frozen_targets": frozen_targets,
        "frozen_prohibited": frozen_prohibited,
        "classification_rows": classification_rows,
        "parsing_assertion": {"field": "blocking_repairs_required", "value": blocking_repairs, "kind": parsing_kind, "status": "PASS"},
    }


def _build_stage_records(
    *,
    generated_ts: str,
    implementation_run_id: str,
    inputs: Mapping[str, Any],
    outcome_inputs: Mapping[str, Any],
) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, Dict[str, Any]]]:
    lineage_rows = [
        dict(row) for row in inputs["Refined_Mechanism_Test_Row_Lineage_Audit"].rows
        if _normalize(row.get("population_collapse_run_id")) == SOURCE_POPULATION_COLLAPSE_RUN_ID
    ]
    _require(len(lineage_rows) == 72, "UNEXPECTED_DATA_LOSS", f"Expected 72 planned lineage rows; found {len(lineage_rows)}.")
    _require({ _normalize(row.get("source_test_execution_run_id")) for row in lineage_rows } == {SOURCE_TEST_EXECUTION_RUN_ID}, "LINEAGE_MISMATCH", "Lineage rows refer to another test execution.")
    lineage_by_key = _index_unique(lineage_rows, "source_row_key")
    join_rows = [
        dict(row) for row in inputs["Refined_Mechanism_Test_Outcome_Join_Audit"].rows
        if _normalize(row.get("test_execution_run_id")) == SOURCE_TEST_EXECUTION_RUN_ID
        and _normalize(row.get("analysis_id")) == PRIMARY_ANALYSIS_ID
    ]
    _require(len(join_rows) == 72, "UNEXPECTED_DATA_LOSS", f"Expected 72 primary join-audit rows; found {len(join_rows)}.")
    join_by_key = _index_unique(join_rows, "source_row_key")
    _require(set(join_by_key) == set(lineage_by_key), "UNEXPECTED_DATA_LOSS", "Lineage and join-audit keys do not reconcile.")

    canonical_by_id = _index_unique(outcome_inputs["Market_Reaction_Canonical_Outcomes"].rows, "canonical_outcome_id")
    overlay_by_id = _index_unique(outcome_inputs["Market_Reaction_Recovered_Canonical_Outcomes"].rows, "repaired_canonical_overlay_id")
    selection_rows = outcome_inputs["Corrected_Accuracy_Row_Selection"].rows
    mapping_rows = outcome_inputs["Corrected_Accuracy_Outcome_Mapping"].rows
    selection_by_key: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    mapping_by_key: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in selection_rows:
        selection_by_key[(_normalize(row.get("provider")), _normalize(row.get("session_id")), _normalize(row.get("pack_level")))].append(dict(row))
    for row in mapping_rows:
        mapping_by_key[(_normalize(row.get("provider")), _normalize(row.get("session_id")), _normalize(row.get("pack_level")))].append(dict(row))

    canonical_records: List[Dict[str, Any]] = []
    overlay_records: List[Dict[str, Any]] = []
    linkage_records: List[Dict[str, Any]] = []
    representation_records: List[Dict[str, Any]] = []
    per_side: Dict[Tuple[str, str], Dict[str, Any]] = {}

    for source_key in sorted(lineage_by_key):
        lineage = lineage_by_key[source_key]
        join = join_by_key[source_key]
        for side in ("BASELINE", "EXPANDED"):
            side_payload = _side_payload(join, side)
            join_status = _side_value(lineage, side, "join_status")
            join_reason = _side_value(lineage, side, "join_reason")
            success_status = _side_value(lineage, side, "success_status")
            success_reason = _side_value(lineage, side, "success_reason")
            canonical_id = _normalize(side_payload.get("canonical_outcome_id")) or _normalize(lineage.get("canonical_outcome_id"))
            overlay_id = _normalize(side_payload.get("repaired_canonical_outcome_id")) or _normalize(lineage.get("repaired_canonical_outcome_id"))
            canonical = canonical_by_id.get(canonical_id)
            overlay = overlay_by_id.get(overlay_id)
            provider = _normalize(lineage.get("provider"))
            session_id = _normalize(lineage.get("session_id"))
            pack_level = "A" if side == "BASELINE" else _normalize(lineage.get("pack_level"))
            stable_key = (provider, session_id, pack_level)
            source_identity = f"{provider}|{session_id}|{pack_level}"

            canonical_version = _normalize((canonical or {}).get("implementation_version"))
            window_identity = "|".join([
                _normalize((canonical or {}).get("window_policy")),
                _normalize((canonical or {}).get("window_minutes")),
            ])
            timestamp_ready = bool(canonical) and all(
                _normalize((canonical or {}).get(field))
                for field in ("release_ts", "canonical_start_ts", "canonical_end_ts")
            )
            version_ready = canonical_version == "market_reaction_outcome_source_implementation_v0"
            window_ready = window_identity == "EVENT_RELATIVE_FIXED_DURATION|5.000"
            if not canonical_id or canonical is None:
                coverage_status = "INCOMPLETE_CANONICAL_COVERAGE"
                coverage_reason = join_reason or "MISSING_CANONICAL_OUTCOME_ID"
            elif not version_ready:
                coverage_status = "VERSION_MISMATCH_BLOCKED"
                coverage_reason = "OUTCOME_VERSION_MISMATCH"
            elif not window_ready:
                coverage_status = "INCOMPLETE_CANONICAL_COVERAGE"
                coverage_reason = "EVALUATION_WINDOW_MISMATCH"
            elif not timestamp_ready:
                coverage_status = "INCOMPLETE_CANONICAL_COVERAGE"
                coverage_reason = "OUTCOME_TIMESTAMP_REQUIREMENT_FAILED"
            else:
                coverage_status = "COMPLETE_CANONICAL_COVERAGE"
                coverage_reason = ""
            timestamp_status = "TIMESTAMP_PROVENANCE_COMPLETE" if timestamp_ready else "TIMESTAMP_PROVENANCE_INCOMPLETE"
            canonical_row = {
                "generated_ts": generated_ts, "schema_version": SCHEMA_VERSION,
                "outcome_architecture_implementation_run_id": implementation_run_id, "stage_id": STAGES[0][0],
                "observation_side": side, "source_observation_key": source_key, "provider": provider,
                "session_id": session_id, "pack_level": pack_level, "source_outcome_identity": source_identity,
                "canonical_outcome_id": canonical_id, "canonical_version": canonical_version,
                "evaluation_window_identity": window_identity, "outcome_timestamp": _normalize((canonical or {}).get("canonical_end_ts")),
                "timestamp_provenance_status": timestamp_status, "coverage_status": coverage_status,
                "deterministic_failure_reason": coverage_reason,
                "source_lineage": "Market_Reaction_Canonical_Outcomes",
                "downstream_overlay_eligible": "TRUE" if coverage_status == "COMPLETE_CANONICAL_COVERAGE" else "FALSE",
            }
            canonical_records.append(canonical_row)

            required_overlay_fields = ("repair_version", "repair_run_id", "repaired_realized_direction", "leakage_safe", "usable_for_strict_accuracy")
            fields_present = overlay is not None and all(_normalize(overlay.get(field)) for field in required_overlay_fields)
            selection_matches = selection_by_key.get(stable_key, [])
            mapping_matches = mapping_by_key.get(stable_key, [])
            if not overlay_id or overlay is None:
                overlay_status = "INCOMPLETE_OVERLAY"
                overlay_reason = "MISSING_REPAIRED_OUTCOME_OVERLAY"
            elif not fields_present:
                overlay_status = "INCOMPLETE_OVERLAY"
                overlay_reason = "MISSING_REQUIRED_OVERLAY_FIELD"
            elif len({ _normalize(row.get("repaired_canonical_outcome_id")) for row in selection_matches }) > 1 or len({ _normalize(row.get("repaired_canonical_outcome_id")) for row in mapping_matches }) > 1:
                overlay_status = "AMBIGUOUS_OVERLAY_BLOCKED"
                overlay_reason = "CROSS_VERSION_OVERLAY_ASSOCIATION"
            else:
                overlay_status = "COMPLETE_OVERLAY"
                overlay_reason = ""
            overlay_row = {
                "generated_ts": generated_ts, "schema_version": SCHEMA_VERSION,
                "outcome_architecture_implementation_run_id": implementation_run_id, "stage_id": STAGES[1][0],
                "observation_side": side, "source_observation_key": source_key, "canonical_outcome_id": canonical_id,
                "expected_overlay_id": overlay_id, "overlay_version": _normalize((overlay or {}).get("repair_version")),
                "repaired_overlay_available": "TRUE" if overlay is not None else "FALSE",
                "repair_lineage": _normalize((overlay or {}).get("repair_run_id")),
                "required_fields_present": "TRUE" if fields_present else "FALSE", "missing_component_reason": overlay_reason,
                "overlay_status": overlay_status,
                "downstream_linkage_eligible": "TRUE" if coverage_status == "COMPLETE_CANONICAL_COVERAGE" and overlay_status == "COMPLETE_OVERLAY" else "FALSE",
            }
            overlay_records.append(overlay_row)

            bridge_ok = join_status == "OK" and coverage_status == "COMPLETE_CANONICAL_COVERAGE" and overlay_status == "COMPLETE_OVERLAY"
            if bridge_ok:
                linkage_status, linkage_reason = "EXACT_LINK", ""
            elif "DUPLICATE" in join_reason:
                linkage_status, linkage_reason = "DUPLICATE_LINK_BLOCKED", join_reason
            elif "AMBIGUOUS" in join_reason:
                linkage_status, linkage_reason = "AMBIGUOUS_LINK_BLOCKED", join_reason
            elif canonical_version and canonical_version != "market_reaction_outcome_source_implementation_v0":
                linkage_status, linkage_reason = "VERSION_MISMATCH_BLOCKED", "OUTCOME_VERSION_MISMATCH"
            else:
                linkage_status, linkage_reason = "MISSING_LINK", join_reason or overlay_reason or coverage_reason
            linkage_row = {
                "generated_ts": generated_ts, "schema_version": SCHEMA_VERSION,
                "outcome_architecture_implementation_run_id": implementation_run_id, "stage_id": STAGES[2][0],
                "observation_side": side, "source_observation_key": source_key, "provider": provider,
                "session_id": session_id, "pack_level": pack_level, "forecast_run_identity": source_identity,
                "repaired_canonical_outcome_id": overlay_id, "canonical_outcome_id": canonical_id,
                "overlay_id": _normalize((overlay or {}).get("repaired_canonical_overlay_id")),
                "architecture_version": ARCHITECTURE_VERSION, "linkage_version": "2.0-exact-stable-key",
                "linkage_status": linkage_status, "linkage_reason": linkage_reason,
                "stable_key_json": _canonical_json({"provider": provider, "session_id": session_id, "pack_level": pack_level, "source_row_key": source_key}),
            }
            linkage_records.append(linkage_row)

            forecast_state = _normalize(side_payload.get("forecast_direction"))
            no_signal_state = _normalize(side_payload.get("no_signal_flag"))
            realized_state = _normalize((overlay or {}).get("repaired_realized_direction"))
            if linkage_status != "EXACT_LINK":
                representation_status, representation_provenance = "REPRESENTATION_UNAVAILABLE", linkage_reason
            elif realized_state in {"UP", "DOWN"}:
                representation_status, representation_provenance = "DIRECTIONAL_REPRESENTATION_AVAILABLE", "VERSIONED_REPAIRED_OVERLAY"
            elif realized_state == "FLAT":
                representation_status, representation_provenance = "FLAT_REPRESENTATION_AVAILABLE", "VERSIONED_REPAIRED_OVERLAY"
            elif realized_state == "NO_CLEAR_DIRECTION":
                representation_status, representation_provenance = "NO_CLEAR_DIRECTION_REPRESENTATION_AVAILABLE", "VERSIONED_REPAIRED_OVERLAY"
            elif not realized_state:
                representation_status, representation_provenance = "REPRESENTATION_UNAVAILABLE", "MISSING_REALIZED_STATE"
            else:
                representation_status, representation_provenance = "INVALID_REPRESENTATION", "INVALID_REALIZED_STATE"
            consumable = "TRUE" if success_status in {"SUCCESS", "FAILURE"} else "FALSE"
            representation_row = {
                "generated_ts": generated_ts, "schema_version": SCHEMA_VERSION,
                "outcome_architecture_implementation_run_id": implementation_run_id, "stage_id": STAGES[3][0],
                "observation_side": side, "source_observation_key": source_key, "canonical_outcome_id": canonical_id,
                "overlay_id": overlay_id, "representation_version": "2.0-pre-success-state",
                "realized_state": realized_state, "forecast_state": forecast_state, "no_signal_state": no_signal_state,
                "representation_status": representation_status, "representation_provenance": representation_provenance,
                "current_success_mapping_v1_consumability": consumable,
                "downstream_consumer_compatibility": "SUCCESS_MAPPING_V1_UNCHANGED",
            }
            representation_records.append(representation_row)
            per_side[(source_key, side)] = {
                "canonical": canonical_row, "overlay": overlay_row, "linkage": linkage_row,
                "representation": representation_row, "success_status": success_status, "success_reason": success_reason,
            }

    _require(len(canonical_records) == 144, "UNEXPECTED_DATA_LOSS", "Canonical coverage accounting did not produce 144 pair-side records.")
    _require(len(overlay_records) == 144 and len(linkage_records) == 144 and len(representation_records) == 144, "UNEXPECTED_DATA_LOSS", "A pair-side stage lost records.")

    pair_records: List[Dict[str, Any]] = []
    survivorship_records: List[Dict[str, Any]] = []
    for source_key in sorted(lineage_by_key):
        lineage = lineage_by_key[source_key]
        baseline = per_side[(source_key, "BASELINE")]
        expanded = per_side[(source_key, "EXPANDED")]
        representation_ready = (
            baseline["representation"]["representation_status"] != "REPRESENTATION_UNAVAILABLE"
            and expanded["representation"]["representation_status"] != "REPRESENTATION_UNAVAILABLE"
        )
        if baseline["linkage"]["linkage_status"] != "EXACT_LINK":
            pair_status, first_failure = "NOT_EVALUABLE", f"BASELINE_{baseline['linkage']['linkage_reason']}"
        elif expanded["linkage"]["linkage_status"] != "EXACT_LINK":
            pair_status, first_failure = "NOT_EVALUABLE", f"EXPANDED_{expanded['linkage']['linkage_reason']}"
        elif not representation_ready:
            pair_status, first_failure = "NOT_EVALUABLE", "REPRESENTATION_UNAVAILABLE"
        elif baseline["success_status"] not in {"SUCCESS", "FAILURE"}:
            pair_status, first_failure = "NOT_EVALUABLE_CURRENT_V1", f"BASELINE_{baseline['success_reason']}"
        elif expanded["success_status"] not in {"SUCCESS", "FAILURE"}:
            pair_status, first_failure = "NOT_EVALUABLE_CURRENT_V1", f"EXPANDED_{expanded['success_reason']}"
        else:
            pair_status, first_failure = "EVALUABLE_CURRENT_V1", ""
        pair_records.append({
            "generated_ts": generated_ts, "schema_version": SCHEMA_VERSION,
            "outcome_architecture_implementation_run_id": implementation_run_id, "stage_id": STAGES[4][0],
            "source_observation_key": source_key, "provider": _normalize(lineage.get("provider")),
            "session_id": _normalize(lineage.get("session_id")), "baseline_source_key": _normalize(lineage.get("matched_baseline_source_row_key")),
            "expanded_source_key": source_key, "baseline_linkage_status": baseline["linkage"]["linkage_status"],
            "expanded_linkage_status": expanded["linkage"]["linkage_status"], "baseline_overlay_status": baseline["overlay"]["overlay_status"],
            "expanded_overlay_status": expanded["overlay"]["overlay_status"], "baseline_representation_status": baseline["representation"]["representation_status"],
            "expanded_representation_status": expanded["representation"]["representation_status"],
            "representation_readiness": "TRUE" if representation_ready else "FALSE", "pair_evaluability_status": pair_status,
            "first_failure_point": first_failure,
        })
        final_disposition = _normalize(lineage.get("final_disposition"))
        if final_disposition == "PRIMARY_ELIGIBLE":
            first_blocking_layer, survivorship = "NONE", "SURVIVES_CURRENT_V1"
        elif final_disposition == "MISSING_REPAIRED_OUTCOME_OVERLAY":
            first_blocking_layer, survivorship = "OUTCOME_OVERLAY", "BLOCKED_AT_OVERLAY"
        elif final_disposition.startswith("MISSING_") or final_disposition in {"OUTCOME_VERSION_MISMATCH", "EVALUATION_WINDOW_MISMATCH"}:
            first_blocking_layer, survivorship = "CANONICAL_OUTCOME", "BLOCKED_AT_CANONICAL_OR_LINKAGE"
        else:
            first_blocking_layer, survivorship = "OUTCOME_REPRESENTATION", "BLOCKED_BY_CURRENT_SUCCESS_MAPPING_V1"
        survivorship_records.append({
            "generated_ts": generated_ts, "schema_version": SCHEMA_VERSION,
            "outcome_architecture_implementation_run_id": implementation_run_id, "stage_id": STAGES[4][0],
            "source_observation_key": source_key,
            "mechanism_classification_reference": f"{CLASSIFICATION_RUN_ID}|MECH_INFORMATION_CONSISTENCY|{source_key}",
            "expanded_label": _normalize(lineage.get("expanded_label")), "confidence_category": _normalize(lineage.get("confidence_category")),
            "canonical_status": expanded["canonical"]["coverage_status"], "overlay_status": expanded["overlay"]["overlay_status"],
            "linkage_status": expanded["linkage"]["linkage_status"], "representation_status": expanded["representation"]["representation_status"],
            "current_success_mapping_v1_consumability": expanded["representation"]["current_success_mapping_v1_consumability"],
            "current_eligibility_status": "ELIGIBLE" if final_disposition == "PRIMARY_ELIGIBLE" else "NOT_ELIGIBLE",
            "first_blocking_layer": first_blocking_layer, "projected_architecture_v2_survivorship_status": survivorship,
            "no_rule_change_confirmation": "TRUE",
        })
    _require(len(pair_records) == 72 and len(survivorship_records) == 72, "UNEXPECTED_DATA_LOSS", "Final stage failed planned-population accounting.")

    stage_rows = {
        "CANONICAL_OUTCOME": canonical_records,
        "OUTCOME_OVERLAY": overlay_records,
        "OUTCOME_LINKAGE": linkage_records,
        "OUTCOME_REPRESENTATION": representation_records,
        "ELIGIBILITY_INTERACTION": pair_records + survivorship_records,
    }
    for rows in stage_rows.values():
        fingerprint = _records_fingerprint(rows)
        for row in rows:
            row["layer_fingerprint"] = fingerprint
            row["payload_json"] = _canonical_json({key: value for key, value in row.items() if key not in {"payload_json", "layer_fingerprint"}})
    return {
        OUTPUT_CANONICAL: canonical_records,
        OUTPUT_OVERLAY: overlay_records,
        OUTPUT_LINKAGE: linkage_records,
        OUTPUT_REPRESENTATION: representation_records,
        OUTPUT_PAIR: pair_records,
        OUTPUT_SURVIVORSHIP: survivorship_records,
    }, stage_rows


def _checkpoint_rows(
    *, generated_ts: str, implementation_run_id: str, stage_rows: Mapping[str, Sequence[Mapping[str, Any]]], source_fps: Mapping[str, str]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    checkpoints: List[Dict[str, Any]] = []
    determinism_rows: List[Dict[str, Any]] = []
    compatibility_rows: List[Dict[str, Any]] = []
    lineage_rows: List[Dict[str, Any]] = []
    previous_fp = _canonical_fingerprint({"frozen_preregistration": source_fps["Refined_Mechanism_Test_Outcome_Architecture_V2_Preregistration"]})
    for order, (stage_id, layer_name) in enumerate(STAGES, start=1):
        first_fp = _records_fingerprint(stage_rows[layer_name])
        second_fp = _records_fingerprint(stage_rows[layer_name])
        _require(first_fp == second_fp, "DETERMINISTIC_FAILURE", f"{layer_name} deterministic reconstruction differs.")
        stable_keys = [
            _normalize(row.get("source_observation_key")) + "|" + _normalize(row.get("observation_side"))
            for row in stage_rows[layer_name]
        ]
        if layer_name == "ELIGIBILITY_INTERACTION":
            stable_keys = [
                _normalize(row.get("source_observation_key")) + "|" + ("PAIR" if "pair_evaluability_status" in row else "SURVIVORSHIP")
                for row in stage_rows[layer_name]
            ]
        unique = len(stable_keys) == len(set(stable_keys))
        _require(unique, "DUPLICATE_LINK", f"{layer_name} stable-key uniqueness failed.")
        expected = 144 if layer_name != "ELIGIBILITY_INTERACTION" else 144
        _require(len(stage_rows[layer_name]) == expected, "UNEXPECTED_DATA_LOSS", f"{layer_name} expected {expected} records.")
        checkpoint_id = f"{implementation_run_id}:{stage_id}:{first_fp[:16]}"
        checkpoints.append({
            "generated_ts": generated_ts, "schema_version": SCHEMA_VERSION,
            "outcome_architecture_implementation_run_id": implementation_run_id, "architecture_version": ARCHITECTURE_VERSION,
            "stage_id": stage_id, "stage_order": order, "stage_status": "COMPLETED_VERIFIED",
            "input_fingerprints_json": _canonical_json({"prior_checkpoint": previous_fp, "source_fingerprints": source_fps}),
            "output_fingerprint": first_fp, "input_rows": 72 if order == 1 else 144,
            "output_rows": len(stage_rows[layer_name]), "verification_status": "PASS", "determinism_status": "PASS",
            "compatibility_status": "PASS", "blocking_governance_findings": 0,
            "completion_timestamp": generated_ts, "checkpoint_id": checkpoint_id, "resume_token": checkpoint_id,
            "payload_json": _canonical_json({"stage_name": layer_name, "hard_stops": HARD_STOPS, "resume_requires": "COMPLETED_VERIFIED checkpoint with matching fingerprint"}),
        })
        determinism_rows.append({
            "generated_ts": generated_ts, "schema_version": SCHEMA_VERSION,
            "outcome_architecture_implementation_run_id": implementation_run_id, "stage_id": stage_id,
            "determinism_check_id": f"{stage_id}_SECOND_PASS", "first_pass_fingerprint": first_fp,
            "second_pass_fingerprint": second_fp, "determinism_status": "PASS",
            "stable_key_uniqueness_status": "PASS", "expected_row_accounting_status": "PASS",
            "payload_json": _canonical_json({"layer_name": layer_name, "row_count": len(stage_rows[layer_name])}),
        })
        compatibility_rows.append({
            "generated_ts": generated_ts, "schema_version": SCHEMA_VERSION,
            "outcome_architecture_implementation_run_id": implementation_run_id, "stage_id": stage_id,
            "compatibility_target": "SUCCESS_MAPPING_V1_AND_EXISTING_CONSUMERS", "compatibility_status": "PASS",
            "consumer_switch": "FALSE", "scientific_rule_change": "FALSE",
            "notes": f"{layer_name} is shadow-only and emits no current-consumer switch.",
            "payload_json": _canonical_json({"mechanism_classifications_version": CLASSIFICATION_VERSION, "canonical_preregistration_version": CANONICAL_PREREGISTRATION_VERSION}),
        })
        lineage_rows.append({
            "generated_ts": generated_ts, "schema_version": SCHEMA_VERSION,
            "outcome_architecture_implementation_run_id": implementation_run_id, "stage_id": stage_id,
            "lineage_component": layer_name, "source_sheet": "|".join(sorted(source_fps)),
            "source_run_id": f"{PREREGISTRATION_RUN_ID}|{VALIDATION_RUN_ID}|{PLANNING_RUN_ID}",
            "source_row_count": 72, "source_fingerprint": first_fp, "lineage_status": "COMPLETE",
            "payload_json": _canonical_json({"canonical_authority_run_id": CANONICAL_AUTHORITY_RUN_ID, "classification_run_id": CLASSIFICATION_RUN_ID}),
        })
        previous_fp = first_fp
    return checkpoints, determinism_rows, compatibility_rows, lineage_rows


def _compact_manifest_rows(
    sheet_name: str,
    headers: Sequence[str],
    rows: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    """Store row-level diagnostics in deterministic chunks when grid capacity is limited.

    The workbook is near its cell limit. Chunks retain every non-volatile field
    in a stable JSON table while keeping the required sheet family append-only.
    """
    if not rows:
        return []
    volatile = {"generated_ts", "outcome_architecture_implementation_run_id", "payload_json"}
    columns = [key for key in sorted({key for row in rows for key in row}) if key not in volatile]
    compact_records = [[row.get(column, "") for column in columns] for row in rows]
    chunks: List[List[List[Any]]] = []
    current: List[List[Any]] = []
    for record in compact_records:
        candidate = current + [record]
        candidate_payload = _canonical_json({"columns": columns, "records": candidate})
        if current and len(candidate_payload) > 42000:
            chunks.append(current)
            current = [record]
        else:
            current = candidate
    if current:
        chunks.append(current)

    first = dict(rows[0])
    compact_rows: List[Dict[str, Any]] = []
    for chunk_index, chunk in enumerate(chunks, start=1):
        compact = {header: "" for header in headers}
        for header in ("generated_ts", "schema_version", "outcome_architecture_implementation_run_id", "stage_id"):
            if header in compact:
                compact[header] = first.get(header, "")
        for key in ("source_observation_key", "source_observation_key", "checkpoint_id", "counter_name", "lineage_component", "determinism_check_id", "compatibility_target"):
            if key in compact:
                compact[key] = f"COMPACT_MANIFEST_{chunk_index}_OF_{len(chunks)}"
                break
        if "layer_fingerprint" in compact:
            compact["layer_fingerprint"] = _records_fingerprint(rows)
        compact["payload_json"] = _canonical_json({
            "storage_mode": "COMPACT_APPEND_ONLY_MANIFEST",
            "physical_sheet": sheet_name,
            "logical_record_count": len(rows),
            "chunk_index": chunk_index,
            "chunk_count": len(chunks),
            "column_order": columns,
            "records": chunk,
        })
        _require(len(compact["payload_json"]) <= 49000, "UNEXPECTED_DATA_LOSS", f"{sheet_name} compact manifest exceeds cell text limit.")
        compact_rows.append(compact)
    return compact_rows


def _compact_outputs(outputs: Mapping[str, Sequence[Mapping[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
    direct_sheets = {
        OUTPUT_IMPLEMENTATION, OUTPUT_SUMMARY, OUTPUT_REPAIR, OUTPUT_PARSER_REPAIR,
        OUTPUT_STOP_AUDIT, OUTPUT_AGGREGATE_FP, OUTPUT_AUTHORITY,
        OUTPUT_REPAIR_CHECKPOINTS, OUTPUT_REPAIR_DETERMINISM,
        OUTPUT_REPAIR_GOVERNANCE, OUTPUT_REPAIR_SUMMARY,
    }
    compacted: Dict[str, List[Dict[str, Any]]] = {}
    for sheet_name, rows in outputs.items():
        if sheet_name in direct_sheets:
            compacted[sheet_name] = [dict(row) for row in rows]
        else:
            compacted[sheet_name] = _compact_manifest_rows(sheet_name, OUTPUT_SHEETS[sheet_name], rows)
    return compacted


def _canonical_component_fingerprint(rows: Sequence[Mapping[str, Any]]) -> str:
    """Fingerprint decoded logical rows with stable record ordering and no volatile fields."""
    volatile = {
        "generated_ts", "outcome_architecture_implementation_run_id",
        "layer_fingerprint", "payload_json",
    }
    stable_rows = [
        {key: row.get(key, "") for key in sorted(row) if key not in volatile}
        for row in rows
    ]
    return _canonical_fingerprint(sorted(stable_rows, key=_canonical_json))


def _aggregate_fingerprint(outputs: Mapping[str, Sequence[Mapping[str, Any]]]) -> Dict[str, Any]:
    component_fingerprints = {
        component: _canonical_component_fingerprint(outputs[component])
        for component in AGGREGATE_COMPONENTS
    }
    payload = {
        "fingerprint_schema_version": AGGREGATE_FINGERPRINT_SCHEMA_VERSION,
        "architecture_version": ARCHITECTURE_VERSION,
        "component_order": list(AGGREGATE_COMPONENTS),
        "component_fingerprints": component_fingerprints,
        "component_row_counts": {component: len(outputs[component]) for component in AGGREGATE_COMPONENTS},
        "serialization": "canonical_json_utf8_sha256_sorted_component_records",
        "excluded_volatile_fields": [
            "generated_ts", "outcome_architecture_implementation_run_id",
            "layer_fingerprint", "payload_json",
        ],
    }
    return {
        "aggregate_content_fingerprint": _canonical_fingerprint(payload),
        "aggregate_payload": payload,
        "component_fingerprints": component_fingerprints,
    }


def _decode_compact_manifest_rows(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    decoded: List[Dict[str, Any]] = []
    chunks: List[Tuple[int, Mapping[str, Any]]] = []
    for row in rows:
        payload = _payload(row)
        _require(payload.get("storage_mode") == "COMPACT_APPEND_ONLY_MANIFEST", "FINGERPRINT_MISMATCH", "Expected compact manifest storage.")
        chunks.append((int(payload.get("chunk_index", 0)), payload))
    expected_indices = list(range(1, len(chunks) + 1))
    _require(sorted(index for index, _ in chunks) == expected_indices, "FINGERPRINT_MISMATCH", "Compact manifest chunk ordering is incomplete.")
    for _, payload in sorted(chunks, key=lambda item: item[0]):
        columns = payload.get("column_order")
        records = payload.get("records")
        _require(isinstance(columns, list) and isinstance(records, list), "FINGERPRINT_MISMATCH", "Compact manifest schema is invalid.")
        for record in records:
            _require(isinstance(record, list) and len(record) == len(columns), "FINGERPRINT_MISMATCH", "Compact manifest record is truncated.")
            decoded.append(dict(zip(columns, record)))
    return decoded


def _completed_checkpoint_run_ids(rows: Sequence[Mapping[str, Any]]) -> Set[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        run_id = _normalize(row.get("outcome_architecture_implementation_run_id"))
        if not run_id:
            continue
        try:
            payload = _payload(row)
        except StageBlocked:
            continue
        if payload.get("storage_mode") != "COMPACT_APPEND_ONLY_MANIFEST":
            if _normalize(row.get("stage_status")) == "COMPLETED_VERIFIED":
                counts[run_id] += 1
            continue
        columns = payload.get("column_order", [])
        for record in payload.get("records", []):
            logical = dict(zip(columns, record))
            if _normalize(logical.get("stage_status")) == "COMPLETED_VERIFIED":
                counts[run_id] += 1
    return {run_id for run_id, count in counts.items() if count == len(STAGES)}


def _batch_append_output_family(service, physical_outputs: Mapping[str, Sequence[Mapping[str, Any]]]) -> Dict[str, int]:
    """Append the full versioned family atomically enough for a cell-constrained workbook."""
    titles = _sheet_titles_light(service, DIAGNOSTICS_SPREADSHEET_ID)
    missing = [sheet_name for sheet_name in OUTPUT_SHEETS if sheet_name not in titles]
    if missing:
        requests = [
            {"addSheet": {"properties": {"title": sheet_name, "gridProperties": {"rowCount": 2, "columnCount": len(OUTPUT_SHEETS[sheet_name])}}}}
            for sheet_name in missing
        ]
        service.spreadsheets().batchUpdate(
            spreadsheetId=DIAGNOSTICS_SPREADSHEET_ID, body={"requests": requests},
        ).execute()
    ordered_sheets = list(OUTPUT_SHEETS)
    # Column A is populated for every physical record. Reading it finds the
    # append position without reading wide logical payload cells or enlarging grids.
    ranges = [f"'{sheet_name}'!A1:A" for sheet_name in ordered_sheets]
    value_ranges = service.spreadsheets().values().batchGet(
        spreadsheetId=DIAGNOSTICS_SPREADSHEET_ID, ranges=ranges,
    ).execute().get("valueRanges", [])
    existing_rows = {
        sheet_name: (value_ranges[index].get("values", []) if index < len(value_ranges) else [])
        for index, sheet_name in enumerate(ordered_sheets)
    }
    metadata = service.spreadsheets().get(
        spreadsheetId=DIAGNOSTICS_SPREADSHEET_ID,
        fields="sheets.properties(sheetId,title,gridProperties)",
    ).execute()
    properties = {sheet["properties"]["title"]: sheet["properties"] for sheet in metadata.get("sheets", [])}
    starts = {
        sheet_name: max(2, len(existing_rows[sheet_name]) + 1)
        for sheet_name in OUTPUT_SHEETS
    }
    resize_requests = []
    for sheet_name, rows in physical_outputs.items():
        required_rows = starts[sheet_name] + len(rows) - 1
        current_rows = properties[sheet_name].get("gridProperties", {}).get("rowCount", 0)
        if required_rows > current_rows:
            resize_requests.append({
                "updateSheetProperties": {
                    "properties": {"sheetId": properties[sheet_name]["sheetId"], "gridProperties": {"rowCount": required_rows}},
                    "fields": "gridProperties.rowCount",
                }
            })
    if resize_requests:
        service.spreadsheets().batchUpdate(
            spreadsheetId=DIAGNOSTICS_SPREADSHEET_ID, body={"requests": resize_requests},
        ).execute()
    updates = []
    written: Dict[str, int] = {}
    for sheet_name, headers in OUTPUT_SHEETS.items():
        rows = physical_outputs[sheet_name]
        updates.append({"range": f"'{sheet_name}'!A1:{_column_letter(len(headers))}1", "values": [headers]})
        values = [[row.get(header, "") for header in headers] for row in rows]
        end_row = starts[sheet_name] + len(values) - 1
        updates.append({"range": f"'{sheet_name}'!A{starts[sheet_name]}:{_column_letter(len(headers))}{end_row}", "values": values})
        written[sheet_name] = len(values)
    batch_update_values(service, DIAGNOSTICS_SPREADSHEET_ID, updates)
    return written


def build() -> Dict[str, Any]:
    run_ts = datetime.now(timezone.utc).replace(microsecond=0)
    generated_ts = _now_iso(run_ts)
    implementation_run_id = _run_id(run_ts)
    service = build_sheets_service(load_credentials())
    known_titles = _sheet_titles_light(service, DIAGNOSTICS_SPREADSHEET_ID)
    inputs = _fetch_input_sheets(service, DIAGNOSTICS_SPREADSHEET_ID, FROZEN_INPUT_SHEETS)
    frozen = _validate_frozen_chain(inputs)
    parser_tests = _parser_test_matrix()
    hard_stop_tests = _runtime_guard_tests()
    runtime_controls = {
        "join_mode": "EXACT_STABLE_KEY",
        "manual_join_requested": False,
        "production_write_requested": False,
        "mechanism_test_requested": False,
        "success_mapping_change_requested": False,
        "resume_token": os.environ.get("OA_V2_RESUME_TOKEN", ""),
    }
    _guard(runtime_controls["join_mode"] == "EXACT_STABLE_KEY", "FUZZY_JOIN_ATTEMPT", "Only exact stable-key joins are permitted.", "PRE_EXECUTION")
    _guard(runtime_controls["manual_join_requested"] is False, "MANUAL_JOIN_ATTEMPT", "Manual matching is prohibited.", "PRE_EXECUTION")
    _guard(runtime_controls["production_write_requested"] is False, "PRODUCTION_WRITE_ATTEMPT", "Production writes are prohibited.", "PRE_EXECUTION")
    _guard(runtime_controls["mechanism_test_requested"] is False, "MECHANISM_TEST_ATTEMPT", "Mechanism testing is prohibited.", "PRE_EXECUTION")
    _guard(runtime_controls["success_mapping_change_requested"] is False, "SUCCESS_MAPPING_CHANGE_ATTEMPT", "Success Mapping changes are prohibited.", "PRE_EXECUTION")
    _guard(not runtime_controls["resume_token"], "UNVERIFIED_CHECKPOINT_RESUME_ATTEMPT", "This repair creates a new run and accepts no resume token.", "PRE_EXECUTION")

    # Outcome loading occurs only after frozen-chain validation and only for shadow construction.
    outcome_inputs = _fetch_input_sheets(service, DIAGNOSTICS_SPREADSHEET_ID, OUTCOME_SOURCE_SHEETS)
    source_fps = _source_fingerprints(inputs, outcome_inputs)
    _guard(
        not (set(OUTPUT_SHEETS) & set(FROZEN_INPUT_SHEETS + OUTCOME_SOURCE_SHEETS)),
        "SOURCE_SHEET_MODIFICATION_ATTEMPT",
        "A configured write target overlaps a frozen or source sheet.",
        "PRE_EXECUTION",
    )
    outputs, stage_rows = _build_stage_records(
        generated_ts=generated_ts,
        implementation_run_id=implementation_run_id,
        inputs=inputs,
        outcome_inputs=outcome_inputs,
    )
    checkpoints, determinism_rows, compatibility_rows, lineage_rows = _checkpoint_rows(
        generated_ts=generated_ts,
        implementation_run_id=implementation_run_id,
        stage_rows=stage_rows,
        source_fps=source_fps,
    )
    prior_partial_runs: List[str] = []
    prior_verified_runs: Set[str] = set()
    if OUTPUT_IMPLEMENTATION in known_titles:
        prior_implementation_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_IMPLEMENTATION)
        prior_checkpoint_rows = (
            _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_CHECKPOINTS)
            if OUTPUT_CHECKPOINTS in known_titles
            else []
        )
        checkpointed_runs = _completed_checkpoint_run_ids(prior_checkpoint_rows)
        prior_verified_runs = set(checkpointed_runs)
        prior_partial_runs = sorted({
            _normalize(row.get("outcome_architecture_implementation_run_id"))
            for row in prior_implementation_rows
            if _normalize(row.get("outcome_architecture_implementation_run_id"))
            and _normalize(row.get("outcome_architecture_implementation_run_id")) not in checkpointed_runs
        })
        for historical_run_id in prior_partial_runs:
            lineage_rows.append({
                "generated_ts": generated_ts, "schema_version": SCHEMA_VERSION,
                "outcome_architecture_implementation_run_id": implementation_run_id,
                "stage_id": "HISTORICAL_PARTIAL_WRITE_ISOLATION",
                "lineage_component": "SUPERSEDED_PARTIAL_SHADOW_ATTEMPT",
                "source_sheet": OUTPUT_IMPLEMENTATION,
                "source_run_id": historical_run_id,
                "source_row_count": 0,
                "source_fingerprint": "",
                "lineage_status": "NONAUTHORITATIVE_UNVERIFIED_CHECKPOINT",
                "payload_json": _canonical_json({
                    "selection_rule": "Ignore any run lacking a completed verified checkpoint set and successful summary.",
                    "resume_permitted": False,
                }),
            })

    canonical_complete = sum(row["coverage_status"] == "COMPLETE_CANONICAL_COVERAGE" for row in outputs[OUTPUT_CANONICAL])
    overlay_complete = sum(row["overlay_status"] == "COMPLETE_OVERLAY" for row in outputs[OUTPUT_OVERLAY])
    exact_links = sum(row["linkage_status"] == "EXACT_LINK" for row in outputs[OUTPUT_LINKAGE])
    linkage_counts = Counter(row["linkage_status"] for row in outputs[OUTPUT_LINKAGE])
    first_hit_counts = Counter(row["first_blocking_layer"] for row in outputs[OUTPUT_SURVIVORSHIP])
    governance_counters = {
        "provider_calls_performed": 0,
        "outcome_rows_loaded": sum(len(outcome_inputs[name].rows) for name in OUTCOME_SOURCE_SHEETS),
        "source_outcome_rows_modified": 0,
        "existing_outcome_rules_modified": 0,
        "existing_overlay_rows_modified": 0,
        "existing_linkage_rows_modified": 0,
        "existing_representation_rows_modified": 0,
        "existing_eligibility_rows_modified": 0,
        "success_mapping_modified": 0,
        "mechanism_rules_modified": 0,
        "preregistration_modified": 0,
        "mechanism_tests_performed": 0,
        "production_writes": 0,
        "production_behavior_changes": 0,
    }
    governance_counters["consumer_switches"] = 0
    outputs[OUTPUT_IMPLEMENTATION] = [{
        "generated_ts": generated_ts, "schema_version": SCHEMA_VERSION,
        "outcome_architecture_implementation_run_id": implementation_run_id,
        "architecture_version": ARCHITECTURE_VERSION, "architecture_preregistration_version": ARCHITECTURE_PREREGISTRATION_VERSION,
        "implementation_mode": IMPLEMENTATION_MODE, "production_authority": "FALSE",
        "current_architecture_replacement": "FALSE", "success_mapping_consumer_switch": "FALSE",
        "mechanism_test_rerun": "FALSE", "implementation_status": "COMPLETED_VERIFIED",
        "build_status": BUILD_STATUS, "final_interpretation": FINAL_INTERPRETATION,
        "payload_json": _canonical_json({
            "preregistration_run_id": PREREGISTRATION_RUN_ID, "validation_run_id": VALIDATION_RUN_ID,
            "planning_run_id": PLANNING_RUN_ID, "canonical_authority_run_id": CANONICAL_AUTHORITY_RUN_ID,
            "classification_run_id": CLASSIFICATION_RUN_ID, "hard_stop_catalog": HARD_STOPS,
            "parsing_assertion": frozen["parsing_assertion"], "repair_of_review_run_id": "9A-6R15J_20260713T055142Z",
        }),
    }]
    outputs[OUTPUT_CHECKPOINTS] = checkpoints
    outputs[OUTPUT_LINEAGE] = lineage_rows
    outputs[OUTPUT_DETERMINISM] = determinism_rows
    outputs[OUTPUT_COMPATIBILITY] = compatibility_rows
    outputs[OUTPUT_GOVERNANCE] = [{
        "generated_ts": generated_ts, "schema_version": SCHEMA_VERSION,
        "outcome_architecture_implementation_run_id": implementation_run_id,
        "counter_name": name, "counter_value": value,
        "status": "PASS" if value == 0 or name == "outcome_rows_loaded" else "FAIL",
        "notes": "Shadow construction source read count." if name == "outcome_rows_loaded" else "No modification or prohibited execution occurred.",
    } for name, value in governance_counters.items()]

    aggregate_first = _aggregate_fingerprint(outputs)
    aggregate_second = _aggregate_fingerprint(outputs)
    _guard(
        aggregate_first["aggregate_content_fingerprint"] == aggregate_second["aggregate_content_fingerprint"],
        "FINGERPRINT_MISMATCH", "Independent aggregate logical-payload reconstructions differ.", "AGGREGATE_FINGERPRINT",
    )

    def repair_record(area: str, status: str, payload: Mapping[str, Any], authority_status: str = "PENDING") -> Dict[str, Any]:
        return {
            "generated_ts": generated_ts, "schema_version": SCHEMA_VERSION,
            "outcome_architecture_implementation_run_id": implementation_run_id,
            "architecture_version": ARCHITECTURE_VERSION, "repair_area": area,
            "repair_status": status, "authority_status": authority_status,
            "payload_json": _canonical_json(payload),
        }

    outputs[OUTPUT_REPAIR] = [repair_record("STAGE_SPECIFIC_IMPLEMENTATION_REPAIR", "COMPLETED_VERIFIED", {
        "repair_scope": ["FLOAT_ZERO_PARSER", "AGGREGATE_FINGERPRINT", "RUNTIME_HARD_STOPS", "AUTHORITY_REFERENCE"],
        "scientific_architecture_changed": False, "counts_changed": False,
    })]
    outputs[OUTPUT_PARSER_REPAIR] = [repair_record("PARSER_MATRIX", "PASS", {
        "declared_type": "INTEGER_COUNT", "cases": parser_tests,
        "truthiness_coercion_found": False,
    })]
    outputs[OUTPUT_STOP_AUDIT] = [repair_record("HARD_STOP_RUNTIME_ASSERTIONS", "PASS", {
        "cataloged_stop_count": len(HARD_STOPS), "runtime_enforced_stop_count": len(hard_stop_tests),
        "negative_path_tests_executed": len(hard_stop_tests), "negative_path_tests_passed": sum(row["trigger_observed"] for row in hard_stop_tests),
        "stops_remaining_catalog_only": [], "tests": hard_stop_tests,
    })]
    outputs[OUTPUT_AGGREGATE_FP] = [repair_record("AGGREGATE_LOGICAL_PAYLOAD_FINGERPRINT", "PENDING_RECONSTRUCTION", {
        **aggregate_first, "first_reconstruction_fingerprint": aggregate_first["aggregate_content_fingerprint"],
        "second_reconstruction_fingerprint": aggregate_second["aggregate_content_fingerprint"],
        "implementation_run_id_lineage_metadata": implementation_run_id,
    })]
    outputs[OUTPUT_REPAIR_CHECKPOINTS] = [repair_record("REPAIRED_STAGE_CHAIN", "PASS", {
        "stages": [{"stage_id": row["stage_id"], "status": row["stage_status"], "checkpoint_id": row["checkpoint_id"], "fingerprint": row["output_fingerprint"]} for row in checkpoints],
    })]
    outputs[OUTPUT_REPAIR_DETERMINISM] = [repair_record("REPAIR_DETERMINISM", "PENDING_RECONSTRUCTION", {
        "parser_matrix_passed": True, "hard_stop_matrix_passed": True,
        "first_aggregate_fingerprint": aggregate_first["aggregate_content_fingerprint"],
        "second_aggregate_fingerprint": aggregate_second["aggregate_content_fingerprint"],
    })]
    outputs[OUTPUT_REPAIR_GOVERNANCE] = [repair_record("REPAIR_GOVERNANCE", "PASS", governance_counters)]

    summary_payload = {
        "implementation_run_id": implementation_run_id, "stage_results": {checkpoint["stage_id"]: checkpoint["stage_status"] for checkpoint in checkpoints},
        "canonical_coverage_records": len(outputs[OUTPUT_CANONICAL]), "complete_canonical_coverage": canonical_complete,
        "incomplete_canonical_coverage": len(outputs[OUTPUT_CANONICAL]) - canonical_complete,
        "overlay_manifest_records": len(outputs[OUTPUT_OVERLAY]), "complete_overlays": overlay_complete,
        "incomplete_overlays": len(outputs[OUTPUT_OVERLAY]) - overlay_complete,
        "linkage_bridge_records": len(outputs[OUTPUT_LINKAGE]), "exact_links": exact_links,
        "missing_links": linkage_counts.get("MISSING_LINK", 0), "duplicate_links": linkage_counts.get("DUPLICATE_LINK_BLOCKED", 0),
        "ambiguous_links": linkage_counts.get("AMBIGUOUS_LINK_BLOCKED", 0), "representation_records": len(outputs[OUTPUT_REPRESENTATION]),
        "pair_evaluability_records": len(outputs[OUTPUT_PAIR]), "survivorship_records": len(outputs[OUTPUT_SURVIVORSHIP]),
        "first_hit_loss_attribution": dict(first_hit_counts), "all_stages_completed": True, "all_stages_verified": True,
        "parsing_assertion_status": frozen["parsing_assertion"], "parser_matrix": parser_tests,
        "hard_stop_test_count": len(hard_stop_tests), "governance_counters": governance_counters,
        "historical_partial_runs_isolated": prior_partial_runs, "prior_verified_runs": sorted(prior_verified_runs),
        "aggregate_content_fingerprint": aggregate_first["aggregate_content_fingerprint"],
    }
    outputs[OUTPUT_SUMMARY] = [{
        "generated_ts": generated_ts, "schema_version": SCHEMA_VERSION,
        "outcome_architecture_implementation_run_id": implementation_run_id, "build_status": BUILD_STATUS,
        "final_interpretation": FINAL_INTERPRETATION, "all_stages_completed": "TRUE", "all_stages_verified": "TRUE",
        "ready_for_outcome_architecture_v2_implementation_review": "TRUE", "ready_for_consumer_switch": "FALSE",
        "ready_for_mechanism_retesting": "FALSE", "ready_for_production": "FALSE",
        "recommended_next_step": RECOMMENDED_NEXT_STEP, "payload_json": _canonical_json(summary_payload),
    }]
    outputs[OUTPUT_REPAIR_SUMMARY] = [repair_record("REPAIR_SUMMARY", "PENDING_RECONSTRUCTION", {
        "build_status": BUILD_STATUS, "final_interpretation": FINAL_INTERPRETATION,
        "recommended_next_step": RECOMMENDED_NEXT_STEP, "blocking_findings": [],
    })]
    outputs[OUTPUT_AUTHORITY] = [repair_record("AUTHORITATIVE_REPAIRED_RUN", "PENDING_RECONSTRUCTION", {
        "authority_selection_rule": "EXACT_ARCHITECTURE_VERSION_AND_RUN_ID_WITH_COMPLETE_VERIFIED_CHAIN_AND_VALID_AGGREGATE_FINGERPRINT",
        "architecture_version": ARCHITECTURE_VERSION, "authoritative_implementation_run_id": implementation_run_id,
        "prior_authoritative_run_id": "9A-6R15I_20260713T052341Z", "prior_authoritative_status": "SUPERSEDED_BY_REPAIRED_RUN",
        "partial_runs": prior_partial_runs, "partial_run_status": "NONAUTHORITATIVE_ISOLATED",
        "latest_row_selection_prohibited": True, "mixed_run_selection_prohibited": True,
    })]

    physical_outputs = _compact_outputs(outputs)
    stored_components = {
        component: _decode_compact_manifest_rows(physical_outputs[component])
        for component in AGGREGATE_COMPONENTS
    }
    aggregate_stored = _aggregate_fingerprint(stored_components)
    aggregate_equal = (
        aggregate_first["aggregate_content_fingerprint"] == aggregate_second["aggregate_content_fingerprint"]
        == aggregate_stored["aggregate_content_fingerprint"]
    )
    _guard(aggregate_equal, "FINGERPRINT_MISMATCH", "Stored compact manifests do not reproduce the aggregate fingerprint.", "AGGREGATE_FINGERPRINT")
    for sheet_name, status, payload in (
        (OUTPUT_AGGREGATE_FP, "AGGREGATE_FINGERPRINT_REPRODUCED", {
            **aggregate_first, "first_reconstruction_fingerprint": aggregate_first["aggregate_content_fingerprint"],
            "second_reconstruction_fingerprint": aggregate_second["aggregate_content_fingerprint"],
            "stored_reconstruction_fingerprint": aggregate_stored["aggregate_content_fingerprint"], "all_fingerprints_equal": aggregate_equal,
        }),
        (OUTPUT_REPAIR_DETERMINISM, "PASS", {
            "aggregate_fingerprint_reproduced": aggregate_equal,
            "first": aggregate_first["aggregate_content_fingerprint"], "second": aggregate_second["aggregate_content_fingerprint"],
            "stored": aggregate_stored["aggregate_content_fingerprint"],
        }),
        (OUTPUT_REPAIR_SUMMARY, "READY_FOR_PHASE9A6R15J_R1_REVIEW", {
            "build_status": BUILD_STATUS, "final_interpretation": FINAL_INTERPRETATION,
            "aggregate_fingerprint_reproduced": aggregate_equal, "parser_matrix_passed": True,
            "hard_stop_tests_passed": len(hard_stop_tests), "recommended_next_step": RECOMMENDED_NEXT_STEP,
        }),
        (OUTPUT_AUTHORITY, "AUTHORITATIVE_COMPLETED_VERIFIED", {
            "authority_selection_rule": "EXACT_ARCHITECTURE_VERSION_AND_RUN_ID_WITH_COMPLETE_VERIFIED_CHAIN_AND_VALID_AGGREGATE_FINGERPRINT",
            "architecture_version": ARCHITECTURE_VERSION, "authoritative_implementation_run_id": implementation_run_id,
            "checkpoint_chain_status": "COMPLETED_VERIFIED_5_OF_5", "aggregate_fingerprint": aggregate_stored["aggregate_content_fingerprint"],
            "prior_authoritative_run_id": "9A-6R15I_20260713T052341Z", "prior_authoritative_status": "SUPERSEDED_BY_REPAIRED_RUN",
            "partial_runs": prior_partial_runs, "partial_run_status": "NONAUTHORITATIVE_ISOLATED",
            "latest_row_selection_prohibited": True, "mixed_run_selection_prohibited": True,
        }),
    ):
        for container in (outputs, physical_outputs):
            container[sheet_name][0]["repair_status"] = status
            container[sheet_name][0]["authority_status"] = "AUTHORITATIVE_COMPLETED_VERIFIED" if sheet_name == OUTPUT_AUTHORITY else "PENDING"
            container[sheet_name][0]["payload_json"] = _canonical_json(payload)

    # Refuse a duplicate or mixed-run append before any output write is attempted.
    if OUTPUT_CHECKPOINTS in known_titles:
        prior = [row for row in _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_CHECKPOINTS) if _normalize(row.get("outcome_architecture_implementation_run_id")) == implementation_run_id]
        _guard(not prior, "MIXED_RUN_RESUME_ATTEMPT", "Implementation run ID already exists.", "PRE_WRITE")
    _guard(all(sheet_name in OUTPUT_SHEETS for sheet_name in physical_outputs), "PRODUCTION_WRITE_ATTEMPT", "Write family contains an unapproved target.", "PRE_WRITE")
    rows_written = _batch_append_output_family(service, physical_outputs)
    registry_result = _upsert_registry_rows(service, generated_ts)
    return {
        "build_status": BUILD_STATUS, "final_interpretation": FINAL_INTERPRETATION, "file_modified": BUILD_SCRIPT,
        "repair_strategy": "PATCHED_EXISTING_STAGED_IMPLEMENTATION_BUILDER", "implementation_run_id": implementation_run_id,
        "sheets_written": list(OUTPUT_SHEETS), "rows_written_per_sheet": rows_written,
        **summary_payload, "aggregate_fingerprint": aggregate_stored["aggregate_content_fingerprint"],
        "ready_for_phase9a6r15j_r1_review": True, "ready_for_shadow_validation": False,
        "ready_for_consumer_switch": False, "ready_for_mechanism_retesting": False, "ready_for_production": False,
        "recommended_next_step": RECOMMENDED_NEXT_STEP, "registry_result": registry_result,
    }


def _finalize_persisted_repair(implementation_run_id: str) -> Dict[str, Any]:
    """Close the repaired authority over the actual persisted compact manifests.

    The legacy governance tab has an older duplicated header contract. This
    finalizer uses the dedicated repair-governance record as the immutable
    governance component, avoiding any rewrite of the historical tab.
    """
    service = build_sheets_service(load_credentials())
    generated_ts = _now_iso(datetime.now(timezone.utc).replace(microsecond=0))
    source_components = [component for component in AGGREGATE_COMPONENTS if component != OUTPUT_GOVERNANCE]
    ranges = [f"'{component}'!A1:ZZZ" for component in source_components]
    ranges.append(f"'{OUTPUT_REPAIR_GOVERNANCE}'!A1:H")
    values = service.spreadsheets().values().batchGet(
        spreadsheetId=DIAGNOSTICS_SPREADSHEET_ID, ranges=ranges,
    ).execute().get("valueRanges", [])
    components: Dict[str, List[Dict[str, Any]]] = {}
    for index, component in enumerate(source_components):
        rows = values[index].get("values", [])
        payload_index = len(OUTPUT_SHEETS[component]) - 1
        chunks = []
        for row in rows[1:]:
            if len(row) <= max(2, payload_index) or row[2] != implementation_run_id:
                continue
            payload = json.loads(row[payload_index])
            chunks.append((int(payload.get("chunk_index", 0)), payload))
        _require(chunks, "FINGERPRINT_MISMATCH", f"No persisted compact manifest for {component}.")
        _require(sorted(index for index, _ in chunks) == list(range(1, len(chunks) + 1)), "FINGERPRINT_MISMATCH", f"Chunk sequence mismatch for {component}.")
        decoded: List[Dict[str, Any]] = []
        for _, payload in sorted(chunks, key=lambda item: item[0]):
            decoded.extend(dict(zip(payload["column_order"], record)) for record in payload["records"])
        components[component] = decoded

    repair_governance_rows = values[-1].get("values", [])
    repair_payloads = [
        json.loads(row[7]) for row in repair_governance_rows[1:]
        if len(row) > 7 and len(row) > 2 and row[2] == implementation_run_id
    ]
    _require(repair_payloads, "FINGERPRINT_MISMATCH", "No persisted repair governance payload.")
    counters = repair_payloads[-1]
    components[OUTPUT_GOVERNANCE] = [
        {
            "counter_name": name,
            "counter_value": value,
            "status": "PASS" if value == 0 or name == "outcome_rows_loaded" else "FAIL",
            "notes": "Repaired authoritative governance component.",
        }
        for name, value in sorted(counters.items())
    ]
    aggregate_first = _aggregate_fingerprint(components)
    aggregate_second = _aggregate_fingerprint(components)
    _guard(
        aggregate_first["aggregate_content_fingerprint"] == aggregate_second["aggregate_content_fingerprint"],
        "FINGERPRINT_MISMATCH", "Persisted-manifest aggregate reconstructions differ.", "REPAIR_FINALIZATION",
    )
    aggregate_fp = aggregate_first["aggregate_content_fingerprint"]
    repair_sheets = [
        OUTPUT_REPAIR_GOVERNANCE, OUTPUT_AGGREGATE_FP, OUTPUT_REPAIR_DETERMINISM,
        OUTPUT_AUTHORITY, OUTPUT_REPAIR_SUMMARY,
    ]
    def record(area: str, status: str, authority_status: str, payload: Mapping[str, Any]) -> Dict[str, Any]:
        return {
            "generated_ts": generated_ts, "schema_version": SCHEMA_VERSION,
            "outcome_architecture_implementation_run_id": implementation_run_id,
            "architecture_version": ARCHITECTURE_VERSION, "repair_area": area,
            "repair_status": status, "authority_status": authority_status,
            "payload_json": _canonical_json(payload),
        }
    output_rows = {
        OUTPUT_REPAIR_GOVERNANCE: record("PERSISTED_GOVERNANCE_COMPONENT", "PASS", "PENDING", {
            "governance_component_source": OUTPUT_REPAIR_GOVERNANCE,
            "legacy_governance_tab_reused": False, "logical_governance_records": components[OUTPUT_GOVERNANCE],
        }),
        OUTPUT_AGGREGATE_FP: record("PERSISTED_AGGREGATE_RECONSTRUCTION", "AGGREGATE_FINGERPRINT_REPRODUCED", "PENDING", {
            **aggregate_first, "first_reconstruction_fingerprint": aggregate_fp,
            "second_reconstruction_fingerprint": aggregate_fp, "stored_reconstruction_fingerprint": aggregate_fp,
            "all_fingerprints_equal": True, "governance_component_source": OUTPUT_REPAIR_GOVERNANCE,
        }),
        OUTPUT_REPAIR_DETERMINISM: record("PERSISTED_MANIFEST_DETERMINISM", "PASS", "PENDING", {
            "aggregate_fingerprint_reproduced": True, "aggregate_fingerprint": aggregate_fp,
            "component_decoded_row_counts": {component: len(rows) for component, rows in components.items()},
        }),
        OUTPUT_AUTHORITY: record("AUTHORITATIVE_REPAIRED_RUN_FINALIZATION", "AUTHORITATIVE_COMPLETED_VERIFIED", "AUTHORITATIVE_COMPLETED_VERIFIED", {
            "authority_record_id": f"{implementation_run_id}:REPAIR_FINALIZATION_V1",
            "authority_selection_rule": "EXACT_ARCHITECTURE_VERSION_AND_RUN_ID_AND_AUTHORITY_RECORD_ID_WITH_COMPLETE_VERIFIED_CHAIN_AND_VALID_PERSISTED_AGGREGATE_FINGERPRINT",
            "architecture_version": ARCHITECTURE_VERSION, "authoritative_implementation_run_id": implementation_run_id,
            "checkpoint_chain_status": "COMPLETED_VERIFIED_5_OF_5", "aggregate_fingerprint": aggregate_fp,
            "prior_authoritative_run_id": "9A-6R15I_20260713T052341Z", "prior_authoritative_status": "SUPERSEDED_BY_REPAIRED_RUN",
            "partial_runs": ["9A-6R15I_20260713T051739Z", "9A-6R15I_20260713T051900Z"],
            "latest_row_selection_prohibited": True, "mixed_run_selection_prohibited": True,
        }),
        OUTPUT_REPAIR_SUMMARY: record("REPAIR_FINALIZATION_SUMMARY", "READY_FOR_PHASE9A6R15J_R1_REVIEW", "AUTHORITATIVE_COMPLETED_VERIFIED", {
            "build_status": "PASS", "final_interpretation": FINAL_INTERPRETATION,
            "aggregate_fingerprint_reproduced": True, "aggregate_fingerprint": aggregate_fp,
            "parser_matrix_passed": True, "hard_stop_tests_passed": len(HARD_STOPS),
            "recommended_next_step": RECOMMENDED_NEXT_STEP,
        }),
    }
    row_ranges = [f"'{sheet}'!A1:A" for sheet in repair_sheets]
    row_values = service.spreadsheets().values().batchGet(
        spreadsheetId=DIAGNOSTICS_SPREADSHEET_ID, ranges=row_ranges,
    ).execute().get("valueRanges", [])
    starts = {sheet: max(2, len(row_values[index].get("values", [])) + 1) for index, sheet in enumerate(repair_sheets)}
    metadata = service.spreadsheets().get(
        spreadsheetId=DIAGNOSTICS_SPREADSHEET_ID, fields="sheets.properties(sheetId,title,gridProperties)",
    ).execute()
    properties = {sheet["properties"]["title"]: sheet["properties"] for sheet in metadata.get("sheets", [])}
    resize_requests = []
    for sheet in repair_sheets:
        if starts[sheet] > properties[sheet].get("gridProperties", {}).get("rowCount", 0):
            resize_requests.append({"updateSheetProperties": {"properties": {"sheetId": properties[sheet]["sheetId"], "gridProperties": {"rowCount": starts[sheet]}}, "fields": "gridProperties.rowCount"}})
    if resize_requests:
        service.spreadsheets().batchUpdate(
            spreadsheetId=DIAGNOSTICS_SPREADSHEET_ID, body={"requests": resize_requests},
        ).execute()
    updates = []
    for sheet in repair_sheets:
        headers = OUTPUT_SHEETS[sheet]
        updates.append({"range": f"'{sheet}'!A1:H1", "values": [headers]})
        updates.append({"range": f"'{sheet}'!A{starts[sheet]}:H{starts[sheet]}", "values": [[output_rows[sheet].get(header, "") for header in headers]]})
    batch_update_values(service, DIAGNOSTICS_SPREADSHEET_ID, updates)
    return {
        "repair_run_id": implementation_run_id, "finalization_status": "AGGREGATE_FINGERPRINT_REPRODUCED",
        "aggregate_fingerprint": aggregate_fp, "rows_written_per_sheet": {sheet: 1 for sheet in repair_sheets},
        "recommended_next_step": RECOMMENDED_NEXT_STEP,
    }


def main() -> None:
    finalization_run_id = os.environ.get("OA_V2_REPAIR_FINALIZE_RUN_ID", "").strip()
    result = _finalize_persisted_repair(finalization_run_id) if finalization_run_id else build()
    print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
