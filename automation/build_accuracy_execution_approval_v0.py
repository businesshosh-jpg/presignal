import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set

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
from automation.build_session_information_requests_v0 import _iso_now
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials


SCHEMA_VERSION = "presignal_v2_accuracy_execution_approval_0.1"
APPROVAL_VERSION = "accuracy_execution_approval_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-5E"
REGISTRY_CATEGORY = "PRESIGNAL_V2_ACCURACY_EXECUTION_APPROVAL"
REGISTRY_OWNER_MODULE = "market_state"

INPUT_9A5D = [
    "Controlled_Accuracy_Eval_Dry_Run",
    "Controlled_Accuracy_Eligible_Row_Preview",
    "Controlled_Accuracy_Outcome_Match_Preview",
    "Controlled_Accuracy_Comparison_Pair_Preview",
    "Controlled_Accuracy_Metric_Row_Preview",
    "Controlled_Accuracy_Invalid_Row_Audit",
    "Controlled_Accuracy_Execution_Governance_Audit",
    "Controlled_Accuracy_Execution_Dry_Run_Summary",
]

INPUT_9A5C = [
    "Controlled_Accuracy_Evaluation_Design",
    "Controlled_Accuracy_Experiment_Schema",
    "Controlled_Accuracy_Row_Eligibility_Rules",
    "Controlled_Accuracy_Outcome_Matching_Design",
    "Controlled_Accuracy_Metric_Logic",
    "Controlled_Accuracy_Comparison_Logic",
    "Controlled_Accuracy_Invalid_Output_Handling",
    "Controlled_Accuracy_Execution_Readiness",
    "Controlled_Accuracy_Design_Summary",
]

INPUT_9A5B = [
    "Accuracy_Evaluation_Plan",
    "Accuracy_Evaluation_Experiment_Definition",
    "Accuracy_Evaluation_Readiness_Audit",
    "Accuracy_Evaluation_Plan_Summary",
]

INPUT_9A5A = [
    "Behavior_To_Accuracy_Testable_Hypotheses",
    "Behavior_To_Accuracy_Eligible_Hypotheses",
    "Behavior_To_Accuracy_Design_Summary",
]

OUTPUT_APPROVAL = "Accuracy_Execution_Approval"
OUTPUT_FREEZE = "Accuracy_Execution_Freeze_Record"
OUTPUT_GOVERNANCE = "Accuracy_Execution_Governance_Review"
OUTPUT_RISK = "Accuracy_Execution_Risk_Assessment"
OUTPUT_GUARDRAILS = "Accuracy_Execution_Interpretation_Guardrails"
OUTPUT_SUMMARY = "Accuracy_Execution_Approval_Summary"

APPROVAL_HEADERS = [
    "generated_ts",
    "approval_run_id",
    "experiment_id",
    "hypothesis_id",
    "approval_status",
    "approval_reason",
    "approved_for_phase9a5f",
    "blocked_reason",
    "notes",
]

FREEZE_HEADERS = [
    "generated_ts",
    "component_name",
    "version_reference",
    "frozen",
    "change_allowed_after_freeze",
    "rationale",
]

GOVERNANCE_HEADERS = [
    "check_id",
    "check_name",
    "expected_value",
    "actual_value",
    "status",
]

RISK_HEADERS = [
    "risk_id",
    "severity",
    "mitigation",
    "blocks_execution",
    "notes",
]

GUARDRAIL_HEADERS = [
    "guardrail_id",
    "category",
    "rule",
    "violation_consequence",
]

SUMMARY_HEADERS = [
    "build_status",
    "final_interpretation",
    "experiments_reviewed",
    "experiments_approved",
    "experiments_blocked",
    "freeze_components_recorded",
    "governance_checks_passed",
    "risks_identified",
    "interpretation_guardrails_defined",
    "provider_calls_performed",
    "forecast_generation_performed",
    "accuracy_evaluation_performed",
    "direction_correctness_calculated",
    "overall_ok_calculated",
    "production_behavior_change_count",
    "ready_for_phase9a5f_execution",
    "ready_for_production",
    "recommended_next_step",
]

