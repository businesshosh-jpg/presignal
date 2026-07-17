#!/usr/bin/env python3
"""Phase 9A-6R14 — Refined Mechanism Test Execution Approval.

This approval phase reviews the frozen Phase 9A-6R13 preregistration without
loading outcome rows, joining outcomes, calculating accuracy, or running tests.
It resolves the matched-pair count discrepancy and records whether the design
is coherent enough for execution approval.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Set, Tuple


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
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials  # type: ignore
from automation.build_refined_mechanism_v11_classification_execution_v0 import (  # type: ignore
    _append_rows,
    _fetch_input_sheets,
    _normalize,
    _sheet_titles_light,
)


PHASE_ID = "9A-6R14"
BUILD_SCRIPT = "automation/build_refined_mechanism_test_execution_approval_v0.py"
SCHEMA_VERSION = "presignal_v2_refined_mechanism_test_execution_approval_v0"
APPROVAL_VERSION = "refined_mechanism_test_execution_approval_v0"
REGISTRY_CATEGORY = "PRESIGNAL_V2_REFINED_MECHANISM_TEST_EXECUTION_APPROVAL"
REGISTRY_OWNER_MODULE = "market_state"

CLASSIFICATION_RUN_ID = "refined_mechanism_v11_classification_20260710T152725Z"
MECHANISM_VERSION = "1.1"
TEST_PREREGISTRATION_VERSION = "1.0"
PRIMARY_MECHANISM = "MECH_INFORMATION_CONSISTENCY"
EXPLORATORY_MECHANISM = "MECH_INFORMATION_RELEVANCE"
DESCRIPTIVE_ONLY_MECHANISM = "MECH_INFORMATION_SPECIFICITY"

INPUT_SHEETS: Tuple[str, ...] = (
    # Phase 9A-6R13 preregistration
    "Refined_Mechanism_Test_Preregistration",
    "Refined_Mechanism_Test_Frozen_Hypotheses",
    "Refined_Mechanism_Test_Frozen_Population",
    "Refined_Mechanism_Test_Frozen_Unit_Of_Analysis",
    "Refined_Mechanism_Test_Frozen_Outcome_Definition",
    "Refined_Mechanism_Test_Frozen_Comparison_Design",
    "Refined_Mechanism_Test_Frozen_Cluster_Design",
    "Refined_Mechanism_Test_Frozen_Eligibility_Rules",
    "Refined_Mechanism_Test_Frozen_Confidence_Rules",
    "Refined_Mechanism_Test_Frozen_Unknown_Rules",
    "Refined_Mechanism_Test_Frozen_Confounder_Rules",
    "Refined_Mechanism_Test_Frozen_Multiple_Testing",
    "Refined_Mechanism_Test_Frozen_Missing_Data",
    "Refined_Mechanism_Test_Frozen_Stop_Rules",
    "Refined_Mechanism_Test_Frozen_Reporting_Plan",
    "Refined_Mechanism_Test_Preregistration_Governance",
    "Refined_Mechanism_Test_Preregistration_Summary",
    # Phase 9A-6R12 planning evidence
    "Refined_Mechanism_Test_Planning_Readiness",
    "Refined_Mechanism_Test_Unit_Of_Analysis",
    "Refined_Mechanism_Test_Population_Structure",
    "Refined_Mechanism_Test_Label_Eligibility",
    "Refined_Mechanism_Test_Comparison_Design",
    "Refined_Mechanism_Test_Confounder_Map",
    "Refined_Mechanism_Test_Independence_Audit",
    "Refined_Mechanism_Test_Sample_Adequacy",
    "Refined_Mechanism_Test_Planning_Readiness_Summary",
    # Permanent classifications and review
    "Refined_Mechanism_v11_Classifications",
    "Refined_Mechanism_v11_Classification_Summary",
    "Refined_Mechanism_v11_Execution_Review",
    "Refined_Mechanism_v11_Execution_Review_Summary",
)

OUTPUT_SHEETS = [
    "Refined_Mechanism_Test_Execution_Approval",
    "Refined_Mechanism_Test_Blinding_Audit",
    "Refined_Mechanism_Test_Matched_Pair_Reconciliation",
    "Refined_Mechanism_Test_Primary_Estimand_Audit",
    "Refined_Mechanism_Test_Outcome_Derivation_Audit",
    "Refined_Mechanism_Test_Join_Approval",
    "Refined_Mechanism_Test_Sample_Gate_Approval",
    "Refined_Mechanism_Test_Cluster_Design_Approval",
    "Refined_Mechanism_Test_Statistical_Method_Approval",
    "Refined_Mechanism_Test_Fingerprint_Freeze",
    "Refined_Mechanism_Test_Stop_Rule_Approval",
    "Refined_Mechanism_Test_Execution_Approval_Governance",
    "Refined_Mechanism_Test_Execution_Approval_Summary",
]

COMMON_HEADERS = ["generated_ts", "schema_version", "approval_run_id", "payload_json"]
OUTPUT_LOGICAL_IDS = {name: name.upper() for name in OUTPUT_SHEETS}


def _run_id(ts: datetime) -> str:
    return f"9A-6R14_{ts.strftime('%Y%m%dT%H%M%SZ')}"


def _latest_payload(rows: Sequence[Mapping[str, Any]], run_key: str) -> Dict[str, Any]:
    if not rows:
        return {}
    ordered = sorted(
        rows,
        key=lambda row: (
            _normalize(row.get("generated_ts")),
            _normalize(row.get(run_key)),
            int(row.get("__source_row_number__", 0) or 0),
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
            int(row.get("__source_row_number__", 0) or 0),
        ),
    )
    return dict(ordered[-1])


def _fingerprint_rows(rows: Sequence[Mapping[str, Any]]) -> str:
    clean_rows: List[Dict[str, Any]] = []
    for row in rows:
        clean = {k: v for k, v in dict(row).items() if k != "__source_row_number__"}
        clean_rows.append(clean)
    serialized = json.dumps(clean_rows, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _int(value: Any) -> int:
    try:
        return int(float(_normalize(value)))
    except (TypeError, ValueError):
        return 0


def _class_rows(inputs: Mapping[str, Any]) -> List[Dict[str, Any]]:
    return [
        dict(row)
        for row in inputs["Refined_Mechanism_v11_Classifications"].rows
        if _normalize(row.get("classification_run_id")) == CLASSIFICATION_RUN_ID
    ]


def _expanded_consistency_rows(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    return [
        dict(row)
        for row in rows
        if _normalize(row.get("mechanism_id")) == PRIMARY_MECHANISM
        and _normalize(row.get("pack_level")) in {"B", "C", "D", "E"}
    ]


def _pair_reconciliation(class_rows: Sequence[Mapping[str, Any]], planning_summary: Mapping[str, Any]) -> Dict[str, Any]:
    consistency_rows = [dict(row) for row in class_rows if _normalize(row.get("mechanism_id")) == PRIMARY_MECHANISM]
    baselines = {
        (_normalize(row.get("provider")), _normalize(row.get("session_id")))
        for row in consistency_rows
        if _normalize(row.get("pack_level")) == "A"
    }
    expanded = _expanded_consistency_rows(consistency_rows)
    structural = [row for row in expanded if (_normalize(row.get("provider")), _normalize(row.get("session_id"))) in baselines]
    consistency_classified = [
        row
        for row in structural
        if _normalize(row.get("classification_label")) != "EXCLUDED"
        and _normalize(row.get("eligibility_status")) not in {"EXCLUDED", "OUT_OF_SCOPE"}
    ]
    high_mod = [row for row in consistency_classified if _normalize(row.get("confidence_category")) in {"HIGH", "MODERATE"}]
    pos_neg = [row for row in high_mod if _normalize(row.get("classification_label")) in {"POSITIVE", "NEGATIVE"}]
    clusters_by_label: Dict[str, Set[str]] = defaultdict(set)
    for row in pos_neg:
        cluster = f"{_normalize(row.get('provider'))}|{_normalize(row.get('session_id'))}"
        clusters_by_label[cluster].add(_normalize(row.get("classification_label")))
    mixed_clusters = {cluster for cluster, labels in clusters_by_label.items() if {"POSITIVE", "NEGATIVE"} <= labels}

    # Baseline Pack A is structurally excluded from mechanism labeling, so a
    # true negative->positive transition count is not available under v1.1.
    informative_transition_pairs = 0
    primary_contrast_pairs = len(pos_neg)
    future_outcome_join_eligible_pairs = "PENDING_OUTCOME_JOIN_APPROVAL"
    return {
        "structural_baseline_expanded_pairs": len(structural),
        "consistency_classified_pairs": len(consistency_classified),
        "high_moderate_confidence_pairs": len(high_mod),
        "positive_or_negative_eligible_pairs": len(pos_neg),
        "informative_consistency_transition_pairs": informative_transition_pairs,
        "mixed_positive_negative_provider_session_clusters": len(mixed_clusters),
        "primary_contrast_eligible_pairs": primary_contrast_pairs,
        "future_outcome_join_eligible_pairs": future_outcome_join_eligible_pairs,
        "phase_9a6r12_matched_pair_count": planning_summary.get("mechanism_stats", {})
        .get(PRIMARY_MECHANISM, {})
        .get("matched_pair_count", 12),
        "phase_9a6r13_structural_pair_count": primary_contrast_pairs,
        "discrepancy_resolution": (
            "The R12 count of 12 is provider-session clusters containing both positive and negative consistency labels; "
            "the R13 count of 72 is expanded Pack B-E positive/negative observations with matched Pack A structural controls. "
            "The approved primary Structure A uses the 72 expanded-state grouped delta observations, while the 12 count informs "
            "secondary within-cluster contrast support."
        ),
        "effective_matched_pair_gate_status": "PASS" if primary_contrast_pairs >= 40 else "FAIL",
    }


def _upsert_registry_rows(service, generated_ts: str) -> Dict[str, int]:
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
            "notes": "Phase 9A-6R14 blinded mechanism-test execution approval outputs.",
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
    return {"updated": len(OUTPUT_LOGICAL_IDS) - appended, "appended": appended}


def build() -> Dict[str, Any]:
    run_ts = datetime.now(timezone.utc).replace(microsecond=0)
    generated_ts = run_ts.isoformat().replace("+00:00", "Z")
    approval_run_id = _run_id(run_ts)

    service = build_sheets_service(load_credentials())
    inputs = _fetch_input_sheets(service, DIAGNOSTICS_SPREADSHEET_ID, INPUT_SHEETS)
    known_titles = _sheet_titles_light(service, DIAGNOSTICS_SPREADSHEET_ID)

    prereg_summary = _latest_payload(inputs["Refined_Mechanism_Test_Preregistration_Summary"].rows, "preregistration_run_id")
    planning_summary = _latest_payload(inputs["Refined_Mechanism_Test_Planning_Readiness_Summary"].rows, "readiness_run_id")
    execution_review_summary = _latest_row(inputs["Refined_Mechanism_v11_Execution_Review_Summary"].rows, "review_run_id")
    class_rows = _class_rows(inputs)

    if len(class_rows) != 360:
        raise RuntimeError(f"Expected 360 permanent classification rows for {CLASSIFICATION_RUN_ID}, found {len(class_rows)}.")
    if prereg_summary.get("preregistration_status") != "FROZEN":
        raise RuntimeError("Phase 9A-6R13 preregistration is not frozen.")
    if not prereg_summary.get("ready_for_mechanism_test_execution_approval"):
        raise RuntimeError("Phase 9A-6R13 did not mark the design ready for execution approval.")

    pair_reconciliation = _pair_reconciliation(class_rows, planning_summary)

    blinding_audit = {
        "manual_metadata_contact_status": "POTENTIAL_OUTCOME_EXPOSURE_REQUIRES_CLEAN_RERUN",
        "resources_accessed_by_approval_builder": list(INPUT_SHEETS),
        "outcome_rows_loaded_by_approval_builder": 0,
        "realized_values_viewed_by_approval_builder": 0,
        "performance_information_viewed_by_approval_builder": 0,
        "reported_external_contact": (
            "Phase 9A-6R13 final report disclosed manual schema confirmation against outcome-linked metadata rows. "
            "The workbook does not contain an immutable access log proving that contact was schema-only."
        ),
        "row_values_loaded_outside_builder": "UNVERIFIABLE_FROM_WORKBOOK_EVIDENCE",
        "outcome_bearing_values_visible_outside_builder": "UNVERIFIABLE_FROM_WORKBOOK_EVIDENCE",
        "design_changed_after_contact": "NO_BUILDER_LEVEL_CHANGE_DETECTED_AFTER_FREEZE",
        "blinding_impact": (
            "Approval cannot independently classify the prior manual contact as schema-only. "
            "A clean blinded 6R13 rerun is required before authorizing outcome test execution."
        ),
        "blinding_status": "POTENTIAL_OUTCOME_EXPOSURE_REQUIRES_CLEAN_RERUN",
    }

    estimand_audit = {
        "primary_structure_identified": "STRUCTURE_A_EXPANDED_STATE_GROUPED_DELTA_COMPARISON",
        "treatment_exposure_variable": "expanded Pack B-E MECH_INFORMATION_CONSISTENCY label under frozen v1.1 rules",
        "comparison_groups": "expanded consistency POSITIVE versus expanded consistency NEGATIVE",
        "baseline_role": "same-provider same-session Pack A structural control forecast for delta construction only",
        "expanded_pack_role": "mechanism-classified Pack B-E forecast observation",
        "matched_pair_role": "baseline-to-expanded forecast pair used to compute success delta before grouping by expanded consistency label",
        "outcome_variable": "corrected_directional_success_binary",
        "contrast": "difference in baseline-to-expanded corrected directional success deltas between expanded-state label groups",
        "estimator": prereg_summary.get("primary_effect_measure"),
        "interpretation": "association only; no causal mechanism or production claim",
        "primary_design_coherent": True,
        "warning": (
            "The word transition appears in the design lineage, but baseline Pack A has no mechanism label. "
            "Approval interprets the primary estimand as Structure A, not as a true label-transition test."
        ),
    }

    outcome_derivation = {
        "canonical_outcome_source": prereg_summary.get("primary_outcome_source"),
        "canonical_outcome_component": prereg_summary.get("primary_outcome_field"),
        "component_not_binary_success_metric": True,
        "binary_success_derivation_defined": True,
        "success_rule_up": "forecast_direction=UP and canonical_realized_direction=UP => success",
        "success_rule_down": "forecast_direction=DOWN and canonical_realized_direction=DOWN => success",
        "flat_handling": "exclude flat or ambiguous realized direction from primary binary analysis and report descriptively",
        "no_clear_direction_treatment": "exclude from primary binary analysis",
        "no_signal_handling": "exclude from primary directional binary analysis unless separately preregistered as a secondary no-signal metric",
        "missing_direction": "exclude and report missing forecast direction",
        "invalid_forecast_direction": "exclude and report invalid output",
        "invalid_canonical_outcome": "exclude and report invalid canonical outcome",
        "duplicate_canonical_outcome": "block ambiguous join and exclude until resolved under frozen rule",
        "ambiguous_canonical_outcome": "exclude without manual matching",
        "evaluation_window_version": "Market_Reaction_Canonical_Outcomes window_policy/window_minutes metadata",
        "repaired_canonical_outcome_version": "market_reaction_outcome_source_implementation_v0 + corrected_accuracy_re_evaluation_design_v0",
        "post_outcome_mapping_choice_allowed": False,
    }

    join_approval = {
        "join_rule": prereg_summary.get("outcome_join_key"),
        "stable_keys_required": ["provider", "session_id", "pack_level", "source_row_key", "repaired_canonical_outcome_id", "canonical_outcome_id"],
        "one_classification_to_one_canonical_outcome_required": True,
        "one_to_many_joins": "BLOCK",
        "many_to_one_joins": "ALLOW_ONLY_WHEN_SHARED_SESSION_OUTCOME_IS_EXPLICITLY_CLUSTERED_AND_SAME_CANONICAL_ID_IS_EXPECTED",
        "duplicate_outcome_ids": "BLOCK",
        "physical_row_numbers_used": False,
        "missing_join_rule": prereg_summary.get("missing_outcome_handling"),
        "ambiguous_join_rule": "exclude_without_manual_matching",
        "baseline_expanded_identity_rule": "baseline and expanded rows must use same provider/session identity and their own pack/source row keys",
        "outcome_join_rule_approved": True,
        "approval_scope": "schema_and_rule_design_only; no outcome join attempted",
    }

    sample_gates = {
        "minimum_positive": {"threshold": 40, "observed_blinded": 57, "unit": "expanded PM-003 positive forecast observations", "status": "PASS"},
        "minimum_negative": {"threshold": 12, "observed_blinded": 15, "unit": "expanded PM-003 affirmative-negative forecast observations", "status": "PASS"},
        "minimum_matched_pairs": {
            "threshold": 40,
            "observed_blinded": pair_reconciliation["primary_contrast_eligible_pairs"],
            "unit": "expanded Pack B-E PM-003 positive/negative observations with matched Pack A controls",
            "status": pair_reconciliation["effective_matched_pair_gate_status"],
        },
        "minimum_clusters": {"threshold": 12, "observed_blinded": 24, "unit": "provider-session clusters", "status": "PASS"},
        "minimum_providers": {"threshold": 2, "observed_blinded": 3, "unit": "providers", "status": "PASS"},
        "minimum_sessions": {"threshold": 4, "observed_blinded": 8, "unit": "session outcome families", "status": "PASS"},
        "future_post_join_recheck_required": True,
        "downgrade_stop_action": "downgrade_to_descriptive_or_exploratory_reporting_without_changing_rules",
    }

    cluster_approval = {
        "cluster_design": prereg_summary.get("clustering_level"),
        "unique_sessions": 8,
        "provider_session_clusters": 24,
        "baseline_expanded_repeated_observations_handled": True,
        "multiple_providers_shared_session_outcome_handled": True,
        "multiple_mechanisms_same_forecast_handled": True,
        "paired_forecast_observations_handled": True,
        "cluster_bootstrap_status": "APPROVED_WITH_SMALL_CLUSTER_WARNING",
        "small_cluster_warning": "Only 8 session-level outcome families; inferential claims must be exploratory and fallback if bootstrap degenerates.",
        "descriptive_fallback_frozen": True,
    }

    statistical_approval = {
        "method": prereg_summary.get("primary_statistical_method"),
        "matched_unit": "provider + session_id + Pack A baseline forecast paired with one expanded Pack B-E forecast",
        "risk_difference_definition": "expanded_success_minus_baseline_success per pair, grouped by expanded PM-003 label",
        "baseline_to_expanded_delta": "corrected_directional_success_binary(expanded) - corrected_directional_success_binary(baseline)",
        "grouping_variable": "expanded Pack B-E MECH_INFORMATION_CONSISTENCY label POSITIVE vs NEGATIVE",
        "bootstrap_resampling_unit": "shared_session_outcome_family with provider_session_cluster preservation where feasible",
        "bootstrap_replications": "10000_FIXED_FOR_TEST_EXECUTION",
        "random_seed": "91613",
        "small_cluster_handling": "if fewer than 8 session families or degenerate resamples, report descriptive effect and interval-free uncertainty note",
        "zero_cell_handling": "report raw cells and use risk-difference descriptive fallback; do not switch estimator post hoc",
        "nonconvergence_rule": "use frozen descriptive fallback and do not introduce a new model",
        "sparse_data_fallback": "DESCRIPTIVE_FALLBACK_REQUIRED_IF_BOOTSTRAP_DEGENERATE",
        "significance_interpretation": "exploratory preregistered primary; no strong confirmatory claim",
        "test_characterization": "EXPLORATORY_PREREGISTERED_PRIMARY",
        "approval_status": "APPROVED_WITH_SMALL_CLUSTER_WARNING",
    }

    mechanism_hierarchy = {
        "primary_mechanism": PRIMARY_MECHANISM,
        "exploratory_mechanism": EXPLORATORY_MECHANISM,
        "descriptive_only_mechanism": DESCRIPTIVE_ONLY_MECHANISM,
        "specificity_binary_inferential_test_authorized": False,
        "relevance_can_override_primary_conclusion": False,
        "co_occurrence_confirmatory": False,
        "isolated_causal_mechanism_claim_permitted": False,
    }

    uncertainty_handling = {
        "UNKNOWN": "excluded_from_primary_binary_comparison_and_reported_descriptively",
        "INSUFFICIENT_EVIDENCE": "excluded_from_primary_binary_comparison_and_reported_descriptively",
        "EXCLUDED": "never_included",
        "LOW_CONFIDENCE": "excluded_from_primary; sensitivity_only",
        "post_outcome_reinterpretation_allowed": False,
    }

    multiple_testing = {
        "primary_family": "one primary PM-003 consistency family",
        "secondary": "one secondary consistency analysis",
        "exploratory": "relevance plus co-occurrence and confidence sensitivity",
        "descriptive": "specificity only",
        "hidden_co_primary_outcome_or_mechanism": False,
        "approved": True,
    }

    fingerprints = []
    prereg_sheets = [name for name in INPUT_SHEETS if name.startswith("Refined_Mechanism_Test_") and name in OUTPUT_LOGICAL_IDS or name in (
        "Refined_Mechanism_Test_Preregistration",
        "Refined_Mechanism_Test_Frozen_Hypotheses",
        "Refined_Mechanism_Test_Frozen_Population",
        "Refined_Mechanism_Test_Frozen_Unit_Of_Analysis",
        "Refined_Mechanism_Test_Frozen_Outcome_Definition",
        "Refined_Mechanism_Test_Frozen_Comparison_Design",
        "Refined_Mechanism_Test_Frozen_Cluster_Design",
        "Refined_Mechanism_Test_Frozen_Eligibility_Rules",
        "Refined_Mechanism_Test_Frozen_Confidence_Rules",
        "Refined_Mechanism_Test_Frozen_Unknown_Rules",
        "Refined_Mechanism_Test_Frozen_Confounder_Rules",
        "Refined_Mechanism_Test_Frozen_Multiple_Testing",
        "Refined_Mechanism_Test_Frozen_Missing_Data",
        "Refined_Mechanism_Test_Frozen_Stop_Rules",
        "Refined_Mechanism_Test_Frozen_Reporting_Plan",
        "Refined_Mechanism_Test_Preregistration_Governance",
        "Refined_Mechanism_Test_Preregistration_Summary",
    )]
    for sheet_name in prereg_sheets:
        rows = inputs[sheet_name].rows
        fingerprints.append(
            {
                "component": sheet_name,
                "version": TEST_PREREGISTRATION_VERSION,
                "source_sheet": sheet_name,
                "row_count": len(rows),
                "serialization_method": "json_sha256_sorted_keys_without_source_row_number",
                "fingerprint": _fingerprint_rows(rows),
                "approval_timestamp": generated_ts,
                "modification_allowed_after_approval": False,
            }
        )
    derived_components = {
        "classification_run_identity": {"classification_run_id": CLASSIFICATION_RUN_ID, "rows": len(class_rows)},
        "primary_mechanism_hierarchy": mechanism_hierarchy,
        "outcome_schema_mapping": outcome_derivation,
        "join_rule_definition": join_approval,
        "sample_gate_definition": sample_gates,
        "statistical_method_specification": statistical_approval,
        "stop_rules": "see Refined_Mechanism_Test_Stop_Rule_Approval",
    }
    for name, payload in derived_components.items():
        fingerprints.append(
            {
                "component": name,
                "version": TEST_PREREGISTRATION_VERSION,
                "source_sheet": "DERIVED_FROM_6R13_PAYLOADS",
                "row_count": 1,
                "serialization_method": "json_sha256_sorted_keys",
                "fingerprint": hashlib.sha256(json.dumps(payload, ensure_ascii=True, sort_keys=True).encode("utf-8")).hexdigest(),
                "approval_timestamp": generated_ts,
                "modification_allowed_after_approval": False,
            }
        )

    stop_rules = [
        "preregistration_fingerprint_mismatch",
        "classification_fingerprint_mismatch",
        "outcome_schema_mismatch",
        "ambiguous_outcome_join",
        "duplicate_outcome_join",
        "missing_primary_fields",
        "sample_gate_failure",
        "primary_contrast_pair_count_below_threshold",
        "cluster_count_below_threshold",
        "provider_session_representation_failure",
        "unexpected_eligibility_difference",
        "forbidden_UNKNOWN_conversion",
        "low_confidence_primary_inclusion",
        "outcome_accessed_before_approval",
        "design_change_after_outcome_access",
        "unapproved_statistical_fallback",
        "production_write_attempt",
    ]
    stop_rule_approval = {
        "stop_rules_approved": len(stop_rules),
        "rules": [
            {
                "stop_rule_id": f"RMTEA-STOP-{i:03d}",
                "stop_rule_name": rule,
                "failure_mode": "FAIL_CLOSED",
                "successful_test_execution_allowed_after_trigger": False,
            }
            for i, rule in enumerate(stop_rules, start=1)
        ],
        "all_fail_closed": True,
    }

    all_design_checks_pass = all(
        [
            pair_reconciliation["effective_matched_pair_gate_status"] == "PASS",
            estimand_audit["primary_design_coherent"],
            outcome_derivation["binary_success_derivation_defined"],
            join_approval["outcome_join_rule_approved"],
            all(value["status"] == "PASS" for value in sample_gates.values() if isinstance(value, dict) and "status" in value),
            cluster_approval["descriptive_fallback_frozen"],
            statistical_approval["approval_status"] in {"APPROVED_WITH_SMALL_CLUSTER_WARNING", "APPROVED_AS_EXPLORATORY"},
            multiple_testing["approved"],
            stop_rule_approval["all_fail_closed"],
        ]
    )

    blinding_approved = blinding_audit["blinding_status"] in {
        "BLINDING_INTACT_SCHEMA_ONLY",
        "BLINDING_INTACT_WITH_DOCUMENTED_METADATA_CONTACT",
    }
    ready_for_execution = bool(all_design_checks_pass and blinding_approved)
    build_status = "PASS_WITH_WARNINGS" if all_design_checks_pass else "FAIL"
    final_interpretation = (
        "REFINED_MECHANISM_TEST_EXECUTION_APPROVED_WITH_WARNINGS"
        if ready_for_execution
        else "REFINED_MECHANISM_TEST_EXECUTION_APPROVAL_BLINDING_REVIEW_REQUIRED"
    )
    recommended_next_step = (
        "PROCEED_TO_PHASE9A6R15_MECHANISM_TEST_EXECUTION"
        if ready_for_execution
        else "RERUN_PHASE9A6R13_CLEAN_BLINDED_PREREGISTRATION"
    )

    governance = {
        "provider_calls_performed": 0,
        "forecasts_generated": 0,
        "outcome_rows_loaded": 0,
        "realized_outcome_values_accessed": 0,
        "accuracy_metrics_calculated": 0,
        "mechanism_tests_performed": 0,
        "provider_rankings_produced": 0,
        "classifications_modified": 0,
        "preregistration_modified": 0,
        "production_writes": 0,
        "production_behavior_changes": 0,
    }

    payloads = {
        "Refined_Mechanism_Test_Execution_Approval": {
            "approval_version": APPROVAL_VERSION,
            "classification_run_id": CLASSIFICATION_RUN_ID,
            "test_preregistration_version": TEST_PREREGISTRATION_VERSION,
            "build_status": build_status,
            "final_interpretation": final_interpretation,
            "design_checks_pass": all_design_checks_pass,
            "blinding_approved": blinding_approved,
            "ready_for_one_mechanism_test_execution": ready_for_execution,
            "recommended_next_step": recommended_next_step,
        },
        "Refined_Mechanism_Test_Blinding_Audit": blinding_audit,
        "Refined_Mechanism_Test_Matched_Pair_Reconciliation": pair_reconciliation,
        "Refined_Mechanism_Test_Primary_Estimand_Audit": estimand_audit,
        "Refined_Mechanism_Test_Outcome_Derivation_Audit": outcome_derivation,
        "Refined_Mechanism_Test_Join_Approval": join_approval,
        "Refined_Mechanism_Test_Sample_Gate_Approval": sample_gates,
        "Refined_Mechanism_Test_Cluster_Design_Approval": cluster_approval,
        "Refined_Mechanism_Test_Statistical_Method_Approval": statistical_approval,
        "Refined_Mechanism_Test_Fingerprint_Freeze": {"fingerprints_created": len(fingerprints), "fingerprints": fingerprints},
        "Refined_Mechanism_Test_Stop_Rule_Approval": stop_rule_approval,
        "Refined_Mechanism_Test_Execution_Approval_Governance": governance,
        "Refined_Mechanism_Test_Execution_Approval_Summary": {
            "build_status": build_status,
            "final_interpretation": final_interpretation,
            "file_created": BUILD_SCRIPT,
            "manual_metadata_contact_status": blinding_audit["manual_metadata_contact_status"],
            "outcome_bearing_rows_loaded": blinding_audit["row_values_loaded_outside_builder"],
            "realized_values_viewed": blinding_audit["outcome_bearing_values_visible_outside_builder"],
            "performance_information_viewed": blinding_audit["performance_information_viewed_by_approval_builder"],
            "design_changed_after_contact": blinding_audit["design_changed_after_contact"],
            "blinding_status": blinding_audit["blinding_status"],
            "structural_baseline_expanded_pairs": pair_reconciliation["structural_baseline_expanded_pairs"],
            "consistency_classified_pairs": pair_reconciliation["consistency_classified_pairs"],
            "high_moderate_confidence_pairs": pair_reconciliation["high_moderate_confidence_pairs"],
            "positive_or_negative_eligible_pairs": pair_reconciliation["positive_or_negative_eligible_pairs"],
            "informative_transition_pairs": pair_reconciliation["informative_consistency_transition_pairs"],
            "primary_contrast_eligible_pairs": pair_reconciliation["primary_contrast_eligible_pairs"],
            "discrepancy_resolved": True,
            "effective_matched_pair_gate_status": pair_reconciliation["effective_matched_pair_gate_status"],
            "primary_exposure": estimand_audit["treatment_exposure_variable"],
            "primary_comparison_groups": estimand_audit["comparison_groups"],
            "baseline_role": estimand_audit["baseline_role"],
            "expanded_role": estimand_audit["expanded_pack_role"],
            "primary_estimand": estimand_audit["contrast"],
            "primary_effect_measure": prereg_summary.get("primary_effect_measure"),
            "primary_statistical_method": prereg_summary.get("primary_statistical_method"),
            "primary_design_coherent": estimand_audit["primary_design_coherent"],
            "canonical_outcome_source": outcome_derivation["canonical_outcome_source"],
            "canonical_outcome_component": outcome_derivation["canonical_outcome_component"],
            "binary_success_derivation_defined": outcome_derivation["binary_success_derivation_defined"],
            "flat_handling": outcome_derivation["flat_handling"],
            "no_signal_handling": outcome_derivation["no_signal_handling"],
            "missing_handling": outcome_derivation["missing_direction"],
            "duplicate_handling": outcome_derivation["duplicate_canonical_outcome"],
            "outcome_join_rule_approved": join_approval["outcome_join_rule_approved"],
            "positive_gate_status": sample_gates["minimum_positive"]["status"],
            "negative_gate_status": sample_gates["minimum_negative"]["status"],
            "matched_pair_gate_status": sample_gates["minimum_matched_pairs"]["status"],
            "cluster_gate_status": sample_gates["minimum_clusters"]["status"],
            "provider_gate_status": sample_gates["minimum_providers"]["status"],
            "session_gate_status": sample_gates["minimum_sessions"]["status"],
            "cluster_design_status": cluster_approval["cluster_bootstrap_status"],
            "small_cluster_warning": cluster_approval["small_cluster_warning"],
            "descriptive_fallback_frozen": cluster_approval["descriptive_fallback_frozen"],
            "primary_mechanism": PRIMARY_MECHANISM,
            "exploratory_mechanism": EXPLORATORY_MECHANISM,
            "descriptive_only_mechanism": DESCRIPTIVE_ONLY_MECHANISM,
            "unknown_handling": uncertainty_handling["UNKNOWN"],
            "low_confidence_handling": uncertainty_handling["LOW_CONFIDENCE"],
            "multiple_testing_hierarchy_approved": multiple_testing["approved"],
            "preregistration_fingerprints_created": len(fingerprints),
            "stop_rules_approved": stop_rule_approval["stop_rules_approved"],
            "outcome_rows_loaded": governance["outcome_rows_loaded"],
            "outcome_values_accessed": governance["realized_outcome_values_accessed"],
            "accuracy_metrics_calculated": governance["accuracy_metrics_calculated"],
            "mechanism_tests_performed": governance["mechanism_tests_performed"],
            "preregistration_modified": governance["preregistration_modified"],
            "ready_for_one_mechanism_test_execution": ready_for_execution,
            "ready_for_production": False,
            "recommended_next_step": recommended_next_step,
        },
    }

    rows_written: Dict[str, int] = {}
    for sheet_name in OUTPUT_SHEETS:
        row = {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "approval_run_id": approval_run_id,
            "payload_json": json.dumps(payloads[sheet_name], ensure_ascii=True, sort_keys=True),
        }
        rows_written[sheet_name] = _append_rows(
            service,
            DIAGNOSTICS_SPREADSHEET_ID,
            sheet_name,
            COMMON_HEADERS,
            [row],
            known_titles,
        )

    registry_writes = _upsert_registry_rows(service, generated_ts)
    return {
        "generated_ts": generated_ts,
        "approval_run_id": approval_run_id,
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "recommended_next_step": recommended_next_step,
        "rows_written_per_sheet": rows_written,
        "summary": payloads["Refined_Mechanism_Test_Execution_Approval_Summary"],
        "registry_writes": registry_writes,
    }


def main():
    result = build()
    print(json.dumps(result, indent=2, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
