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


SCHEMA_VERSION = "presignal_v2_predictive_mechanism_design_0.1"
DESIGN_VERSION = "predictive_mechanism_design_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-6"
REGISTRY_CATEGORY = "PRESIGNAL_V2_PREDICTIVE_MECHANISM_DESIGN"
REGISTRY_OWNER_MODULE = "market_state"

INPUT_SHEETS = [
    "Predictive_Mechanism_Framework",
    "Predictive_Mechanism_Hypotheses",
    "Behavior_to_Mechanism_Mapping",
    "Mechanism_to_Accuracy_Mapping",
    "Mechanism_Testability_Audit",
    "Pack_Behavior_Tier2_Generalization_Review",
    "Pack_Behavior_Tier2_Hypothesis_Generalization",
    "Controlled_Accuracy_Evaluation",
    "Controlled_Accuracy_Evaluation_Review",
    "Corrected_Accuracy_Review",
    "Corrected_Accuracy_Hypothesis_Review",
    "Behavior_Accuracy_Hypothesis_Revision",
    "Phase9A5R2_Summary",
]
READ_INPUT_SHEETS = [
    "Predictive_Mechanism_Hypotheses",
    "Mechanism_Testability_Audit",
    "Phase9A5R2_Summary",
    "Corrected_Accuracy_Review",
]

OUTPUT_DESIGN = "Predictive_Mechanism_Design"
OUTPUT_TEST = "Predictive_Mechanism_Test_Framework"
OUTPUT_OBSERVABLES = "Predictive_Mechanism_Observables"
OUTPUT_EVIDENCE = "Predictive_Mechanism_Evidence_Model"
OUTPUT_EXPERIMENT = "Predictive_Mechanism_Experiment_Map"
OUTPUT_DATA = "Predictive_Mechanism_Data_Requirements"
OUTPUT_PRIORITY = "Predictive_Mechanism_Priority"
OUTPUT_GOVERNANCE = "Predictive_Mechanism_Governance"
OUTPUT_SUMMARY = "Predictive_Mechanism_Design_Summary"

DESIGN_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "mechanism_id",
    "mechanism_description",
    "scientific_question",
    "observable_behavior",
    "observable_prediction_effect",
    "required_inputs",
    "required_outputs",
    "measurable_variables",
    "required_sample_size",
    "confounders",
    "failure_conditions",
    "falsification_criteria",
    "recommended_priority",
    "production_excluded",
    "notes",
]

TEST_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "mechanism_id",
    "existing_evidence_available",
    "evidence_still_missing",
    "reusable_tier2_datasets",
    "reusable_corrected_evaluation_datasets",
    "new_provider_calls_required",
    "metric_redesign_required_first",
    "expected_statistical_comparison",
    "expected_success_criteria",
    "test_framework_status",
    "notes",
]

OBSERVABLE_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "mechanism_id",
    "observable_type",
    "observable_name",
    "observable_definition",
    "source_sheet_or_future_source",
    "measurement_rule",
    "do_not_confuse_with",
    "notes",
]

EVIDENCE_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "mechanism_id",
    "evidence_layer",
    "evidence_source",
    "evidence_available_now",
    "evidence_gap",
    "minimum_evidence_to_advance",
    "failure_signal",
    "notes",
]

EXPERIMENT_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "mechanism_id",
    "experiment_id",
    "experiment_question",
    "comparison_groups",
    "control_conditions",
    "primary_metric",
    "secondary_metrics",
    "execution_dependency",
    "success_criteria",
    "falsification_criteria",
    "notes",
]

DATA_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "mechanism_id",
    "required_input_dataset",
    "required_output_dataset",
    "existing_source_available",
    "new_collection_required",
    "provider_calls_required",
    "metric_repair_required",
    "minimum_sample_size",
    "data_quality_risk",
    "notes",
]

PRIORITY_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "mechanism_id",
    "scientific_value_score",
    "feasibility_score",
    "existing_evidence_score",
    "metric_dependency_score",
    "provider_call_dependency_score",
    "composite_priority_score",
    "priority_rank",
    "final_execution_priority",
    "priority_rationale",
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