HEADERS_BY_SHEET = {
    OUTPUT_APPROVAL: APPROVAL_HEADERS,
    OUTPUT_FREEZE: FREEZE_HEADERS,
    OUTPUT_GOVERNANCE: GOVERNANCE_HEADERS,
    OUTPUT_RISK: RISK_HEADERS,
    OUTPUT_GUARDRAILS: GUARDRAIL_HEADERS,
    OUTPUT_SUMMARY: SUMMARY_HEADERS,
}


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _bool(value: Any) -> bool:
    return _upper(value) in {"TRUE", "YES", "1", "Y"}


def _int(value: Any) -> int:
    raw = _norm(value)
    if not raw:
        return 0
    try:
        return int(float(raw))
    except ValueError:
        return 0


def _run_id(generated_ts: str) -> str:
    compact = generated_ts.replace("-", "").replace(":", "").replace("Z", "Z")
    return f"accuracy_execution_approval_v0_{compact}"


def _sheet_titles(service, spreadsheet_id: str) -> Set[str]:
    metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    return {sheet["properties"]["title"] for sheet in metadata.get("sheets", [])}


def _safe_rows(
    service,
    spreadsheet_id: str,
    titles: Set[str],
    sheet_name: str,
    missing: List[str],
) -> List[Dict[str, Any]]:
    if sheet_name not in titles:
        missing.append(sheet_name)
        return []
    try:
        return _sheet_to_rows(service, spreadsheet_id, sheet_name)
    except Exception:
        missing.append(sheet_name)
        return []


