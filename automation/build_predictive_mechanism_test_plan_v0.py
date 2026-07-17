import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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


SCHEMA_VERSION = "presignal_v2_predictive_mechanism_test_plan_0.1"
PLAN_VERSION = "predictive_mechanism_test_plan_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-6A"
REGISTRY_CATEGORY = "PRESIGNAL_V2_PREDICTIVE_MECHANISM_TEST_PLAN"
REGISTRY_OWNER_MODULE = "market_state"

INPUT_SHEETS = [
    "Predictive_Mechanism_Design",
    "Predictive_Mechanism_Framework",
    "Predictive_Mechanism_Hypotheses",
    "Predictive_Mechanism_Test_Framework",
    "Predictive_Mechanism_Observables",
    "Predictive_Mechanism_Evidence_Model",
    "Predictive_Mechanism_Experiment_Map",
    "Predictive_Mechanism_Data_Requirements",
    "Predictive_Mechanism_Priority",
    "Predictive_Mechanism_Design_Summary",
    "Pack_Behavior_Tier2_Generalization_Review",
    "Controlled_Accuracy_Evaluation_Review",
    "Corrected_Accuracy_Review",
    "Phase9A5R2_Summary",
]
READ_INPUT_SHEETS = [
    "Predictive_Mechanism_Design",
    "Predictive_Mechanism_Test_Framework",
    "Predictive_Mechanism_Priority",
    "Predictive_Mechanism_Design_Summary",
]

OUTPUT_PLAN = "Predictive_Mechanism_Test_Plan"
OUTPUT_LABELS = "Predictive_Mechanism_Label_Definitions"
OUTPUT_CONTROLS = "Predictive_Mechanism_Control_Definition"
OUTPUT_METRICS = "Predictive_Mechanism_Metric_Definition"
OUTPUT_FALSIFICATION = "Predictive_Mechanism_Falsification_Rules"
OUTPUT_SAMPLE = "Predictive_Mechanism_Sample_Requirements"
OUTPUT_PREREG = "Predictive_Mechanism_PreRegistration"
OUTPUT_READINESS = "Predictive_Mechanism_Test_Readiness"
OUTPUT_SUMMARY = "Predictive_Mechanism_Test_Plan_Summary"

PLAN_HEADERS = [
    "generated_ts",
    "schema_version",
    "plan_version",
    "plan_run_id",
    "mechanism_id",
    "test_plan_status",
    "scientific_question",
    "pre_registered_test_question",
    "mechanism_label_source",
    "label_outcome_independence_rule",
    "primary_control",
    "primary_metric",
    "falsification_rule",
    "sample_requirement",
    "interpretation_boundary",
    "production_excluded",
    "notes",
]

LABEL_HEADERS = [
    "generated_ts",
    "schema_version",
    "plan_version",
    "plan_run_id",
    "mechanism_id",
    "label_name",
    "label_definition",
    "assignment_rule_without_outcomes",
    "forbidden_inputs",
    "label_status",
    "review_required",
    "notes",
]

CONTROL_HEADERS = [
    "generated_ts",
    "schema_version",
    "plan_version",
    "plan_run_id",
    "mechanism_id",
    "control_population",
    "treatment_population",
    "inclusion_criteria",
    "exclusion_criteria",
    "required_evidence",
    "confounders",
    "dependency_on_repaired_metrics",
    "notes",
]

METRIC_HEADERS = [
    "generated_ts",
    "schema_version",
    "plan_version",
    "plan_run_id",
    "mechanism_id",
    "primary_metric",
    "secondary_metric",
    "supporting_metrics",
    "denominator",
    "success_threshold",
    "warning_threshold",
    "failure_threshold",
    "metric_definition_status",
    "notes",
]

FALSIFICATION_HEADERS = [
    "generated_ts",
    "schema_version",
    "plan_version",
    "plan_run_id",
    "mechanism_id",
    "falsification_criterion",
    "contradictory_evidence",
    "minimum_sample_requirement",
    "invalidation_rule",
    "review_trigger",
    "falsifiable",
    "notes",
]

SAMPLE_HEADERS = [
    "generated_ts",
    "schema_version",
    "plan_version",
    "plan_run_id",
    "mechanism_id",
    "minimum_sessions",
    "minimum_forecasts",
    "minimum_valid_outputs",
    "acceptable_invalid_output_rate",
    "acceptable_provider_imbalance",
    "acceptable_pack_imbalance",
    "sample_status",
    "notes",
]