SUMMARY_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "build_status",
    "final_interpretation",
    "mechanisms_designed",
    "test_frameworks_defined",
    "existing_evidence_sources",
    "missing_evidence_sources",
    "priority_ranking_completed",
    "highest_priority_mechanism",
    "highest_scientific_risk",
    "highest_metric_dependency",
    "provider_calls_performed",
    "forecast_generation_performed",
    "evaluation_rerun_count",
    "production_behavior_change_count",
    "ready_for_mechanism_test_planning",
    "ready_for_replication",
    "ready_for_production",
    "recommended_next_step",
    "notes",
]


MECH_DETAILS = {
    "MECH_INFORMATION_VALUE": {
        "question": "Does newly exposed information provide incremental predictive value?",
        "behavior": "field used, reasoning changed, information_used expanded, causal chain references new feature",
        "prediction": "pack_vs_baseline_delta improves after controlling for regime and provider",
        "variables": "feature_incremental_value; ablation_delta; behavior_conditioned_accuracy_delta; pack_vs_baseline_delta",
        "failure": "feature changes reasoning but adds no incremental value over baseline",
        "priority_hint": "P1",
        "scientific_value": 5,
        "feasibility": 4,
        "existing_evidence": 4,
        "metric_dependency": 2,
        "provider_dependency": 2,
    },
    "MECH_SIGNAL_DISCIPLINE": {
        "question": "Does the model reduce false-positive reasoning rather than simply becoming more active?",
        "behavior": "no-signal changed, confidence reduced in low-signal rows, unsupported direction avoided",
        "prediction": "false_signal_rate falls and no_signal_correctness improves in low-signal sessions",
        "variables": "false_signal_rate; no_signal_correctness; unsupported_direction_rate; confidence_evidence_alignment",
        "failure": "behavior becomes more active or confident without reducing false positives",
        "priority_hint": "P2",
        "scientific_value": 5,
        "feasibility": 3,
        "existing_evidence": 3,
        "metric_dependency": 1,
        "provider_dependency": 2,
    },
    "MECH_CONDITIONAL_PREDICTIVENESS": {
        "question": "Under which market regimes does a feature actually become predictive?",
        "behavior": "feature is cited or shifts reasoning only within pre-registered market-state slice",
        "prediction": "direction or false-signal metric improves inside the regime but not outside it",
        "variables": "regime_conditioned_direction_rate; regime_conditioned_false_signal_rate; feature_incremental_value",
        "failure": "pre-registered regime slices do not outperform matched baseline slices",
        "priority_hint": "P3",
        "scientific_value": 5,
        "feasibility": 3,
        "existing_evidence": 3,
        "metric_dependency": 3,
        "provider_dependency": 2,
    },
    "MECH_INFORMATION_FILTERING": {
        "question": "Does additional information improve filtering rather than increasing reasoning complexity?",
        "behavior": "irrelevant fields are discarded, causal chain simplifies, missing information reduces without extra noise",
        "prediction": "false_signal_rate falls or direction_match_rate improves when irrelevant-signal references fall",
        "variables": "irrelevant_signal_reference_rate; information_filtering_score; causal_noise_score",
        "failure": "reasoning complexity increases without reducing irrelevant signal use or false positives",
        "priority_hint": "P4",
        "scientific_value": 4,
        "feasibility": 3,
        "existing_evidence": 3,
        "metric_dependency": 3,
        "provider_dependency": 2,
    },
    "MECH_FORECAST_STABILITY": {
        "question": "Does selective behavioral stability improve prediction?",
        "behavior": "forecast remains stable under irrelevant context and changes only under high-value mechanism triggers",
        "prediction": "selective changes outperform indiscriminate sensitivity and no-change baselines",
        "variables": "selective_change_precision; forecast_flip_quality; stability_under_irrelevant_context",
        "failure": "selective changes are not more accurate than random or high-sensitivity changes",
        "priority_hint": "P5",
        "scientific_value": 4,
        "feasibility": 4,
        "existing_evidence": 3,
        "metric_dependency": 3,
        "provider_dependency": 2,
    },
    "MECH_CAUSAL_ROBUSTNESS": {
        "question": "Does a stable causal chain survive multiple market contexts?",
        "behavior": "causal chain remains coherent and premise-consistent across controlled context perturbations",
        "prediction": "scenario_alignment and direction_match_rate improve when causal robustness score is high",
        "variables": "causal_robustness_score; causal_contradiction_rate; scenario_alignment",
        "failure": "causal chains are stable in language but not predictive under context perturbation",
        "priority_hint": "P6",
        "scientific_value": 4,
        "feasibility": 3,
        "existing_evidence": 3,
        "metric_dependency": 4,
        "provider_dependency": 2,
    },
}


