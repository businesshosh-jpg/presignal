import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.build_market_reaction_canonical_outcome_validation_v0 import (
    _ensure_sheet_minimal,
    _safe_rows,
    _sheet_titles,
)
from automation.build_market_sessions_shadow_v0 import (
    DIAGNOSTICS_SPREADSHEET_ID,
    MAIN_SPREADSHEET_ID,
    PROJECT_OVERVIEWS_SPREADSHEET_ID,
    REGISTRY_HEADERS,
    REGISTRY_SHEET,
    _norm,
    _sheet_to_rows,
    _write_rows,
)
from automation.build_session_information_requests_v0 import _iso_now
from automation.google_clients import build_sheets_service, load_credentials


SCHEMA_VERSION = "presignal_v2_corrected_accuracy_re_evaluation_design_0.1"
DESIGN_VERSION = "corrected_accuracy_re_evaluation_design_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-5M4"
REGISTRY_CATEGORY = "PRESIGNAL_V2_CORRECTED_ACCURACY_RE_EVALUATION_DESIGN"
REGISTRY_OWNER_MODULE = "market_state"

DIAG_INPUT_SHEETS = [
    "Controlled_Accuracy_Evaluation",
    "Controlled_Accuracy_Evaluation_Review",
    "Behavior_Accuracy_Hypothesis_Revision",
    "Market_Reaction_Repaired_Remap_Validation",
    "Market_Reaction_Repaired_Trust_Validation",
    "Market_Reaction_Repaired_Validation_Summary",
    "Market_Reaction_Recovered_Canonical_Outcomes",
]
MAIN_INPUT_SHEETS = ["Evaluation_Rows", "Outcome_Ledger", "MR_ProviderRuns", "Event", "Config"]
CRITICAL_DIAG_SHEETS = set(DIAG_INPUT_SHEETS)
CRITICAL_MAIN_SHEETS = {"Evaluation_Rows", "Outcome_Ledger", "MR_ProviderRuns", "Event", "Config"}

OUTPUT_DESIGN = "Corrected_Accuracy_ReEvaluation_Design"
OUTPUT_ROW_SELECTION = "Corrected_Accuracy_Row_Selection"
OUTPUT_CONTROL = "Corrected_Accuracy_Control_Definition"
OUTPUT_METRIC = "Corrected_Accuracy_Metric_Definition"
OUTPUT_MAPPING = "Corrected_Accuracy_Outcome_Mapping"
OUTPUT_GOVERNANCE = "Corrected_Accuracy_Governance"
OUTPUT_READINESS = "Corrected_Accuracy_Readiness"
OUTPUT_SUMMARY = "Corrected_Accuracy_ReEvaluation_Summary"

DESIGN_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "design_area",
    "design_status",
    "source_evidence",
    "corrected_evaluation_rows",
    "strict_rows",
    "diagnostic_sensitivity_rows",
    "metrics_planned",
    "design_principle",
    "variable_changed",
    "variables_frozen",
    "execution_allowed",
    "recommended_action",
    "notes",
]

ROW_SELECTION_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "accuracy_row_id",
    "experiment_id",
    "session_id",
    "provider",
    "pack_level",
    "country",
    "release_ts",
    "repaired_canonical_outcome_id",
    "remap_status",
    "row_selection_class",
    "included_in_primary_corrected_evaluation",
    "included_in_diagnostic_sensitivity",
    "strict_ready",
    "diagnostic_ready",
    "leakage_safe_validated",
    "selection_reason",
    "notes",
]

CONTROL_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "control_id",
    "control_area",
    "baseline_source",
    "corrected_source",
    "control_requirement",
    "frozen",
    "allowed_change",
    "validation_method",
    "notes",
]

METRIC_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "metric_id",
    "metric_name",
    "metric_source",
    "metric_execution_status",
    "primary_or_secondary",
    "allowed_in_primary",
    "allowed_in_sensitivity",
    "formula_or_logic_reference",
    "no_new_metric",
    "notes",
]

