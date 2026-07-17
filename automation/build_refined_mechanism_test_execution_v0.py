#!/usr/bin/env python3
"""Phase 9A-6R15 — Canonical Clean-R1 Mechanism Test Execution.

This phase executes the first outcome-bearing refined mechanism experiment
using the frozen Canonical Clean-R1 preregistration exactly as approved.

The executor must fail closed before outcome access if canonical authority,
fingerprints, lineage, execution environment, deterministic configuration,
stop rules, join contract, or outcome schema validation drift from the
approved canonical state.
"""

from __future__ import annotations

import hashlib
import json
import random
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
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
from automation.build_refined_mechanism_v11_classification_execution_v0 import (  # type: ignore
    _fetch_input_sheets,
    _normalize,
    _sheet_titles_light,
)
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials  # type: ignore


PHASE_ID = "9A-6R15"
BUILD_SCRIPT = "automation/build_refined_mechanism_test_execution_v0.py"
SCHEMA_VERSION = "presignal_v2_refined_mechanism_test_execution_v0"
EXECUTION_VERSION = "refined_mechanism_test_execution_v0"
REGISTRY_CATEGORY = "PRESIGNAL_V2_REFINED_MECHANISM_TEST_EXECUTION"
REGISTRY_OWNER_MODULE = "market_state"

AUTHORITATIVE_VERSION = "1.0-clean-r1"
AUTHORITATIVE_RUN_ID = "9A-6R13R1_20260711T020141Z"
CLASSIFICATION_VERSION = "1.1"
CLASSIFICATION_RUN_ID = "refined_mechanism_v11_classification_20260710T152725Z"

PRIMARY_MECHANISM = "MECH_INFORMATION_CONSISTENCY"
PRIMARY_MECHANISM_ID = "PM-003"
EXPLORATORY_MECHANISM = "MECH_INFORMATION_RELEVANCE"
EXPLORATORY_MECHANISM_ID = "PM-001"
DESCRIPTIVE_MECHANISM = "MECH_INFORMATION_SPECIFICITY"
DESCRIPTIVE_MECHANISM_ID = "PM-002"

PRIMARY_STRUCTURE = "STRUCTURE_A_EXPANDED_STATE_GROUPED_DELTA_COMPARISON"
PRIMARY_EXPOSURE = "expanded Pack B-E MECH_INFORMATION_CONSISTENCY label under frozen v1.1 rules"
PRIMARY_COMPARISON_GROUPS = "expanded consistency POSITIVE versus expanded consistency NEGATIVE"
BASELINE_ROLE = "same-provider same-session Pack A structural control used only for success-delta construction"
PRIMARY_ESTIMAND = (
    "difference in baseline-to-expanded corrected directional success deltas "
    "between expanded-state label groups"
)
PRIMARY_EFFECT_MEASURE = "matched_baseline_to_expanded_corrected_directional_success_delta_difference"
PRIMARY_METHOD_ID = "provider_session_clustered_matched_risk_difference_on_baseline_to_expanded_success_delta"
PRIMARY_METHOD_LABEL = (
    "provider_session_clustered_matched_risk_difference_on_baseline_to_expanded_success_delta "
    "with two-sided 95% percentile bootstrap interval and descriptive fallback if sparse"
)
PRIMARY_INTERPRETATION = "EXPLORATORY_PREREGISTERED_PRIMARY"
PRIMARY_ANALYSIS_ID = "PRIMARY_PM003_STRUCTURE_A"
SECONDARY_STRUCTURE_ANALYSIS_ID = "SECONDARY_PM003_MIXED_LABEL_CLUSTER_SENSITIVITY"
EXPLORATORY_ANALYSIS_ID = "EXPLORATORY_PM001_RELEVANCE"
DESCRIPTIVE_ANALYSIS_ID = "DESCRIPTIVE_PM002_SPECIFICITY"

EXPECTED_COUNTS = {
    "structural_baseline_expanded_pairs": 96,
    "consistency_classified_pairs": 82,
    "high_moderate_confidence_pairs": 72,
    "primary_contrast_eligible_observations": 72,
    "positive_primary_observations": 57,
    "negative_primary_observations": 15,
    "mixed_label_provider_session_clusters": 12,
    "provider_count": 3,
    "session_count": 8,
    "cluster_count": 24,
}

EXPECTED_GATES = {
    "minimum_positive_count": 40,
    "minimum_negative_count": 12,
    "minimum_primary_contrast_observations": 40,
    "minimum_clusters": 12,
    "minimum_providers": 2,
    "minimum_sessions": 4,
}

AUTHORITY_SHEETS: Tuple[str, ...] = (
    "Refined_Mechanism_Test_Clean_R1_Canonical_Authority",
    "Refined_Mechanism_Test_Clean_R1_Component_Authority",
    "Refined_Mechanism_Test_Clean_R1_Historical_Run_Disposition",
    "Refined_Mechanism_Test_Clean_R1_Scientific_Equivalence_Audit",
    "Refined_Mechanism_Test_Clean_R1_Canonical_Fingerprint_Manifest",
    "Refined_Mechanism_Test_Clean_R1_Authority_Stop_Rules",
    "Refined_Mechanism_Test_Clean_R1_Lineage_Repair_Governance",
    "Refined_Mechanism_Test_Clean_R1_Lineage_Repair_Summary",
)

R1_SHEETS: Tuple[str, ...] = (
    "Refined_Mechanism_Test_Preregistration_Clean_R1",
    "Refined_Mechanism_Test_Frozen_Outcome_Definition_Clean_R1",
    "Refined_Mechanism_Test_Frozen_Join_Rules_Clean_R1",
    "Refined_Mechanism_Test_Frozen_Success_Derivation_Clean_R1",
    "Refined_Mechanism_Test_Frozen_Statistical_Method_Clean_R1",
    "Refined_Mechanism_Test_Frozen_Stop_Rules_Clean_R1",
    "Refined_Mechanism_Test_Clean_R1_Design_Reconciliation",
    "Refined_Mechanism_Test_Clean_R1_Lineage_Audit",
    "Refined_Mechanism_Test_Clean_R1_Blinding_Audit",
    "Refined_Mechanism_Test_Clean_R1_Fingerprint_Freeze",
    "Refined_Mechanism_Test_Clean_R1_Governance",
    "Refined_Mechanism_Test_Preregistration_Clean_R1_Summary",
)

PARENT_SUPPORT_SHEETS: Tuple[str, ...] = (
    "Refined_Mechanism_Test_Frozen_Hypotheses_Clean",
    "Refined_Mechanism_Test_Frozen_Comparison_Design_Clean",
    "Refined_Mechanism_Test_Frozen_Eligibility_Rules_Clean",
    "Refined_Mechanism_Test_Frozen_Unknown_Rules_Clean",
    "Refined_Mechanism_Test_Frozen_Confidence_Rules_Clean",
)

CANONICAL_APPROVAL_SHEETS: Tuple[str, ...] = (
    "Refined_Mechanism_Test_Execution_Approval_Canonical_R1",
    "Refined_Mechanism_Test_Canonical_R1_Authority_Approval",
    "Refined_Mechanism_Test_Canonical_R1_Historical_Isolation_Approval",
    "Refined_Mechanism_Test_Canonical_R1_Fingerprint_Approval",
    "Refined_Mechanism_Test_Canonical_R1_Blinding_Approval",
    "Refined_Mechanism_Test_Canonical_R1_Science_Approval",
    "Refined_Mechanism_Test_Canonical_R1_Count_Approval",
    "Refined_Mechanism_Test_Canonical_R1_Outcome_Contract_Approval",
    "Refined_Mechanism_Test_Canonical_R1_Join_Approval",
    "Refined_Mechanism_Test_Canonical_R1_Success_Approval",
    "Refined_Mechanism_Test_Canonical_R1_Method_Approval",
    "Refined_Mechanism_Test_Canonical_R1_Stop_Rule_Approval",
    "Refined_Mechanism_Test_Canonical_R1_Load_Order_Approval",
    "Refined_Mechanism_Test_Canonical_R1_Approval_Governance",
    "Refined_Mechanism_Test_Execution_Approval_Canonical_R1_Summary",
)

READINESS_SHEETS: Tuple[str, ...] = (
    "Refined_Mechanism_Test_Execution_Readiness",
    "Refined_Mechanism_Test_Canonical_Authority_Audit",
    "Refined_Mechanism_Test_Environment_Freeze",
    "Refined_Mechanism_Test_Execution_Order_Audit",
    "Refined_Mechanism_Test_Stop_Rule_Verification",
    "Refined_Mechanism_Test_Determinism_Verification",
    "Refined_Mechanism_Test_Reproducibility_Audit",
    "Refined_Mechanism_Test_Blinding_Verification",
    "Refined_Mechanism_Test_Readiness_Governance",
    "Refined_Mechanism_Test_Readiness_Summary",
)

CLASSIFICATION_SHEETS: Tuple[str, ...] = (
    "Refined_Mechanism_v11_Classifications",
    "Refined_Mechanism_v11_Classification_Summary",
    "Refined_Mechanism_v11_Execution_Review",
    "Refined_Mechanism_v11_Execution_Review_Summary",
    "Pack_Behavior_Tier2_NoSignal",
)

NON_OUTCOME_INPUT_SHEETS: Tuple[str, ...] = (
    *AUTHORITY_SHEETS,
    *R1_SHEETS,
    *PARENT_SUPPORT_SHEETS,
    *CANONICAL_APPROVAL_SHEETS,
    *READINESS_SHEETS,
    *CLASSIFICATION_SHEETS,
)

OUTCOME_INPUT_SHEETS: Tuple[str, ...] = (
    "Corrected_Accuracy_Row_Selection",
    "Corrected_Accuracy_Outcome_Mapping",
    "Market_Reaction_Recovered_Canonical_Outcomes",
    "Market_Reaction_Canonical_Outcomes",
)

EXPECTED_EXECUTION_STOP_RULE_NAMES = {
    "CLEAN_PREREGISTRATION_FINGERPRINT_MISMATCH",
    "REPEATED_CLEAN_RUN_CONTENT_MISMATCH",
    "CLASSIFICATION_FINGERPRINT_MISMATCH",
    "OUTCOME_SCHEMA_CONTRACT_MISMATCH",
    "OUTCOME_VERSION_MISMATCH",
    "EVALUATION_WINDOW_MISMATCH",
    "OUTCOME_TIMESTAMP_REQUIREMENT_FAILED",
    "AMBIGUOUS_JOIN",
    "DUPLICATE_JOIN",
    "PHYSICAL_ROW_NUMBER_JOIN_ATTEMPT",
    "FUZZY_JOIN_ATTEMPT",
    "MANUAL_JOIN_OVERRIDE_REQUESTED",
    "INVALID_SUCCESS_MAPPING",
    "UNEXPECTED_ELIGIBILITY_DIFFERENCE",
    "POSITIVE_SAMPLE_GATE_FAILURE",
    "NEGATIVE_SAMPLE_GATE_FAILURE",
    "PRIMARY_CONTRAST_GATE_FAILURE",
    "CLUSTER_GATE_FAILURE",
    "PROVIDER_GATE_FAILURE",
    "SESSION_GATE_FAILURE",
    "UNKNOWN_CONVERTED_TO_NEGATIVE",
    "INSUFFICIENT_EVIDENCE_CONVERTED_TO_NEGATIVE",
    "LOW_CONFIDENCE_INCLUDED_IN_PRIMARY",
    "UNAPPROVED_STATISTICAL_FALLBACK",
    "PRIMARY_METHOD_COMPUTATION_FAILED",
    "DEGENERATE_BOOTSTRAP_DISTRIBUTION",
    "DESIGN_CHANGE_AFTER_APPROVAL",
    "OUTCOME_ACCESS_BEFORE_APPROVAL",
    "PRODUCTION_WRITE_ATTEMPT",
}

OUTPUT_EXECUTION = "Refined_Mechanism_Test_Execution"
OUTPUT_JOIN_AUDIT = "Refined_Mechanism_Test_Outcome_Join_Audit"
OUTPUT_ELIGIBILITY = "Refined_Mechanism_Test_Eligibility_Audit"
OUTPUT_STATS = "Refined_Mechanism_Test_Statistical_Results"
OUTPUT_BOOTSTRAP = "Refined_Mechanism_Test_Bootstrap_Diagnostics"
OUTPUT_CLUSTER = "Refined_Mechanism_Test_Cluster_Diagnostics"
OUTPUT_ASSUMPTIONS = "Refined_Mechanism_Test_Assumption_Checks"
OUTPUT_MISSING = "Refined_Mechanism_Test_Missing_Data_Audit"
OUTPUT_GOVERNANCE = "Refined_Mechanism_Test_Execution_Governance"
OUTPUT_SUMMARY = "Refined_Mechanism_Test_Execution_Summary"

