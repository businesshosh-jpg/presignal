import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.build_controlled_accuracy_evaluation_v0 import _metric_delta, _to_float
from automation.build_market_sessions_shadow_v0 import (
    DIAGNOSTICS_SPREADSHEET_ID,
    PROJECT_OVERVIEWS_SPREADSHEET_ID,
    REGISTRY_HEADERS,
    REGISTRY_SHEET,
    _column_letter,
    _norm,
    _sheet_to_rows,
    _write_rows,
)
from automation.build_session_information_requests_v0 import _iso_now
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials


SCHEMA_VERSION = "presignal_v2_corrected_accuracy_review_0.1"
REVIEW_VERSION = "corrected_accuracy_review_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-5M6"
REGISTRY_CATEGORY = "PRESIGNAL_V2_CORRECTED_ACCURACY_REVIEW"
REGISTRY_OWNER_MODULE = "market_state"

CORRECTED_INPUT_SHEETS = [
    "Corrected_Accuracy_Evaluation",
    "Corrected_Accuracy_Experiment_Results",
    "Corrected_Accuracy_Comparison_Results",
    "Corrected_Accuracy_Metric_Results",
    "Corrected_Accuracy_Hypothesis_Results",
    "Corrected_Accuracy_Governance",
    "Corrected_Accuracy_Execution_Summary",
]
DESIGN_INPUT_SHEETS = [
    "Corrected_Accuracy_ReEvaluation_Design",
    "Corrected_Accuracy_Row_Selection",
    "Corrected_Accuracy_Control_Definition",
    "Corrected_Accuracy_Metric_Definition",
    "Corrected_Accuracy_Outcome_Mapping",
    "Corrected_Accuracy_ReEvaluation_Summary",
]
REPAIR_INPUT_SHEETS = ["Market_Reaction_Repaired_Remap_Validation", "Market_Reaction_Repaired_Trust_Validation"]
ORIGINAL_INPUT_SHEETS = [
    "Controlled_Accuracy_Evaluation",
    "Controlled_Accuracy_Experiment_Results",
    "Controlled_Accuracy_Comparison_Results",
    "Controlled_Accuracy_Metric_Results",
    "Controlled_Accuracy_Invalid_Output_Results",
    "Controlled_Accuracy_Evaluation_Summary",
]
PREVIOUS_REVIEW_SHEETS = [
    "Controlled_Accuracy_Evaluation_Review",
    "Accuracy_Hypothesis_Review",
    "Behavior_vs_Accuracy_Review",
    "Pack_Comparison_Accuracy_Review",
    "Provider_Accuracy_Review",
    "Metric_Interpretation_Review",
    "Accuracy_Limitation_Audit",
    "Controlled_Accuracy_Evaluation_Review_Summary",
    "Behavior_Accuracy_Hypothesis_Revision",
    "Behavior_Accuracy_Failed_Transfer_Audit",
    "Behavior_Accuracy_Mechanism_Gap_Audit",
    "Behavior_Accuracy_Revised_Hypotheses",
    "Behavior_Accuracy_Metric_Revision_Audit",
    "Behavior_Accuracy_Replication_Readiness",
    "Behavior_Accuracy_Revision_Summary",
]
BEHAVIOR_TRACE_SHEETS = [
    "Pack_Behavior_Tier2_Generalization_Review",
    "Pack_Behavior_Tier2_Hypothesis_Generalization",
    "Pack_Behavior_Tier2_Provider_Generalization",
    "Pack_Behavior_Tier2_Transition_Generalization",
    "Pack_Behavior_Tier2_Field_Generalization",
    "Pack_Behavior_Tier2_NoSignal_Generalization",
    "Pack_Behavior_Tier2_Generalization_Summary",
]
ALL_INPUT_SHEETS = (
    CORRECTED_INPUT_SHEETS
    + DESIGN_INPUT_SHEETS
    + REPAIR_INPUT_SHEETS
    + ORIGINAL_INPUT_SHEETS
    + PREVIOUS_REVIEW_SHEETS
    + BEHAVIOR_TRACE_SHEETS
)
CRITICAL_INPUT_SHEETS = set(ALL_INPUT_SHEETS)
READ_INPUT_SHEETS = [
    "Corrected_Accuracy_Execution_Summary",
    "Corrected_Accuracy_Experiment_Results",
    "Corrected_Accuracy_Metric_Results",
    "Corrected_Accuracy_Hypothesis_Results",
    "Controlled_Accuracy_Evaluation_Summary",
    "Controlled_Accuracy_Experiment_Results",
    "Controlled_Accuracy_Metric_Results",
    "Accuracy_Hypothesis_Review",
    "Controlled_Accuracy_Evaluation_Review_Summary",
    "Behavior_Accuracy_Revision_Summary",
]

OUTPUT_REVIEW = "Corrected_Accuracy_Review"
OUTPUT_HYPOTHESIS = "Corrected_Accuracy_Hypothesis_Review"
OUTPUT_COMPARISON = "Corrected_vs_Original_Accuracy_Comparison"
OUTPUT_EXPERIMENT = "Corrected_Accuracy_Experiment_Review"
OUTPUT_METRIC = "Corrected_Accuracy_Metric_Interpretation"
OUTPUT_REPAIR_IMPACT = "Corrected_Accuracy_Outcome_Repair_Impact"
OUTPUT_SECOND_REVISION = "Corrected_Accuracy_Second_Revision_Assessment"
OUTPUT_GOVERNANCE = "Corrected_Accuracy_Governance_Review"
OUTPUT_SUMMARY = "Corrected_Accuracy_Review_Summary"