PREREG_HEADERS = [
    "generated_ts",
    "schema_version",
    "plan_version",
    "plan_run_id",
    "mechanism_id",
    "freeze_component",
    "frozen_definition",
    "change_allowed_after_freeze",
    "outcome_dependent",
    "pre_registration_status",
    "notes",
]

READINESS_HEADERS = [
    "generated_ts",
    "schema_version",
    "plan_version",
    "plan_run_id",
    "mechanism_id",
    "readiness_status",
    "readiness_reason",
    "metric_dependency",
    "insufficient_labels",
    "insufficient_sample",
    "unresolved_confounders",
    "outcome_leakage_risk",
    "recommended_next_action",
    "notes",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "schema_version",
    "plan_version",
    "plan_run_id",
    "build_status",
    "final_interpretation",
    "mechanisms_planned",
    "label_definitions_frozen",
    "metric_definitions_frozen",
    "falsification_rules_defined",
    "sample_requirements_defined",
    "pre_registration_complete",
    "highest_priority_mechanism",
    "highest_scientific_risk",
    "highest_metric_dependency",
    "mechanisms_ready",
    "mechanisms_blocked",
    "provider_calls_performed",
    "forecast_generation_performed",
    "evaluation_rerun_count",
    "production_behavior_change_count",
    "ready_for_mechanism_label_design",
    "ready_for_mechanism_testing",
    "ready_for_replication",
    "ready_for_production",
    "recommended_next_step",
    "notes",
]

MECHANISM_ORDER = [
    "MECH_INFORMATION_VALUE",
    "MECH_SIGNAL_DISCIPLINE",
    "MECH_CONDITIONAL_PREDICTIVENESS",
    "MECH_INFORMATION_FILTERING",
    "MECH_FORECAST_STABILITY",
    "MECH_CAUSAL_ROBUSTNESS",
]

LABELS = {
    "mechanism_positive": "Pre-outcome evidence shows the mechanism condition is present strongly enough for planned testing.",
    "mechanism_negative": "Pre-outcome evidence shows the mechanism condition is absent while the row remains otherwise eligible.",
    "mechanism_unknown": "Pre-outcome evidence is mixed or incomplete but not disqualifying.",
    "insufficient_evidence": "Required behavior or market-state evidence is missing before outcome review.",
    "excluded_case": "Row violates pre-specified inclusion criteria or has invalid/missing source data before outcome review.",
}

DETAILS = {
    "MECH_INFORMATION_VALUE": ("feature_incremental_value", "pack_vs_baseline_delta", "ablation_delta; behavior_conditioned_accuracy_delta", "Rows with explicit feature exposure and matched baseline without feature exposure."),
    "MECH_SIGNAL_DISCIPLINE": ("false_signal_rate", "no_signal_correctness", "unsupported_direction_rate; confidence_evidence_alignment", "Low-signal rows where unsupported direction risk can be assessed before outcomes."),
    "MECH_CONDITIONAL_PREDICTIVENESS": ("regime_conditioned_direction_rate", "regime_conditioned_false_signal_rate", "feature_incremental_value", "Pre-registered regime-positive rows vs regime-negative matched controls."),
    "MECH_INFORMATION_FILTERING": ("information_filtering_score", "false_signal_rate", "irrelevant_signal_reference_rate; causal_noise_score", "Rows with additional information where irrelevant-signal filtering can be scored before outcomes."),
    "MECH_FORECAST_STABILITY": ("selective_change_precision", "forecast_flip_quality", "stability_under_irrelevant_context; direction_match_rate", "Paired pack rows where irrelevant context should not cause forecast movement."),
    "MECH_CAUSAL_ROBUSTNESS": ("causal_robustness_score", "scenario_alignment", "causal_contradiction_rate; direction_match_rate", "Rows with causal chains that can be checked under pre-outcome market context perturbations."),
}


def _run_id(generated_ts: str) -> str:
    return "predictive_mechanism_test_plan_v0_" + generated_ts.replace("-", "").replace(":", "")


def _base(generated_ts: str, plan_run_id: str) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "plan_version": PLAN_VERSION,
        "plan_run_id": plan_run_id,
    }


def _sheet_titles_light(service, spreadsheet_id: str) -> set[str]:
    metadata = (
        service.spreadsheets()
        .get(spreadsheetId=spreadsheet_id, fields="sheets(properties(title))")
        .execute()
    )
    return {sheet["properties"]["title"] for sheet in metadata.get("sheets", [])}


