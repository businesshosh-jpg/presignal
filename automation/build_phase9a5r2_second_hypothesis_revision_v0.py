import json
import sys
from collections import Counter
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


SCHEMA_VERSION = "presignal_v2_phase9a5r2_second_hypothesis_revision_0.1"
REVISION_VERSION = "phase9a5r2_second_hypothesis_revision_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-5R2"
REGISTRY_CATEGORY = "PRESIGNAL_V2_PREDICTIVE_MECHANISM_HYPOTHESIS_REVISION"
REGISTRY_OWNER_MODULE = "market_state"

INPUT_SHEETS = [
    "Pack_Behavior_Tier2_Generalization_Review",
    "Pack_Behavior_Tier2_Hypothesis_Generalization",
    "Pack_Behavior_Tier2_Generalization_Summary",
    "Controlled_Accuracy_Evaluation",
    "Controlled_Accuracy_Evaluation_Review",
    "Controlled_Accuracy_Evaluation_Review_Summary",
    "Corrected_Accuracy_Evaluation",
    "Corrected_Accuracy_Review",
    "Corrected_Accuracy_Review_Summary",
    "Behavior_Accuracy_Hypothesis_Revision",
    "Behavior_Accuracy_Mechanism_Gap_Audit",
    "Behavior_Accuracy_Revised_Hypotheses",
    "Behavior_Accuracy_Revision_Summary",
]
READ_INPUT_SHEETS = [
    "Pack_Behavior_Tier2_Generalization_Summary",
    "Controlled_Accuracy_Evaluation_Review_Summary",
    "Corrected_Accuracy_Review_Summary",
    "Behavior_Accuracy_Revision_Summary",
]

OUTPUT_FRAMEWORK = "Predictive_Mechanism_Framework"
OUTPUT_HYPOTHESES = "Predictive_Mechanism_Hypotheses"
OUTPUT_BEHAVIOR_MAPPING = "Behavior_to_Mechanism_Mapping"
OUTPUT_ACCURACY_MAPPING = "Mechanism_to_Accuracy_Mapping"
OUTPUT_TESTABILITY = "Mechanism_Testability_Audit"
OUTPUT_LEGACY = "Legacy_Hypothesis_Disposition"
OUTPUT_GOVERNANCE = "Phase9A5R2_Governance"
OUTPUT_SUMMARY = "Phase9A5R2_Summary"

FRAMEWORK_HEADERS = [
    "generated_ts",
    "schema_version",
    "revision_version",
    "revision_run_id",
    "framework_layer",
    "layer_order",
    "layer_definition",
    "key_research_question",
    "evidence_from_prior_phases",
    "design_implication",
    "production_excluded",
    "notes",
]

HYPOTHESIS_HEADERS = [
    "generated_ts",
    "schema_version",
    "revision_version",
    "revision_run_id",
    "mechanism_id",
    "mechanism_description",
    "mechanism_hypothesis",
    "why_previous_hypothesis_failed",
    "measurable_evidence",
    "future_experiment",
    "required_metrics",
    "required_sample_size",
    "confounders",
    "expected_falsification_criteria",
    "related_legacy_hypotheses",
    "testability_status",
    "priority",
    "production_excluded",
    "notes",
]

BEHAVIOR_MAPPING_HEADERS = [
    "generated_ts",
    "schema_version",
    "revision_version",
    "revision_run_id",
    "behavior_hypothesis_id",
    "behavior_evidence_status",
    "mapped_mechanism_id",
    "behavior_to_mechanism_assumption",
    "observable_mechanism_indicator",
    "mapping_status",
    "risk_if_assumption_false",
    "future_test",
    "notes",
]

ACCURACY_MAPPING_HEADERS = [
    "generated_ts",
    "schema_version",
    "revision_version",
    "revision_run_id",
    "mechanism_id",
    "accuracy_pathway",
    "target_accuracy_metric",
    "expected_accuracy_effect",
    "required_comparison",
    "minimum_sample_design",
    "falsification_rule",
    "interpretation_limit",
    "replication_readiness",
    "notes",
]

TESTABILITY_HEADERS = [
    "generated_ts",
    "schema_version",
    "revision_version",
    "revision_run_id",
    "mechanism_id",
    "observable",
    "measurable_without_provider_calls",
    "requires_metric_repair",
    "requires_new_forecasts",
    "requires_outcome_repair",
    "required_data",
    "testability_classification",
    "blocking_issue",
    "recommended_next_design",
    "notes",
]