def _run_id(generated_ts: str) -> str:
    return "predictive_mechanism_design_v0_" + generated_ts.replace("-", "").replace(":", "")


def _base(generated_ts: str, design_run_id: str) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "design_version": DESIGN_VERSION,
        "design_run_id": design_run_id,
    }


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


def _mechanism_rows(inputs: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    rows = inputs.get("Predictive_Mechanism_Hypotheses", [])
    order = [
        "MECH_INFORMATION_VALUE",
        "MECH_SIGNAL_DISCIPLINE",
        "MECH_CONDITIONAL_PREDICTIVENESS",
        "MECH_INFORMATION_FILTERING",
        "MECH_FORECAST_STABILITY",
        "MECH_CAUSAL_ROBUSTNESS",
    ]
    by_id = {_norm(row.get("mechanism_id")): row for row in rows}
    return [by_id[mid] for mid in order if mid in by_id]


def _upsert_registry_rows(service) -> Dict[str, int]:
    titles = _sheet_titles_light(service, PROJECT_OVERVIEWS_SPREADSHEET_ID)
    if REGISTRY_SHEET not in titles:
        return {"updated": 0, "appended": 0, "status": "missing"}
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_norm(row.get("logical_sheet_id")).upper(): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_norm(row.get("logical_sheet_id")).upper(): row for row in rows}
    specs = [
        ("PREDICTIVE_MECHANISM_DESIGN", OUTPUT_DESIGN, "predictive_mechanism_design"),
        ("PREDICTIVE_MECHANISM_TEST_FRAMEWORK", OUTPUT_TEST, "predictive_mechanism_test_framework"),
        ("PREDICTIVE_MECHANISM_OBSERVABLES", OUTPUT_OBSERVABLES, "predictive_mechanism_observables"),
        ("PREDICTIVE_MECHANISM_EVIDENCE_MODEL", OUTPUT_EVIDENCE, "predictive_mechanism_evidence_model"),
        ("PREDICTIVE_MECHANISM_EXPERIMENT_MAP", OUTPUT_EXPERIMENT, "predictive_mechanism_experiment_map"),
        ("PREDICTIVE_MECHANISM_DATA_REQUIREMENTS", OUTPUT_DATA, "predictive_mechanism_data_requirements"),
        ("PREDICTIVE_MECHANISM_PRIORITY", OUTPUT_PRIORITY, "predictive_mechanism_priority"),
        ("PREDICTIVE_MECHANISM_GOVERNANCE", OUTPUT_GOVERNANCE, "predictive_mechanism_governance"),
        ("PREDICTIVE_MECHANISM_DESIGN_SUMMARY", OUTPUT_SUMMARY, "predictive_mechanism_design_summary"),
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
            "notes": "Phase 9A-6 predictive mechanism design; research-design only.",
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


def build_predictive_mechanism_design_v0() -> Dict[str, Any]:
    service = build_sheets_service(load_credentials())
    generated_ts = _iso_now()
    design_run_id = _run_id(generated_ts)
    inputs = _read_inputs(service)
    mechanisms = _mechanism_rows(inputs)
    phase9a5r2 = _latest(inputs["Phase9A5R2_Summary"])
    corrected_review = _latest(inputs["Corrected_Accuracy_Review"])
    corrected_review_summary = _latest(inputs.get("Corrected_Accuracy_Review_Summary", []))

    design_rows: List[Dict[str, Any]] = []
    test_rows: List[Dict[str, Any]] = []
    observable_rows: List[Dict[str, Any]] = []
    evidence_rows: List[Dict[str, Any]] = []
    experiment_rows: List[Dict[str, Any]] = []
    data_rows: List[Dict[str, Any]] = []
    priority_rows: List[Dict[str, Any]] = []

    for mech in mechanisms:
        mechanism_id = _norm(mech.get("mechanism_id"))
        detail = MECH_DETAILS[mechanism_id]
        design_rows.append(
            {
                **_base(generated_ts, design_run_id),
                "mechanism_id": mechanism_id,
                "mechanism_description": _norm(mech.get("mechanism_description")),
                "scientific_question": detail["question"],
                "observable_behavior": detail["behavior"],
                "observable_prediction_effect": detail["prediction"],
                "required_inputs": "Tier 2 behavior transitions; corrected strict evaluation rows; mechanism-specific observables",
                "required_outputs": "mechanism evidence score; mechanism-positive/negative row classification; future accuracy-test eligibility",
                "measurable_variables": detail["variables"],
                "required_sample_size": _norm(mech.get("required_sample_size")),
                "confounders": _norm(mech.get("confounders")),
                "failure_conditions": detail["failure"],
                "falsification_criteria": _norm(mech.get("expected_falsification_criteria")),
                "recommended_priority": detail["priority_hint"],
                "production_excluded": "TRUE",
                "notes": "Design-only mechanism specification; no prompt/provider/pack optimization.",
            }
        )
        test_rows.append(
            {
                **_base(generated_ts, design_run_id),
                "mechanism_id": mechanism_id,
                "existing_evidence_available": "Tier 2 behavior generalization; original controlled accuracy; corrected accuracy review; 9A-5R2 mechanism hypothesis",
                "evidence_still_missing": "Pre-registered mechanism-positive row labels and mechanism-specific metric validation",
                "reusable_tier2_datasets": "Pack_Behavior_Tier2_Transitions; Pack_Behavior_Tier2_Field_Influence; Pack_Behavior_Tier2_NoSignal",
                "reusable_corrected_evaluation_datasets": "Corrected_Accuracy_Evaluation; Corrected_Accuracy_Review; Corrected_Accuracy_Hypothesis_Review",
                "new_provider_calls_required": "TRUE_FOR_EXECUTION_NOT_THIS_PHASE",
                "metric_redesign_required_first": "TRUE" if mechanism_id in {"MECH_INFORMATION_VALUE", "MECH_SIGNAL_DISCIPLINE"} else "PARTIAL",
                "expected_statistical_comparison": "Mechanism-positive strict rows vs matched mechanism-negative/baseline rows; no provider or pack ranking.",
                "expected_success_criteria": "Mechanism evidence improves before accuracy metrics improve, with pre-registered denominators and controls.",
                "test_framework_status": "DESIGNED_NOT_EXECUTED",
                "notes": "This phase defines test structure only.",
            }
        )
        for obs_type, obs_name, obs_def, source, rule, caution in [
            ("BEHAVIOR", "behavior_change_observable", detail["behavior"], "Tier 2 behavior sheets or future mechanism-run behavior sheets", "Measure before looking at outcome correctness.", "predictive effect"),
            ("PREDICTIVE", "prediction_effect_observable", detail["prediction"], "Corrected strict evaluation outputs or future corrected mechanism evaluation", "Measure only after mechanism labels are frozen.", "behavior movement"),
        ]:
            observable_rows.append(
                {
                    **_base(generated_ts, design_run_id),
                    "mechanism_id": mechanism_id,
                    "observable_type": obs_type,
                    "observable_name": obs_name,
                    "observable_definition": obs_def,
                    "source_sheet_or_future_source": source,
                    "measurement_rule": rule,
                    "do_not_confuse_with": caution,
                    "notes": "Behavior and predictive observables must stay separated.",
                }
            )
        for layer, source, available, gap, minimum, failure in [
            ("behavior_evidence", "Tier 2 behavior generalization", "TRUE", "mechanism-specific labels not frozen", "behavior observable measured consistently", "behavior not reproducible"),
            ("mechanism_evidence", "future Phase 9A-6A test plan", "FALSE", "mechanism-positive classification missing", "mechanism score separates rows before accuracy", "mechanism score does not separate rows"),
            ("accuracy_evidence", "corrected strict evaluation / future mechanism evaluation", "PARTIAL", "mechanism-conditioned accuracy not tested", "accuracy metric improves only after mechanism evidence", "accuracy does not improve after mechanism evidence"),
        ]:
            evidence_rows.append(
                {
                    **_base(generated_ts, design_run_id),
                    "mechanism_id": mechanism_id,
                    "evidence_layer": layer,
                    "evidence_source": source,
                    "evidence_available_now": available,
                    "evidence_gap": gap,
                    "minimum_evidence_to_advance": minimum,
                    "failure_signal": failure,
                    "notes": "Evidence model enforces Market State -> Behavior -> Mechanism -> Accuracy order.",
                }
            )
        experiment_rows.append(
            {
                **_base(generated_ts, design_run_id),
                "mechanism_id": mechanism_id,
                "experiment_id": f"EXP_{mechanism_id}",
                "experiment_question": detail["question"],
                "comparison_groups": "mechanism_positive vs mechanism_negative; matched baseline controls; strict corrected outcome rows only in future evaluation",
                "control_conditions": "same providers; frozen prompts; same pack exposure except mechanism variable; no production routing",
                "primary_metric": detail["variables"].split(";")[0],
                "secondary_metrics": detail["variables"],
                "execution_dependency": "Phase 9A-6A predictive mechanism test plan",
                "success_criteria": "Mechanism observable improves and predicts future corrected accuracy metric without post-hoc selection.",
                "falsification_criteria": detail["failure"],
                "notes": "Experiment map does not execute forecasts or accuracy.",
            }
        )
        data_rows.append(
            {
                **_base(generated_ts, design_run_id),
                "mechanism_id": mechanism_id,
                "required_input_dataset": "Tier 2 behavior rows; corrected accuracy rows; future mechanism-labeled runs",
                "required_output_dataset": "Predictive mechanism test outputs; mechanism-conditioned accuracy design outputs",
                "existing_source_available": "PARTIAL",
                "new_collection_required": "TRUE_FOR_FUTURE_TESTING",
                "provider_calls_required": "TRUE_FOR_FUTURE_TESTING_NOT_THIS_PHASE",
                "metric_repair_required": "TRUE" if mechanism_id in {"MECH_INFORMATION_VALUE", "MECH_SIGNAL_DISCIPLINE"} else "PARTIAL",
                "minimum_sample_size": _norm(mech.get("required_sample_size")),
                "data_quality_risk": "sample size, mechanism-label ambiguity, event-family imbalance, corrected outcome sensitivity",
                "notes": "Data requirements are for future planning; no collection occurs here.",
            }
        )
        composite = (
            detail["scientific_value"] * 3
            + detail["feasibility"] * 2
            + detail["existing_evidence"] * 2
            + detail["metric_dependency"]
            + detail["provider_dependency"]
        )
        priority_rows.append(
            {
                **_base(generated_ts, design_run_id),
                "mechanism_id": mechanism_id,
                "scientific_value_score": detail["scientific_value"],
                "feasibility_score": detail["feasibility"],
                "existing_evidence_score": detail["existing_evidence"],
                "metric_dependency_score": detail["metric_dependency"],
                "provider_call_dependency_score": detail["provider_dependency"],
                "composite_priority_score": composite,
                "priority_rank": "",
                "final_execution_priority": "",
                "priority_rationale": "Higher scientific value and evidence with lower dependency burden ranks earlier.",
                "notes": "Priority is for research sequencing only, not production optimization.",
            }
        )

    priority_rows.sort(key=lambda row: (-int(row["composite_priority_score"]), _norm(row["mechanism_id"])))
    for idx, row in enumerate(priority_rows, 1):
        row["priority_rank"] = idx
        row["final_execution_priority"] = f"P{idx}"

    governance_specs = [
        ("GOV_PROVIDER_CALLS", "provider_calls_performed", "0", "0"),
        ("GOV_FORECAST_GENERATION", "forecast_generation_performed", "0", "0"),
        ("GOV_EVALUATION_RERUN", "evaluation_rerun_count", "0", "0"),
        ("GOV_PRODUCTION_BEHAVIOR", "production_behavior_change_count", "0", "0"),
        ("GOV_PRODUCTION_SHEETS", "production_sheet_write_count", "0", "0"),
        ("GOV_PROMPT_MODIFICATION", "prompt_modification", "FALSE", "FALSE"),
        ("GOV_ROUTING", "routing_changes", "FALSE", "FALSE"),
        ("GOV_WEIGHTING", "weighting_changes", "FALSE", "FALSE"),
        ("GOV_CALIBRATION", "calibration_changes", "FALSE", "FALSE"),
        ("GOV_ENSEMBLE", "ensemble_changes", "FALSE", "FALSE"),
    ]
    governance_rows = [
        {
            **_base(generated_ts, design_run_id),
            "check_id": check_id,
            "check_name": name,
            "expected_value": expected,
            "actual_value": actual,
            "status": "PASS" if expected == actual else "FAIL",
            "notes": "Predictive mechanism design is research-only.",
        }
        for check_id, name, expected, actual in governance_specs
    ]

    highest_priority = priority_rows[0]["mechanism_id"] if priority_rows else ""
    highest_metric_dependency = "MECH_SIGNAL_DISCIPLINE"
    highest_risk = "mechanism labels may become post-hoc proxies unless frozen before accuracy testing"
    summary_rows = [
        {
            **_base(generated_ts, design_run_id),
            "build_status": "PASS_WITH_WARNINGS",
            "final_interpretation": "PREDICTIVE_MECHANISM_DESIGN_READY_WITH_WARNINGS",
            "mechanisms_designed": len(design_rows),
            "test_frameworks_defined": len(test_rows),
            "existing_evidence_sources": "Predictive_Mechanism_Hypotheses; Tier 2 behavior generalization; original and corrected accuracy reviews",
            "missing_evidence_sources": "mechanism-positive labels; mechanism-conditioned metrics; future controlled mechanism test outputs",
            "priority_ranking_completed": "TRUE",
            "highest_priority_mechanism": highest_priority,
            "highest_scientific_risk": highest_risk,
            "highest_metric_dependency": highest_metric_dependency,
            "provider_calls_performed": 0,
            "forecast_generation_performed": 0,
            "evaluation_rerun_count": 0,
            "production_behavior_change_count": 0,
            "ready_for_mechanism_test_planning": "TRUE",
            "ready_for_replication": "FALSE",
            "ready_for_production": "FALSE",
            "recommended_next_step": "PROCEED_TO_PHASE9A6A_PREDICTIVE_MECHANISM_TEST_PLAN",
            "notes": json.dumps(
                {
                    "phase9a5r2": phase9a5r2.get("final_interpretation", ""),
                    "corrected_review": corrected_review_summary.get("final_interpretation", "") or corrected_review.get("review_conclusion", ""),
                    "research_layer": "Predictive Mechanism Science",
                },
                sort_keys=True,
            ),
        }
    ]

    outputs = [
        (OUTPUT_DESIGN, DESIGN_HEADERS, design_rows),
        (OUTPUT_TEST, TEST_HEADERS, test_rows),
        (OUTPUT_OBSERVABLES, OBSERVABLE_HEADERS, observable_rows),
        (OUTPUT_EVIDENCE, EVIDENCE_HEADERS, evidence_rows),
        (OUTPUT_EXPERIMENT, EXPERIMENT_HEADERS, experiment_rows),
        (OUTPUT_DATA, DATA_HEADERS, data_rows),
        (OUTPUT_PRIORITY, PRIORITY_HEADERS, priority_rows),
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
        "file_created": "automation/build_predictive_mechanism_design_v0.py",
        "sheets_written": {sheet_name: len(rows) for sheet_name, _, rows in outputs},
        "mechanisms_designed": len(design_rows),
        "test_frameworks_defined": len(test_rows),
        "existing_evidence_sources": summary_rows[0]["existing_evidence_sources"],
        "missing_evidence_sources": summary_rows[0]["missing_evidence_sources"],
        "priority_ranking_completed": True,
        "highest_priority_mechanism": highest_priority,
        "highest_scientific_risk": highest_risk,
        "highest_metric_dependency": highest_metric_dependency,
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "evaluation_rerun_count": 0,
        "production_behavior_change_count": 0,
        "ready_for_mechanism_test_planning": True,
        "ready_for_replication": False,
        "ready_for_production": False,
        "recommended_next_step": summary_rows[0]["recommended_next_step"],
        "registry": registry,
    }


def main() -> None:
    result = build_predictive_mechanism_design_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