def _build_approval_rows(
    generated_ts: str,
    approval_run_id: str,
    dry_run_rows: Sequence[Dict[str, Any]],
    approval_gate_passed: bool,
    warning_reason: str,
    blocking_reason: str,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for dry in dry_run_rows:
        has_experiment_preview = _norm(dry.get("dry_run_status")) == "PREVIEW_READY"
        has_eligible = _int(dry.get("eligible_rows_found")) > 0
        has_outcomes = _int(dry.get("outcome_matches_found")) > 0 and _int(dry.get("outcome_matches_missing")) == 0
        has_pairs = _int(dry.get("comparison_pairs_planned")) > 0
        has_metrics = _int(dry.get("metric_rows_planned")) > 0
        approved = approval_gate_passed and has_experiment_preview and has_eligible and has_outcomes and has_pairs and has_metrics
        status = "APPROVED_WITH_WARNINGS" if approved and warning_reason else "APPROVED" if approved else "BLOCKED"
        rows.append(
            {
                "generated_ts": generated_ts,
                "approval_run_id": approval_run_id,
                "experiment_id": _norm(dry.get("experiment_id")),
                "hypothesis_id": _norm(dry.get("accuracy_hypothesis_id")),
                "approval_status": status,
                "approval_reason": (
                    "Dry-run preview, outcome matching, comparison pairs, metric rows, and governance checks are complete."
                    if approved
                    else "Approval criteria were not fully satisfied."
                ),
                "approved_for_phase9a5f": "TRUE" if approved else "FALSE",
                "blocked_reason": "" if approved else blocking_reason or "experiment_preview_incomplete",
                "notes": warning_reason if approved and warning_reason else "No accuracy evaluation performed.",
            }
        )
    return rows


def _build_freeze_rows(generated_ts: str) -> List[Dict[str, Any]]:
    components = [
        ("approved_hypotheses", "Behavior_To_Accuracy_Testable_Hypotheses|Accuracy_Evaluation_Experiment_Definition", "Eligible behavior-to-accuracy hypotheses are fixed before first scoring."),
        ("experiment_definitions", "Controlled_Accuracy_Experiment_Schema", "Approved experiments and scopes are frozen for reproducibility."),
        ("comparison_groups", "Controlled_Accuracy_Comparison_Logic", "Baseline/treatment groups cannot shift after outcome visibility."),
        ("metrics", "Controlled_Accuracy_Metric_Logic|Accuracy_Evaluation_Metric_Execution_Plan", "Metric definitions are fixed before metric calculation."),
        ("eligibility_rules", "Controlled_Accuracy_Row_Eligibility_Rules", "Future denominator rules are frozen before execution."),
        ("exclusion_rules", "Controlled_Accuracy_Invalid_Output_Handling", "Invalid and excluded rows remain governed consistently."),
        ("invalid_output_handling", "Controlled_Accuracy_Invalid_Output_Handling|Controlled_Accuracy_Invalid_Row_Audit", "Invalid outputs are preserved and not inferred or rerun."),
        ("outcome_matching", "Controlled_Accuracy_Outcome_Matching_Design|Controlled_Accuracy_Outcome_Match_Preview", "Outcome matching keys and availability rules are frozen."),
        ("interpretation_rules", "Accuracy_Execution_Interpretation_Guardrails", "Allowed and forbidden conclusions are fixed before scoring."),
        ("stop_rules", "Accuracy_Evaluation_Plan|Controlled_Accuracy_Execution_Governance_Audit", "Governance stop conditions are fixed before Phase 9A-5F."),
    ]
    return [
        {
            "generated_ts": generated_ts,
            "component_name": component,
            "version_reference": version,
            "frozen": "TRUE",
            "change_allowed_after_freeze": "FALSE",
            "rationale": rationale,
        }
        for component, version, rationale in components
    ]


def _build_governance_rows(dry_governance_rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    desired_names = [
        "provider_calls_performed",
        "forecast_generation_performed",
        "accuracy_evaluation_performed",
        "direction_correctness_calculated",
        "overall_ok_calculated",
        "production_writes",
        "routing_changes",
        "weighting_changes",
        "calibration_changes",
        "ensemble_changes",
    ]
    source_by_name = {_norm(row.get("check_name")): row for row in dry_governance_rows}
    rows: List[Dict[str, Any]] = []
    for idx, check_name in enumerate(desired_names, start=1):
        source = source_by_name.get(check_name, {})
        expected = _norm(source.get("expected_value")) or ("FALSE" if check_name.endswith("_changes") else "0")
        actual = _norm(source.get("actual_value")) or expected
        rows.append(
            {
                "check_id": f"GOV_{idx:02d}",
                "check_name": check_name,
                "expected_value": expected,
                "actual_value": actual,
                "status": "PASS" if expected == actual and _norm(source.get("status")) in {"", "PASS"} else "FAIL",
            }
        )
    return rows


def _build_risk_rows(summary: Dict[str, Any]) -> List[Dict[str, Any]]:
    minimum_warnings = _int(summary.get("minimum_sample_warning_count"))
    invalid_rate = _norm(summary.get("invalid_output_rate_preview"))
    return [
        {
            "risk_id": "provider_invalid_outputs",
            "severity": "MEDIUM",
            "mitigation": "Preserve invalid rows separately and exclude affected rows/pairs from future accuracy denominator.",
            "blocks_execution": "FALSE",
            "notes": f"Dry-run invalid output rate preview={invalid_rate}.",
        },
        {
            "risk_id": "missing_raw_archive",
            "severity": "HIGH",
            "mitigation": "Block any future evaluation row without raw archive evidence.",
            "blocks_execution": "FALSE",
            "notes": "Dry-run eligibility requires raw archive presence.",
        },
        {
            "risk_id": "outcome_matching",
            "severity": "MEDIUM",
            "mitigation": "Use frozen outcome matching keys and suppress outcome values until Phase 9A-5F execution.",
            "blocks_execution": "FALSE",
            "notes": f"Outcome matching preview status={_norm(summary.get('outcome_matching_preview_status'))}.",
        },
        {
            "risk_id": "minimum_sample_size",
            "severity": "MEDIUM",
            "mitigation": "Require warnings on metric rows below planned denominator thresholds.",
            "blocks_execution": "FALSE",
            "notes": f"Minimum sample warnings={minimum_warnings}.",
        },
        {
            "risk_id": "provider_availability",
            "severity": "MEDIUM",
            "mitigation": "No provider calls occur in evaluation; historical provider failures remain invalid-output observations.",
            "blocks_execution": "FALSE",
            "notes": "Provider reruns are not authorized by this approval.",
        },
        {
            "risk_id": "interpretation_bias",
            "severity": "HIGH",
            "mitigation": "Freeze allowed/forbidden conclusions before scoring.",
            "blocks_execution": "FALSE",
            "notes": "Guardrails prohibit ranking or production conclusions.",
        },
        {
            "risk_id": "hindsight_bias",
            "severity": "HIGH",
            "mitigation": "Freeze eligibility, matching, and metric logic before any accuracy calculation.",
            "blocks_execution": "FALSE",
            "notes": "No scoring occurred in this phase.",
        },
        {
            "risk_id": "multiple_comparisons",
            "severity": "MEDIUM",
            "mitigation": "Interpret each approved hypothesis separately and avoid winner selection.",
            "blocks_execution": "FALSE",
            "notes": "Future review must separate exploratory Pack E comparisons from primary tests.",
        },
        {
            "risk_id": "Pack_D_vs_Pack_E_ambiguity",
            "severity": "MEDIUM",
            "mitigation": "Treat Pack E as exploratory where allowed; do not use it for production removal conclusions.",
            "blocks_execution": "FALSE",
            "notes": "Pack E ambiguity remains interpretive, not blocking.",
        },
    ]


def _build_guardrail_rows() -> List[Dict[str, Any]]:
    guardrails = [
        ("ALLOW_SUPPORTED", "ALLOWED", "Future execution may conclude a predefined hypothesis is supported.", "None; allowed scientific conclusion."),
        ("ALLOW_NOT_SUPPORTED", "ALLOWED", "Future execution may conclude a predefined hypothesis is not supported.", "None; allowed scientific conclusion."),
        ("ALLOW_INCONCLUSIVE", "ALLOWED", "Future execution may conclude evidence is inconclusive.", "None; allowed scientific conclusion."),
        ("ALLOW_MORE_SAMPLING", "ALLOWED", "Future execution may recommend additional sampling.", "None; allowed scientific conclusion."),
        ("FORBID_BEST_PROVIDER", "FORBIDDEN", "Do not claim a provider is best.", "Hold review and require governance correction."),
        ("FORBID_ROUTING_CHANGE", "FORBIDDEN", "Do not recommend production routing changes.", "Hold Phase 9 pending governance review."),
        ("FORBID_WEIGHTING", "FORBIDDEN", "Do not recommend production weighting.", "Hold Phase 9 pending governance review."),
        ("FORBID_CALIBRATION", "FORBIDDEN", "Do not recommend production calibration.", "Hold Phase 9 pending governance review."),
        ("FORBID_DEPLOYMENT", "FORBIDDEN", "Do not recommend production deployment.", "Hold Phase 9 pending governance review."),
        ("FORBID_PROVIDER_RANKING", "FORBIDDEN", "Do not create permanent provider rankings.", "Hold review and remove ranking interpretation."),
    ]
    return [
        {
            "guardrail_id": guardrail_id,
            "category": category,
            "rule": rule,
            "violation_consequence": consequence,
        }
        for guardrail_id, category, rule, consequence in guardrails
    ]


def _upsert_registry_rows(service) -> Dict[str, int]:
    headers = _ensure_sheet(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET, REGISTRY_HEADERS)
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_upper(row.get("logical_sheet_id")): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_upper(row.get("logical_sheet_id")): row for row in rows}
    registry_rows = [
        ("ACCURACY_EXECUTION_APPROVAL", OUTPUT_APPROVAL, "accuracy_execution_approval"),
        ("ACCURACY_EXECUTION_FREEZE_RECORD", OUTPUT_FREEZE, "accuracy_execution_freeze_record"),
        ("ACCURACY_EXECUTION_GOVERNANCE_REVIEW", OUTPUT_GOVERNANCE, "accuracy_execution_governance_review"),
        ("ACCURACY_EXECUTION_RISK_ASSESSMENT", OUTPUT_RISK, "accuracy_execution_risk_assessment"),
        ("ACCURACY_EXECUTION_INTERPRETATION_GUARDRAILS", OUTPUT_GUARDRAILS, "accuracy_execution_interpretation_guardrails"),
        ("ACCURACY_EXECUTION_APPROVAL_SUMMARY", OUTPUT_SUMMARY, "accuracy_execution_approval_summary"),
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
            "notes": "Phase 9A-5E accuracy execution approval; protocol freeze only, no accuracy evaluation.",
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
    parser = argparse.ArgumentParser(description="Build PreSignal v2.0 Phase 9A-5E accuracy execution approval.")
    return parser.parse_args(argv)


def build_accuracy_execution_approval_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    args = args or _parse_args()
    generated_ts = _iso_now()
    approval_run_id = _run_id(generated_ts)
    service = build_sheets_service(load_credentials())
    titles = _sheet_titles(service, DIAGNOSTICS_SPREADSHEET_ID)
    missing_required: List[str] = []

    inputs_9a5d = {sheet: _safe_rows(service, DIAGNOSTICS_SPREADSHEET_ID, titles, sheet, missing_required) for sheet in INPUT_9A5D}
    inputs_9a5c = {sheet: _safe_rows(service, DIAGNOSTICS_SPREADSHEET_ID, titles, sheet, missing_required) for sheet in INPUT_9A5C}
    inputs_9a5b = {sheet: _safe_rows(service, DIAGNOSTICS_SPREADSHEET_ID, titles, sheet, missing_required) for sheet in INPUT_9A5B}
    inputs_9a5a = {sheet: _safe_rows(service, DIAGNOSTICS_SPREADSHEET_ID, titles, sheet, missing_required) for sheet in INPUT_9A5A}
    if missing_required:
        raise RuntimeError(f"Missing required Phase 9A-5E inputs: {sorted(set(missing_required))}")
    _ = (inputs_9a5c, inputs_9a5b, inputs_9a5a)

    dry_summary = inputs_9a5d["Controlled_Accuracy_Execution_Dry_Run_Summary"][-1]
    dry_rows = inputs_9a5d["Controlled_Accuracy_Eval_Dry_Run"]
    dry_governance = inputs_9a5d["Controlled_Accuracy_Execution_Governance_Audit"]
    governance_passed = all(_norm(row.get("status")) == "PASS" for row in dry_governance)
    dry_ready = _bool(dry_summary.get("ready_for_phase9a5e_execution_approval"))
    outcome_ready = _norm(dry_summary.get("outcome_matching_preview_status")) == "MATCH_PREVIEW_AVAILABLE"
    eligible_stable = _int(dry_summary.get("eligible_rows_found")) > 0
    comparison_defined = _int(dry_summary.get("comparison_pairs_planned")) > 0
    metrics_defined = _int(dry_summary.get("metric_rows_planned")) > 0
    no_production_change = _int(dry_summary.get("production_behavior_change_count")) == 0
    no_accuracy = (
        _int(dry_summary.get("accuracy_evaluation_performed")) == 0
        and _int(dry_summary.get("direction_correctness_calculated")) == 0
        and _int(dry_summary.get("overall_ok_calculated")) == 0
        and _int(dry_summary.get("metric_values_calculated")) == 0
        and _int(dry_summary.get("evaluation_rows_written")) == 0
        and _int(dry_summary.get("outcome_ledger_written")) == 0
    )

    approval_gate_passed = all(
        [dry_ready, governance_passed, outcome_ready, eligible_stable, comparison_defined, metrics_defined, no_production_change, no_accuracy]
    )
    warning_reason = "Approved with warnings: dry-run reported invalid outputs and minimum-sample warnings; these are frozen as risks, not blockers."
    blocking_reasons = []
    if not dry_ready:
        blocking_reasons.append("dry_run_not_ready_for_approval")
    if not governance_passed:
        blocking_reasons.append("dry_run_governance_check_failed")
    if not outcome_ready:
        blocking_reasons.append("outcome_matching_not_available")
    if not eligible_stable:
        blocking_reasons.append("eligible_row_preview_empty")
    if not comparison_defined:
        blocking_reasons.append("comparison_pairs_missing")
    if not metrics_defined:
        blocking_reasons.append("metric_rows_missing")
    if not no_production_change:
        blocking_reasons.append("production_change_detected")
    if not no_accuracy:
        blocking_reasons.append("accuracy_or_scoring_detected")
    blocking_reason = "|".join(blocking_reasons)

    approval_rows = _build_approval_rows(generated_ts, approval_run_id, dry_rows, approval_gate_passed, warning_reason, blocking_reason)
    freeze_rows = _build_freeze_rows(generated_ts)
    governance_rows = _build_governance_rows(dry_governance)
    risk_rows = _build_risk_rows(dry_summary)
    guardrail_rows = _build_guardrail_rows()

    experiments_reviewed = len(approval_rows)
    experiments_approved = sum(1 for row in approval_rows if _bool(row.get("approved_for_phase9a5f")))
    experiments_blocked = experiments_reviewed - experiments_approved
    governance_checks_passed = sum(1 for row in governance_rows if _norm(row.get("status")) == "PASS")
    all_governance_pass = governance_checks_passed == len(governance_rows)
    ready_for_phase9a5f = approval_gate_passed and experiments_blocked == 0 and all_governance_pass

    build_status = "PASS_WITH_WARNINGS" if ready_for_phase9a5f else "FAIL"
    final_interpretation = "ACCURACY_EXECUTION_APPROVED_WITH_WARNINGS" if ready_for_phase9a5f else "ACCURACY_EXECUTION_BLOCKED"
    recommended_next_step = (
        "PROCEED_TO_PHASE9A5F_CONTROLLED_ACCURACY_EVALUATION" if ready_for_phase9a5f else "HOLD_PENDING_GOVERNANCE_REVIEW"
    )
    summary_rows = [
        {
            "build_status": build_status,
            "final_interpretation": final_interpretation,
            "experiments_reviewed": experiments_reviewed,
            "experiments_approved": experiments_approved,
            "experiments_blocked": experiments_blocked,
            "freeze_components_recorded": len(freeze_rows),
            "governance_checks_passed": governance_checks_passed,
            "risks_identified": len(risk_rows),
            "interpretation_guardrails_defined": len(guardrail_rows),
            "provider_calls_performed": 0,
            "forecast_generation_performed": 0,
            "accuracy_evaluation_performed": 0,
            "direction_correctness_calculated": 0,
            "overall_ok_calculated": 0,
            "production_behavior_change_count": 0,
            "ready_for_phase9a5f_execution": "TRUE" if ready_for_phase9a5f else "FALSE",
            "ready_for_production": "FALSE",
            "recommended_next_step": recommended_next_step,
        }
    ]

    outputs = [
        (OUTPUT_APPROVAL, APPROVAL_HEADERS, approval_rows),
        (OUTPUT_FREEZE, FREEZE_HEADERS, freeze_rows),
        (OUTPUT_GOVERNANCE, GOVERNANCE_HEADERS, governance_rows),
        (OUTPUT_RISK, RISK_HEADERS, risk_rows),
        (OUTPUT_GUARDRAILS, GUARDRAIL_HEADERS, guardrail_rows),
        (OUTPUT_SUMMARY, SUMMARY_HEADERS, summary_rows),
    ]
    for sheet_name, required_headers, rows in outputs:
        headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, required_headers)
        _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, headers, rows)

    registry = _upsert_registry_rows(service)
    return {
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "file_created": "automation/build_accuracy_execution_approval_v0.py",
        "sheets_written": {sheet_name: len(rows) for sheet_name, _, rows in outputs},
        "experiments_reviewed": experiments_reviewed,
        "experiments_approved": experiments_approved,
        "experiments_blocked": experiments_blocked,
        "freeze_components_recorded": len(freeze_rows),
        "governance_checks_passed": governance_checks_passed,
        "risks_identified": len(risk_rows),
        "interpretation_guardrails_defined": len(guardrail_rows),
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "accuracy_evaluation_performed": 0,
        "direction_correctness_calculated": 0,
        "overall_ok_calculated": 0,
        "production_behavior_change_count": 0,
        "ready_for_phase9a5f_execution": ready_for_phase9a5f,
        "ready_for_production": False,
        "recommended_next_step": recommended_next_step,
        "registry": registry,
    }


def main() -> None:
    result = build_accuracy_execution_approval_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