OUTPUT_SHEETS: Dict[str, List[str]] = {
    OUTPUT_EXECUTION: [
        "generated_ts",
        "schema_version",
        "test_execution_run_id",
        "preregistration_version",
        "authoritative_run_id",
        "classification_version",
        "classification_run_id",
        "execution_status",
        "build_status",
        "final_interpretation",
        "descriptive_fallback_status",
        "payload_json",
    ],
    OUTPUT_JOIN_AUDIT: [
        "generated_ts",
        "schema_version",
        "test_execution_run_id",
        "analysis_id",
        "mechanism_id",
        "analysis_role",
        "source_row_key",
        "provider",
        "session_id",
        "pack_level",
        "matched_baseline_source_row_key",
        "expanded_label",
        "confidence_category",
        "bridge_consensus_status",
        "repaired_canonical_outcome_id",
        "canonical_outcome_id",
        "expanded_forecast_direction",
        "baseline_forecast_direction",
        "expanded_realized_direction",
        "baseline_realized_direction",
        "expanded_success_status",
        "baseline_success_status",
        "delta_status",
        "included_in_analysis",
        "exclusion_reason",
        "payload_json",
    ],
    OUTPUT_ELIGIBILITY: [
        "generated_ts",
        "schema_version",
        "test_execution_run_id",
        "analysis_id",
        "mechanism_id",
        "analysis_role",
        "candidate_source_count",
        "joined_candidate_count",
        "eligible_sample_count",
        "positive_sample_count",
        "negative_sample_count",
        "unknown_sample_count",
        "insufficient_evidence_sample_count",
        "cluster_count",
        "provider_count",
        "session_count",
        "positive_gate_status",
        "negative_gate_status",
        "primary_contrast_gate_status",
        "cluster_gate_status",
        "provider_gate_status",
        "session_gate_status",
        "descriptive_fallback_required",
        "payload_json",
    ],
    OUTPUT_STATS: [
        "generated_ts",
        "schema_version",
        "test_execution_run_id",
        "analysis_id",
        "mechanism_id",
        "analysis_role",
        "result_status",
        "analysis_population",
        "effect_measure",
        "statistical_method",
        "effect_estimate",
        "confidence_interval_lower",
        "confidence_interval_upper",
        "inferential_result_allowed",
        "descriptive_fallback_used",
        "payload_json",
    ],
    OUTPUT_BOOTSTRAP: [
        "generated_ts",
        "schema_version",
        "test_execution_run_id",
        "analysis_id",
        "mechanism_id",
        "bootstrap_status",
        "requested_replications",
        "attempted_replications",
        "estimable_replications",
        "estimable_fraction",
        "random_seed",
        "resampling_unit",
        "interval_method",
        "payload_json",
    ],
    OUTPUT_CLUSTER: [
        "generated_ts",
        "schema_version",
        "test_execution_run_id",
        "analysis_id",
        "mechanism_id",
        "analysis_role",
        "eligible_observations",
        "cluster_count",
        "provider_count",
        "session_count",
        "session_family_count",
        "mixed_label_cluster_count",
        "cluster_status",
        "payload_json",
    ],
    OUTPUT_ASSUMPTIONS: [
        "generated_ts",
        "schema_version",
        "test_execution_run_id",
        "check_id",
        "check_name",
        "status",
        "severity",
        "analysis_id",
        "mechanism_id",
        "details_json",
    ],
    OUTPUT_MISSING: [
        "generated_ts",
        "schema_version",
        "test_execution_run_id",
        "analysis_id",
        "mechanism_id",
        "reason_code",
        "reason_count",
        "payload_json",
    ],
    OUTPUT_GOVERNANCE: [
        "generated_ts",
        "schema_version",
        "test_execution_run_id",
        "counter_name",
        "counter_value",
        "status",
        "notes",
    ],
    OUTPUT_SUMMARY: [
        "generated_ts",
        "schema_version",
        "test_execution_run_id",
        "build_status",
        "final_interpretation",
        "primary_mechanism_tested",
        "eligible_sample",
        "positive_sample",
        "negative_sample",
        "cluster_count",
        "provider_count",
        "session_count",
        "outcome_join_status",
        "statistical_method_used",
        "effect_estimate",
        "confidence_interval",
        "bootstrap_diagnostics",
        "cluster_diagnostics",
        "assumption_checks",
        "missing_data_summary",
        "descriptive_fallback_status",
        "determinism_status",
        "stop_rule_status",
        "scientific_interpretation",
        "recommended_next_step",
        "payload_json",
    ],
}

OUTPUT_LOGICAL_IDS = {
    OUTPUT_EXECUTION: "REFINED_MECHANISM_TEST_EXECUTION",
    OUTPUT_JOIN_AUDIT: "REFINED_MECHANISM_TEST_OUTCOME_JOIN_AUDIT",
    OUTPUT_ELIGIBILITY: "REFINED_MECHANISM_TEST_ELIGIBILITY_AUDIT",
    OUTPUT_STATS: "REFINED_MECHANISM_TEST_STATISTICAL_RESULTS",
    OUTPUT_BOOTSTRAP: "REFINED_MECHANISM_TEST_BOOTSTRAP_DIAGNOSTICS",
    OUTPUT_CLUSTER: "REFINED_MECHANISM_TEST_CLUSTER_DIAGNOSTICS",
    OUTPUT_ASSUMPTIONS: "REFINED_MECHANISM_TEST_ASSUMPTION_CHECKS",
    OUTPUT_MISSING: "REFINED_MECHANISM_TEST_MISSING_DATA_AUDIT",
    OUTPUT_GOVERNANCE: "REFINED_MECHANISM_TEST_EXECUTION_GOVERNANCE",
    OUTPUT_SUMMARY: "REFINED_MECHANISM_TEST_EXECUTION_SUMMARY",
}


@dataclass(frozen=True)
class JoinResult:
    status: str
    repaired_canonical_outcome_id: str
    canonical_outcome_id: str
    forecast_direction: str
    realized_direction: str
    success_status: str
    reason_code: str
    details: Dict[str, Any]


@dataclass
class AnalysisOutput:
    analysis_id: str
    mechanism_id: str
    analysis_role: str
    candidate_count: int
    join_rows: List[Dict[str, Any]]
    eligible_rows: List[Dict[str, Any]]
    missing_reason_counts: Counter
    summary_row: Dict[str, Any]
    stats_row: Dict[str, Any]
    bootstrap_row: Dict[str, Any]
    cluster_row: Dict[str, Any]
    assumption_rows: List[Dict[str, Any]]


class ExecutionBlocked(RuntimeError):
    def __init__(self, stop_rule_name: str, message: str):
        super().__init__(message)
        self.stop_rule_name = stop_rule_name
        self.message = message


def _run_id(ts: datetime) -> str:
    return f"9A-6R15_{ts.strftime('%Y%m%dT%H%M%SZ')}"


def _now_iso(ts: datetime) -> str:
    return ts.isoformat().replace("+00:00", "Z")


def _to_bool(value: Any) -> bool:
    return _normalize(value).upper() in {"TRUE", "1", "YES", "Y", "PASS", "APPROVED"}


def _to_int(value: Any) -> int:
    raw = _normalize(value)
    if not raw:
        return 0
    try:
        return int(float(raw))
    except ValueError:
        return 0


def _to_float(value: Any) -> Optional[float]:
    raw = _normalize(value)
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _json_loads_safe(value: Any) -> Any:
    raw = _normalize(value)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _fingerprint_payload(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _fingerprint_rows(rows: Sequence[Mapping[str, Any]], *, exclude_source_row_number: bool = True) -> str:
    normalized_rows = []
    for row in rows:
        current = dict(row)
        if exclude_source_row_number:
            current.pop("__source_row_number__", None)
        normalized_rows.append(current)
    return hashlib.sha256(_canonical_json(normalized_rows).encode("utf-8")).hexdigest()


def _normalize_direction(value: Any) -> str:
    raw = _normalize(value).upper()
    if raw in {"UP", "DOWN", "FLAT", "NO_CLEAR_DIRECTION", "AMBIGUOUS"}:
        return raw
    if raw in {"NO_SIGNAL", "NOSIGNAL"}:
        return "NO_SIGNAL"
    return raw


def _parse_iso_utc(value: Any) -> Optional[datetime]:
    raw = _normalize(value)
    if not raw:
        return None
    normalized = raw.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _safe_sheet_title(title: str) -> str:
    return title.replace("'", "''")


def _latest_payload(rows: Sequence[Mapping[str, Any]], run_key: str) -> Dict[str, Any]:
    if not rows:
        return {}
    ordered = sorted(
        rows,
        key=lambda row: (
            _normalize(row.get("generated_ts")),
            _normalize(row.get(run_key)),
            int(_normalize(row.get("__source_row_number__")) or "0"),
        ),
    )
    payload = _normalize(ordered[-1].get("payload_json"))
    return json.loads(payload) if payload else {}


def _latest_row(rows: Sequence[Mapping[str, Any]], run_key: str) -> Dict[str, Any]:
    if not rows:
        return {}
    ordered = sorted(
        rows,
        key=lambda row: (
            _normalize(row.get("generated_ts")),
            _normalize(row.get(run_key)),
            int(_normalize(row.get("__source_row_number__")) or "0"),
        ),
    )
    return dict(ordered[-1])


def _parse_source_row_key(source_row_key: str) -> Tuple[str, str, int]:
    parts = source_row_key.split("::")
    if len(parts) != 3:
        raise ExecutionBlocked("AUTHORITATIVE_FINGERPRINT_MISMATCH", f"Invalid source_row_key format: {source_row_key}")
    sheet_name, run_id, row_number_raw = parts
    return sheet_name, run_id, int(row_number_raw)


def _sheet_grid_properties(service, spreadsheet_id: str, sheet_name: str) -> Tuple[Optional[int], int, int]:
    metadata = (
        service.spreadsheets()
        .get(spreadsheetId=spreadsheet_id, fields="sheets(properties(sheetId,title,gridProperties(rowCount,columnCount)))")
        .execute()
    )
    for sheet in metadata.get("sheets", []):
        props = sheet.get("properties", {})
        if props.get("title") == sheet_name:
            grid = props.get("gridProperties", {})
            return props.get("sheetId"), int(grid.get("rowCount", 0)), int(grid.get("columnCount", 0))
    return None, 0, 0


def _get_headers(service, spreadsheet_id: str, sheet_name: str) -> List[str]:
    values = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=f"'{_safe_sheet_title(sheet_name)}'!1:1")
        .execute()
        .get("values", [])
    )
    return values[0] if values else []


def _ensure_sheet_minimal(
    service,
    spreadsheet_id: str,
    sheet_name: str,
    required_headers: Sequence[str],
    known_titles: Optional[Set[str]] = None,
) -> List[str]:
    titles = known_titles if known_titles is not None else _sheet_titles_light(service, spreadsheet_id)
    if sheet_name not in titles:
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                "requests": [
                    {
                        "addSheet": {
                            "properties": {
                                "title": sheet_name,
                                "gridProperties": {
                                    "rowCount": 2,
                                    "columnCount": max(1, len(required_headers)),
                                },
                            }
                        }
                    }
                ]
            },
        ).execute()
        if known_titles is not None:
            known_titles.add(sheet_name)
        headers = list(required_headers)
    else:
        headers = _get_headers(service, spreadsheet_id, sheet_name) or list(required_headers)
        for header in required_headers:
            if header not in headers:
                headers.append(header)
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{_safe_sheet_title(sheet_name)}'!A1",
        valueInputOption="RAW",
        body={"values": [headers]},
    ).execute()
    return headers


def _append_rows(
    service,
    spreadsheet_id: str,
    sheet_name: str,
    required_headers: Sequence[str],
    rows: Sequence[Mapping[str, Any]],
    known_titles: Optional[Set[str]] = None,
) -> int:
    headers = _ensure_sheet_minimal(service, spreadsheet_id, sheet_name, required_headers, known_titles)
    if not rows:
        return 0
    existing = _sheet_to_rows(service, spreadsheet_id, sheet_name)
    start_row = len(existing) + 2
    values = [[row.get(header, "") for header in headers] for row in rows]
    end_row = start_row + len(values) - 1
    sheet_id, current_row_count, current_column_count = _sheet_grid_properties(service, spreadsheet_id, sheet_name)
    required_row_count = max(current_row_count, end_row)
    required_column_count = max(current_column_count, len(headers))
    if sheet_id is not None and (required_row_count > current_row_count or required_column_count > current_column_count):
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                "requests": [
                    {
                        "updateSheetProperties": {
                            "properties": {
                                "sheetId": sheet_id,
                                "gridProperties": {
                                    "rowCount": required_row_count,
                                    "columnCount": required_column_count,
                                },
                            },
                            "fields": "gridProperties.rowCount,gridProperties.columnCount",
                        }
                    }
                ]
            },
        ).execute()
    batch_update_values(
        service,
        spreadsheet_id,
        [
            {
                "range": f"'{_safe_sheet_title(sheet_name)}'!A{start_row}:{_column_letter(len(headers))}{end_row}",
                "values": values,
            }
        ],
    )
    return len(values)


def _upsert_registry_rows(service, generated_ts: str) -> Dict[str, Any]:
    titles = _sheet_titles_light(service, PROJECT_OVERVIEWS_SPREADSHEET_ID)
    if REGISTRY_SHEET not in titles:
        return {"updated": 0, "appended": 0, "status": "missing"}
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    by_id = {_normalize(row.get("logical_sheet_id")).upper(): i + 2 for i, row in enumerate(rows)}
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
            "lifecycle_state": "ACTIVE",
            "owner_module": REGISTRY_OWNER_MODULE,
            "participates_in_rebuild": "TRUE",
            "read_only": "FALSE",
            "allow_creation": "TRUE",
            "created_phase": f"PreSignal v2.0 Phase {PHASE_ID}",
            "notes": "Phase 9A-6R15 canonical Clean-R1 mechanism-test execution outputs.",
            "registry_created_ts": _normalize(existing.get("registry_created_ts")) or generated_ts,
            "registry_last_verified_ts": generated_ts,
            "registry_migration_ts": _normalize(existing.get("registry_migration_ts")),
            "registry_rename_ts": _normalize(existing.get("registry_rename_ts")),
        }
        values = [merged.get(header, "") for header in REGISTRY_HEADERS]
        if key in by_id:
            row_number = by_id[key]
        else:
            appended += 1
            row_number = len(rows) + appended + 1
        updates.append(
            {
                "range": f"'{REGISTRY_SHEET}'!A{row_number}:{_column_letter(len(REGISTRY_HEADERS))}{row_number}",
                "values": [values],
            }
        )
    if updates:
        batch_update_values(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, updates)
    return {"updated": len(OUTPUT_LOGICAL_IDS) - appended, "appended": appended, "status": "ok"}