LEGACY_HEADERS = [
    "generated_ts",
    "schema_version",
    "revision_version",
    "revision_run_id",
    "legacy_accuracy_hypothesis_id",
    "source_behavior_hypothesis_id",
    "original_result",
    "corrected_result",
    "disposition",
    "disposition_reason",
    "replacement_mechanism_ids",
    "archive_direct_accuracy_claim",
    "future_use",
    "production_excluded",
    "notes",
]

GOVERNANCE_HEADERS = [
    "generated_ts",
    "schema_version",
    "revision_version",
    "revision_run_id",
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
    "revision_version",
    "revision_run_id",
    "build_status",
    "final_interpretation",
    "legacy_hypotheses_reviewed",
    "legacy_hypotheses_retained",
    "legacy_hypotheses_transformed",
    "legacy_hypotheses_archived",
    "predictive_mechanisms_defined",
    "strongest_mechanism_candidate",
    "primary_scientific_discovery",
    "replication_ready",
    "metric_repair_still_required",
    "second_revision_complete",
    "provider_calls_performed",
    "forecast_generation_performed",
    "evaluation_rerun_count",
    "production_behavior_change_count",
    "ready_for_predictive_mechanism_design",
    "ready_for_replication",
    "ready_for_production",
    "recommended_next_step",
    "notes",
]


def _run_id(generated_ts: str) -> str:
    return "phase9a5r2_second_hypothesis_revision_v0_" + generated_ts.replace("-", "").replace(":", "")


def _base(generated_ts: str, revision_run_id: str) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "revision_version": REVISION_VERSION,
        "revision_run_id": revision_run_id,
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
    out: Dict[str, List[Dict[str, Any]]] = {}
    for sheet in READ_INPUT_SHEETS:
        out[sheet] = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet)
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
        ("PREDICTIVE_MECHANISM_FRAMEWORK", OUTPUT_FRAMEWORK, "predictive_mechanism_framework"),
        ("PREDICTIVE_MECHANISM_HYPOTHESES", OUTPUT_HYPOTHESES, "predictive_mechanism_hypotheses"),
        ("BEHAVIOR_TO_MECHANISM_MAPPING", OUTPUT_BEHAVIOR_MAPPING, "behavior_to_mechanism_mapping"),
        ("MECHANISM_TO_ACCURACY_MAPPING", OUTPUT_ACCURACY_MAPPING, "mechanism_to_accuracy_mapping"),
        ("MECHANISM_TESTABILITY_AUDIT", OUTPUT_TESTABILITY, "mechanism_testability_audit"),
        ("LEGACY_HYPOTHESIS_DISPOSITION", OUTPUT_LEGACY, "legacy_hypothesis_disposition"),
        ("PHASE9A5R2_GOVERNANCE", OUTPUT_GOVERNANCE, "phase9a5r2_governance"),
        ("PHASE9A5R2_SUMMARY", OUTPUT_SUMMARY, "phase9a5r2_summary"),
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
            "notes": "Phase 9A-5R2 predictive mechanism science transition; diagnostic-only, non-production.",
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