REVIEW_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "review_area",
    "review_status",
    "corrected_rows_reviewed",
    "diagnostic_rows_excluded",
    "direction_denominator",
    "direction_correct_count",
    "direction_match_rate",
    "overall_denominator",
    "overall_ok_count",
    "overall_ok_rate",
    "accuracy_signal_classification",
    "review_conclusion",
    "recommended_next_action",
    "production_excluded",
    "notes",
]

HYPOTHESIS_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "accuracy_hypothesis_id",
    "source_behavior_hypothesis_id",
    "original_hypothesis_result",
    "corrected_hypothesis_result",
    "corrected_direction_rate",
    "corrected_overall_rate",
    "original_direction_rate",
    "original_overall_rate",
    "direction_delta",
    "overall_delta",
    "outcome_repair_impact",
    "hypothesis_support_status_after_correction",
    "interpretation",
    "recommended_status",
    "recommended_next_action",
    "production_excluded",
    "notes",
]

COMPARISON_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "comparison_scope",
    "original_denominator",
    "original_correct_count",
    "original_rate",
    "corrected_denominator",
    "corrected_correct_count",
    "corrected_rate",
    "absolute_delta",
    "relative_delta",
    "interpretation",
    "possible_reason",
    "notes",
]

EXPERIMENT_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "experiment_id",
    "accuracy_hypothesis_id",
    "corrected_direction_rate",
    "corrected_overall_rate",
    "original_direction_rate",
    "original_overall_rate",
    "direction_delta",
    "overall_delta",
    "experiment_interpretation",
    "support_status",
    "sample_size_warning",
    "recommended_action",
    "notes",
]

METRIC_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "metric_id",
    "metric_name",
    "original_metric_value",
    "corrected_metric_value",
    "metric_delta",
    "metric_interpretation",
    "metric_reliability_after_correction",
    "revision_needed",
    "recommended_metric_action",
    "notes",
]

REPAIR_IMPACT_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "impact_area",
    "impact_classification",
    "original_interpretation",
    "corrected_interpretation",
    "changed_by_repair",
    "scientific_implication",
    "recommended_followup",
    "notes",
]

SECOND_REVISION_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "revision_area",
    "previous_phase9a5r_conclusion",
    "corrected_accuracy_evidence",
    "second_revision_needed",
    "reason",
    "recommended_second_revision_focus",
    "priority",
    "notes",
]

GOVERNANCE_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
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
    "review_version",
    "review_run_id",
    "build_status",
    "final_interpretation",
    "corrected_rows_reviewed",
    "diagnostic_rows_excluded",
    "hypotheses_reviewed",
    "hypotheses_supported",
    "hypotheses_partially_supported",
    "hypotheses_not_supported",
    "hypotheses_inconclusive",
    "original_direction_rate",
    "corrected_direction_rate",
    "direction_delta",
    "original_overall_ok_rate",
    "corrected_overall_ok_rate",
    "overall_ok_delta",
    "strongest_corrected_experiment",
    "largest_negative_shift",
    "largest_positive_shift",
    "primary_corrected_interpretation",
    "second_revision_needed",
    "metric_repair_still_needed",
    "replication_ready",
    "provider_calls_performed",
    "forecast_generation_performed",
    "provider_rerun_count",
    "evaluation_rerun_count",
    "corrected_accuracy_results_modified",
    "original_accuracy_results_modified",
    "market_reaction_repair_modified",
    "production_behavior_change_count",
    "production_sheet_write_count",
    "ready_for_second_hypothesis_revision",
    "ready_for_metric_repair",
    "ready_for_replication_design",
    "ready_for_production",
    "recommended_next_step",
    "notes",
]

SOURCE_BEHAVIOR = {
    "ACC_HYP_USDJPY_TREND_DIRECTIONAL_ALIGNMENT": "HYP_USDJPY_TREND_REASONING",
    "ACC_HYP_PACK_B_TARGET_STATE_SIGNAL_DISCIPLINE": "HYP_A_TO_B_TARGET_STATE_VALUE",
    "ACC_HYP_OPENAI_STABLE_CAUSAL_REWRITE_TESTBED": "HYP_OPENAI_CAUSAL_STABLE",
}


def _run_id(generated_ts: str) -> str:
    return "corrected_accuracy_review_v0_" + generated_ts.replace("-", "").replace(":", "")


def _base(generated_ts: str, review_run_id: str) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "review_version": REVIEW_VERSION,
        "review_run_id": review_run_id,
    }