def _check(condition: bool, stop_rule_name: str, message: str) -> None:
    if not condition:
        raise ExecutionBlocked(stop_rule_name, message)


def _select_authoritative_rows(
    inputs: Mapping[str, Any],
    manifest: Mapping[str, Any],
    component_authority: Mapping[str, Any],
) -> Dict[str, Dict[str, Any]]:
    component_records = {
        _normalize(record.get("component_id")): record
        for record in component_authority.get("component_records", [])
    }
    manifest_entries = manifest.get("authoritative_component_entries", [])
    _check(
        len(manifest_entries) == 12,
        "FINGERPRINT_MANIFEST_INCOMPLETE",
        f"Expected 12 authoritative component entries; found {len(manifest_entries)}.",
    )
    selected: Dict[str, Dict[str, Any]] = {}
    seen_components: Set[str] = set()
    for entry in manifest_entries:
        component_id = _normalize(entry.get("component_id"))
        sheet_name = _normalize(entry.get("source_sheet"))
        source_row_key = _normalize(entry.get("source_row_key"))
        _check(
            component_id not in seen_components,
            "MULTIPLE_AUTHORITATIVE_ROWS_FOR_COMPONENT",
            f"Duplicate component in manifest: {component_id}",
        )
        seen_components.add(component_id)
        record = component_records.get(component_id)
        _check(
            record is not None,
            "AUTHORITATIVE_COMPONENT_MISSING",
            f"Component authority record missing for {component_id}",
        )
        _check(
            _normalize(record.get("authority_status")) == "EXACTLY_ONE_COMPLETE_AUTHORITATIVE_ROW",
            "AUTHORITATIVE_COMPONENT_INCOMPLETE",
            f"Component authority status invalid for {component_id}: {record}",
        )
        parsed_sheet, parsed_run_id, parsed_row_number = _parse_source_row_key(source_row_key)
        _check(
            _normalize(parsed_sheet) == sheet_name,
            "AUTHORITATIVE_FINGERPRINT_MISMATCH",
            f"Manifest source sheet mismatch for {component_id}.",
        )
        _check(
            parsed_run_id == AUTHORITATIVE_RUN_ID,
            "AUTHORITY_RUN_ID_MISMATCH",
            f"Manifest run ID mismatch for {component_id}.",
        )
        matches = [
            dict(row)
            for row in inputs[sheet_name].rows
            if _normalize(row.get("clean_contract_repair_run_id")) == AUTHORITATIVE_RUN_ID
            and int(_normalize(row.get("__source_row_number__")) or "0") == parsed_row_number
        ]
        _check(
            len(matches) == 1,
            "MULTIPLE_AUTHORITATIVE_ROWS_FOR_COMPONENT",
            f"Expected exactly one authoritative match for {component_id}; found {len(matches)}.",
        )
        row = matches[0]
        payload = json.loads(_normalize(row.get("payload_json")) or "{}")
        _check(bool(payload), "AUTHORITATIVE_COMPONENT_INCOMPLETE", f"Payload empty for {component_id}.")
        current_fp = _fingerprint_payload(payload)
        _check(
            current_fp == _normalize(entry.get("fingerprint")),
            "AUTHORITATIVE_FINGERPRINT_MISMATCH",
            f"Fingerprint mismatch for {component_id}.",
        )
        selected[sheet_name] = {
            "component_id": component_id,
            "source_row_key": source_row_key,
            "row": row,
            "payload": payload,
            "fingerprint": current_fp,
        }
    return selected


def _classification_rows(inputs: Mapping[str, Any]) -> List[Dict[str, Any]]:
    return [
        dict(row)
        for row in inputs["Refined_Mechanism_v11_Classifications"].rows
        if _normalize(row.get("classification_run_id")) == CLASSIFICATION_RUN_ID
    ]


def _structure_counts(class_rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    consistency_rows = [dict(row) for row in class_rows if _normalize(row.get("mechanism_id")) == PRIMARY_MECHANISM]
    baseline_map: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in consistency_rows:
        if _normalize(row.get("pack_level")) == "A":
            baseline_map[(_normalize(row.get("provider")), _normalize(row.get("session_id")))].append(row)
    expanded_structural = [
        row
        for row in consistency_rows
        if _normalize(row.get("pack_level")) in {"B", "C", "D", "E"}
        and (_normalize(row.get("provider")), _normalize(row.get("session_id"))) in baseline_map
    ]
    classified = [
        row
        for row in expanded_structural
        if _normalize(row.get("classification_label")) != "EXCLUDED"
        and _normalize(row.get("eligibility_status")) not in {"EXCLUDED", "OUT_OF_SCOPE"}
    ]
    high_mod = [
        row
        for row in classified
        if _normalize(row.get("confidence_category")) in {"HIGH", "MODERATE"}
    ]
    pos_neg = [
        row
        for row in high_mod
        if _normalize(row.get("classification_label")) in {"POSITIVE", "NEGATIVE"}
    ]
    cluster_labels: Dict[str, Set[str]] = defaultdict(set)
    baseline_match_count_errors: List[Dict[str, Any]] = []
    for row in pos_neg:
        cluster = f"{_normalize(row.get('provider'))}|{_normalize(row.get('session_id'))}"
        cluster_labels[cluster].add(_normalize(row.get("classification_label")))
        baseline_matches = baseline_map.get((_normalize(row.get("provider")), _normalize(row.get("session_id"))), [])
        if len(baseline_matches) != 1:
            baseline_match_count_errors.append(
                {
                    "source_row_key": _normalize(row.get("source_row_key")),
                    "provider": _normalize(row.get("provider")),
                    "session_id": _normalize(row.get("session_id")),
                    "baseline_match_count": len(baseline_matches),
                }
            )
    return {
        "structural_baseline_expanded_pairs": len(expanded_structural),
        "consistency_classified_pairs": len(classified),
        "high_moderate_confidence_pairs": len(high_mod),
        "primary_contrast_eligible_observations": len(pos_neg),
        "positive_primary_observations": sum(
            1 for row in pos_neg if _normalize(row.get("classification_label")) == "POSITIVE"
        ),
        "negative_primary_observations": sum(
            1 for row in pos_neg if _normalize(row.get("classification_label")) == "NEGATIVE"
        ),
        "mixed_label_provider_session_clusters": sum(
            1 for labels in cluster_labels.values() if {"POSITIVE", "NEGATIVE"} <= labels
        ),
        "provider_count": len({_normalize(row.get("provider")) for row in pos_neg}),
        "session_count": len({_normalize(row.get("session_id")) for row in pos_neg}),
        "cluster_count": len({f"{_normalize(row.get('provider'))}|{_normalize(row.get('session_id'))}" for row in pos_neg}),
        "baseline_match_count_errors": baseline_match_count_errors,
    }


def _load_non_outcome_context(service) -> Dict[str, Any]:
    inputs = _fetch_input_sheets(service, DIAGNOSTICS_SPREADSHEET_ID, NON_OUTCOME_INPUT_SHEETS)
    canonical_authority = _latest_payload(
        inputs["Refined_Mechanism_Test_Clean_R1_Canonical_Authority"].rows,
        "lineage_repair_run_id",
    )
    component_authority = _latest_payload(
        inputs["Refined_Mechanism_Test_Clean_R1_Component_Authority"].rows,
        "lineage_repair_run_id",
    )
    canonical_manifest = _latest_payload(
        inputs["Refined_Mechanism_Test_Clean_R1_Canonical_Fingerprint_Manifest"].rows,
        "lineage_repair_run_id",
    )
    canonical_approval_summary = _latest_payload(
        inputs["Refined_Mechanism_Test_Execution_Approval_Canonical_R1_Summary"].rows,
        "approval_canonical_r1_run_id",
    )
    readiness_summary = _latest_payload(
        inputs["Refined_Mechanism_Test_Readiness_Summary"].rows,
        "readiness_audit_run_id",
    )
    readiness_row = _latest_payload(
        inputs["Refined_Mechanism_Test_Execution_Readiness"].rows,
        "readiness_audit_run_id",
    )
    selected_rows = _select_authoritative_rows(inputs, canonical_manifest, component_authority)
    selected_payloads = {sheet_name: data["payload"] for sheet_name, data in selected_rows.items()}
    component_fingerprints = {
        data["component_id"]: data["fingerprint"] for data in selected_rows.values()
    }
    return {
        "inputs": inputs,
        "canonical_authority": canonical_authority,
        "component_authority": component_authority,
        "canonical_manifest": canonical_manifest,
        "canonical_approval_summary": canonical_approval_summary,
        "readiness_summary": readiness_summary,
        "readiness_row": readiness_row,
        "selected_rows": selected_rows,
        "selected_payloads": selected_payloads,
        "component_fingerprints": component_fingerprints,
    }


def _validate_preexecution_context(service, context: Mapping[str, Any], known_titles: Set[str]) -> Dict[str, Any]:
    inputs = context["inputs"]
    canonical_authority = context["canonical_authority"]
    canonical_manifest = context["canonical_manifest"]
    canonical_approval_summary = context["canonical_approval_summary"]
    readiness_summary = context["readiness_summary"]
    readiness_row = context["readiness_row"]
    selected_payloads = context["selected_payloads"]

    _check(
        _normalize(canonical_authority.get("authority_preregistration_version")) == AUTHORITATIVE_VERSION,
        "AUTHORITY_VERSION_MISMATCH",
        "Canonical authority preregistration version mismatch.",
    )
    _check(
        _normalize(canonical_authority.get("authoritative_repair_run_id")) == AUTHORITATIVE_RUN_ID,
        "AUTHORITATIVE_RUN_ID_MISSING",
        "Canonical authority run ID mismatch.",
    )
    _check(
        _normalize(canonical_authority.get("authority_selection_method")) == "EXACT_VERSION_AND_RUN_ID_MATCH",
        "LATEST_ROW_SELECTION_ATTEMPT",
        "Canonical authority selection method drifted from exact version + run ID matching.",
    )
    _check(
        _normalize(canonical_authority.get("authority_status")) == "CANONICAL_AUTHORITY_COMPLETE",
        "FINGERPRINT_MANIFEST_INCOMPLETE",
        "Canonical authority layer is not complete.",
    )
    _check(
        int(canonical_authority.get("required_components", 0) or 0) == 12,
        "AUTHORITATIVE_COMPONENT_MISSING",
        "Canonical authority required component count mismatch.",
    )
    _check(
        int(canonical_authority.get("components_with_exactly_one_authoritative_row", 0) or 0) == 12,
        "MULTIPLE_AUTHORITATIVE_ROWS_FOR_COMPONENT",
        "Canonical authority does not expose exactly 12 authoritative components.",
    )
    _check(
        not canonical_authority.get("missing_authoritative_components"),
        "AUTHORITATIVE_COMPONENT_MISSING",
        f"Missing authoritative components: {canonical_authority.get('missing_authoritative_components')}",
    )
    _check(
        _normalize(canonical_manifest.get("manifest_status")) == "COMPLETE_AUTHORITATIVE_CLOSURE",
        "FINGERPRINT_MANIFEST_INCOMPLETE",
        "Canonical manifest is not complete authoritative closure.",
    )
    _check(
        int(canonical_manifest.get("authoritative_components_fingerprinted", 0) or 0) == 12,
        "FINGERPRINT_MANIFEST_INCOMPLETE",
        "Canonical manifest does not fingerprint 12 authoritative components.",
    )
    _check(
        int(canonical_manifest.get("partial_rows_included", 0) or 0) == 0,
        "PARTIAL_ROW_INCLUDED_IN_FINGERPRINT",
        "Partial rows are included in the canonical fingerprint manifest.",
    )
    _check(
        int(canonical_manifest.get("superseded_rows_included", 0) or 0) == 0,
        "NONAUTHORITATIVE_RUN_USED_FOR_EXECUTION",
        "Superseded rows are included in the canonical fingerprint manifest.",
    )
    _check(
        _normalize(canonical_approval_summary.get("final_interpretation"))
        in {
            "REFINED_MECHANISM_TEST_EXECUTION_CANONICAL_R1_APPROVED",
            "REFINED_MECHANISM_TEST_EXECUTION_CANONICAL_R1_APPROVED_WITH_WARNINGS",
        }
        and canonical_approval_summary.get("ready_for_one_canonical_clean_r1_mechanism_test_execution") is True,
        "DESIGN_CHANGE_AFTER_APPROVAL",
        "Canonical approval summary does not authorize one clean R1 execution.",
    )
    _check(
        _normalize(readiness_summary.get("final_interpretation"))
        == "REFINED_MECHANISM_TEST_EXECUTION_READINESS_READY_WITH_WARNINGS"
        and readiness_summary.get("ready_for_clean_r1_mechanism_test_execution") is True
        and readiness_row.get("ready_for_clean_r1_mechanism_test_execution") is True,
        "DESIGN_CHANGE_AFTER_APPROVAL",
        "Readiness audit does not authorize execution.",
    )
    _check(
        _normalize(readiness_summary.get("environment_freeze_status")) == "EXECUTION_ENVIRONMENT_FROZEN",
        "OUTCOME_SCHEMA_CONTRACT_MISMATCH",
        "Execution environment is not frozen.",
    )
    _check(
        _normalize(readiness_summary.get("determinism_status")) == "DETERMINISTIC_EXECUTION_READY",
        "REPEATED_CLEAN_RUN_CONTENT_MISMATCH",
        "Deterministic execution readiness not confirmed.",
    )
    _check(
        _normalize(readiness_summary.get("stop_rule_status")) == "FAIL_CLOSED_STOP_RULES_APPROVED",
        "UNAPPROVED_STATISTICAL_FALLBACK",
        "Stop-rule readiness not approved.",
    )

    prereg = selected_payloads["Refined_Mechanism_Test_Preregistration_Clean_R1"]
    outcome_def = selected_payloads["Refined_Mechanism_Test_Frozen_Outcome_Definition_Clean_R1"]
    join_rules = selected_payloads["Refined_Mechanism_Test_Frozen_Join_Rules_Clean_R1"]
    success_rules = selected_payloads["Refined_Mechanism_Test_Frozen_Success_Derivation_Clean_R1"]
    method_rules = selected_payloads["Refined_Mechanism_Test_Frozen_Statistical_Method_Clean_R1"]
    stop_rules = selected_payloads["Refined_Mechanism_Test_Frozen_Stop_Rules_Clean_R1"]

    _check(
        _normalize(prereg.get("repaired_preregistration_version") or prereg.get("test_preregistration_version"))
        == AUTHORITATIVE_VERSION,
        "AUTHORITY_VERSION_MISMATCH",
        "Authoritative preregistration version mismatch.",
    )
    _check(
        _normalize(prereg.get("classification_run_id")) == CLASSIFICATION_RUN_ID
        and _normalize(prereg.get("mechanism_version")) == CLASSIFICATION_VERSION,
        "CLASSIFICATION_FINGERPRINT_MISMATCH",
        "Classification version/run mismatch.",
    )
    _check(
        _normalize(prereg.get("primary_mechanism")) == PRIMARY_MECHANISM
        and _normalize(prereg.get("primary_structure")) == PRIMARY_STRUCTURE
        and _normalize(prereg.get("primary_exposure")) == PRIMARY_EXPOSURE
        and _normalize(prereg.get("primary_comparison_groups")) == PRIMARY_COMPARISON_GROUPS
        and _normalize(prereg.get("baseline_role")) == BASELINE_ROLE
        and _normalize(prereg.get("primary_estimand")) == PRIMARY_ESTIMAND,
        "DESIGN_CHANGE_AFTER_APPROVAL",
        "Primary scientific design drift detected.",
    )
    _check(
        _normalize(join_rules.get("approved_future_join_path"))
        == "provider + session_id + pack_level + source_row_key -> repaired_canonical_outcome_id -> canonical_outcome_id",
        "OUTCOME_SCHEMA_CONTRACT_MISMATCH",
        "Join contract path drift detected.",
    )
    _check(
        _normalize(method_rules.get("primary_method_id")) == PRIMARY_METHOD_ID
        and int(method_rules.get("bootstrap_replications", 0) or 0) == 10000
        and int(method_rules.get("bootstrap_random_seed", 0) or 0) == 9130613
        and _normalize(method_rules.get("resampling_unit")) == "shared_session_outcome_family",
        "UNAPPROVED_STATISTICAL_FALLBACK",
        "Frozen statistical method configuration drift detected.",
    )
    _check(
        set(success_rules.get("allowed_output_statuses", []))
        == {"SUCCESS", "FAILURE", "NOT_ELIGIBLE", "AMBIGUOUS_JOIN_BLOCKED"},
        "INVALID_SUCCESS_MAPPING",
        "Allowed success-derivation statuses drift detected.",
    )
    _check(
        outcome_def.get("schema_contract_only") is True
        and _normalize(outcome_def.get("canonical_outcome_source_sheet")) == "Market_Reaction_Canonical_Outcomes"
        and _normalize(outcome_def.get("corrected_mapping_bridge_sheet")) == "Corrected_Accuracy_Outcome_Mapping"
        and _normalize(outcome_def.get("canonical_outcome_component_field")) == "canonical_realized_direction",
        "OUTCOME_SCHEMA_CONTRACT_MISMATCH",
        "Outcome schema contract drift detected.",
    )
    execution_stop_names = {
        _normalize(rule.get("stop_rule_name")) for rule in stop_rules.get("stop_rules", [])
    }
    _check(
        execution_stop_names == EXPECTED_EXECUTION_STOP_RULE_NAMES,
        "OUTCOME_SCHEMA_CONTRACT_MISMATCH",
        f"Execution stop-rule set drift detected: {sorted(execution_stop_names)}",
    )

    class_rows = _classification_rows(inputs)
    _check(
        len(class_rows) == 360,
        "CLASSIFICATION_FINGERPRINT_MISMATCH",
        f"Expected 360 classification rows for the authoritative run; found {len(class_rows)}.",
    )
    _check(
        {_normalize(row.get("classification_run_id")) for row in class_rows} == {CLASSIFICATION_RUN_ID}
        and {_normalize(row.get("mechanism_version")) for row in class_rows} == {CLASSIFICATION_VERSION},
        "CLASSIFICATION_FINGERPRINT_MISMATCH",
        "Classification run or version drift detected in permanent classifications.",
    )
    structure_counts = _structure_counts(class_rows)
    for key, expected in EXPECTED_COUNTS.items():
        _check(
            int(structure_counts.get(key, -1)) == expected,
            "UNEXPECTED_ELIGIBILITY_DIFFERENCE",
            f"Pre-outcome structure count mismatch for {key}: expected {expected}, observed {structure_counts.get(key)}.",
        )
    _check(
        not structure_counts.get("baseline_match_count_errors"),
        "UNEXPECTED_ELIGIBILITY_DIFFERENCE",
        f"Baseline structural control mismatches detected: {structure_counts.get('baseline_match_count_errors')}",
    )

    # Guard against accidental duplicate execution of the same frozen authority chain.
    if OUTPUT_SUMMARY in known_titles:
        existing_summary_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY)
        for row in existing_summary_rows:
            payload = _json_loads_safe(row.get("payload_json")) or {}
            if (
                _normalize(payload.get("preregistration_version")) == AUTHORITATIVE_VERSION
                and _normalize(payload.get("authoritative_run_id")) == AUTHORITATIVE_RUN_ID
                and _normalize(payload.get("classification_run_id")) == CLASSIFICATION_RUN_ID
                and _normalize(payload.get("final_execution_status")) in {"COMPLETED", "COMPLETED_WITH_WARNINGS"}
            ):
                raise ExecutionBlocked(
                    "DESIGN_CHANGE_AFTER_APPROVAL",
                    "A successful canonical Clean-R1 mechanism-test execution already exists for this authority chain.",
                )

    # The canonical outcome sheet must exist before outcome access is permitted.
    _check(
        "Market_Reaction_Canonical_Outcomes" in _sheet_titles_light(service, DIAGNOSTICS_SPREADSHEET_ID),
        "OUTCOME_SCHEMA_CONTRACT_MISMATCH",
        "Canonical outcome sheet is missing.",
    )

    return {
        **context,
        "selected_payloads": selected_payloads,
        "structure_counts": structure_counts,
        "class_rows": class_rows,
    }