def _mechanism_specs() -> List[Dict[str, str]]:
    return [
        {
            "mechanism_id": "MECH_INFORMATION_FILTERING",
            "mechanism_description": "Additional market-state information improves forecasts only when it suppresses irrelevant or stale signals.",
            "mechanism_hypothesis": "Prediction improves only when additional information filters irrelevant signals rather than merely increasing reasoning complexity.",
            "why_previous_hypothesis_failed": "USDJPY and pack exposure changed reasoning, but behavior movement alone did not prove that irrelevant signals were filtered out.",
            "measurable_evidence": "Lower irrelevant-field citation rate; fewer unsupported causal links; reduced contradiction between information_used and final direction.",
            "future_experiment": "Compare full-context pack outputs against filtered-context outputs and measure whether irrelevant field references decrease before accuracy is tested.",
            "required_metrics": "irrelevant_signal_reference_rate; information_filtering_score; false_signal_rate; direction_match_rate",
            "required_sample_size": "At least 150 strict-ready rows across repeated event families before accuracy replication.",
            "confounders": "Field salience bias; provider verbosity; market regime clustering; outcome-label sensitivity.",
            "expected_falsification_criteria": "If filtering score improves but false_signal_rate and direction_match_rate do not improve in strict rows, the mechanism is falsified.",
            "related_legacy_hypotheses": "ACC_HYP_USDJPY_TREND_DIRECTIONAL_ALIGNMENT",
            "testability_status": "READY_FOR_DESIGN",
            "priority": "HIGH",
        },
        {
            "mechanism_id": "MECH_SIGNAL_DISCIPLINE",
            "mechanism_description": "Accuracy improves when forecasts become more selective and avoid unsupported directional calls.",
            "mechanism_hypothesis": "Accuracy improves by reducing false positive forecasts rather than increasing directional confidence.",
            "why_previous_hypothesis_failed": "Pack B showed behavior movement and some overall_ok improvement, but corrected direction weakened and direct accuracy support failed.",
            "measurable_evidence": "Reduced false_signal_rate; improved no_signal correctness; fewer high-confidence low-evidence directional forecasts.",
            "future_experiment": "Design a low-signal session slice and test whether Pack B changes no-signal discipline before comparing direction accuracy.",
            "required_metrics": "false_signal_rate; no_signal_correctness; unsupported_direction_rate; confidence_evidence_alignment",
            "required_sample_size": "At least 120 low-signal strict-ready rows plus matched baseline rows.",
            "confounders": "No-signal proxy definition; flat threshold sensitivity; provider confidence scale drift.",
            "expected_falsification_criteria": "If Pack B increases decisiveness without reducing false positives or improving no-signal correctness, the mechanism is falsified.",
            "related_legacy_hypotheses": "ACC_HYP_PACK_B_TARGET_STATE_SIGNAL_DISCIPLINE",
            "testability_status": "READY_AFTER_METRIC_REPAIR",
            "priority": "HIGH",
        },
        {
            "mechanism_id": "MECH_CAUSAL_ROBUSTNESS",
            "mechanism_description": "Causal chains help prediction only when they remain valid across market contexts and not merely coherent in one prompt.",
            "mechanism_hypothesis": "Stable causal reasoning only improves prediction when the causal chain remains valid under multiple market contexts.",
            "why_previous_hypothesis_failed": "OpenAI causal stability created a clean testbed but did not produce supported accuracy after corrected outcomes.",
            "measurable_evidence": "Causal-chain invariance across pack levels; causal premise survival under counter-context checks; low contradiction rate.",
            "future_experiment": "Use paired context perturbation tests to check whether causal premises remain stable and outcome-relevant before accuracy testing.",
            "required_metrics": "causal_robustness_score; causal_contradiction_rate; scenario_alignment; direction_match_rate",
            "required_sample_size": "At least 100 paired strict-ready rows per provider/control condition.",
            "confounders": "Provider style consistency mistaken for causal validity; prompt-induced consistency; event-family imbalance.",
            "expected_falsification_criteria": "If causal robustness does not predict better strict accuracy or lower contradiction, the mechanism is falsified.",
            "related_legacy_hypotheses": "ACC_HYP_OPENAI_STABLE_CAUSAL_REWRITE_TESTBED",
            "testability_status": "READY_FOR_DESIGN",
            "priority": "MEDIUM",
        },
        {
            "mechanism_id": "MECH_CONDITIONAL_PREDICTIVENESS",
            "mechanism_description": "A feature can be predictive only in certain regimes, event families, or volatility states.",
            "mechanism_hypothesis": "Certain features are only predictive under specific market regimes.",
            "why_previous_hypothesis_failed": "USDJPY trend was tested too broadly as a universal directional alignment signal.",
            "measurable_evidence": "Feature effect differs by regime slice; predictive value appears only when pre-specified regime conditions hold.",
            "future_experiment": "Pre-register regime slices for USDJPY trend and compare strict rows inside vs outside those slices.",
            "required_metrics": "regime_conditioned_direction_rate; regime_conditioned_false_signal_rate; feature_incremental_value",
            "required_sample_size": "At least 80 strict-ready rows per pre-registered regime slice.",
            "confounders": "Multiple-comparison risk; regime definition leakage; event cluster dependence.",
            "expected_falsification_criteria": "If pre-registered regimes do not improve feature-conditioned accuracy over baseline, the mechanism is falsified.",
            "related_legacy_hypotheses": "ACC_HYP_USDJPY_TREND_DIRECTIONAL_ALIGNMENT",
            "testability_status": "READY_AFTER_SCOPE_DEFINITION",
            "priority": "HIGH",
        },
        {
            "mechanism_id": "MECH_INFORMATION_VALUE",
            "mechanism_description": "Behaviorally influential fields matter only when they add incremental predictive value over baseline forecasts.",
            "mechanism_hypothesis": "Feature usefulness depends on incremental predictive value, not behavioral influence.",
            "why_previous_hypothesis_failed": "Behavior audits confirmed field influence, but corrected accuracy showed influence did not imply predictive lift.",
            "measurable_evidence": "Ablation lift; incremental value over Pack A; lower error conditional on field use after controlling for regime.",
            "future_experiment": "Run feature-ablation and feature-addition designs with fixed forecasts to estimate incremental predictive value before replication.",
            "required_metrics": "ablation_delta; feature_incremental_value; pack_vs_baseline_delta; behavior_conditioned_accuracy_delta",
            "required_sample_size": "At least 200 strict-ready rows with balanced feature presence/absence.",
            "confounders": "Feature collinearity; pack-level confounding; provider verbosity; sample imbalance.",
            "expected_falsification_criteria": "If behavior-moving fields add no incremental value after ablation controls, the mechanism is falsified.",
            "related_legacy_hypotheses": "ACC_HYP_USDJPY_TREND_DIRECTIONAL_ALIGNMENT; ACC_HYP_PACK_B_TARGET_STATE_SIGNAL_DISCIPLINE",
            "testability_status": "READY_AFTER_METRIC_REPAIR",
            "priority": "HIGH",
        },
        {
            "mechanism_id": "MECH_FORECAST_STABILITY",
            "mechanism_description": "Useful prediction may require a stable forecast core plus selective updates, not maximum sensitivity to every pack.",
            "mechanism_hypothesis": "Prediction quality depends on stable reasoning combined with selective behavioral change rather than maximal behavioral sensitivity.",
            "why_previous_hypothesis_failed": "Provider stability was treated as a clean testbed but not as a measured selective-update mechanism.",
            "measurable_evidence": "Stable forecast direction under irrelevant context; change only when high-value mechanism trigger is present.",
            "future_experiment": "Measure whether selective forecast changes outperform high-sensitivity or no-change behavior across paired pack exposures.",
            "required_metrics": "selective_change_precision; forecast_flip_quality; stability_under_irrelevant_context; direction_match_rate",
            "required_sample_size": "At least 150 paired strict-ready rows across providers and pack transitions.",
            "confounders": "Provider invalid outputs; prompt drift; source coverage; confidence scale differences.",
            "expected_falsification_criteria": "If selective changes are not more accurate than random or maximal sensitivity changes, the mechanism is falsified.",
            "related_legacy_hypotheses": "ACC_HYP_OPENAI_STABLE_CAUSAL_REWRITE_TESTBED",
            "testability_status": "READY_FOR_DESIGN",
            "priority": "MEDIUM",
        },
    ]