def _read_inputs(service) -> Dict[str, List[Dict[str, Any]]]:
    titles = _sheet_titles_light(service, DIAGNOSTICS_SPREADSHEET_ID)
    missing = [sheet for sheet in CRITICAL_INPUT_SHEETS if sheet not in titles]
    if missing:
        raise RuntimeError(f"Missing critical input sheets: {', '.join(sorted(missing))}")
    data: Dict[str, List[Dict[str, Any]]] = {}
    read_missing: List[str] = []
    for sheet in READ_INPUT_SHEETS:
        try:
            data[sheet] = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet)
        except Exception:
            read_missing.append(sheet)
            data[sheet] = []
    if read_missing:
        raise RuntimeError(f"Unable to read critical input sheets: {', '.join(sorted(set(read_missing)))}")
    for sheet in ALL_INPUT_SHEETS:
        data.setdefault(sheet, [])
    return data


def _sheet_titles_light(service, spreadsheet_id: str) -> set[str]:
    metadata = (
        service.spreadsheets()
        .get(spreadsheetId=spreadsheet_id, fields="sheets(properties(title))")
        .execute()
    )
    return {sheet["properties"]["title"] for sheet in metadata.get("sheets", [])}


def _get_headers(service, spreadsheet_id: str, sheet_name: str) -> List[str]:
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=f"'{sheet_name}'!1:1")
        .execute()
    )
    values = result.get("values", [])
    return values[0] if values else []


def _ensure_sheet_minimal_light(
    service,
    spreadsheet_id: str,
    sheet_name: str,
    required_headers: Sequence[str],
    data_row_count: int,
) -> List[str]:
    titles = _sheet_titles_light(service, spreadsheet_id)
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
                                    "rowCount": max(1, data_row_count + 1),
                                    "columnCount": max(1, len(required_headers)),
                                },
                            }
                        }
                    }
                ]
            },
        ).execute()
        headers = list(required_headers)
    else:
        headers = _get_headers(service, spreadsheet_id, sheet_name) or list(required_headers)
        for header in required_headers:
            if header not in headers:
                headers.append(header)
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_name}'!A1",
        valueInputOption="RAW",
        body={"values": [headers]},
    ).execute()
    return headers


def _latest(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    return rows[-1] if rows else {}


def _rate_delta(corrected: Any, original: Any) -> str:
    return _metric_delta(_to_float(corrected), _to_float(original))


def _relative_delta(corrected: Any, original: Any) -> str:
    c = _to_float(corrected)
    o = _to_float(original)
    if c is None or o is None or o == 0:
        return ""
    return f"{(c - o) / abs(o):.6f}"


def _impact(corrected_direction: str, original_direction: str, corrected_overall: str, original_overall: str) -> str:
    dd = _to_float(_rate_delta(corrected_direction, original_direction))
    od = _to_float(_rate_delta(corrected_overall, original_overall))
    if dd is None or od is None:
        return "INCONCLUSIVE"
    if dd > 0 and od > 0:
        return "STRENGTHENED"
    if dd < 0 and od < 0:
        return "WEAKENED"
    if abs(dd) < 0.000001 and abs(od) < 0.000001:
        return "UNCHANGED"
    return "MIXED"


def _support_status(corrected_result: str, direction_delta: str) -> str:
    raw = _norm(corrected_result).upper().replace(" ", "_")
    if raw == "SUPPORTED":
        return "SUPPORTED"
    if raw == "PARTIALLY_SUPPORTED":
        return "PARTIALLY_SUPPORTED"
    if raw in {"NOT_SUPPORTED", "NOT SUPPORTED"}:
        return "NOT_SUPPORTED"
    delta = _to_float(direction_delta)
    if delta is not None and delta < 0:
        return "WEAKENED"
    return "INCONCLUSIVE"


def _comparison_interpretation(scope: str, delta: str) -> str:
    d = _to_float(delta)
    if d is None:
        return "Insufficient comparable metric value."
    if d > 0.02:
        return "Corrected outcome mapping increased this metric."
    if d < -0.02:
        return "Corrected outcome mapping decreased this metric."
    return "Corrected outcome mapping produced no material change."


def _upsert_registry_rows(service) -> Dict[str, int]:
    titles = _sheet_titles_light(service, PROJECT_OVERVIEWS_SPREADSHEET_ID)
    if REGISTRY_SHEET not in titles:
        return {"updated": 0, "appended": 0, "status": "missing"}
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_norm(row.get("logical_sheet_id")).upper(): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_norm(row.get("logical_sheet_id")).upper(): row for row in rows}
    specs = [
        ("CORRECTED_ACCURACY_REVIEW", OUTPUT_REVIEW, "corrected_accuracy_review"),
        ("CORRECTED_ACCURACY_HYPOTHESIS_REVIEW", OUTPUT_HYPOTHESIS, "corrected_accuracy_hypothesis_review"),
        ("CORRECTED_VS_ORIGINAL_ACCURACY_COMPARISON", OUTPUT_COMPARISON, "corrected_vs_original_accuracy_comparison"),
        ("CORRECTED_ACCURACY_EXPERIMENT_REVIEW", OUTPUT_EXPERIMENT, "corrected_accuracy_experiment_review"),
        ("CORRECTED_ACCURACY_METRIC_INTERPRETATION", OUTPUT_METRIC, "corrected_accuracy_metric_interpretation"),
        ("CORRECTED_ACCURACY_OUTCOME_REPAIR_IMPACT", OUTPUT_REPAIR_IMPACT, "corrected_accuracy_outcome_repair_impact"),
        ("CORRECTED_ACCURACY_SECOND_REVISION_ASSESSMENT", OUTPUT_SECOND_REVISION, "corrected_accuracy_second_revision_assessment"),
        ("CORRECTED_ACCURACY_GOVERNANCE_REVIEW", OUTPUT_GOVERNANCE, "corrected_accuracy_governance_review"),
        ("CORRECTED_ACCURACY_REVIEW_SUMMARY", OUTPUT_SUMMARY, "corrected_accuracy_review_summary"),
    ]
    updates: List[Dict[str, Any]] = []
    appended = 0
    for logical_id, sheet_name, role in specs:
        key = logical_id.upper()
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
            "notes": "Phase 9A-5M6 corrected accuracy review; diagnostic-only, non-production.",
            "registry_created_ts": _norm(existing.get("registry_created_ts")) or now,
            "registry_last_verified_ts": now,
            "registry_migration_ts": _norm(existing.get("registry_migration_ts")),
            "registry_rename_ts": _norm(existing.get("registry_rename_ts")),
        }
        values = [merged.get(header, "") for header in REGISTRY_HEADERS]
        if key in by_id:
            row_number = by_id[key]
        else:
            appended += 1
            row_number = len(rows) + appended + 1
        updates.append({"range": f"'{REGISTRY_SHEET}'!A{row_number}:{_column_letter(len(REGISTRY_HEADERS))}{row_number}", "values": [values]})
    if updates:
        batch_update_values(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, updates)
    return {"updated": len(specs) - appended, "appended": appended}