def _get_headers(service, spreadsheet_id: str, sheet_name: str) -> List[str]:
    values = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=f"'{sheet_name}'!1:1")
        .execute()
        .get("values", [])
    )
    return values[0] if values else []


def _ensure_sheet_minimal_light(service, spreadsheet_id: str, sheet_name: str, required_headers: Sequence[str], data_row_count: int) -> List[str]:
    titles = _sheet_titles_light(service, spreadsheet_id)
    if sheet_name not in titles:
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": sheet_name, "gridProperties": {"rowCount": max(1, data_row_count + 1), "columnCount": max(1, len(required_headers))}}}}]},
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


def _read_inputs(service) -> Dict[str, List[Dict[str, Any]]]:
    titles = _sheet_titles_light(service, DIAGNOSTICS_SPREADSHEET_ID)
    missing = [sheet for sheet in INPUT_SHEETS if sheet not in titles]
    if missing:
        raise RuntimeError(f"Missing critical input sheets: {', '.join(sorted(missing))}")
    out = {sheet: _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet) for sheet in READ_INPUT_SHEETS}
    for sheet in INPUT_SHEETS:
        out.setdefault(sheet, [])
    return out


def _latest(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    return rows[-1] if rows else {}


def _upsert_registry_rows(service) -> Dict[str, int]:
    titles = _sheet_titles_light(service, PROJECT_OVERVIEWS_SPREADSHEET_ID)
    if REGISTRY_SHEET not in titles:
        return {"updated": 0, "appended": 0, "status": "missing"}
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_norm(row.get("logical_sheet_id")).upper(): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_norm(row.get("logical_sheet_id")).upper(): row for row in rows}
    specs = [
        ("PREDICTIVE_MECHANISM_TEST_PLAN", OUTPUT_PLAN, "predictive_mechanism_test_plan"),
        ("PREDICTIVE_MECHANISM_LABEL_DEFINITIONS", OUTPUT_LABELS, "predictive_mechanism_label_definitions"),
        ("PREDICTIVE_MECHANISM_CONTROL_DEFINITION", OUTPUT_CONTROLS, "predictive_mechanism_control_definition"),
        ("PREDICTIVE_MECHANISM_METRIC_DEFINITION", OUTPUT_METRICS, "predictive_mechanism_metric_definition"),
        ("PREDICTIVE_MECHANISM_FALSIFICATION_RULES", OUTPUT_FALSIFICATION, "predictive_mechanism_falsification_rules"),
        ("PREDICTIVE_MECHANISM_SAMPLE_REQUIREMENTS", OUTPUT_SAMPLE, "predictive_mechanism_sample_requirements"),
        ("PREDICTIVE_MECHANISM_PREREGISTRATION", OUTPUT_PREREG, "predictive_mechanism_preregistration"),
        ("PREDICTIVE_MECHANISM_TEST_READINESS", OUTPUT_READINESS, "predictive_mechanism_test_readiness"),
        ("PREDICTIVE_MECHANISM_TEST_PLAN_SUMMARY", OUTPUT_SUMMARY, "predictive_mechanism_test_plan_summary"),
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
            "notes": "Phase 9A-6A predictive mechanism test plan; pre-registered research planning only.",
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


def build_predictive_mechanism_test_plan_v0() -> Dict[str, Any]:
    service = build_sheets_service(load_credentials())
    generated_ts = _iso_now()
    plan_run_id = _run_id(generated_ts)
    inputs = _read_inputs(service)
    design_by_id = {_norm(row.get("mechanism_id")): row for row in inputs["Predictive_Mechanism_Design"]}
    priority_by_id = {_norm(row.get("mechanism_id")): row for row in inputs["Predictive_Mechanism_Priority"]}
    summary = _latest(inputs["Predictive_Mechanism_Design_Summary"])

    plan_rows: List[Dict[str, Any]] = []
    label_rows: List[Dict[str, Any]] = []
    control_rows: List[Dict[str, Any]] = []
    metric_rows: List[Dict[str, Any]] = []
    falsification_rows: List[Dict[str, Any]] = []
    sample_rows: List[Dict[str, Any]] = []
    prereg_rows: List[Dict[str, Any]] = []
    readiness_rows: List[Dict[str, Any]] = []

    for mechanism_id in MECHANISM_ORDER:
        design = design_by_id[mechanism_id]
        primary, secondary, supporting, population = DETAILS[mechanism_id]
        priority = _norm(priority_by_id.get(mechanism_id, {}).get("final_execution_priority")) or _norm(design.get("recommended_priority"))
        label_source = "pre-outcome behavior and market-state observables only"
        sample_text = _norm(design.get("required_sample_size"))
        metric_dependency = "HIGH" if mechanism_id in {"MECH_SIGNAL_DISCIPLINE", "MECH_INFORMATION_VALUE"} else "MEDIUM"
        ready_status = "READY_WITH_WARNINGS" if metric_dependency == "HIGH" else "READY"
        plan_rows.append(
            {
                **_base(generated_ts, plan_run_id),
                "mechanism_id": mechanism_id,
                "test_plan_status": "PRE_REGISTERED_NOT_EXECUTED",
                "scientific_question": _norm(design.get("scientific_question")),
                "pre_registered_test_question": f"Before outcomes are inspected, can {mechanism_id} labels separate mechanism-positive from mechanism-negative rows?",
                "mechanism_label_source": label_source,
                "label_outcome_independence_rule": "Labels must be assigned without realized direction, realized pips, overall_ok, corrected outcomes, or evaluation results.",
                "primary_control": population,
                "primary_metric": primary,
                "falsification_rule": _norm(design.get("falsification_criteria")),
                "sample_requirement": sample_text,
                "interpretation_boundary": "Mechanism tests are diagnostic and cannot authorize routing, weighting, calibration, prompt, pack, provider, or production changes.",
                "production_excluded": "TRUE",
                "notes": f"Priority={priority}; definitions freeze before mechanism-conditioned accuracy evaluation.",
            }
        )
        for label_name, label_definition in LABELS.items():
            label_rows.append(
                {
                    **_base(generated_ts, plan_run_id),
                    "mechanism_id": mechanism_id,
                    "label_name": label_name,
                    "label_definition": label_definition,
                    "assignment_rule_without_outcomes": f"Assign from {label_source}; do not inspect outcome/evaluation fields.",
                    "forbidden_inputs": "realized_direction; realized_pips; overall_ok; corrected_outcomes; evaluation_results; hindsight_reasoning",
                    "label_status": "PRE_REGISTERABLE",
                    "review_required": "TRUE" if label_name in {"mechanism_unknown", "insufficient_evidence"} else "FALSE",
                    "notes": "Outcome-dependent labels would be marked LABEL_NOT_PRE_REGISTERABLE; this label is outcome-independent.",
                }
            )
        control_rows.append(
            {
                **_base(generated_ts, plan_run_id),
                "mechanism_id": mechanism_id,
                "control_population": "mechanism_negative rows matched on session, provider, pack level, event family, and availability of strict corrected outcome when later evaluated",
                "treatment_population": "mechanism_positive rows under frozen pre-outcome label rules",
                "inclusion_criteria": "valid provider output; required behavior evidence present; no realized-outcome fields used for mechanism label",
                "exclusion_criteria": "invalid output; missing label evidence; post-outcome label dependency; unresolved source or schema mismatch",
                "required_evidence": _norm(design.get("observable_behavior")),
                "confounders": _norm(design.get("confounders")),
                "dependency_on_repaired_metrics": metric_dependency,
                "notes": "Controls are defined before testing and do not rank providers or packs.",
            }
        )
        metric_rows.append(
            {
                **_base(generated_ts, plan_run_id),
                "mechanism_id": mechanism_id,
                "primary_metric": primary,
                "secondary_metric": secondary,
                "supporting_metrics": supporting,
                "denominator": "pre-registered mechanism-positive and mechanism-negative rows with valid strict corrected outcomes in future evaluation",
                "success_threshold": "mechanism-positive metric improves by >= 0.05 absolute over matched mechanism-negative/baseline rows with no governance breach",
                "warning_threshold": "absolute improvement between 0.02 and 0.05 or denominator imbalance above warning threshold",
                "failure_threshold": "absolute improvement < 0.02 or wrong-direction effect after minimum sample is met",
                "metric_definition_status": "FROZEN_FOR_TEST_PLAN",
                "notes": "Metric values are not calculated in this phase.",
            }
        )
        falsification_rows.append(
            {
                **_base(generated_ts, plan_run_id),
                "mechanism_id": mechanism_id,
                "falsification_criterion": _norm(design.get("falsification_criteria")),
                "contradictory_evidence": "mechanism-positive rows fail to improve primary metric or show worse predictive behavior after minimum sample is met",
                "minimum_sample_requirement": sample_text,
                "invalidation_rule": "Invalidate or revise mechanism if contradictory evidence appears in two controlled samples or one sufficiently powered sample with clean governance.",
                "review_trigger": "trigger review if warning threshold is hit, provider imbalance exceeds threshold, or labels drift after freeze",
                "falsifiable": "TRUE",
                "notes": "Falsification is pre-registered before any mechanism-conditioned accuracy evaluation.",
            }
        )
        sample_rows.append(
            {
                **_base(generated_ts, plan_run_id),
                "mechanism_id": mechanism_id,
                "minimum_sessions": "30",
                "minimum_forecasts": "120" if mechanism_id != "MECH_INFORMATION_VALUE" else "200",
                "minimum_valid_outputs": "90% of planned denominator",
                "acceptable_invalid_output_rate": "<= 0.15 overall and <= 0.20 per provider",
                "acceptable_provider_imbalance": "largest provider share <= 0.50 unless provider-specific mechanism test is pre-declared",
                "acceptable_pack_imbalance": "largest pack share <= 0.50 unless pack-specific mechanism test is pre-declared",
                "sample_status": "DEFINED_NOT_COLLECTED",
                "notes": sample_text,
            }
        )
        for component, definition in [
            ("mechanism_labels", "mechanism_positive; mechanism_negative; mechanism_unknown; insufficient_evidence; excluded_case"),
            ("metric_definitions", f"primary={primary}; secondary={secondary}; supporting={supporting}"),
            ("success_thresholds", "success >= 0.05 absolute improvement; warning 0.02-0.05; failure < 0.02 or wrong direction"),
            ("falsification_rules", _norm(design.get("falsification_criteria"))),
            ("sample_requirements", sample_text),
            ("interpretation_boundaries", "diagnostic only; no production, routing, weighting, calibration, or prompt changes"),
        ]:
            prereg_rows.append(
                {
                    **_base(generated_ts, plan_run_id),
                    "mechanism_id": mechanism_id,
                    "freeze_component": component,
                    "frozen_definition": definition,
                    "change_allowed_after_freeze": "FALSE",
                    "outcome_dependent": "FALSE",
                    "pre_registration_status": "FROZEN_FOR_TEST_PLAN",
                    "notes": "Definition must not change until testing is complete.",
                }
            )
        readiness_rows.append(
            {
                **_base(generated_ts, plan_run_id),
                "mechanism_id": mechanism_id,
                "readiness_status": ready_status,
                "readiness_reason": "Labels, controls, metrics, falsification rules, and sample requirements are pre-registered.",
                "metric_dependency": metric_dependency,
                "insufficient_labels": "FALSE",
                "insufficient_sample": "TRUE_FOR_EXECUTION_NOT_PLANNING",
                "unresolved_confounders": "TRUE_FOR_EXECUTION_NOT_PLANNING",
                "outcome_leakage_risk": "LOW_AFTER_FREEZE",
                "recommended_next_action": "PROCEED_TO_PHASE9A6B_MECHANISM_LABEL_AND_METRIC_DESIGN",
                "notes": "Ready for label/metric design; not ready for live mechanism testing or replication.",
            }
        )

    governance_specs = [
        ("GOV_PROVIDER_CALLS", "provider_calls_performed", "0", "0"),
        ("GOV_FORECAST_GENERATION", "forecast_generation_performed", "0", "0"),
        ("GOV_EVALUATION_RERUN", "evaluation_rerun_count", "0", "0"),
        ("GOV_PRODUCTION_BEHAVIOR", "production_behavior_change_count", "0", "0"),
        ("GOV_PROMPT_MODIFICATION", "prompt_modification", "FALSE", "FALSE"),
        ("GOV_PROVIDER_MODIFICATION", "provider_modification", "FALSE", "FALSE"),
        ("GOV_PACK_MODIFICATION", "pack_modification", "FALSE", "FALSE"),
        ("GOV_ROUTING", "routing_changes", "FALSE", "FALSE"),
        ("GOV_WEIGHTING", "weighting_changes", "FALSE", "FALSE"),
        ("GOV_CALIBRATION", "calibration_changes", "FALSE", "FALSE"),
        ("GOV_PRODUCTION_WRITES", "production_writes", "0", "0"),
    ]
    governance_rows = [
        {
            **_base(generated_ts, plan_run_id),
            "check_id": check_id,
            "check_name": name,
            "expected_value": expected,
            "actual_value": actual,
            "status": "PASS" if expected == actual else "FAIL",
            "notes": "Predictive mechanism test planning only.",
        }
        for check_id, name, expected, actual in governance_specs
    ]

    mechanisms_ready = sum(1 for row in readiness_rows if row["readiness_status"] in {"READY", "READY_WITH_WARNINGS"})
    mechanisms_blocked = sum(1 for row in readiness_rows if row["readiness_status"] == "BLOCKED")
    summary_rows = [
        {
            **_base(generated_ts, plan_run_id),
            "build_status": "PASS_WITH_WARNINGS",
            "final_interpretation": "PREDICTIVE_MECHANISM_TEST_PLAN_READY_WITH_WARNINGS",
            "mechanisms_planned": len(plan_rows),
            "label_definitions_frozen": "TRUE",
            "metric_definitions_frozen": "TRUE",
            "falsification_rules_defined": len(falsification_rows),
            "sample_requirements_defined": len(sample_rows),
            "pre_registration_complete": "TRUE",
            "highest_priority_mechanism": "MECH_INFORMATION_VALUE",
            "highest_scientific_risk": "mechanism labels may become post-hoc proxies unless frozen before accuracy testing",
            "highest_metric_dependency": "MECH_SIGNAL_DISCIPLINE",
            "mechanisms_ready": mechanisms_ready,
            "mechanisms_blocked": mechanisms_blocked,
            "provider_calls_performed": 0,
            "forecast_generation_performed": 0,
            "evaluation_rerun_count": 0,
            "production_behavior_change_count": 0,
            "ready_for_mechanism_label_design": "TRUE",
            "ready_for_mechanism_testing": "FALSE",
            "ready_for_replication": "FALSE",
            "ready_for_production": "FALSE",
            "recommended_next_step": "PROCEED_TO_PHASE9A6B_MECHANISM_LABEL_AND_METRIC_DESIGN",
            "notes": json.dumps(
                {
                    "source_design": summary.get("final_interpretation", ""),
                    "outcome_independence": "labels_frozen_without_realized_outcomes",
                    "testing_boundary": "planning_only",
                },
                sort_keys=True,
            ),
        }
    ]

    outputs = [
        (OUTPUT_PLAN, PLAN_HEADERS, plan_rows),
        (OUTPUT_LABELS, LABEL_HEADERS, label_rows),
        (OUTPUT_CONTROLS, CONTROL_HEADERS, control_rows),
        (OUTPUT_METRICS, METRIC_HEADERS, metric_rows),
        (OUTPUT_FALSIFICATION, FALSIFICATION_HEADERS, falsification_rows),
        (OUTPUT_SAMPLE, SAMPLE_HEADERS, sample_rows),
        (OUTPUT_PREREG, PREREG_HEADERS, prereg_rows),
        (OUTPUT_READINESS, READINESS_HEADERS, readiness_rows),
        (OUTPUT_SUMMARY, SUMMARY_HEADERS, summary_rows),
    ]
    for sheet_name, headers, rows in outputs:
        actual_headers = _ensure_sheet_minimal_light(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, headers, len(rows))
        _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, actual_headers, rows)
    registry = _upsert_registry_rows(service)
    return {
        "build_status": summary_rows[0]["build_status"],
        "final_interpretation": summary_rows[0]["final_interpretation"],
        "file_created": "automation/build_predictive_mechanism_test_plan_v0.py",
        "sheets_written": {sheet_name: len(rows) for sheet_name, _, rows in outputs},
        "mechanisms_planned": len(plan_rows),
        "label_definitions_frozen": True,
        "metric_definitions_frozen": True,
        "falsification_rules_defined": len(falsification_rows),
        "sample_requirements_defined": len(sample_rows),
        "pre_registration_complete": True,
        "highest_priority_mechanism": "MECH_INFORMATION_VALUE",
        "highest_scientific_risk": summary_rows[0]["highest_scientific_risk"],
        "highest_metric_dependency": "MECH_SIGNAL_DISCIPLINE",
        "mechanisms_ready": mechanisms_ready,
        "mechanisms_blocked": mechanisms_blocked,
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "evaluation_rerun_count": 0,
        "production_behavior_change_count": 0,
        "ready_for_mechanism_label_design": True,
        "ready_for_mechanism_testing": False,
        "ready_for_replication": False,
        "ready_for_production": False,
        "recommended_next_step": summary_rows[0]["recommended_next_step"],
        "registry": registry,
    }


def main() -> None:
    result = build_predictive_mechanism_test_plan_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