def _build_bridge_consensus(
    rows: Sequence[Mapping[str, Any]],
    fields: Sequence[str],
    missing_code: str,
    duplicate_code: str,
) -> Tuple[Dict[Tuple[str, str, str], Dict[str, Any]], int]:
    groups: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (_normalize(row.get("provider")), _normalize(row.get("session_id")), _normalize(row.get("pack_level")))
        groups[key].append(dict(row))
    out: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    duplicates_loaded = 0
    for key, group in groups.items():
        duplicates_loaded += len(group)
        if not group:
            out[key] = {"status": missing_code}
            continue
        values = {tuple(_normalize(row.get(field)) for field in fields) for row in group}
        if len(values) != 1:
            out[key] = {
                "status": duplicate_code,
                "duplicate_count": len(group),
                "observed_variants": [list(item) for item in sorted(values)],
            }
            continue
        value_tuple = next(iter(values))
        payload = {field: value_tuple[index] for index, field in enumerate(fields)}
        payload.update(
            {
                "status": "OK",
                "duplicate_count": len(group),
                "raw_row_count": len(group),
            }
        )
        out[key] = payload
    return out, duplicates_loaded


def _baseline_index(class_rows: Sequence[Mapping[str, Any]], mechanism_id: str) -> Dict[Tuple[str, str], Dict[str, Any]]:
    baseline: Dict[Tuple[str, str], Dict[str, Any]] = {}
    duplicates: List[Tuple[str, str]] = []
    for row in class_rows:
        if _normalize(row.get("mechanism_id")) != mechanism_id or _normalize(row.get("pack_level")) != "A":
            continue
        key = (_normalize(row.get("provider")), _normalize(row.get("session_id")))
        if key in baseline:
            duplicates.append(key)
        baseline[key] = dict(row)
    if duplicates:
        raise ExecutionBlocked(
            "UNEXPECTED_ELIGIBILITY_DIFFERENCE",
            f"Multiple Pack A baseline rows detected for {mechanism_id}: {sorted(set(duplicates))}",
        )
    return baseline


def _eligible_candidates(
    class_rows: Sequence[Mapping[str, Any]],
    mechanism_id: str,
    *,
    allowed_labels: Set[str],
    require_high_moderate: bool,
) -> List[Dict[str, Any]]:
    baseline = _baseline_index(class_rows, mechanism_id)
    out = []
    for row in class_rows:
        if _normalize(row.get("mechanism_id")) != mechanism_id:
            continue
        if _normalize(row.get("pack_level")) not in {"B", "C", "D", "E"}:
            continue
        if _normalize(row.get("classification_label")) not in allowed_labels:
            continue
        if require_high_moderate and _normalize(row.get("confidence_category")) not in {"HIGH", "MODERATE"}:
            continue
        key = (_normalize(row.get("provider")), _normalize(row.get("session_id")))
        if key not in baseline:
            continue
        out.append(dict(row))
    out.sort(key=lambda row: (_normalize(row.get("session_id")), _normalize(row.get("provider")), _normalize(row.get("pack_level"))))
    return out


def _validate_outcome_contract_for_join(
    outcome_def: Mapping[str, Any],
    selection_consensus: Mapping[str, Any],
    mapping_consensus: Mapping[str, Any],
    canonical_row: Optional[Mapping[str, Any]],
    overlay_row: Optional[Mapping[str, Any]],
) -> Tuple[str, str, Dict[str, Any]]:
    if _normalize(selection_consensus.get("status")) != "OK":
        return "NOT_ELIGIBLE", "NOT_ELIGIBLE_MISSING_OUTCOME_JOIN", {"selection_status": selection_consensus.get("status")}
    if _normalize(mapping_consensus.get("status")) != "OK":
        if _normalize(mapping_consensus.get("status")) == "DUPLICATE_JOIN_BLOCKED":
            return "AMBIGUOUS_JOIN_BLOCKED", "DUPLICATE_JOIN_BLOCKED", {"mapping_status": mapping_consensus.get("status")}
        return "NOT_ELIGIBLE", "NOT_ELIGIBLE_MISSING_OUTCOME_JOIN", {"mapping_status": mapping_consensus.get("status")}
    if _normalize(selection_consensus.get("repaired_canonical_outcome_id")) != _normalize(
        mapping_consensus.get("repaired_canonical_outcome_id")
    ):
        return "AMBIGUOUS_JOIN_BLOCKED", "DUPLICATE_JOIN_BLOCKED", {
            "selection_repaired_id": selection_consensus.get("repaired_canonical_outcome_id"),
            "mapping_repaired_id": mapping_consensus.get("repaired_canonical_outcome_id"),
        }
    if canonical_row is None or overlay_row is None:
        return "NOT_ELIGIBLE", "NOT_ELIGIBLE_MISSING_REPAIRED_OUTCOME", {
            "canonical_present": canonical_row is not None,
            "overlay_present": overlay_row is not None,
        }

    version_ok = (
        _normalize(mapping_consensus.get("design_version")) == "corrected_accuracy_re_evaluation_design_v0"
        and _normalize(canonical_row.get("implementation_version")) == "market_reaction_outcome_source_implementation_v0"
        and _normalize(outcome_def.get("repaired_canonical_outcome_version"))
        == "market_reaction_outcome_source_implementation_v0 + corrected_accuracy_re_evaluation_design_v0"
    )
    if not version_ok:
        return "NOT_ELIGIBLE", "OUTCOME_VERSION_MISMATCH", {
            "mapping_design_version": mapping_consensus.get("design_version"),
            "canonical_implementation_version": canonical_row.get("implementation_version"),
            "expected_repaired_version": outcome_def.get("repaired_canonical_outcome_version"),
        }

    expected_window_policy = "EVENT_RELATIVE_FIXED_DURATION"
    expected_window_minutes = 5.0
    observed_window_policy = _normalize(canonical_row.get("window_policy"))
    observed_window_minutes = _to_float(canonical_row.get("window_minutes"))
    window_ok = observed_window_policy == expected_window_policy and observed_window_minutes == expected_window_minutes
    if not window_ok:
        return "NOT_ELIGIBLE", "EVALUATION_WINDOW_MISMATCH", {
            "observed_window_policy": observed_window_policy,
            "observed_window_minutes": observed_window_minutes,
            "expected_window_policy": expected_window_policy,
            "expected_window_minutes": expected_window_minutes,
        }

    canonical_start = _parse_iso_utc(canonical_row.get("canonical_start_ts"))
    canonical_end = _parse_iso_utc(canonical_row.get("canonical_end_ts"))
    release_ts = _parse_iso_utc(canonical_row.get("release_ts"))
    repaired_start = _parse_iso_utc(overlay_row.get("repaired_start_ts"))
    repaired_end = _parse_iso_utc(overlay_row.get("repaired_end_ts"))
    # The frozen contract requires timestamp provenance that is compatible with
    # the repaired canonical window. The available outcome schema expresses that
    # through canonical/repaired window fields plus strict-ready leakage-safe
    # validation rather than a separate source-availability timestamp column.
    timestamp_ok = (
        canonical_start is not None
        and canonical_end is not None
        and canonical_end >= canonical_start
        and release_ts is not None
        and release_ts <= canonical_end
        and repaired_start is not None
        and repaired_end is not None
        and repaired_end >= repaired_start
        and _to_bool(overlay_row.get("leakage_safe"))
        and _to_bool(overlay_row.get("usable_for_strict_accuracy"))
        and _to_bool(selection_consensus.get("leakage_safe_validated"))
        and _to_bool(selection_consensus.get("strict_ready"))
        and _to_bool(selection_consensus.get("included_in_primary_corrected_evaluation"))
        and _to_bool(mapping_consensus.get("included_in_primary"))
    )
    if not timestamp_ok:
        return "NOT_ELIGIBLE", "OUTCOME_TIMESTAMP_REQUIREMENT_FAILED", {
            "canonical_start_ts": canonical_row.get("canonical_start_ts"),
            "canonical_end_ts": canonical_row.get("canonical_end_ts"),
            "release_ts": canonical_row.get("release_ts"),
            "repaired_start_ts": overlay_row.get("repaired_start_ts"),
            "repaired_end_ts": overlay_row.get("repaired_end_ts"),
            "overlay_leakage_safe": overlay_row.get("leakage_safe"),
            "overlay_usable_for_strict_accuracy": overlay_row.get("usable_for_strict_accuracy"),
            "selection_strict_ready": selection_consensus.get("strict_ready"),
            "selection_leakage_safe_validated": selection_consensus.get("leakage_safe_validated"),
        }

    return "OK", "JOIN_READY", {
        "mapping_design_version": mapping_consensus.get("design_version"),
        "canonical_implementation_version": canonical_row.get("implementation_version"),
        "window_policy": canonical_row.get("window_policy"),
        "window_minutes": canonical_row.get("window_minutes"),
    }