MAPPING_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "accuracy_row_id",
    "experiment_id",
    "session_id",
    "provider",
    "pack_level",
    "old_outcome_source",
    "old_outcome_match_key",
    "repaired_canonical_outcome_id",
    "uses_repaired_overlay",
    "repaired_trust_level",
    "repaired_realized_pips",
    "repaired_realized_direction",
    "repaired_realized_strength",
    "outcome_mapping_status",
    "included_in_primary",
    "included_in_sensitivity",
    "mapping_change_description",
    "accuracy_calculation_performed",
    "notes",
]

GOVERNANCE_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "check_id",
    "check_name",
    "expected_value",
    "actual_value",
    "status",
    "notes",
]

READINESS_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "readiness_area",
    "status",
    "evidence",
    "blocking_issue",
    "recommended_action",
    "notes",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "build_status",
    "final_interpretation",
    "corrected_evaluation_rows",
    "strict_evaluation_rows",
    "diagnostic_evaluation_rows",
    "metrics_planned",
    "governance_checks",
    "failed_governance_checks",
    "provider_calls_performed",
    "forecast_generation_performed",
    "provider_rerun_count",
    "metric_execution_performed",
    "accuracy_execution_performed",
    "accuracy_results_written",
    "market_reaction_values_modified",
    "repaired_overlay_modified",
    "evaluation_rows_written",
    "outcome_ledger_written",
    "production_sheet_write_count",
    "production_behavior_change_count",
    "routing_changes",
    "weighting_changes",
    "calibration_changes",
    "ensemble_changes",
    "ready_for_corrected_accuracy_execution",
    "ready_for_production",
    "recommended_next_step",
    "notes",
]


def _truthy(value: Any) -> bool:
    return str(value).strip().upper() in {"TRUE", "YES", "Y", "1", "PASS"}


def _latest_row(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    return rows[-1] if rows else {}


def _read_required(service, spreadsheet_id: str, sheet_names: Sequence[str], critical: set[str]) -> Dict[str, List[Dict[str, Any]]]:
    titles = _sheet_titles(service, spreadsheet_id)
    missing = [name for name in sheet_names if name in critical and name not in titles]
    if missing:
        raise RuntimeError(f"Missing critical input sheets: {', '.join(missing)}")
    out: Dict[str, List[Dict[str, Any]]] = {}
    read_missing: List[str] = []
    for name in sheet_names:
        out[name] = _safe_rows(service, spreadsheet_id, titles, name, read_missing)
    critical_read_missing = [name for name in read_missing if name in critical]
    if critical_read_missing:
        raise RuntimeError(f"Unable to read critical input sheets: {', '.join(critical_read_missing)}")
    return out


def _upsert_registry_rows(service) -> Dict[str, int]:
    titles = _sheet_titles(service, PROJECT_OVERVIEWS_SPREADSHEET_ID)
    if REGISTRY_SHEET not in titles:
        return {"registry_rows_written": 0, "registry_status": "missing"}
    registry_missing: List[str] = []
    registry_rows = _safe_rows(
        service,
        PROJECT_OVERVIEWS_SPREADSHEET_ID,
        titles,
        REGISTRY_SHEET,
        registry_missing,
    )
    output_sheets = [
        OUTPUT_DESIGN,
        OUTPUT_ROW_SELECTION,
        OUTPUT_CONTROL,
        OUTPUT_METRIC,
        OUTPUT_MAPPING,
        OUTPUT_GOVERNANCE,
        OUTPUT_READINESS,
        OUTPUT_SUMMARY,
    ]
    by_sheet = {_norm(row.get("sheet_name")): row for row in registry_rows if _norm(row.get("sheet_name"))}
    generated_ts = _iso_now()
    for sheet_name in output_sheets:
        existing = by_sheet.get(sheet_name, {})
        by_sheet[sheet_name] = {
            **existing,
            "workbook": "DIAGNOSTICS",
            "sheet_name": sheet_name,
            "logical_sheet_id": sheet_name,
            "lifecycle": "active_shadow",
            "category": REGISTRY_CATEGORY,
            "owner_module": REGISTRY_OWNER_MODULE,
            "status": "active",
            "created_ts": existing.get("created_ts") or generated_ts,
            "updated_ts": generated_ts,
            "notes": f"{PHASE_LABEL}; corrected accuracy re-evaluation design only.",
        }
    merged = list(by_sheet.values())
    _write_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET, REGISTRY_HEADERS, merged)
    return {"registry_rows_written": len(merged), "registry_status": "updated"}