def build_phase9a5r2_second_hypothesis_revision_v0() -> Dict[str, Any]:
    service = build_sheets_service(load_credentials())
    generated_ts = _iso_now()
    revision_run_id = _run_id(generated_ts)
    inputs = _read_inputs(service)
    behavior_summary = _latest(inputs["Pack_Behavior_Tier2_Generalization_Summary"])
    original_review = _latest(inputs["Controlled_Accuracy_Evaluation_Review_Summary"])
    corrected_review = _latest(inputs["Corrected_Accuracy_Review_Summary"])
    first_revision = _latest(inputs["Behavior_Accuracy_Revision_Summary"])

    mechanisms = _mechanism_specs()
    framework_layers = [
        ("Market State", 1, "Observable pre-release and market-context conditions available before the forecast.", "Which conditions could make a behavior change predictive?"),
        ("Behavior Change", 2, "Provider reasoning, causal chain, no-signal, confidence, or direction movement caused by information exposure.", "What changed in model behavior, and was it selective or noisy?"),
        ("Predictive Mechanism", 3, "A measurable causal bridge explaining why the behavior should improve a specific metric.", "What mechanism converts behavior movement into predictive value?"),
        ("Accuracy", 4, "Strict corrected diagnostic accuracy metrics evaluated only after mechanism evidence is defined.", "Did the mechanism-conditioned behavior improve validated outcomes?"),
    ]
    framework_rows = [
        {
            **_base(generated_ts, revision_run_id),
            "framework_layer": layer,
            "layer_order": order,
            "layer_definition": definition,
            "key_research_question": question,
            "evidence_from_prior_phases": (
                f"behavior={behavior_summary.get('final_interpretation', '')}; "
                f"original_accuracy={original_review.get('final_interpretation', '')}; "
                f"corrected_accuracy={corrected_review.get('final_interpretation', '')}"
            ),
            "design_implication": "Do not move from behavior to accuracy without an explicit predictive mechanism.",
            "production_excluded": "TRUE",
            "notes": "Framework is diagnostic-only and does not change prompts, routing, weights, calibration, scoring, or production behavior.",
        }
        for layer, order, definition, question in framework_layers
    ]

    hypothesis_rows = [
        {
            **_base(generated_ts, revision_run_id),
            **spec,
            "production_excluded": "TRUE",
            "notes": "Predictive mechanism candidate; not an accuracy claim and not production-ready.",
        }
        for spec in mechanisms
    ]

    behavior_mapping_specs = [
        ("HYP_USDJPY_TREND_REASONING", "BEHAVIOR_CONFIRMED", "MECH_CONDITIONAL_PREDICTIVENESS", "USDJPY trend changes reasoning only matter if trend is predictive in a pre-specified regime.", "regime_conditioned_feature_value", "REQUIRES_MECHANISM_TEST"),
        ("HYP_USDJPY_TREND_REASONING", "BEHAVIOR_CONFIRMED", "MECH_INFORMATION_VALUE", "Behaviorally active USDJPY fields must add incremental value over baseline.", "feature_incremental_value", "REQUIRES_ABLATION"),
        ("HYP_A_TO_B_TARGET_STATE_VALUE", "BEHAVIOR_CONFIRMED", "MECH_SIGNAL_DISCIPLINE", "Pack B should reduce unsupported directional calls before it can improve accuracy.", "false_signal_reduction", "REQUIRES_METRIC_REPAIR"),
        ("HYP_A_TO_B_TARGET_STATE_VALUE", "BEHAVIOR_CONFIRMED", "MECH_INFORMATION_FILTERING", "Pack B behavior value should come from filtering low-value signals, not just more complex reasoning.", "irrelevant_signal_reference_rate", "REQUIRES_MECHANISM_TEST"),
        ("HYP_OPENAI_CAUSAL_STABLE", "BEHAVIOR_CONFIRMED", "MECH_CAUSAL_ROBUSTNESS", "Stable causal rewriting must remain valid across contexts to become predictive.", "causal_robustness_score", "REQUIRES_CONTEXT_TEST"),
        ("HYP_OPENAI_CAUSAL_STABLE", "BEHAVIOR_CONFIRMED", "MECH_FORECAST_STABILITY", "OpenAI may be a control for selective update quality, not a direct accuracy-improving provider.", "selective_change_precision", "REQUIRES_DESIGN"),
    ]
    behavior_mapping_rows = [
        {
            **_base(generated_ts, revision_run_id),
            "behavior_hypothesis_id": behavior_id,
            "behavior_evidence_status": status,
            "mapped_mechanism_id": mechanism_id,
            "behavior_to_mechanism_assumption": assumption,
            "observable_mechanism_indicator": indicator,
            "mapping_status": mapping_status,
            "risk_if_assumption_false": "Behavior remains explanatory but non-predictive.",
            "future_test": "Design a mechanism-first experiment before another accuracy replication.",
            "notes": "Mapping preserves behavior evidence but blocks direct production interpretation.",
        }
        for behavior_id, status, mechanism_id, assumption, indicator, mapping_status in behavior_mapping_specs
    ]

    accuracy_mapping_rows = [
        {
            **_base(generated_ts, revision_run_id),
            "mechanism_id": spec["mechanism_id"],
            "accuracy_pathway": "Market State -> Behavior Change -> Predictive Mechanism -> Accuracy",
            "target_accuracy_metric": spec["required_metrics"],
            "expected_accuracy_effect": "Metric improvement should occur only after mechanism evidence is observed.",
            "required_comparison": "Pre-registered mechanism-positive rows vs matched mechanism-negative/baseline rows.",
            "minimum_sample_design": spec["required_sample_size"],
            "falsification_rule": spec["expected_falsification_criteria"],
            "interpretation_limit": "Mechanism support is not production validation and does not rank providers or packs.",
            "replication_readiness": "NOT_READY_BEFORE_MECHANISM_DESIGN",
            "notes": "Accuracy evaluation is deferred until mechanism tests are specified.",
        }
        for spec in mechanisms
    ]

    testability_rows = [
        {
            **_base(generated_ts, revision_run_id),
            "mechanism_id": spec["mechanism_id"],
            "observable": "TRUE",
            "measurable_without_provider_calls": "PARTIAL",
            "requires_metric_repair": "TRUE" if spec["mechanism_id"] in {"MECH_SIGNAL_DISCIPLINE", "MECH_INFORMATION_VALUE"} else "FALSE",
            "requires_new_forecasts": "TRUE",
            "requires_outcome_repair": "FALSE",
            "required_data": spec["measurable_evidence"],
            "testability_classification": spec["testability_status"],
            "blocking_issue": "metric_framework_or_mechanism_design_not_yet_frozen",
            "recommended_next_design": "Phase 9A-6 predictive mechanism design",
            "notes": "New provider calls are not made in this phase; future experiments require separate governance approval.",
        }
        for spec in mechanisms
    ]

    legacy_specs = [
        (
            "ACC_HYP_USDJPY_TREND_DIRECTIONAL_ALIGNMENT",
            "HYP_USDJPY_TREND_REASONING",
            "Not supported after original/corrected evaluation.",
            "Not Supported",
            "Transform",
            "Direct directional-alignment claim failed; convert into conditional predictiveness and information-value mechanisms.",
            "MECH_CONDITIONAL_PREDICTIVENESS; MECH_INFORMATION_VALUE",
        ),
        (
            "ACC_HYP_PACK_B_TARGET_STATE_SIGNAL_DISCIPLINE",
            "HYP_A_TO_B_TARGET_STATE_VALUE",
            "Not supported after original/corrected evaluation.",
            "Not Supported",
            "Transform",
            "Direct Pack B accuracy claim failed; convert into signal discipline and information-filtering mechanisms.",
            "MECH_SIGNAL_DISCIPLINE; MECH_INFORMATION_FILTERING",
        ),
        (
            "ACC_HYP_OPENAI_STABLE_CAUSAL_REWRITE_TESTBED",
            "HYP_OPENAI_CAUSAL_STABLE",
            "Not supported after original/corrected evaluation.",
            "Not Supported",
            "Transform",
            "Direct OpenAI accuracy/testbed claim failed; convert into causal robustness and forecast-stability mechanisms.",
            "MECH_CAUSAL_ROBUSTNESS; MECH_FORECAST_STABILITY",
        ),
    ]
    legacy_rows = [
        {
            **_base(generated_ts, revision_run_id),
            "legacy_accuracy_hypothesis_id": legacy_id,
            "source_behavior_hypothesis_id": behavior_id,
            "original_result": original_result,
            "corrected_result": corrected_result,
            "disposition": disposition,
            "disposition_reason": reason,
            "replacement_mechanism_ids": replacements,
            "archive_direct_accuracy_claim": "TRUE",
            "future_use": "Traceability parent only; do not use as direct replication target.",
            "production_excluded": "TRUE",
            "notes": "Legacy hypothesis is not deleted; it is dispositioned into mechanism science.",
        }
        for legacy_id, behavior_id, original_result, corrected_result, disposition, reason, replacements in legacy_specs
    ]

    governance_specs = [
        ("GOV_PROVIDER_CALLS", "provider_calls_performed", "0", "0"),
        ("GOV_FORECAST_GENERATION", "forecast_generation_performed", "0", "0"),
        ("GOV_EVALUATION_RERUN", "evaluation_rerun_count", "0", "0"),
        ("GOV_PREVIOUS_RESULTS_MODIFIED", "previous_results_modified", "0", "0"),
        ("GOV_PRODUCTION_BEHAVIOR", "production_behavior_change_count", "0", "0"),
        ("GOV_PRODUCTION_SHEETS", "production_sheet_write_count", "0", "0"),
        ("GOV_ROUTING", "routing_changes", "FALSE", "FALSE"),
        ("GOV_WEIGHTING", "weighting_changes", "FALSE", "FALSE"),
        ("GOV_CALIBRATION", "calibration_changes", "FALSE", "FALSE"),
        ("GOV_PROMPTS", "prompt_changes", "FALSE", "FALSE"),
        ("GOV_ENSEMBLE", "ensemble_changes", "FALSE", "FALSE"),
    ]
    governance_rows = [
        {
            **_base(generated_ts, revision_run_id),
            "check_id": check_id,
            "check_name": name,
            "expected_value": expected,
            "actual_value": actual,
            "status": "PASS" if expected == actual else "FAIL",
            "notes": "Second hypothesis revision is research-design only.",
        }
        for check_id, name, expected, actual in governance_specs
    ]

    disposition_counts = Counter(row["disposition"] for row in legacy_rows)
    strongest_mechanism = "MECH_INFORMATION_VALUE"
    primary_discovery = "Behavior change is not sufficient; PreSignal must test incremental predictive mechanisms before accuracy replication."
    summary_rows = [
        {
            **_base(generated_ts, revision_run_id),
            "build_status": "PASS_WITH_WARNINGS",
            "final_interpretation": "PHASE9A5R2_SECOND_HYPOTHESIS_REVISION_READY_WITH_WARNINGS",
            "legacy_hypotheses_reviewed": len(legacy_rows),
            "legacy_hypotheses_retained": disposition_counts["Retain"],
            "legacy_hypotheses_transformed": disposition_counts["Transform"],
            "legacy_hypotheses_archived": disposition_counts["Archive"],
            "predictive_mechanisms_defined": len(hypothesis_rows),
            "strongest_mechanism_candidate": strongest_mechanism,
            "primary_scientific_discovery": primary_discovery,
            "replication_ready": "FALSE",
            "metric_repair_still_required": "TRUE",
            "second_revision_complete": "TRUE",
            "provider_calls_performed": 0,
            "forecast_generation_performed": 0,
            "evaluation_rerun_count": 0,
            "production_behavior_change_count": 0,
            "ready_for_predictive_mechanism_design": "TRUE",
            "ready_for_replication": "FALSE",
            "ready_for_production": "FALSE",
            "recommended_next_step": "PROCEED_TO_PHASE9A6_PREDICTIVE_MECHANISM_DESIGN",
            "notes": json.dumps(
                {
                    "corrected_review": corrected_review.get("final_interpretation", ""),
                    "first_revision": first_revision.get("final_interpretation", ""),
                    "framework": "Market State -> Behavior Change -> Predictive Mechanism -> Accuracy",
                },
                sort_keys=True,
            ),
        }
    ]

    outputs = [
        (OUTPUT_FRAMEWORK, FRAMEWORK_HEADERS, framework_rows),
        (OUTPUT_HYPOTHESES, HYPOTHESIS_HEADERS, hypothesis_rows),
        (OUTPUT_BEHAVIOR_MAPPING, BEHAVIOR_MAPPING_HEADERS, behavior_mapping_rows),
        (OUTPUT_ACCURACY_MAPPING, ACCURACY_MAPPING_HEADERS, accuracy_mapping_rows),
        (OUTPUT_TESTABILITY, TESTABILITY_HEADERS, testability_rows),
        (OUTPUT_LEGACY, LEGACY_HEADERS, legacy_rows),
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
        "file_created": "automation/build_phase9a5r2_second_hypothesis_revision_v0.py",
        "sheets_written": {sheet_name: len(rows) for sheet_name, _, rows in outputs},
        "legacy_hypotheses_reviewed": len(legacy_rows),
        "legacy_hypotheses_retained": disposition_counts["Retain"],
        "legacy_hypotheses_transformed": disposition_counts["Transform"],
        "legacy_hypotheses_archived": disposition_counts["Archive"],
        "predictive_mechanisms_defined": len(hypothesis_rows),
        "strongest_mechanism_candidate": strongest_mechanism,
        "primary_scientific_discovery": primary_discovery,
        "replication_ready": False,
        "metric_repair_still_required": True,
        "second_revision_complete": True,
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "evaluation_rerun_count": 0,
        "production_behavior_change_count": 0,
        "ready_for_predictive_mechanism_design": True,
        "ready_for_replication": False,
        "ready_for_production": False,
        "recommended_next_step": summary_rows[0]["recommended_next_step"],
        "registry": registry,
    }


def main() -> None:
    result = build_phase9a5r2_second_hypothesis_revision_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