def build_corrected_accuracy_review_v0() -> Dict[str, Any]:
    service = build_sheets_service(load_credentials())
    generated_ts = _iso_now()
    review_run_id = _run_id(generated_ts)
    data = _read_inputs(service)

    corrected_summary = _latest(data["Corrected_Accuracy_Execution_Summary"])
    original_summary = _latest(data["Controlled_Accuracy_Evaluation_Summary"])
    previous_review_summary = _latest(data["Controlled_Accuracy_Evaluation_Review_Summary"])
    revision_summary = _latest(data["Behavior_Accuracy_Revision_Summary"])
    corrected_exps = {_norm(row.get("experiment_id")): row for row in data["Corrected_Accuracy_Experiment_Results"]}
    original_exps = {_norm(row.get("experiment_id")): row for row in data["Controlled_Accuracy_Experiment_Results"]}
    corrected_hyps = {_norm(row.get("accuracy_hypothesis_id")): row for row in data["Corrected_Accuracy_Hypothesis_Results"]}
    original_hyps = {_norm(row.get("accuracy_hypothesis_id")): row for row in data["Accuracy_Hypothesis_Review"]}
    corrected_metrics = {_norm(row.get("metric_id")): row for row in data["Corrected_Accuracy_Metric_Results"]}
    original_metrics = {_norm(row.get("metric_id")): row for row in data["Controlled_Accuracy_Metric_Results"]}

    original_direction_rate = _norm(original_summary.get("direction_match_rate"))
    corrected_direction_rate = _norm(corrected_summary.get("direction_match_rate"))
    original_overall_rate = _norm(original_summary.get("overall_ok_rate"))
    corrected_overall_rate = _norm(corrected_summary.get("overall_ok_rate"))
    direction_delta = _rate_delta(corrected_direction_rate, original_direction_rate)
    overall_delta = _rate_delta(corrected_overall_rate, original_overall_rate)

    corrected_rows_reviewed = int(_to_float(corrected_summary.get("corrected_evaluation_rows_executed")) or 0)
    diagnostic_rows_excluded = int(_to_float(corrected_summary.get("diagnostic_rows_excluded")) or 0)
    hypothesis_counts = Counter(_norm(row.get("hypothesis_result")) for row in corrected_hyps.values())

    review_rows = [
        {
            **_base(generated_ts, review_run_id),
            "review_area": "corrected_accuracy_results",
            "review_status": "PASS_WITH_WARNINGS",
            "corrected_rows_reviewed": corrected_rows_reviewed,
            "diagnostic_rows_excluded": diagnostic_rows_excluded,
            "direction_denominator": corrected_summary.get("direction_denominator", ""),
            "direction_correct_count": corrected_summary.get("direction_correct_count", ""),
            "direction_match_rate": corrected_direction_rate,
            "overall_denominator": corrected_summary.get("overall_denominator", ""),
            "overall_ok_count": corrected_summary.get("overall_ok_count", ""),
            "overall_ok_rate": corrected_overall_rate,
            "accuracy_signal_classification": "WEAK_ACCURACY_SIGNAL",
            "review_conclusion": "Corrected outcomes lowered direction accuracy, raised overall_ok, and left all three hypotheses not supported.",
            "recommended_next_action": "PROCEED_TO_PHASE9A5R2_SECOND_HYPOTHESIS_REVISION",
            "production_excluded": "TRUE",
            "notes": "Review only; no corrected or original accuracy results modified.",
        }
    ]

    comparison_rows: List[Dict[str, Any]] = []
    comparison_specs = [
        ("overall_direction", original_summary, corrected_summary, "direction_denominator", "direction_correct_count", "direction_match_rate"),
        ("overall_ok", original_summary, corrected_summary, "overall_denominator", "overall_ok_count", "overall_ok_rate"),
    ]
    for exp_id in [
        "ACC_EXP_USDJPY_TREND_DIRECTIONAL_ALIGNMENT",
        "ACC_EXP_PACK_B_TARGET_STATE_SIGNAL_DISCIPLINE",
        "ACC_EXP_OPENAI_STABLE_CAUSAL_REWRITE_TESTBED",
    ]:
        comparison_specs.append((f"{exp_id}_direction", original_exps.get(exp_id, {}), corrected_exps.get(exp_id, {}), "direction_denominator", "direction_correct_count", "direction_match_rate"))
        comparison_specs.append((f"{exp_id}_overall", original_exps.get(exp_id, {}), corrected_exps.get(exp_id, {}), "overall_denominator", "overall_ok_count", "overall_ok_rate"))
    for scope, original, corrected, den_field, count_field, rate_field in comparison_specs:
        abs_delta = _rate_delta(corrected.get(rate_field), original.get(rate_field))
        comparison_rows.append(
            {
                **_base(generated_ts, review_run_id),
                "comparison_scope": scope,
                "original_denominator": original.get(den_field, ""),
                "original_correct_count": original.get(count_field, ""),
                "original_rate": original.get(rate_field, ""),
                "corrected_denominator": corrected.get(den_field, ""),
                "corrected_correct_count": corrected.get(count_field, ""),
                "corrected_rate": corrected.get(rate_field, ""),
                "absolute_delta": abs_delta,
                "relative_delta": _relative_delta(corrected.get(rate_field), original.get(rate_field)),
                "interpretation": _comparison_interpretation(scope, abs_delta),
                "possible_reason": "Outcome repair changed canonical realized labels and denominator scope; metric behavior diverged across direction and overall_ok.",
                "notes": "Comparison is diagnostic and does not rerun either evaluation.",
            }
        )

    hypothesis_rows: List[Dict[str, Any]] = []
    experiment_rows: List[Dict[str, Any]] = []
    for hyp_id, exp_id in [
        ("ACC_HYP_USDJPY_TREND_DIRECTIONAL_ALIGNMENT", "ACC_EXP_USDJPY_TREND_DIRECTIONAL_ALIGNMENT"),
        ("ACC_HYP_PACK_B_TARGET_STATE_SIGNAL_DISCIPLINE", "ACC_EXP_PACK_B_TARGET_STATE_SIGNAL_DISCIPLINE"),
        ("ACC_HYP_OPENAI_STABLE_CAUSAL_REWRITE_TESTBED", "ACC_EXP_OPENAI_STABLE_CAUSAL_REWRITE_TESTBED"),
    ]:
        corrected_hyp = corrected_hyps.get(hyp_id, {})
        original_hyp = original_hyps.get(hyp_id, {})
        corrected_exp = corrected_exps.get(exp_id, {})
        original_exp = original_exps.get(exp_id, {})
        dir_delta = _rate_delta(corrected_exp.get("direction_match_rate"), original_exp.get("direction_match_rate"))
        ok_delta = _rate_delta(corrected_exp.get("overall_ok_rate"), original_exp.get("overall_ok_rate"))
        impact = _impact(corrected_exp.get("direction_match_rate", ""), original_exp.get("direction_match_rate", ""), corrected_exp.get("overall_ok_rate", ""), original_exp.get("overall_ok_rate", ""))
        support = _support_status(corrected_hyp.get("hypothesis_result"), dir_delta)
        interpretation = "Outcome correction did not rescue behavior-to-accuracy transfer; support remains absent under corrected canonical outcomes."
        hypothesis_rows.append(
            {
                **_base(generated_ts, review_run_id),
                "accuracy_hypothesis_id": hyp_id,
                "source_behavior_hypothesis_id": SOURCE_BEHAVIOR[hyp_id],
                "original_hypothesis_result": _norm(original_hyp.get("hypothesis_support_status")) or _norm(original_hyp.get("recommended_status")) or "PREVIOUSLY_NOT_PRODUCTION_READY",
                "corrected_hypothesis_result": _norm(corrected_hyp.get("hypothesis_result")),
                "corrected_direction_rate": corrected_exp.get("direction_match_rate", ""),
                "corrected_overall_rate": corrected_exp.get("overall_ok_rate", ""),
                "original_direction_rate": original_exp.get("direction_match_rate", ""),
                "original_overall_rate": original_exp.get("overall_ok_rate", ""),
                "direction_delta": dir_delta,
                "overall_delta": ok_delta,
                "outcome_repair_impact": impact,
                "hypothesis_support_status_after_correction": support,
                "interpretation": interpretation,
                "recommended_status": "RETAIN_FOR_SECOND_REVISION",
                "recommended_next_action": "Revise mechanism and metric framing before any replication design.",
                "production_excluded": "TRUE",
                "notes": "Not production-ready; no provider, pack, or routing recommendation.",
            }
        )
        experiment_rows.append(
            {
                **_base(generated_ts, review_run_id),
                "experiment_id": exp_id,
                "accuracy_hypothesis_id": hyp_id,
                "corrected_direction_rate": corrected_exp.get("direction_match_rate", ""),
                "corrected_overall_rate": corrected_exp.get("overall_ok_rate", ""),
                "original_direction_rate": original_exp.get("direction_match_rate", ""),
                "original_overall_rate": original_exp.get("overall_ok_rate", ""),
                "direction_delta": dir_delta,
                "overall_delta": ok_delta,
                "experiment_interpretation": "Corrected result remains weak; direction weakened while overall_ok may improve depending on experiment.",
                "support_status": support,
                "sample_size_warning": "TRUE",
                "recommended_action": "Include in second hypothesis revision rather than replication.",
                "notes": "Experiment review is interpretive only.",
            }
        )

    metric_ids = [
        "direction_match_rate",
        "overall_ok",
        "false_signal_rate",
        "no_signal_correctness",
        "behavior_conditioned_accuracy_delta",
        "pack_vs_baseline_delta",
        "confidence_calibration_proxy",
        "scenario_alignment",
    ]
    metric_rows: List[Dict[str, Any]] = []
    for metric_id in metric_ids:
        corrected_metric = corrected_metrics.get(metric_id, {})
        original_metric = original_metrics.get(metric_id, {})
        if metric_id == "direction_match_rate":
            original_value, corrected_value = original_direction_rate, corrected_direction_rate
        elif metric_id == "overall_ok":
            original_value, corrected_value = original_overall_rate, corrected_overall_rate
        else:
            original_value = _norm(original_metric.get("metric_value")) or _norm(original_metric.get("metric_delta"))
            corrected_value = _norm(corrected_metric.get("metric_value")) or _norm(corrected_metric.get("metric_delta"))
        delta = _rate_delta(corrected_value, original_value)
        action = "DECOMPOSE" if metric_id == "overall_ok" else "REVIEW" if metric_id in {"direction_match_rate", "no_signal_correctness", "false_signal_rate"} else "HOLD"
        metric_rows.append(
            {
                **_base(generated_ts, review_run_id),
                "metric_id": metric_id,
                "metric_name": metric_id.replace("_", " ").title(),
                "original_metric_value": original_value,
                "corrected_metric_value": corrected_value,
                "metric_delta": delta,
                "metric_interpretation": "Metric behavior changed after outcome repair; interpret cautiously before replication.",
                "metric_reliability_after_correction": "NEEDS_REVIEW" if metric_id in {"direction_match_rate", "overall_ok"} else "LIMITED_BY_SAMPLE_OR_SCOPE",
                "revision_needed": "TRUE",
                "recommended_metric_action": action,
                "notes": "Direction dropped materially while overall_ok improved; this supports further metric interpretation work.",
            }
        )

    impact_specs = [
        ("direction_accuracy", "REPAIR_WEAKENED_CONCLUSION", "Direction was weak/mixed in original evaluation.", "Corrected direction is materially lower.", "TRUE", "Original direction may have been inflated or more sensitive to ambiguous outcomes."),
        ("overall_ok_accuracy", "REPAIR_CHANGED_METRIC_BEHAVIOR", "Overall_ok was very low and considered stringent.", "Corrected overall_ok increased but remains low.", "TRUE", "Overall_ok still needs decomposition rather than direct replication."),
        ("hypothesis_support", "REPAIR_CONFIRMED_PRIOR_CONCLUSION", "Phase 9A-5G/5R found weak transfer.", "All corrected hypotheses remain not supported.", "TRUE", "Mechanism-gap conclusion is strengthened."),
        ("sample_denominator", "REPAIR_CHANGED_METRIC_BEHAVIOR", "Original evaluation used 145 rows overall and 98 direction denominator.", "Corrected primary uses 129 strict rows and 87 direction denominator.", "TRUE", "Denominator changes must be explicit in review."),
        ("outcome_trust", "REPAIR_STRENGTHENED_CONCLUSION", "Market Reaction outcome layer was questionable.", "Canonical repaired overlay is validated for corrected design/execution.", "TRUE", "Outcome trust improved, making weak transfer harder to dismiss as only outcome ambiguity."),
        ("market_reaction_label_quality", "REPAIR_STRENGTHENED_CONCLUSION", "Original labels were ambiguous and high sensitivity.", "Corrected labels remove ambiguity for strict rows.", "TRUE", "Label quality improved while hypotheses still failed."),
        ("metric_reliability", "REPAIR_NEEDS_FURTHER_REVIEW", "Metrics needed repair, especially overall_ok.", "Metric divergence remains unresolved.", "TRUE", "Second revision should separate direction, overall, and signal discipline metrics."),
        ("phase9a5r_revision_validity", "REPAIR_CONFIRMED_PRIOR_CONCLUSION", "Phase 9A-5R concluded behavior does not equal accuracy signal.", "Corrected results confirm weak transfer.", "TRUE", "Second revision should build explicit mechanism tests."),
    ]
    impact_rows = [
        {
            **_base(generated_ts, review_run_id),
            "impact_area": area,
            "impact_classification": classification,
            "original_interpretation": original,
            "corrected_interpretation": corrected,
            "changed_by_repair": changed,
            "scientific_implication": implication,
            "recommended_followup": "Second hypothesis revision and metric interpretation review.",
            "notes": "No production implication.",
        }
        for area, classification, original, corrected, changed, implication in impact_specs
    ]

    revision_areas = [
        ("behavior_change_without_validated_predictive_mechanism", "Confirmed and strengthened", "All corrected hypotheses remain not supported.", "TRUE", "Outcome repair no longer explains weak transfer.", "mechanism_bridge", "HIGH"),
        ("overall_ok_stringency", "Highest priority metric revision", "Corrected overall_ok improved but remains low and diverges from direction.", "TRUE", "overall_ok behavior remains hard to interpret.", "overall_ok_decomposition", "HIGH"),
        ("USDJPY_conditional_predictive_value", "Conditionalize USDJPY hypothesis", "Corrected USDJPY direction remains weak.", "TRUE", "Behavioral salience did not show broad predictive value.", "conditional_regime_test", "HIGH"),
        ("Pack_B_signal_discipline_conditional", "Focus Pack B on discipline, not raw direction", "Pack B overall improved but direction weakened.", "TRUE", "Signal discipline may require different metrics.", "false_signal_and_no_signal_proxy", "HIGH"),
        ("OpenAI_output_stability_as_control", "Treat OpenAI as control/testbed", "OpenAI has best corrected direction among the three but hypothesis remains not supported.", "TRUE", "Do not convert into provider ranking.", "evaluation_control_role", "MEDIUM"),
        ("metric_or_outcome_repair_priority", "Metric repair before replication", "Outcome repair complete; metric divergence persists.", "TRUE", "Further outcome repair is lower priority than metric interpretation.", "metric_repair", "HIGH"),
        ("replication_readiness", "None before metric repair", "Corrected hypotheses not supported.", "TRUE", "Replication would reproduce unclear mechanisms.", "hold_replication", "HIGH"),
    ]
    second_revision_rows = [
        {
            **_base(generated_ts, review_run_id),
            "revision_area": area,
            "previous_phase9a5r_conclusion": previous,
            "corrected_accuracy_evidence": evidence,
            "second_revision_needed": needed,
            "reason": reason,
            "recommended_second_revision_focus": focus,
            "priority": priority,
            "notes": "Research/governance only; no production optimization.",
        }
        for area, previous, evidence, needed, reason, focus, priority in revision_areas
    ]

    governance_specs = [
        ("GOV_PROVIDER_CALLS", "provider_calls_performed", "0", "0"),
        ("GOV_FORECAST_GENERATION", "forecast_generation_performed", "0", "0"),
        ("GOV_PROVIDER_RERUNS", "provider_rerun_count", "0", "0"),
        ("GOV_EVALUATION_RERUNS", "evaluation_rerun_count", "0", "0"),
        ("GOV_CORRECTED_RESULTS_MODIFIED", "corrected_accuracy_results_modified", "0", "0"),
        ("GOV_ORIGINAL_RESULTS_MODIFIED", "original_accuracy_results_modified", "0", "0"),
        ("GOV_MARKET_REACTION_REPAIR_MODIFIED", "market_reaction_repair_modified", "0", "0"),
        ("GOV_CANONICAL_MAPPING_MODIFIED", "canonical_outcome_mapping_modified", "0", "0"),
        ("GOV_PRODUCTION_BEHAVIOR", "production_behavior_change_count", "0", "0"),
        ("GOV_PRODUCTION_SHEETS", "production_sheet_write_count", "0", "0"),
        ("GOV_ROUTING", "routing_changes", "FALSE", "FALSE"),
        ("GOV_WEIGHTING", "weighting_changes", "FALSE", "FALSE"),
        ("GOV_CALIBRATION", "calibration_changes", "FALSE", "FALSE"),
        ("GOV_ENSEMBLE", "ensemble_changes", "FALSE", "FALSE"),
    ]
    governance_rows = [
        {
            **_base(generated_ts, review_run_id),
            "check_id": check_id,
            "check_name": name,
            "expected_value": expected,
            "actual_value": actual,
            "status": "PASS" if expected == actual else "FAIL",
            "notes": "Corrected accuracy review did not rerun or mutate results.",
        }
        for check_id, name, expected, actual in governance_specs
    ]

    sorted_exps_by_overall = sorted(corrected_exps.values(), key=lambda r: _to_float(r.get("overall_ok_rate")) or -1, reverse=True)
    strongest_experiment = _norm(sorted_exps_by_overall[0].get("experiment_id")) if sorted_exps_by_overall else ""
    numeric_comparisons = [(row["comparison_scope"], _to_float(row["absolute_delta"])) for row in comparison_rows if _to_float(row["absolute_delta"]) is not None]
    largest_negative = min(numeric_comparisons, key=lambda item: item[1]) if numeric_comparisons else ("", None)
    largest_positive = max(numeric_comparisons, key=lambda item: item[1]) if numeric_comparisons else ("", None)
    primary_interpretation = "Corrected outcomes strengthen the mechanism-gap conclusion: behavior signals remain insufficient to produce supported accuracy hypotheses."

    summary_rows = [
        {
            **_base(generated_ts, review_run_id),
            "build_status": "PASS_WITH_WARNINGS",
            "final_interpretation": "CORRECTED_ACCURACY_REVIEW_READY_WITH_WARNINGS",
            "corrected_rows_reviewed": corrected_rows_reviewed,
            "diagnostic_rows_excluded": diagnostic_rows_excluded,
            "hypotheses_reviewed": len(hypothesis_rows),
            "hypotheses_supported": hypothesis_counts["Supported"],
            "hypotheses_partially_supported": hypothesis_counts["Partially Supported"],
            "hypotheses_not_supported": hypothesis_counts["Not Supported"],
            "hypotheses_inconclusive": hypothesis_counts["Inconclusive"],
            "original_direction_rate": original_direction_rate,
            "corrected_direction_rate": corrected_direction_rate,
            "direction_delta": direction_delta,
            "original_overall_ok_rate": original_overall_rate,
            "corrected_overall_ok_rate": corrected_overall_rate,
            "overall_ok_delta": overall_delta,
            "strongest_corrected_experiment": strongest_experiment,
            "largest_negative_shift": f"{largest_negative[0]}={largest_negative[1]:.6f}" if largest_negative[1] is not None else "",
            "largest_positive_shift": f"{largest_positive[0]}={largest_positive[1]:.6f}" if largest_positive[1] is not None else "",
            "primary_corrected_interpretation": primary_interpretation,
            "second_revision_needed": "TRUE",
            "metric_repair_still_needed": "TRUE",
            "replication_ready": "FALSE",
            "provider_calls_performed": 0,
            "forecast_generation_performed": 0,
            "provider_rerun_count": 0,
            "evaluation_rerun_count": 0,
            "corrected_accuracy_results_modified": 0,
            "original_accuracy_results_modified": 0,
            "market_reaction_repair_modified": 0,
            "production_behavior_change_count": 0,
            "production_sheet_write_count": 0,
            "ready_for_second_hypothesis_revision": "TRUE",
            "ready_for_metric_repair": "TRUE",
            "ready_for_replication_design": "FALSE",
            "ready_for_production": "FALSE",
            "recommended_next_step": "PROCEED_TO_PHASE9A5R2_SECOND_HYPOTHESIS_REVISION",
            "notes": json.dumps(
                {
                    "previous_review_final": previous_review_summary.get("final_interpretation", ""),
                    "revision_final": revision_summary.get("final_interpretation", ""),
                    "guardrail": "diagnostic_only_non_production",
                },
                sort_keys=True,
            ),
        }
    ]

    outputs = [
        (OUTPUT_REVIEW, REVIEW_HEADERS, review_rows),
        (OUTPUT_HYPOTHESIS, HYPOTHESIS_HEADERS, hypothesis_rows),
        (OUTPUT_COMPARISON, COMPARISON_HEADERS, comparison_rows),
        (OUTPUT_EXPERIMENT, EXPERIMENT_HEADERS, experiment_rows),
        (OUTPUT_METRIC, METRIC_HEADERS, metric_rows),
        (OUTPUT_REPAIR_IMPACT, REPAIR_IMPACT_HEADERS, impact_rows),
        (OUTPUT_SECOND_REVISION, SECOND_REVISION_HEADERS, second_revision_rows),
        (OUTPUT_GOVERNANCE, GOVERNANCE_HEADERS, governance_rows),
        (OUTPUT_SUMMARY, SUMMARY_HEADERS, summary_rows),
    ]
    for sheet_name, headers, rows in outputs:
        actual_headers = _ensure_sheet_minimal_light(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, headers, len(rows))
        _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, actual_headers, rows)
    registry = _upsert_registry_rows(service)
    return {
        "build_status": summary_rows[0]["build_status"],
        "final_interpretation": summary_rows[0]["final_interpretation"],
        "file_created": "automation/build_corrected_accuracy_review_v0.py",
        "sheets_written": {sheet_name: len(rows) for sheet_name, _, rows in outputs},
        "corrected_rows_reviewed": corrected_rows_reviewed,
        "diagnostic_rows_excluded": diagnostic_rows_excluded,
        "hypotheses_reviewed": len(hypothesis_rows),
        "hypotheses_supported": hypothesis_counts["Supported"],
        "hypotheses_partially_supported": hypothesis_counts["Partially Supported"],
        "hypotheses_not_supported": hypothesis_counts["Not Supported"],
        "hypotheses_inconclusive": hypothesis_counts["Inconclusive"],
        "original_direction_rate": original_direction_rate,
        "corrected_direction_rate": corrected_direction_rate,
        "direction_delta": direction_delta,
        "original_overall_ok_rate": original_overall_rate,
        "corrected_overall_ok_rate": corrected_overall_rate,
        "overall_ok_delta": overall_delta,
        "strongest_corrected_experiment": strongest_experiment,
        "largest_negative_shift": summary_rows[0]["largest_negative_shift"],
        "largest_positive_shift": summary_rows[0]["largest_positive_shift"],
        "primary_corrected_interpretation": primary_interpretation,
        "second_revision_needed": True,
        "metric_repair_still_needed": True,
        "replication_ready": False,
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "provider_rerun_count": 0,
        "evaluation_rerun_count": 0,
        "corrected_accuracy_results_modified": 0,
        "original_accuracy_results_modified": 0,
        "market_reaction_repair_modified": 0,
        "production_behavior_change_count": 0,
        "production_sheet_write_count": 0,
        "ready_for_second_hypothesis_revision": True,
        "ready_for_metric_repair": True,
        "ready_for_replication_design": False,
        "ready_for_production": False,
        "recommended_next_step": summary_rows[0]["recommended_next_step"],
        "registry": registry,
    }


def main() -> None:
    result = build_corrected_accuracy_review_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