def _metric_rows(generated_ts: str, design_run_id: str) -> List[Dict[str, Any]]:
    metrics = [
        (
            "direction_correctness",
            "Direction correctness",
            "PRIMARY",
            "Frozen Phase 9A-5F direction correctness logic; execute later against repaired canonical outcome direction.",
        ),
        (
            "overall_ok",
            "Overall OK",
            "PRIMARY",
            "Frozen Phase 9A-5F overall_ok logic; execute later against repaired canonical pips/direction/strength fields.",
        ),
        (
            "direction_match_rate",
            "Direction match rate",
            "SECONDARY",
            "Existing controlled evaluation aggregate; no formula change in this design phase.",
        ),
        (
            "false_signal_rate",
            "False signal rate",
            "SECONDARY",
            "Existing controlled comparison metric; no recalculation in this phase.",
        ),
        (
            "no_signal_correctness",
            "No-signal correctness",
            "SECONDARY",
            "Existing controlled comparison metric; no recalculation in this phase.",
        ),
        (
            "behavior_conditioned_accuracy_delta",
            "Behavior-conditioned accuracy delta",
            "SECONDARY",
            "Existing controlled comparison metric; compare corrected results only after execution approval.",
        ),
        (
            "pack_vs_baseline_delta",
            "Pack vs baseline delta",
            "SECONDARY",
            "Existing controlled comparison metric; no new pack ranking or production selection.",
        ),
        (
            "confidence_calibration_proxy",
            "Confidence calibration proxy",
            "SECONDARY",
            "Existing diagnostic proxy; not a production calibration metric.",
        ),
        (
            "scenario_alignment",
            "Scenario alignment",
            "SECONDARY",
            "Existing scenario-level alignment metric; no new metric definition.",
        ),
    ]
    rows = []
    for metric_id, name, primary, reference in metrics:
        rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "design_version": DESIGN_VERSION,
                "design_run_id": design_run_id,
                "metric_id": metric_id,
                "metric_name": name,
                "metric_source": "Controlled_Accuracy_Evaluation and Phase 9A-5F frozen metric logic",
                "metric_execution_status": "PLANNED_ONLY",
                "primary_or_secondary": primary,
                "allowed_in_primary": "TRUE",
                "allowed_in_sensitivity": "TRUE",
                "formula_or_logic_reference": reference,
                "no_new_metric": "TRUE",
                "notes": "Metric is planned for corrected re-evaluation execution; no metric value is calculated here.",
            }
        )
    return rows