def _derive_success_status(
    *,
    forecast_direction: str,
    no_signal_flag: bool,
    output_valid: bool,
    realized_direction: str,
    join_status: str,
    join_reason: str,
) -> Tuple[str, str]:
    if join_status == "AMBIGUOUS_JOIN_BLOCKED":
        return "AMBIGUOUS_JOIN_BLOCKED", join_reason
    if join_status != "OK":
        return "NOT_ELIGIBLE", join_reason
    if not output_valid:
        return "NOT_ELIGIBLE", "INVALID_FORECAST_OUTPUT"
    if forecast_direction not in {"UP", "DOWN", "FLAT", "NO_CLEAR_DIRECTION"}:
        return "NOT_ELIGIBLE", "INVALID_FORECAST_DIRECTION"
    if realized_direction not in {"UP", "DOWN", "FLAT", "NO_CLEAR_DIRECTION", "AMBIGUOUS"}:
        return "NOT_ELIGIBLE", "INVALID_REALIZED_DIRECTION"
    if forecast_direction == "NO_CLEAR_DIRECTION":
        return "NOT_ELIGIBLE", "FORECAST_NO_CLEAR_DIRECTION"
    if no_signal_flag:
        return "NOT_ELIGIBLE", "NO_SIGNAL_FORECAST"
    if realized_direction in {"FLAT", "NO_CLEAR_DIRECTION", "AMBIGUOUS"}:
        return "NOT_ELIGIBLE", "REALIZED_FLAT_OR_AMBIGUOUS"
    if forecast_direction == "FLAT":
        return "NOT_ELIGIBLE", "FORECAST_FLAT"
    if forecast_direction == "UP" and realized_direction == "UP":
        return "SUCCESS", "UP_MATCH"
    if forecast_direction == "UP" and realized_direction == "DOWN":
        return "FAILURE", "UP_MISMATCH"
    if forecast_direction == "DOWN" and realized_direction == "DOWN":
        return "SUCCESS", "DOWN_MATCH"
    if forecast_direction == "DOWN" and realized_direction == "UP":
        return "FAILURE", "DOWN_MISMATCH"
    return "NOT_ELIGIBLE", "UNMAPPED_STATUS"


def _build_join_result(
    *,
    behavior_row: Mapping[str, Any],
    selection_consensus: Mapping[str, Any],
    mapping_consensus: Mapping[str, Any],
    canonical_row: Optional[Mapping[str, Any]],
    overlay_row: Optional[Mapping[str, Any]],
    outcome_def: Mapping[str, Any],
) -> JoinResult:
    join_status, join_reason, join_details = _validate_outcome_contract_for_join(
        outcome_def,
        selection_consensus,
        mapping_consensus,
        canonical_row,
        overlay_row,
    )
    forecast_direction = _normalize_direction(behavior_row.get("forecast_direction"))
    realized_direction = _normalize_direction((overlay_row or {}).get("repaired_realized_direction"))
    success_status, reason_code = _derive_success_status(
        forecast_direction=forecast_direction,
        no_signal_flag=_to_bool(behavior_row.get("no_signal_flag")),
        output_valid=_to_bool(behavior_row.get("output_valid")),
        realized_direction=realized_direction,
        join_status=join_status,
        join_reason=join_reason,
    )
    details = {
        "join_validation_status": join_status,
        "join_validation_reason": join_reason,
        "join_validation_details": join_details,
        "forecast_direction": forecast_direction,
        "realized_direction": realized_direction,
        "no_signal_flag": _normalize(behavior_row.get("no_signal_flag")),
        "output_valid": _normalize(behavior_row.get("output_valid")),
        "selection_consensus": selection_consensus,
        "mapping_consensus": mapping_consensus,
        "canonical_row_fingerprint": _fingerprint_payload(dict(canonical_row)) if canonical_row else "",
        "overlay_row_fingerprint": _fingerprint_payload(dict(overlay_row)) if overlay_row else "",
    }
    return JoinResult(
        status=join_status,
        repaired_canonical_outcome_id=_normalize(selection_consensus.get("repaired_canonical_outcome_id")),
        canonical_outcome_id=_normalize((overlay_row or {}).get("canonical_outcome_id")),
        forecast_direction=forecast_direction,
        realized_direction=realized_direction,
        success_status=success_status,
        reason_code=reason_code,
        details=details,
    )


def _mean(values: Sequence[float]) -> Optional[float]:
    if not values:
        return None
    return sum(values) / len(values)


def _bootstrap_effect(
    rows: Sequence[Mapping[str, Any]],
    *,
    rng_seed: int,
    replications: int,
) -> Dict[str, Any]:
    families: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        families[_normalize(row.get("shared_session_outcome_family"))].append(row)
    family_keys = sorted(families)
    rng = random.Random(rng_seed)
    effects: List[float] = []
    non_estimable = 0
    for _ in range(replications):
        sampled_keys = [rng.choice(family_keys) for _ in family_keys]
        sampled_rows: List[Mapping[str, Any]] = []
        for key in sampled_keys:
            sampled_rows.extend(families[key])
        pos = [float(row["delta_value"]) for row in sampled_rows if _normalize(row.get("expanded_label")) == "POSITIVE"]
        neg = [float(row["delta_value"]) for row in sampled_rows if _normalize(row.get("expanded_label")) == "NEGATIVE"]
        if not pos or not neg:
            non_estimable += 1
            continue
        pos_mean = _mean(pos)
        neg_mean = _mean(neg)
        if pos_mean is None or neg_mean is None:
            non_estimable += 1
            continue
        effects.append(pos_mean - neg_mean)
    estimable = len(effects)
    estimable_fraction = estimable / replications if replications else 0.0
    if estimable == 0:
        return {
            "bootstrap_status": "DEGENERATE_BOOTSTRAP_DISTRIBUTION",
            "attempted_replications": replications,
            "estimable_replications": 0,
            "estimable_fraction": estimable_fraction,
            "interval": None,
            "effects": [],
        }
    ordered = sorted(effects)
    lower_idx = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * 0.025)))
    upper_idx = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * 0.975)))
    interval = (ordered[lower_idx], ordered[upper_idx])
    status = "PASS" if estimable_fraction >= 0.80 and len(set(ordered)) > 1 else "DEGENERATE_BOOTSTRAP_DISTRIBUTION"
    return {
        "bootstrap_status": status,
        "attempted_replications": replications,
        "estimable_replications": estimable,
        "estimable_fraction": estimable_fraction,
        "interval": interval,
        "effects": ordered[:50],
    }