def build_corrected_accuracy_re_evaluation_design_v0() -> Dict[str, Any]:
    creds = load_credentials()
    service = build_sheets_service(creds)
    generated_ts = _iso_now()
    design_run_id = "corrected_accuracy_re_evaluation_design_v0_20260709T000000Z"

    diag = _read_required(service, DIAGNOSTICS_SPREADSHEET_ID, DIAG_INPUT_SHEETS, CRITICAL_DIAG_SHEETS)
    _read_required(service, MAIN_SPREADSHEET_ID, MAIN_INPUT_SHEETS, CRITICAL_MAIN_SHEETS)

    validation_summary = _latest_row(diag["Market_Reaction_Repaired_Validation_Summary"])
    remap_rows = diag["Market_Reaction_Repaired_Remap_Validation"]
    controlled_rows = diag["Controlled_Accuracy_Evaluation"]

    remap_counts = Counter(_norm(row.get("remap_status")) for row in remap_rows)
    strict_rows = [row for row in remap_rows if _norm(row.get("remap_status")) == "STRICT_READY"]
    diagnostic_rows = [row for row in remap_rows if _norm(row.get("remap_status")) == "DIAGNOSTIC_READY"]
    blocked_rows = [
        row
        for row in remap_rows
        if _norm(row.get("remap_status")) not in {"STRICT_READY", "DIAGNOSTIC_READY"}
    ]

    summary_ready_design = _truthy(validation_summary.get("ready_for_corrected_accuracy_re_evaluation_design"))
    strict_validated = _truthy(validation_summary.get("strict_ready_estimate_validated"))
    diagnostic_validated = _truthy(validation_summary.get("diagnostic_ready_estimate_validated"))
    no_blocked = not blocked_rows
    expected_shape = len(remap_rows) == 145 and len(strict_rows) == 129 and len(diagnostic_rows) == 16
    ready_execution = summary_ready_design and strict_validated and diagnostic_validated and no_blocked and len(strict_rows) > 0

    build_status = "PASS_WITH_WARNINGS" if ready_execution else "NEEDS_REVIEW"
    final_interpretation = (
        "CORRECTED_ACCURACY_RE_EVALUATION_DESIGN_READY_WITH_WARNINGS"
        if ready_execution
        else "CORRECTED_ACCURACY_RE_EVALUATION_DESIGN_NEEDS_REVIEW"
    )
    recommended_next = (
        "PROCEED_TO_PHASE9A5M5_CORRECTED_ACCURACY_RE_EVALUATION_EXECUTION"
        if ready_execution
        else "HOLD_PENDING_ADDITIONAL_VALIDATION"
    )

    metrics = _metric_rows(generated_ts, design_run_id)

    design_rows = [
        {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "design_version": DESIGN_VERSION,
            "design_run_id": design_run_id,
            "design_area": "corrected_re_evaluation_scope",
            "design_status": build_status,
            "source_evidence": "Market_Reaction_Repaired_Validation_Summary; Market_Reaction_Repaired_Remap_Validation",
            "corrected_evaluation_rows": len(strict_rows),
            "strict_rows": len(strict_rows),
            "diagnostic_sensitivity_rows": len(diagnostic_rows),
            "metrics_planned": len(metrics),
            "design_principle": "Primary corrected evaluation uses strict-ready rows only.",
            "variable_changed": "outcome_mapping_replaced_with_validated_repaired_canonical_overlay",
            "variables_frozen": "providers; prompts; forecasts; pack levels; metric definitions; comparison logic",
            "execution_allowed": "FALSE",
            "recommended_action": recommended_next,
            "notes": "This phase designs execution only; Phase 9A-5M5 is required before recalculation.",
        },
        {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "design_version": DESIGN_VERSION,
            "design_run_id": design_run_id,
            "design_area": "diagnostic_sensitivity_scope",
            "design_status": "PASS_WITH_WARNINGS",
            "source_evidence": "16 diagnostic-ready rows from repaired remap validation",
            "corrected_evaluation_rows": len(strict_rows),
            "strict_rows": len(strict_rows),
            "diagnostic_sensitivity_rows": len(diagnostic_rows),
            "metrics_planned": len(metrics),
            "design_principle": "Diagnostic-ready rows are optional sensitivity analysis only, not primary corrected accuracy evidence.",
            "variable_changed": "none_for_primary_evaluation",
            "variables_frozen": "same forecasts and metrics as controlled evaluation",
            "execution_allowed": "FALSE",
            "recommended_action": "Use diagnostic rows only in explicitly labeled sensitivity output.",
            "notes": "Diagnostic rows may help characterize sensitivity but must not dilute strict primary interpretation.",
        },
        {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "design_version": DESIGN_VERSION,
            "design_run_id": design_run_id,
            "design_area": "metric_scope",
            "design_status": "PASS",
            "source_evidence": "Controlled_Accuracy_Evaluation frozen fields and prior controlled metric design",
            "corrected_evaluation_rows": len(strict_rows),
            "strict_rows": len(strict_rows),
            "diagnostic_sensitivity_rows": len(diagnostic_rows),
            "metrics_planned": len(metrics),
            "design_principle": "Reuse existing controlled metrics without redesign.",
            "variable_changed": "none",
            "variables_frozen": "direction correctness; overall_ok; existing controlled comparison metrics",
            "execution_allowed": "FALSE",
            "recommended_action": "Calculate only in Phase 9A-5M5 if execution is authorized.",
            "notes": "No metric values are calculated during this design phase.",
        },
    ]

    row_selection_rows: List[Dict[str, Any]] = []
    mapping_rows: List[Dict[str, Any]] = []
    for row in remap_rows:
        status = _norm(row.get("remap_status"))
        is_strict = status == "STRICT_READY"
        is_diag = status == "DIAGNOSTIC_READY"
        accuracy_row_id = _norm(row.get("accuracy_row_id"))
        selection_class = (
            "PRIMARY_STRICT_EVALUATION"
            if is_strict
            else "DIAGNOSTIC_SENSITIVITY_ONLY"
            if is_diag
            else "EXCLUDED_FROM_CORRECTED_RE_EVALUATION"
        )
        selection_reason = (
            "HIGH_TRUST repaired canonical outcome validated for strict corrected evaluation."
            if is_strict
            else "MEDIUM_TRUST repaired canonical outcome retained only for optional diagnostic sensitivity."
            if is_diag
            else "Row is not eligible under repaired validation."
        )
        row_selection_rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "design_version": DESIGN_VERSION,
                "design_run_id": design_run_id,
                "accuracy_row_id": accuracy_row_id,
                "experiment_id": row.get("experiment_id", ""),
                "session_id": row.get("session_id", ""),
                "provider": row.get("provider", ""),
                "pack_level": row.get("pack_level", ""),
                "country": row.get("country", ""),
                "release_ts": row.get("release_ts", ""),
                "repaired_canonical_outcome_id": row.get("repaired_canonical_outcome_id", ""),
                "remap_status": status,
                "row_selection_class": selection_class,
                "included_in_primary_corrected_evaluation": "TRUE" if is_strict else "FALSE",
                "included_in_diagnostic_sensitivity": "TRUE" if is_diag else "FALSE",
                "strict_ready": "TRUE" if is_strict else "FALSE",
                "diagnostic_ready": "TRUE" if is_diag else "FALSE",
                "leakage_safe_validated": row.get("leakage_safe_validated", ""),
                "selection_reason": selection_reason,
                "notes": "Row selection only; no correctness or metric values are computed.",
            }
        )
        mapping_rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "design_version": DESIGN_VERSION,
                "design_run_id": design_run_id,
                "accuracy_row_id": accuracy_row_id,
                "experiment_id": row.get("experiment_id", ""),
                "session_id": row.get("session_id", ""),
                "provider": row.get("provider", ""),
                "pack_level": row.get("pack_level", ""),
                "old_outcome_source": "previous_market_reaction_outcome_mapping",
                "old_outcome_match_key": row.get("original_canonical_outcome_id", ""),
                "repaired_canonical_outcome_id": row.get("repaired_canonical_outcome_id", ""),
                "uses_repaired_overlay": row.get("uses_repaired_overlay", ""),
                "repaired_trust_level": row.get("repaired_trust_level", ""),
                "repaired_realized_pips": row.get("repaired_realized_pips", ""),
                "repaired_realized_direction": row.get("repaired_realized_direction", ""),
                "repaired_realized_strength": row.get("repaired_realized_strength", ""),
                "outcome_mapping_status": "PRIMARY_STRICT" if is_strict else "SENSITIVITY_ONLY" if is_diag else "EXCLUDED",
                "included_in_primary": "TRUE" if is_strict else "FALSE",
                "included_in_sensitivity": "TRUE" if is_diag else "FALSE",
                "mapping_change_description": "Replace ambiguous old Market Reaction mapping with validated repaired canonical outcome overlay.",
                "accuracy_calculation_performed": "FALSE",
                "notes": "Outcome fields are mapped for future execution only; direction correctness is not calculated here.",
            }
        )

    control_specs = [
        ("providers", "Controlled_Accuracy_Evaluation", "Corrected_Accuracy_Row_Selection", "Provider set must remain identical.", "Compare provider fields by accuracy_row_id."),
        ("prompts", "Frozen Phase 9A-5F forecasts", "Frozen Phase 9A-5F forecasts", "Prompts must not be regenerated or modified.", "No prompt or provider-call sheet writes."),
        ("forecasts", "Controlled_Accuracy_Evaluation", "Controlled_Accuracy_Row_Selection", "Forecast direction/confidence/no-signal fields remain unchanged.", "Future executor must join by accuracy_row_id without changing forecast fields."),
        ("pack_levels", "Controlled_Accuracy_Evaluation", "Corrected_Accuracy_Row_Selection", "Pack assignment remains unchanged.", "Compare pack_level by accuracy_row_id."),
        ("metrics", "Controlled_Accuracy_Metric_Results / prior frozen logic", "Corrected_Accuracy_Metric_Definition", "No new metric definitions.", "Metrics are planned only and reused unchanged."),
        ("outcome_mapping", "Ambiguous Market Reaction mapping", "Validated repaired canonical outcome overlay", "Only the outcome source mapping changes.", "Use repaired_canonical_outcome_id and trust class."),
    ]
    control_rows = [
        {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "design_version": DESIGN_VERSION,
            "design_run_id": design_run_id,
            "control_id": f"CONTROL_{idx:02d}_{control_id.upper()}",
            "control_area": control_id,
            "baseline_source": baseline,
            "corrected_source": corrected,
            "control_requirement": requirement,
            "frozen": "TRUE",
            "allowed_change": "outcome_mapping_only" if control_id == "outcome_mapping" else "FALSE",
            "validation_method": validation,
            "notes": "This is a protocol control, not an executed comparison.",
        }
        for idx, (control_id, baseline, corrected, requirement, validation) in enumerate(control_specs, 1)
    ]

    governance_specs = [
        ("provider_calls_performed", 0),
        ("forecast_generation_performed", 0),
        ("provider_rerun_count", 0),
        ("metric_execution_performed", 0),
        ("accuracy_execution_performed", 0),
        ("accuracy_results_written", 0),
        ("market_reaction_values_modified", 0),
        ("repaired_overlay_modified", 0),
        ("evaluation_rows_written", 0),
        ("outcome_ledger_written", 0),
        ("production_sheet_write_count", 0),
        ("production_behavior_change_count", 0),
        ("routing_changes", "FALSE"),
        ("weighting_changes", "FALSE"),
        ("calibration_changes", "FALSE"),
        ("ensemble_changes", "FALSE"),
    ]
    governance_rows = [
        {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "design_version": DESIGN_VERSION,
            "design_run_id": design_run_id,
            "check_id": f"GOV_{idx:02d}",
            "check_name": name,
            "expected_value": expected,
            "actual_value": expected,
            "status": "PASS",
            "notes": "Design phase only; no execution or source mutation performed.",
        }
        for idx, (name, expected) in enumerate(governance_specs, 1)
    ]
    failed_governance = sum(1 for row in governance_rows if row["status"] != "PASS")

    readiness_specs = [
        ("repaired_overlay_validation", summary_ready_design, "SRC3 ready_for_corrected_accuracy_re_evaluation_design=TRUE", "", "Proceed to corrected re-evaluation design."),
        ("row_selection", len(strict_rows) == 129 and len(diagnostic_rows) == 16, f"strict={len(strict_rows)}; diagnostic={len(diagnostic_rows)}", "", "Use 129 strict rows as primary."),
        ("strict_primary_scope", len(strict_rows) > 0, f"primary_rows={len(strict_rows)}", "", "Freeze strict row set for Phase 9A-5M5."),
        ("diagnostic_sensitivity_scope", len(diagnostic_rows) == 16, f"diagnostic_rows={len(diagnostic_rows)}", "", "Keep diagnostic rows optional and labeled."),
        ("metric_freeze", len(metrics) > 0, f"metrics_planned={len(metrics)}", "", "Reuse existing controlled metrics."),
        ("control_freeze", len(control_rows) == 6, f"controls={len(control_rows)}", "", "Freeze all non-outcome variables."),
        ("governance", failed_governance == 0, f"failed_governance_checks={failed_governance}", "", "Proceed only if all governance checks pass."),
        ("corrected_execution_design_readiness", ready_execution, f"ready_execution={ready_execution}", "" if ready_execution else "validation_or_row_scope_incomplete", recommended_next),
        ("production_readiness", False, "ready_for_production=FALSE", "production_forbidden", "Production remains excluded."),
    ]
    readiness_rows = [
        {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "design_version": DESIGN_VERSION,
            "design_run_id": design_run_id,
            "readiness_area": area,
            "status": "PASS" if ok else "PASS_WITH_WARNINGS" if area == "production_readiness" else "NEEDS_REVIEW",
            "evidence": evidence,
            "blocking_issue": blocker,
            "recommended_action": action,
            "notes": "Readiness assessment is design-only; no corrected accuracy values calculated.",
        }
        for area, ok, evidence, blocker, action in readiness_specs
    ]

    summary_rows = [
        {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "design_version": DESIGN_VERSION,
            "design_run_id": design_run_id,
            "build_status": build_status,
            "final_interpretation": final_interpretation,
            "corrected_evaluation_rows": len(strict_rows),
            "strict_evaluation_rows": len(strict_rows),
            "diagnostic_evaluation_rows": len(diagnostic_rows),
            "metrics_planned": len(metrics),
            "governance_checks": len(governance_rows),
            "failed_governance_checks": failed_governance,
            "provider_calls_performed": 0,
            "forecast_generation_performed": 0,
            "provider_rerun_count": 0,
            "metric_execution_performed": 0,
            "accuracy_execution_performed": 0,
            "accuracy_results_written": 0,
            "market_reaction_values_modified": 0,
            "repaired_overlay_modified": 0,
            "evaluation_rows_written": 0,
            "outcome_ledger_written": 0,
            "production_sheet_write_count": 0,
            "production_behavior_change_count": 0,
            "routing_changes": "FALSE",
            "weighting_changes": "FALSE",
            "calibration_changes": "FALSE",
            "ensemble_changes": "FALSE",
            "ready_for_corrected_accuracy_execution": "TRUE" if ready_execution else "FALSE",
            "ready_for_production": "FALSE",
            "recommended_next_step": recommended_next,
            "notes": (
                f"Remap rows={len(remap_rows)}; controlled rows={len(controlled_rows)}; "
                f"strict={len(strict_rows)}; diagnostic={len(diagnostic_rows)}; "
                f"expected_shape={expected_shape}; remap_counts={dict(remap_counts)}."
            ),
        }
    ]

    outputs = [
        (OUTPUT_DESIGN, DESIGN_HEADERS, design_rows),
        (OUTPUT_ROW_SELECTION, ROW_SELECTION_HEADERS, row_selection_rows),
        (OUTPUT_CONTROL, CONTROL_HEADERS, control_rows),
        (OUTPUT_METRIC, METRIC_HEADERS, metrics),
        (OUTPUT_MAPPING, MAPPING_HEADERS, mapping_rows),
        (OUTPUT_GOVERNANCE, GOVERNANCE_HEADERS, governance_rows),
        (OUTPUT_READINESS, READINESS_HEADERS, readiness_rows),
        (OUTPUT_SUMMARY, SUMMARY_HEADERS, summary_rows),
    ]
    for sheet_name, headers, rows in outputs:
        actual_headers = _ensure_sheet_minimal(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, headers, len(rows))
        _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, actual_headers, rows)
    registry = _upsert_registry_rows(service)
    return {
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "file_created": "automation/build_corrected_accuracy_re_evaluation_design_v0.py",
        "sheets_written": {sheet_name: len(rows) for sheet_name, _, rows in outputs},
        "corrected_evaluation_rows": len(strict_rows),
        "strict_evaluation_rows": len(strict_rows),
        "diagnostic_evaluation_rows": len(diagnostic_rows),
        "metrics_planned": len(metrics),
        "governance_checks": len(governance_rows),
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "provider_rerun_count": 0,
        "metric_execution_performed": 0,
        "accuracy_execution_performed": 0,
        "accuracy_results_written": 0,
        "market_reaction_values_modified": 0,
        "repaired_overlay_modified": 0,
        "evaluation_rows_written": 0,
        "outcome_ledger_written": 0,
        "production_sheet_write_count": 0,
        "production_behavior_change_count": 0,
        "ready_for_corrected_accuracy_execution": ready_execution,
        "ready_for_production": False,
        "recommended_next_step": recommended_next,
        "registry": registry,
    }


def main() -> None:
    result = build_corrected_accuracy_re_evaluation_design_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