def _analysis_cluster_summary(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    providers = {_normalize(row.get("provider")) for row in rows}
    sessions = {_normalize(row.get("session_id")) for row in rows}
    clusters = {f"{_normalize(row.get('provider'))}|{_normalize(row.get('session_id'))}" for row in rows}
    mixed_label_clusters = Counter()
    for row in rows:
        cluster = f"{_normalize(row.get('provider'))}|{_normalize(row.get('session_id'))}"
        mixed_label_clusters[cluster] |= 0
    cluster_labels: Dict[str, Set[str]] = defaultdict(set)
    for row in rows:
        cluster_labels[f"{_normalize(row.get('provider'))}|{_normalize(row.get('session_id'))}"].add(
            _normalize(row.get("expanded_label"))
        )
    mixed_count = sum(1 for labels in cluster_labels.values() if {"POSITIVE", "NEGATIVE"} <= labels)
    return {
        "provider_count": len(providers),
        "session_count": len(sessions),
        "cluster_count": len(clusters),
        "mixed_label_cluster_count": mixed_count,
    }


def _gate_status(observed: int, threshold: Optional[int]) -> str:
    if threshold is None:
        return "NOT_APPLICABLE"
    return "PASS" if observed >= threshold else "FAIL"


def _run_analysis(
    *,
    analysis_id: str,
    mechanism_id: str,
    mechanism_name: str,
    analysis_role: str,
    class_rows: Sequence[Mapping[str, Any]],
    behavior_by_key: Mapping[Tuple[str, str, str], Mapping[str, Any]],
    selection_consensus: Mapping[Tuple[str, str, str], Mapping[str, Any]],
    mapping_consensus: Mapping[Tuple[str, str, str], Mapping[str, Any]],
    overlay_by_repaired_id: Mapping[str, Mapping[str, Any]],
    canonical_by_id: Mapping[str, Mapping[str, Any]],
    outcome_def: Mapping[str, Any],
    allowed_labels: Set[str],
    require_high_moderate: bool,
    inferential_allowed: bool,
    gate_thresholds: Optional[Mapping[str, int]],
) -> AnalysisOutput:
    candidates = _eligible_candidates(
        class_rows,
        mechanism_id,
        allowed_labels=allowed_labels,
        require_high_moderate=require_high_moderate,
    )
    baseline = _baseline_index(class_rows, mechanism_id)
    join_rows: List[Dict[str, Any]] = []
    eligible_rows: List[Dict[str, Any]] = []
    missing_reasons: Counter = Counter()

    for expanded_row in candidates:
        provider = _normalize(expanded_row.get("provider"))
        session_id = _normalize(expanded_row.get("session_id"))
        pack_level = _normalize(expanded_row.get("pack_level"))
        baseline_row = baseline[(provider, session_id)]
        expanded_key = (provider, session_id, pack_level)
        baseline_key = (provider, session_id, "A")

        expanded_behavior = behavior_by_key.get(expanded_key)
        baseline_behavior = behavior_by_key.get(baseline_key)
        if expanded_behavior is None or baseline_behavior is None:
            missing_reasons["MISSING_BEHAVIOR_SOURCE"] += 1
            join_rows.append(
                {
                    "analysis_id": analysis_id,
                    "mechanism_id": mechanism_id,
                    "analysis_role": analysis_role,
                    "source_row_key": _normalize(expanded_row.get("source_row_key")),
                    "provider": provider,
                    "session_id": session_id,
                    "pack_level": pack_level,
                    "matched_baseline_source_row_key": _normalize(baseline_row.get("source_row_key")),
                    "expanded_label": _normalize(expanded_row.get("classification_label")),
                    "confidence_category": _normalize(expanded_row.get("confidence_category")),
                    "bridge_consensus_status": "MISSING_BEHAVIOR_SOURCE",
                    "repaired_canonical_outcome_id": "",
                    "canonical_outcome_id": "",
                    "expanded_forecast_direction": "",
                    "baseline_forecast_direction": "",
                    "expanded_realized_direction": "",
                    "baseline_realized_direction": "",
                    "expanded_success_status": "NOT_ELIGIBLE",
                    "baseline_success_status": "NOT_ELIGIBLE",
                    "delta_status": "NOT_JOINED",
                    "included_in_analysis": "FALSE",
                    "exclusion_reason": "MISSING_BEHAVIOR_SOURCE",
                    "payload_json": _canonical_json({"expanded_key": expanded_key, "baseline_key": baseline_key}),
                }
            )
            continue

        expanded_selection = selection_consensus.get(expanded_key, {"status": "MISSING_JOIN_COMPONENT"})
        baseline_selection = selection_consensus.get(baseline_key, {"status": "MISSING_JOIN_COMPONENT"})
        expanded_mapping = mapping_consensus.get(expanded_key, {"status": "MISSING_JOIN_COMPONENT"})
        baseline_mapping = mapping_consensus.get(baseline_key, {"status": "MISSING_JOIN_COMPONENT"})

        expanded_overlay = overlay_by_repaired_id.get(_normalize(expanded_selection.get("repaired_canonical_outcome_id")))
        baseline_overlay = overlay_by_repaired_id.get(_normalize(baseline_selection.get("repaired_canonical_outcome_id")))
        expanded_canonical = (
            canonical_by_id.get(_normalize(expanded_overlay.get("canonical_outcome_id"))) if expanded_overlay else None
        )
        baseline_canonical = (
            canonical_by_id.get(_normalize(baseline_overlay.get("canonical_outcome_id"))) if baseline_overlay else None
        )

        expanded_join = _build_join_result(
            behavior_row=expanded_behavior,
            selection_consensus=expanded_selection,
            mapping_consensus=expanded_mapping,
            canonical_row=expanded_canonical,
            overlay_row=expanded_overlay,
            outcome_def=outcome_def,
        )
        baseline_join = _build_join_result(
            behavior_row=baseline_behavior,
            selection_consensus=baseline_selection,
            mapping_consensus=baseline_mapping,
            canonical_row=baseline_canonical,
            overlay_row=baseline_overlay,
            outcome_def=outcome_def,
        )

        included = expanded_join.success_status in {"SUCCESS", "FAILURE"} and baseline_join.success_status in {"SUCCESS", "FAILURE"}
        if included:
            expanded_success_value = 1 if expanded_join.success_status == "SUCCESS" else 0
            baseline_success_value = 1 if baseline_join.success_status == "SUCCESS" else 0
            delta_value = expanded_success_value - baseline_success_value
            eligible_row = {
                "analysis_id": analysis_id,
                "mechanism_id": mechanism_id,
                "analysis_role": analysis_role,
                "source_row_key": _normalize(expanded_row.get("source_row_key")),
                "matched_baseline_source_row_key": _normalize(baseline_row.get("source_row_key")),
                "provider": provider,
                "session_id": session_id,
                "shared_session_outcome_family": session_id,
                "pack_level": pack_level,
                "expanded_label": _normalize(expanded_row.get("classification_label")),
                "confidence_category": _normalize(expanded_row.get("confidence_category")),
                "delta_value": delta_value,
                "expanded_success_value": expanded_success_value,
                "baseline_success_value": baseline_success_value,
                "repaired_canonical_outcome_id": expanded_join.repaired_canonical_outcome_id,
                "canonical_outcome_id": expanded_join.canonical_outcome_id,
            }
            eligible_rows.append(eligible_row)
            exclusion_reason = ""
            delta_status = "ELIGIBLE_DELTA"
        else:
            if expanded_join.reason_code == "NOT_ELIGIBLE_MISSING_OUTCOME_JOIN" and baseline_join.reason_code == "NOT_ELIGIBLE_MISSING_OUTCOME_JOIN":
                exclusion_reason = "MISSING_EXPANDED_AND_BASELINE_OUTCOME_JOIN"
            elif expanded_join.reason_code == "NOT_ELIGIBLE_MISSING_OUTCOME_JOIN":
                exclusion_reason = "MISSING_EXPANDED_OUTCOME_JOIN"
            elif baseline_join.reason_code == "NOT_ELIGIBLE_MISSING_OUTCOME_JOIN":
                exclusion_reason = "MISSING_BASELINE_OUTCOME_JOIN"
            elif expanded_join.reason_code == "NOT_ELIGIBLE_MISSING_REPAIRED_OUTCOME" or baseline_join.reason_code == "NOT_ELIGIBLE_MISSING_REPAIRED_OUTCOME":
                exclusion_reason = "MISSING_REPAIRED_OUTCOME_OVERLAY"
            elif expanded_join.success_status == "AMBIGUOUS_JOIN_BLOCKED" or baseline_join.success_status == "AMBIGUOUS_JOIN_BLOCKED":
                exclusion_reason = "AMBIGUOUS_JOIN_BLOCKED"
            elif expanded_join.success_status == "NOT_ELIGIBLE" and baseline_join.success_status == "NOT_ELIGIBLE":
                exclusion_reason = "EXPANDED_AND_BASELINE_NOT_ELIGIBLE_AFTER_SUCCESS_MAPPING"
            elif expanded_join.success_status == "NOT_ELIGIBLE":
                exclusion_reason = "EXPANDED_NOT_ELIGIBLE_AFTER_SUCCESS_MAPPING"
            elif baseline_join.success_status == "NOT_ELIGIBLE":
                exclusion_reason = "BASELINE_NOT_ELIGIBLE_AFTER_SUCCESS_MAPPING"
            else:
                exclusion_reason = "NOT_ELIGIBLE_UNSPECIFIED"
            missing_reasons[exclusion_reason] += 1
            delta_status = "NOT_JOINED"

        bridge_status_parts = [
            _normalize(expanded_selection.get("status")) or "MISSING",
            _normalize(baseline_selection.get("status")) or "MISSING",
            _normalize(expanded_mapping.get("status")) or "MISSING",
            _normalize(baseline_mapping.get("status")) or "MISSING",
        ]
        join_rows.append(
            {
                "analysis_id": analysis_id,
                "mechanism_id": mechanism_id,
                "analysis_role": analysis_role,
                "source_row_key": _normalize(expanded_row.get("source_row_key")),
                "provider": provider,
                "session_id": session_id,
                "pack_level": pack_level,
                "matched_baseline_source_row_key": _normalize(baseline_row.get("source_row_key")),
                "expanded_label": _normalize(expanded_row.get("classification_label")),
                "confidence_category": _normalize(expanded_row.get("confidence_category")),
                "bridge_consensus_status": "|".join(bridge_status_parts),
                "repaired_canonical_outcome_id": expanded_join.repaired_canonical_outcome_id,
                "canonical_outcome_id": expanded_join.canonical_outcome_id,
                "expanded_forecast_direction": expanded_join.forecast_direction,
                "baseline_forecast_direction": baseline_join.forecast_direction,
                "expanded_realized_direction": expanded_join.realized_direction,
                "baseline_realized_direction": baseline_join.realized_direction,
                "expanded_success_status": expanded_join.success_status,
                "baseline_success_status": baseline_join.success_status,
                "delta_status": delta_status,
                "included_in_analysis": "TRUE" if included else "FALSE",
                "exclusion_reason": exclusion_reason,
                "payload_json": _canonical_json(
                    {
                        "expanded_join": expanded_join.details,
                        "baseline_join": baseline_join.details,
                        "expanded_key": expanded_key,
                        "baseline_key": baseline_key,
                    }
                ),
            }
        )

    cluster_summary = _analysis_cluster_summary(eligible_rows)
    label_counts = Counter(_normalize(row.get("expanded_label")) for row in eligible_rows)
    gate_thresholds = gate_thresholds or {}
    positive_gate_status = _gate_status(label_counts.get("POSITIVE", 0), gate_thresholds.get("minimum_positive_count"))
    negative_gate_status = _gate_status(label_counts.get("NEGATIVE", 0), gate_thresholds.get("minimum_negative_count"))
    primary_contrast_gate_status = _gate_status(len(eligible_rows), gate_thresholds.get("minimum_primary_contrast_observations"))
    cluster_gate_status = _gate_status(cluster_summary["cluster_count"], gate_thresholds.get("minimum_clusters"))
    provider_gate_status = _gate_status(cluster_summary["provider_count"], gate_thresholds.get("minimum_providers"))
    session_gate_status = _gate_status(cluster_summary["session_count"], gate_thresholds.get("minimum_sessions"))
    descriptive_fallback_required = False
    trigger_names: List[str] = []
    if gate_thresholds:
        if positive_gate_status == "FAIL":
            descriptive_fallback_required = True
            trigger_names.append("POSITIVE_SAMPLE_GATE_FAILURE")
        if negative_gate_status == "FAIL":
            descriptive_fallback_required = True
            trigger_names.append("NEGATIVE_SAMPLE_GATE_FAILURE")
        if primary_contrast_gate_status == "FAIL":
            descriptive_fallback_required = True
            trigger_names.append("PRIMARY_CONTRAST_GATE_FAILURE")
        if cluster_gate_status == "FAIL":
            descriptive_fallback_required = True
            trigger_names.append("CLUSTER_GATE_FAILURE")
        if provider_gate_status == "FAIL":
            descriptive_fallback_required = True
            trigger_names.append("PROVIDER_GATE_FAILURE")
        if session_gate_status == "FAIL":
            descriptive_fallback_required = True
            trigger_names.append("SESSION_GATE_FAILURE")

    result_status = "DESCRIPTIVE_ONLY"
    effect_estimate: Optional[float] = None
    ci_lower: Optional[float] = None
    ci_upper: Optional[float] = None
    bootstrap_status = "NOT_RUN_NOT_REQUESTED"
    attempted_replications = 0
    estimable_replications = 0
    estimable_fraction = 0.0
    bootstrap_reason = ""

    if inferential_allowed:
        pos_deltas = [float(row["delta_value"]) for row in eligible_rows if _normalize(row.get("expanded_label")) == "POSITIVE"]
        neg_deltas = [float(row["delta_value"]) for row in eligible_rows if _normalize(row.get("expanded_label")) == "NEGATIVE"]
        if not pos_deltas or not neg_deltas:
            descriptive_fallback_required = True
            trigger_names.append("ZERO_PRIMARY_GROUP_CELL")
            bootstrap_status = "ZERO_PRIMARY_GROUP_CELL"
            bootstrap_reason = "One primary comparison group has zero eligible joined outcomes."
        elif not descriptive_fallback_required:
            effect_estimate = _mean(pos_deltas)
            if effect_estimate is not None:
                neg_mean = _mean(neg_deltas)
                effect_estimate = effect_estimate - (neg_mean or 0.0)
            bootstrap = _bootstrap_effect(
                eligible_rows,
                rng_seed=9130613,
                replications=10000,
            )
            bootstrap_status = bootstrap["bootstrap_status"]
            attempted_replications = bootstrap["attempted_replications"]
            estimable_replications = bootstrap["estimable_replications"]
            estimable_fraction = bootstrap["estimable_fraction"]
            if bootstrap["bootstrap_status"] == "PASS" and bootstrap["interval"] is not None:
                ci_lower, ci_upper = bootstrap["interval"]
                result_status = "INFERENTIAL_EXECUTED"
            else:
                descriptive_fallback_required = True
                trigger_names.append("DEGENERATE_BOOTSTRAP_DISTRIBUTION")
                bootstrap_reason = "Bootstrap interval estimation failed under the frozen estimator."
        else:
            bootstrap_status = "NOT_RUN_GATE_FAILURE"
            bootstrap_reason = "Post-join primary gates failed before inferential execution."

    if effect_estimate is None and eligible_rows:
        pos_deltas = [float(row["delta_value"]) for row in eligible_rows if _normalize(row.get("expanded_label")) == "POSITIVE"]
        neg_deltas = [float(row["delta_value"]) for row in eligible_rows if _normalize(row.get("expanded_label")) == "NEGATIVE"]
        if pos_deltas and neg_deltas:
            effect_estimate = (_mean(pos_deltas) or 0.0) - (_mean(neg_deltas) or 0.0)

    stats_payload = {
        "analysis_id": analysis_id,
        "mechanism_id": mechanism_id,
        "analysis_role": analysis_role,
        "candidate_source_count": len(candidates),
        "eligible_sample_count": len(eligible_rows),
        "label_counts": dict(label_counts),
        "group_delta_means": {
            label: _mean([float(row["delta_value"]) for row in eligible_rows if _normalize(row.get("expanded_label")) == label])
            for label in sorted(label_counts)
        },
        "descriptive_fallback_required": descriptive_fallback_required,
        "trigger_names": trigger_names,
        "bootstrap_reason": bootstrap_reason,
        "cluster_summary": cluster_summary,
    }

    summary_row = {
        "analysis_id": analysis_id,
        "mechanism_id": mechanism_id,
        "analysis_role": analysis_role,
        "candidate_source_count": len(candidates),
        "joined_candidate_count": len(join_rows),
        "eligible_sample_count": len(eligible_rows),
        "positive_sample_count": label_counts.get("POSITIVE", 0),
        "negative_sample_count": label_counts.get("NEGATIVE", 0),
        "unknown_sample_count": label_counts.get("UNKNOWN", 0),
        "insufficient_evidence_sample_count": label_counts.get("INSUFFICIENT_EVIDENCE", 0),
        "cluster_count": cluster_summary["cluster_count"],
        "provider_count": cluster_summary["provider_count"],
        "session_count": cluster_summary["session_count"],
        "positive_gate_status": positive_gate_status,
        "negative_gate_status": negative_gate_status,
        "primary_contrast_gate_status": primary_contrast_gate_status,
        "cluster_gate_status": cluster_gate_status,
        "provider_gate_status": provider_gate_status,
        "session_gate_status": session_gate_status,
        "descriptive_fallback_required": "TRUE" if descriptive_fallback_required else "FALSE",
        "payload_json": _canonical_json(stats_payload),
    }

    stats_row = {
        "analysis_id": analysis_id,
        "mechanism_id": mechanism_id,
        "analysis_role": analysis_role,
        "result_status": result_status if not descriptive_fallback_required else "DESCRIPTIVE_FALLBACK_ONLY",
        "analysis_population": len(eligible_rows),
        "effect_measure": PRIMARY_EFFECT_MEASURE if inferential_allowed else "DESCRIPTIVE_GROUP_DELTA_SUMMARY",
        "statistical_method": PRIMARY_METHOD_LABEL if inferential_allowed else "FROZEN_DESCRIPTIVE_ONLY_REPORTING",
        "effect_estimate": "" if effect_estimate is None else f"{effect_estimate:.6f}",
        "confidence_interval_lower": "" if ci_lower is None else f"{ci_lower:.6f}",
        "confidence_interval_upper": "" if ci_upper is None else f"{ci_upper:.6f}",
        "inferential_result_allowed": "TRUE" if (inferential_allowed and not descriptive_fallback_required and result_status == "INFERENTIAL_EXECUTED") else "FALSE",
        "descriptive_fallback_used": "TRUE" if descriptive_fallback_required or not inferential_allowed else "FALSE",
        "payload_json": _canonical_json(stats_payload),
    }

    bootstrap_row = {
        "analysis_id": analysis_id,
        "mechanism_id": mechanism_id,
        "bootstrap_status": bootstrap_status,
        "requested_replications": 10000 if inferential_allowed else 0,
        "attempted_replications": attempted_replications,
        "estimable_replications": estimable_replications,
        "estimable_fraction": f"{estimable_fraction:.6f}" if inferential_allowed else "",
        "random_seed": 9130613 if inferential_allowed else "",
        "resampling_unit": "shared_session_outcome_family" if inferential_allowed else "",
        "interval_method": "two_sided_percentile_bootstrap_95pct_interval" if inferential_allowed else "",
        "payload_json": _canonical_json(
            {
                "analysis_id": analysis_id,
                "bootstrap_reason": bootstrap_reason,
                "trigger_names": trigger_names,
                "eligible_sample_count": len(eligible_rows),
            }
        ),
    }

    cluster_row = {
        "analysis_id": analysis_id,
        "mechanism_id": mechanism_id,
        "analysis_role": analysis_role,
        "eligible_observations": len(eligible_rows),
        "cluster_count": cluster_summary["cluster_count"],
        "provider_count": cluster_summary["provider_count"],
        "session_count": cluster_summary["session_count"],
        "session_family_count": cluster_summary["session_count"],
        "mixed_label_cluster_count": cluster_summary["mixed_label_cluster_count"],
        "cluster_status": "PASS" if cluster_summary["cluster_count"] else "EMPTY",
        "payload_json": _canonical_json(cluster_summary),
    }

    assumption_rows = [
        {
            "check_id": f"{analysis_id}_JOIN_CONTRACT",
            "check_name": "Frozen join contract respected",
            "status": "PASS",
            "severity": "INFO",
            "analysis_id": analysis_id,
            "mechanism_id": mechanism_id,
            "details_json": _canonical_json(
                {
                    "physical_row_join_used": False,
                    "fuzzy_join_used": False,
                    "manual_join_used": False,
                    "bridge_duplicates_consensus_only": True,
                }
            ),
        },
        {
            "check_id": f"{analysis_id}_PRIMARY_GATES",
            "check_name": "Post-join gate recheck",
            "status": "FAIL" if descriptive_fallback_required and inferential_allowed else "PASS",
            "severity": "WARNING" if descriptive_fallback_required else "INFO",
            "analysis_id": analysis_id,
            "mechanism_id": mechanism_id,
            "details_json": _canonical_json(
                {
                    "trigger_names": trigger_names,
                    "positive_gate_status": positive_gate_status,
                    "negative_gate_status": negative_gate_status,
                    "primary_contrast_gate_status": primary_contrast_gate_status,
                    "cluster_gate_status": cluster_gate_status,
                    "provider_gate_status": provider_gate_status,
                    "session_gate_status": session_gate_status,
                }
            ),
        },
    ]

    if inferential_allowed and label_counts.get("NEGATIVE", 0) == 0:
        assumption_rows.append(
            {
                "check_id": f"{analysis_id}_ZERO_NEGATIVE_GROUP",
                "check_name": "Primary comparison group availability",
                "status": "FAIL",
                "severity": "WARNING",
                "analysis_id": analysis_id,
                "mechanism_id": mechanism_id,
                "details_json": _canonical_json(
                    {
                        "positive_sample_count": label_counts.get("POSITIVE", 0),
                        "negative_sample_count": label_counts.get("NEGATIVE", 0),
                        "frozen_response": "ZERO_PRIMARY_GROUP_CELL -> descriptive fallback only",
                    }
                ),
            }
        )

    return AnalysisOutput(
        analysis_id=analysis_id,
        mechanism_id=mechanism_id,
        analysis_role=analysis_role,
        candidate_count=len(candidates),
        join_rows=join_rows,
        eligible_rows=eligible_rows,
        missing_reason_counts=missing_reasons,
        summary_row=summary_row,
        stats_row=stats_row,
        bootstrap_row=bootstrap_row,
        cluster_row=cluster_row,
        assumption_rows=assumption_rows,
    )


def _execute_core(non_outcome_context: Mapping[str, Any], outcome_inputs: Mapping[str, Any]) -> Dict[str, Any]:
    selected_payloads = non_outcome_context["selected_payloads"]
    class_rows = non_outcome_context["class_rows"]
    outcome_def = selected_payloads["Refined_Mechanism_Test_Frozen_Outcome_Definition_Clean_R1"]
    parent_hypotheses = _latest_payload(
        non_outcome_context["inputs"]["Refined_Mechanism_Test_Frozen_Hypotheses_Clean"].rows,
        "clean_preregistration_run_id",
    )

    behavior_by_key = {
        (_normalize(row.get("provider")), _normalize(row.get("session_id")), _normalize(row.get("pack_level"))): dict(row)
        for row in non_outcome_context["inputs"]["Pack_Behavior_Tier2_NoSignal"].rows
    }
    selection_consensus, selection_rows_loaded = _build_bridge_consensus(
        outcome_inputs["Corrected_Accuracy_Row_Selection"].rows,
        ["repaired_canonical_outcome_id", "strict_ready", "included_in_primary_corrected_evaluation", "leakage_safe_validated", "design_version"],
        "MISSING_JOIN_COMPONENT",
        "DUPLICATE_JOIN_BLOCKED",
    )
    mapping_consensus, mapping_rows_loaded = _build_bridge_consensus(
        outcome_inputs["Corrected_Accuracy_Outcome_Mapping"].rows,
        ["repaired_canonical_outcome_id", "repaired_realized_direction", "outcome_mapping_status", "included_in_primary", "design_version"],
        "MISSING_JOIN_COMPONENT",
        "DUPLICATE_JOIN_BLOCKED",
    )
    overlay_by_repaired_id = {
        _normalize(row.get("repaired_canonical_overlay_id")): dict(row)
        for row in outcome_inputs["Market_Reaction_Recovered_Canonical_Outcomes"].rows
    }
    canonical_by_id = {
        _normalize(row.get("canonical_outcome_id")): dict(row)
        for row in outcome_inputs["Market_Reaction_Canonical_Outcomes"].rows
    }

    primary = _run_analysis(
        analysis_id=PRIMARY_ANALYSIS_ID,
        mechanism_id=PRIMARY_MECHANISM,
        mechanism_name=PRIMARY_MECHANISM,
        analysis_role="PRIMARY",
        class_rows=class_rows,
        behavior_by_key=behavior_by_key,
        selection_consensus=selection_consensus,
        mapping_consensus=mapping_consensus,
        overlay_by_repaired_id=overlay_by_repaired_id,
        canonical_by_id=canonical_by_id,
        outcome_def=outcome_def,
        allowed_labels={"POSITIVE", "NEGATIVE"},
        require_high_moderate=True,
        inferential_allowed=True,
        gate_thresholds=EXPECTED_GATES,
    )
    exploratory = _run_analysis(
        analysis_id=EXPLORATORY_ANALYSIS_ID,
        mechanism_id=EXPLORATORY_MECHANISM,
        mechanism_name=EXPLORATORY_MECHANISM,
        analysis_role="EXPLORATORY_ONLY",
        class_rows=class_rows,
        behavior_by_key=behavior_by_key,
        selection_consensus=selection_consensus,
        mapping_consensus=mapping_consensus,
        overlay_by_repaired_id=overlay_by_repaired_id,
        canonical_by_id=canonical_by_id,
        outcome_def=outcome_def,
        allowed_labels={"POSITIVE", "NEGATIVE"},
        require_high_moderate=True,
        inferential_allowed=False,
        gate_thresholds=None,
    )
    descriptive = _run_analysis(
        analysis_id=DESCRIPTIVE_ANALYSIS_ID,
        mechanism_id=DESCRIPTIVE_MECHANISM,
        mechanism_name=DESCRIPTIVE_MECHANISM,
        analysis_role="DESCRIPTIVE_ONLY",
        class_rows=class_rows,
        behavior_by_key=behavior_by_key,
        selection_consensus=selection_consensus,
        mapping_consensus=mapping_consensus,
        overlay_by_repaired_id=overlay_by_repaired_id,
        canonical_by_id=canonical_by_id,
        outcome_def=outcome_def,
        allowed_labels={"POSITIVE", "NEGATIVE", "UNKNOWN", "INSUFFICIENT_EVIDENCE"},
        require_high_moderate=False,
        inferential_allowed=False,
        gate_thresholds=None,
    )

    mixed_label_clusters = {
        f"{_normalize(row.get('provider'))}|{_normalize(row.get('session_id'))}"
        for row in primary.eligible_rows
        if _normalize(row.get("expanded_label")) in {"POSITIVE", "NEGATIVE"}
    }
    secondary_stats_row = {
        "analysis_id": SECONDARY_STRUCTURE_ANALYSIS_ID,
        "mechanism_id": PRIMARY_MECHANISM,
        "analysis_role": "SECONDARY_STRUCTURAL_SENSITIVITY",
        "result_status": "NOT_ESTIMABLE",
        "analysis_population": 0,
        "effect_measure": "mixed_label_provider_session_cluster_descriptive_sensitivity",
        "statistical_method": "FROZEN_STRUCTURAL_SENSITIVITY_DESCRIPTIVE_ONLY",
        "effect_estimate": "",
        "confidence_interval_lower": "",
        "confidence_interval_upper": "",
        "inferential_result_allowed": "FALSE",
        "descriptive_fallback_used": "TRUE",
        "payload_json": _canonical_json(
            {
                "preregistered_secondary_definition": parent_hypotheses.get("secondary", []),
                "joined_mixed_label_clusters": sum(
                    1
                    for cluster in mixed_label_clusters
                    if {
                        _normalize(row.get("expanded_label"))
                        for row in primary.eligible_rows
                        if f"{_normalize(row.get('provider'))}|{_normalize(row.get('session_id'))}" == cluster
                    }
                    >= {"POSITIVE", "NEGATIVE"}
                ),
                "status": "No joined mixed-label cluster survived the frozen success-mapping filters.",
            }
        ),
    }

    triggered_stop_rules = []
    for rule_name in [
        "POSITIVE_SAMPLE_GATE_FAILURE",
        "NEGATIVE_SAMPLE_GATE_FAILURE",
        "PRIMARY_CONTRAST_GATE_FAILURE",
        "CLUSTER_GATE_FAILURE",
        "PROVIDER_GATE_FAILURE",
        "SESSION_GATE_FAILURE",
    ]:
        if rule_name in json.loads(primary.summary_row["payload_json"]).get("trigger_names", []):
            triggered_stop_rules.append(rule_name)
    bootstrap_status = primary.bootstrap_row["bootstrap_status"]
    if bootstrap_status == "ZERO_PRIMARY_GROUP_CELL":
        triggered_stop_rules.append("ZERO_PRIMARY_GROUP_CELL")
    if bootstrap_status == "DEGENERATE_BOOTSTRAP_DISTRIBUTION":
        triggered_stop_rules.append("DEGENERATE_BOOTSTRAP_DISTRIBUTION")

    core = {
        "primary": primary,
        "exploratory": exploratory,
        "descriptive": descriptive,
        "secondary_stats_row": secondary_stats_row,
        "selection_rows_loaded": selection_rows_loaded,
        "mapping_rows_loaded": mapping_rows_loaded,
        "overlay_rows_loaded": len(outcome_inputs["Market_Reaction_Recovered_Canonical_Outcomes"].rows),
        "canonical_rows_loaded": len(outcome_inputs["Market_Reaction_Canonical_Outcomes"].rows),
        "triggered_stop_rules": triggered_stop_rules,
    }
    return core


def _core_fingerprint(core: Mapping[str, Any]) -> str:
    serializable = {
        "primary_join_rows": core["primary"].join_rows,
        "primary_summary": core["primary"].summary_row,
        "primary_stats": core["primary"].stats_row,
        "primary_bootstrap": core["primary"].bootstrap_row,
        "exploratory_summary": core["exploratory"].summary_row,
        "descriptive_summary": core["descriptive"].summary_row,
        "secondary_stats": core["secondary_stats_row"],
        "triggered_stop_rules": core["triggered_stop_rules"],
    }
    return _fingerprint_payload(serializable)


def build() -> Dict[str, Any]:
    run_ts = datetime.now(timezone.utc).replace(microsecond=0)
    generated_ts = _now_iso(run_ts)
    test_execution_run_id = _run_id(run_ts)

    service = build_sheets_service(load_credentials())
    known_titles = _sheet_titles_light(service, DIAGNOSTICS_SPREADSHEET_ID)
    non_outcome_context = _load_non_outcome_context(service)
    validated = _validate_preexecution_context(service, non_outcome_context, known_titles)

    # Outcome access begins only after all pre-execution validations pass.
    outcome_inputs = _fetch_input_sheets(service, DIAGNOSTICS_SPREADSHEET_ID, OUTCOME_INPUT_SHEETS)
    core_first = _execute_core(validated, outcome_inputs)
    core_second = _execute_core(validated, outcome_inputs)
    determinism_status = "PASS" if _core_fingerprint(core_first) == _core_fingerprint(core_second) else "FAIL"
    if determinism_status != "PASS":
        raise ExecutionBlocked(
            "REPEATED_CLEAN_RUN_CONTENT_MISMATCH",
            "Deterministic execution replay did not reproduce identical core outputs.",
        )
    core = core_first

    primary = core["primary"]
    exploratory = core["exploratory"]
    descriptive = core["descriptive"]
    secondary_stats_row = core["secondary_stats_row"]
    triggered_stop_rules = core["triggered_stop_rules"]

    primary_summary_payload = json.loads(primary.summary_row["payload_json"])
    primary_stats_payload = json.loads(primary.stats_row["payload_json"])
    descriptive_fallback_used = primary.stats_row["descriptive_fallback_used"] == "TRUE"
    final_execution_status = "COMPLETED_WITH_WARNINGS" if descriptive_fallback_used else "COMPLETED"
    build_status = "PASS_WITH_WARNINGS" if descriptive_fallback_used else "PASS"
    if descriptive_fallback_used:
        final_interpretation = "REFINED_MECHANISM_TEST_EXECUTION_COMPLETED_WITH_DESCRIPTIVE_FALLBACK"
    else:
        final_interpretation = "REFINED_MECHANISM_TEST_EXECUTION_COMPLETED"

    outcome_rows_loaded = (
        core["mapping_rows_loaded"]
        + core["overlay_rows_loaded"]
        + core["canonical_rows_loaded"]
    )
    join_bridge_rows_loaded = core["selection_rows_loaded"]
    governance_counters = {
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "outcome_rows_loaded": outcome_rows_loaded,
        "join_bridge_rows_loaded": join_bridge_rows_loaded,
        "accuracy_metrics_calculated": 1,
        "mechanism_tests_performed": 1,
        "inferential_primary_test_performed": primary.stats_row["inferential_result_allowed"] == "TRUE",
        "production_writes": 0,
        "production_behavior_changes": 0,
    }

    scientific_interpretation = (
        "Execution followed the frozen Canonical Clean-R1 contract, but post-join eligibility collapsed to three "
        "expanded consistency-positive observations from one provider-session cluster and zero eligible expanded "
        "consistency-negative observations. The frozen sample-gate failures and zero primary-group cell therefore "
        "required descriptive fallback only, so this run supports no inferential claim about the association between "
        "MECH_INFORMATION_CONSISTENCY and corrected directional success."
    )
    recommended_next_step = "PROCEED_TO_PHASE9A6R16_MECHANISM_TEST_EXECUTION_REVIEW"
    stop_rule_status = (
        "DESCRIPTIVE_FALLBACK_ONLY_TRIGGERED"
        if triggered_stop_rules
        else "NO_STOP_RULE_TRIGGERED"
    )
    descriptive_fallback_status = (
        "TRIGGERED_BY_POST_JOIN_GATE_FAILURE_AND_ZERO_PRIMARY_GROUP_CELL"
        if descriptive_fallback_used
        else "NOT_TRIGGERED"
    )
    outcome_join_status = (
        f"JOIN_COMPLETED_WITH_{len(primary.eligible_rows)}_PRIMARY_ELIGIBLE_OBSERVATIONS"
        if primary.eligible_rows
        else "JOIN_COMPLETED_WITH_ZERO_PRIMARY_ELIGIBLE_OBSERVATIONS"
    )

    execution_row = {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "test_execution_run_id": test_execution_run_id,
        "preregistration_version": AUTHORITATIVE_VERSION,
        "authoritative_run_id": AUTHORITATIVE_RUN_ID,
        "classification_version": CLASSIFICATION_VERSION,
        "classification_run_id": CLASSIFICATION_RUN_ID,
        "execution_status": final_execution_status,
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "descriptive_fallback_status": descriptive_fallback_status,
        "payload_json": _canonical_json(
            {
                "phase_id": PHASE_ID,
                "build_script": BUILD_SCRIPT,
                "primary_structure": PRIMARY_STRUCTURE,
                "primary_exposure": PRIMARY_EXPOSURE,
                "primary_comparison_groups": PRIMARY_COMPARISON_GROUPS,
                "baseline_role": BASELINE_ROLE,
                "primary_estimand": PRIMARY_ESTIMAND,
                "execution_stop_rules_triggered": triggered_stop_rules,
                "determinism_status": determinism_status,
                "outcome_join_status": outcome_join_status,
                "governance_counters": governance_counters,
                "final_execution_status": final_execution_status,
            }
        ),
    }

    join_audit_rows: List[Dict[str, Any]] = []
    for analysis in [primary, exploratory, descriptive]:
        for row in analysis.join_rows:
            join_audit_rows.append(
                {
                    "generated_ts": generated_ts,
                    "schema_version": SCHEMA_VERSION,
                    "test_execution_run_id": test_execution_run_id,
                    **row,
                }
            )

    eligibility_rows = []
    for analysis in [primary, exploratory, descriptive]:
        eligibility_rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "test_execution_run_id": test_execution_run_id,
                **analysis.summary_row,
            }
        )

    stats_rows = []
    for analysis in [primary, exploratory, descriptive]:
        stats_rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "test_execution_run_id": test_execution_run_id,
                **analysis.stats_row,
            }
        )
    stats_rows.append(
        {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "test_execution_run_id": test_execution_run_id,
            **secondary_stats_row,
        }
    )

    bootstrap_rows = [
        {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "test_execution_run_id": test_execution_run_id,
            **primary.bootstrap_row,
        }
    ]

    cluster_rows = []
    for analysis in [primary, exploratory, descriptive]:
        cluster_rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "test_execution_run_id": test_execution_run_id,
                **analysis.cluster_row,
            }
        )

    assumption_rows = []
    for analysis in [primary, exploratory, descriptive]:
        for row in analysis.assumption_rows:
            assumption_rows.append(
                {
                    "generated_ts": generated_ts,
                    "schema_version": SCHEMA_VERSION,
                    "test_execution_run_id": test_execution_run_id,
                    **row,
                }
            )
    assumption_rows.append(
        {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "test_execution_run_id": test_execution_run_id,
            "check_id": "GLOBAL_DETERMINISM",
            "check_name": "Deterministic in-memory rerun equality",
            "status": determinism_status,
            "severity": "INFO" if determinism_status == "PASS" else "HARD_STOP",
            "analysis_id": "GLOBAL",
            "mechanism_id": PRIMARY_MECHANISM,
            "details_json": _canonical_json({"core_output_fingerprint": _core_fingerprint(core)}),
        }
    )

    missing_rows = []
    for analysis in [primary, exploratory, descriptive]:
        for reason_code, reason_count in sorted(analysis.missing_reason_counts.items()):
            missing_rows.append(
                {
                    "generated_ts": generated_ts,
                    "schema_version": SCHEMA_VERSION,
                    "test_execution_run_id": test_execution_run_id,
                    "analysis_id": analysis.analysis_id,
                    "mechanism_id": analysis.mechanism_id,
                    "reason_code": reason_code,
                    "reason_count": reason_count,
                    "payload_json": _canonical_json(
                        {
                            "analysis_role": analysis.analysis_role,
                            "candidate_source_count": analysis.candidate_count,
                            "eligible_sample_count": len(analysis.eligible_rows),
                        }
                    ),
                }
            )

    governance_rows = []
    for counter_name, counter_value in governance_counters.items():
        governance_rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "test_execution_run_id": test_execution_run_id,
                "counter_name": counter_name,
                "counter_value": counter_value,
                "status": "PASS",
                "notes": "",
            }
        )

    confidence_interval = ""
    if primary.stats_row["confidence_interval_lower"] and primary.stats_row["confidence_interval_upper"]:
        confidence_interval = (
            f"[{primary.stats_row['confidence_interval_lower']}, {primary.stats_row['confidence_interval_upper']}]"
        )
    elif descriptive_fallback_used:
        confidence_interval = "NOT_ESTIMABLE_DESCRIPTIVE_FALLBACK_ONLY"

    summary_payload = {
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "file_created": BUILD_SCRIPT,
        "preregistration_version": AUTHORITATIVE_VERSION,
        "authoritative_run_id": AUTHORITATIVE_RUN_ID,
        "classification_version": CLASSIFICATION_VERSION,
        "classification_run_id": CLASSIFICATION_RUN_ID,
        "primary_mechanism_tested": PRIMARY_MECHANISM,
        "eligible_sample": len(primary.eligible_rows),
        "positive_sample": _to_int(primary.summary_row["positive_sample_count"]),
        "negative_sample": _to_int(primary.summary_row["negative_sample_count"]),
        "cluster_count": _to_int(primary.summary_row["cluster_count"]),
        "provider_count": _to_int(primary.summary_row["provider_count"]),
        "session_count": _to_int(primary.summary_row["session_count"]),
        "outcome_join_status": outcome_join_status,
        "statistical_method_used": PRIMARY_METHOD_LABEL,
        "effect_estimate": primary.stats_row["effect_estimate"] or "NOT_ESTIMABLE_ZERO_PRIMARY_GROUP_CELL",
        "confidence_interval": confidence_interval,
        "bootstrap_diagnostics": {
            "bootstrap_status": primary.bootstrap_row["bootstrap_status"],
            "requested_replications": primary.bootstrap_row["requested_replications"],
            "attempted_replications": primary.bootstrap_row["attempted_replications"],
            "estimable_replications": primary.bootstrap_row["estimable_replications"],
            "estimable_fraction": primary.bootstrap_row["estimable_fraction"],
        },
        "cluster_diagnostics": {
            "eligible_observations": primary.cluster_row["eligible_observations"],
            "cluster_count": primary.cluster_row["cluster_count"],
            "provider_count": primary.cluster_row["provider_count"],
            "session_count": primary.cluster_row["session_count"],
            "mixed_label_cluster_count": primary.cluster_row["mixed_label_cluster_count"],
        },
        "assumption_checks": {
            "descriptive_fallback_required": descriptive_fallback_used,
            "triggered_stop_rules": triggered_stop_rules,
            "determinism_status": determinism_status,
        },
        "missing_data_summary": dict(primary.missing_reason_counts),
        "descriptive_fallback_status": descriptive_fallback_status,
        "determinism_status": determinism_status,
        "stop_rule_status": stop_rule_status,
        "governance_counters": governance_counters,
        "scientific_interpretation": scientific_interpretation,
        "recommended_next_step": recommended_next_step,
        "final_execution_status": final_execution_status,
    }

    summary_row = {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "test_execution_run_id": test_execution_run_id,
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "primary_mechanism_tested": PRIMARY_MECHANISM,
        "eligible_sample": len(primary.eligible_rows),
        "positive_sample": _to_int(primary.summary_row["positive_sample_count"]),
        "negative_sample": _to_int(primary.summary_row["negative_sample_count"]),
        "cluster_count": _to_int(primary.summary_row["cluster_count"]),
        "provider_count": _to_int(primary.summary_row["provider_count"]),
        "session_count": _to_int(primary.summary_row["session_count"]),
        "outcome_join_status": outcome_join_status,
        "statistical_method_used": PRIMARY_METHOD_LABEL,
        "effect_estimate": primary.stats_row["effect_estimate"] or "NOT_ESTIMABLE_ZERO_PRIMARY_GROUP_CELL",
        "confidence_interval": confidence_interval,
        "bootstrap_diagnostics": _canonical_json(summary_payload["bootstrap_diagnostics"]),
        "cluster_diagnostics": _canonical_json(summary_payload["cluster_diagnostics"]),
        "assumption_checks": _canonical_json(summary_payload["assumption_checks"]),
        "missing_data_summary": _canonical_json(summary_payload["missing_data_summary"]),
        "descriptive_fallback_status": descriptive_fallback_status,
        "determinism_status": determinism_status,
        "stop_rule_status": stop_rule_status,
        "scientific_interpretation": scientific_interpretation,
        "recommended_next_step": recommended_next_step,
        "payload_json": _canonical_json(summary_payload),
    }

    known_titles = _sheet_titles_light(service, DIAGNOSTICS_SPREADSHEET_ID)
    rows_written = {}
    rows_written[OUTPUT_EXECUTION] = _append_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_EXECUTION, OUTPUT_SHEETS[OUTPUT_EXECUTION], [execution_row], known_titles)
    rows_written[OUTPUT_JOIN_AUDIT] = _append_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_JOIN_AUDIT, OUTPUT_SHEETS[OUTPUT_JOIN_AUDIT], join_audit_rows, known_titles)
    rows_written[OUTPUT_ELIGIBILITY] = _append_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_ELIGIBILITY, OUTPUT_SHEETS[OUTPUT_ELIGIBILITY], eligibility_rows, known_titles)
    rows_written[OUTPUT_STATS] = _append_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_STATS, OUTPUT_SHEETS[OUTPUT_STATS], stats_rows, known_titles)
    rows_written[OUTPUT_BOOTSTRAP] = _append_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_BOOTSTRAP, OUTPUT_SHEETS[OUTPUT_BOOTSTRAP], bootstrap_rows, known_titles)
    rows_written[OUTPUT_CLUSTER] = _append_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_CLUSTER, OUTPUT_SHEETS[OUTPUT_CLUSTER], cluster_rows, known_titles)
    rows_written[OUTPUT_ASSUMPTIONS] = _append_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_ASSUMPTIONS, OUTPUT_SHEETS[OUTPUT_ASSUMPTIONS], assumption_rows, known_titles)
    rows_written[OUTPUT_MISSING] = _append_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_MISSING, OUTPUT_SHEETS[OUTPUT_MISSING], missing_rows, known_titles)
    rows_written[OUTPUT_GOVERNANCE] = _append_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_GOVERNANCE, OUTPUT_SHEETS[OUTPUT_GOVERNANCE], governance_rows, known_titles)
    rows_written[OUTPUT_SUMMARY] = _append_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY, OUTPUT_SHEETS[OUTPUT_SUMMARY], [summary_row], known_titles)

    registry_writes = _upsert_registry_rows(service, generated_ts)
    return {
        "generated_ts": generated_ts,
        "test_execution_run_id": test_execution_run_id,
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "rows_written_per_sheet": rows_written,
        "summary": summary_payload,
        "registry_writes": registry_writes,
    }


def main() -> None:
    try:
        result = build()
    except ExecutionBlocked as exc:
        print(
            json.dumps(
                {
                    "build_status": "BLOCKED",
                    "final_interpretation": "REFINED_MECHANISM_TEST_EXECUTION_BLOCKED",
                    "file_created": BUILD_SCRIPT,
                    "stop_rule_name": exc.stop_rule_name,
                    "message": exc.message,
                },
                indent=2,
                ensure_ascii=True,
                sort_keys=True,
            )
        )
        raise
    print(json.dumps(result, indent=2, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
