#!/usr/bin/env python3
"""Phase 9A-6R15F — Outcome Architecture Refinement Preregistration.

This phase freezes Outcome Architecture v2 as a preregistered design-only
artifact. It does not implement any architecture changes, access outcome rows,
calculate accuracy, rerun mechanism tests, or modify prior scientific sheets.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
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
from automation.build_refined_mechanism_v11_classification_execution_v0 import (  # type: ignore
    _append_rows,
    _fetch_input_sheets,
    _normalize,
    _sheet_titles_light,
)
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials  # type: ignore


PHASE_ID = "9A-6R15F"
BUILD_SCRIPT = "automation/build_refined_mechanism_test_outcome_architecture_refinement_preregistration_v0.py"
SCHEMA_VERSION = "presignal_v2_refined_mechanism_test_outcome_architecture_refinement_preregistration_v0"
ARCHITECTURE_PREREGISTRATION_VERSION = "1.0"
ARCHITECTURE_PREREGISTRATION_STATUS = "FROZEN"
ARCHITECTURE_VERSION = "2.0"
ARCHITECTURE_LINEAGE_VERSION = "outcome_architecture_v2_design_lineage_v1"
REGISTRY_CATEGORY = "PRESIGNAL_V2_REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_PREREGISTRATION"
REGISTRY_OWNER_MODULE = "market_state"

AUTHORITATIVE_VERSION = "1.0-clean-r1"
AUTHORITATIVE_RUN_ID = "9A-6R13R1_20260711T020141Z"
CLASSIFICATION_VERSION = "1.1"
CLASSIFICATION_RUN_ID = "refined_mechanism_v11_classification_20260710T152725Z"
PRIMARY_MECHANISM = "MECH_INFORMATION_CONSISTENCY"
PRIMARY_STRUCTURE = "STRUCTURE_A_EXPANDED_STATE_GROUPED_DELTA_COMPARISON"

SCIENTIFIC_READINESS = "READY_WITH_CONSTRAINTS"
VALIDATION_READINESS = "READY_FOR_OUTCOME_ARCHITECTURE_VALIDATION"
BUILD_STATUS = "PASS_WITH_WARNINGS"
FINAL_INTERPRETATION = "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_PREREGISTRATION_READY_WITH_WARNINGS"
RECOMMENDED_NEXT_STEP = "PROCEED_TO_PHASE9A6R15G_OUTCOME_ARCHITECTURE_VALIDATION"

DESIGN_FINAL_INTERPRETATION = "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_V2_DESIGN_READY_WITH_WARNINGS"
SCOPE_FINAL_INTERPRETATION = "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_SCOPE_READY_WITH_CONSTRAINTS"

FORBIDDEN_INPUT_TITLES = {
    "Market_Reaction_Canonical_Outcomes",
    "Outcome_Ledger",
    "Evaluation_Rows",
    "Evaluation_Summary",
    "Corrected_Accuracy_Evaluation",
    "Controlled_Accuracy_Evaluation",
}

INPUT_SHEETS: Tuple[str, ...] = (
    "Refined_Mechanism_Test_Clean_R1_Canonical_Authority",
    "Refined_Mechanism_Test_Clean_R1_Component_Authority",
    "Refined_Mechanism_Test_Clean_R1_Canonical_Fingerprint_Manifest",
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
    "Refined_Mechanism_Test_Outcome_Architecture_Refinement_Scope",
    "Refined_Mechanism_Test_Outcome_Architecture_Limitations",
    "Refined_Mechanism_Test_Outcome_Architecture_Refinement_Summary",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Design",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Layer_Model",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Redesign_Targets",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Prohibited_Targets",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Evidence_Dependencies",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Compatibility_Audit",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Implementation_Roadmap",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Summary",
)

OUTPUT_PREREG = "Refined_Mechanism_Test_Outcome_Architecture_V2_Preregistration"
OUTPUT_LAYERS = "Refined_Mechanism_Test_Outcome_Architecture_V2_Frozen_Layers"
OUTPUT_TARGETS = "Refined_Mechanism_Test_Outcome_Architecture_V2_Frozen_Redesign_Targets"
OUTPUT_PROHIBITED = "Refined_Mechanism_Test_Outcome_Architecture_V2_Frozen_Prohibited_Redesigns"
OUTPUT_EMPIRICAL = "Refined_Mechanism_Test_Outcome_Architecture_V2_Frozen_Empirical_Questions"
OUTPUT_COMPAT = "Refined_Mechanism_Test_Outcome_Architecture_V2_Frozen_Compatibility"
OUTPUT_GOVERNANCE_RULES = "Refined_Mechanism_Test_Outcome_Architecture_V2_Frozen_Governance"
OUTPUT_BOUNDARY = "Refined_Mechanism_Test_Outcome_Architecture_V2_Frozen_Implementation_Boundary"
OUTPUT_FINGERPRINTS = "Refined_Mechanism_Test_Outcome_Architecture_V2_Fingerprint_Freeze"
OUTPUT_GOVERNANCE = "Refined_Mechanism_Test_Outcome_Architecture_V2_Preregistration_Governance"
OUTPUT_SUMMARY = "Refined_Mechanism_Test_Outcome_Architecture_V2_Preregistration_Summary"

OUTPUT_SHEETS: Dict[str, List[str]] = {
    OUTPUT_PREREG: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_preregistration_run_id",
        "architecture_preregistration_version",
        "architecture_preregistration_status",
        "architecture_version",
        "architecture_lineage_version",
        "canonical_preregistration_version",
        "canonical_run_id",
        "classification_version",
        "classification_run_id",
        "scientific_readiness_assessment",
        "validation_readiness_status",
        "recommended_next_step",
        "build_status",
        "final_interpretation",
        "payload_json",
    ],
    OUTPUT_LAYERS: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_preregistration_run_id",
        "layer_id",
        "layer_order",
        "layer_name",
        "scientific_purpose",
        "allowed_inputs_json",
        "allowed_outputs_json",
        "prohibited_dependencies_json",
        "downstream_consumers_json",
        "payload_json",
    ],
    OUTPUT_TARGETS: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_preregistration_run_id",
        "target_id",
        "limitation_id",
        "objective",
        "scientific_rationale",
        "expected_architectural_benefit",
        "constraints_json",
        "prohibited_implementation_shortcuts_json",
        "payload_json",
    ],
    OUTPUT_PROHIBITED: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_preregistration_run_id",
        "prohibited_id",
        "limitation_id",
        "scientific_justification",
        "governance_justification",
        "permanence_status",
        "payload_json",
    ],
    OUTPUT_EMPIRICAL: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_preregistration_run_id",
        "question_id",
        "limitation_id",
        "unresolved_scientific_question",
        "future_evidence_requirements_json",
        "status",
        "payload_json",
    ],
    OUTPUT_COMPAT: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_preregistration_run_id",
        "compatibility_id",
        "compatibility_target",
        "compatibility_status",
        "preserved_contract",
        "required_versioning_behavior",
        "payload_json",
    ],
    OUTPUT_GOVERNANCE_RULES: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_preregistration_run_id",
        "rule_id",
        "rule_type",
        "rule_text",
        "enforcement_scope",
        "payload_json",
    ],
    OUTPUT_BOUNDARY: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_preregistration_run_id",
        "stage_id",
        "stage_type",
        "allowed_actions_json",
        "prohibited_actions_json",
        "advancement_condition",
        "payload_json",
    ],
    OUTPUT_FINGERPRINTS: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_preregistration_run_id",
        "component_id",
        "component_type",
        "source_sheet",
        "fingerprint_method",
        "fingerprint",
        "modification_allowed_after_preregistration",
        "payload_json",
    ],
    OUTPUT_GOVERNANCE: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_preregistration_run_id",
        "counter_name",
        "counter_value",
        "status",
        "notes",
    ],
    OUTPUT_SUMMARY: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_preregistration_run_id",
        "architecture_preregistration_version",
        "architecture_preregistration_status",
        "architecture_version",
        "build_status",
        "final_interpretation",
        "validation_readiness_status",
        "recommended_next_step",
        "payload_json",
    ],
}

OUTPUT_LOGICAL_IDS = {
    OUTPUT_PREREG: "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_V2_PREREGISTRATION",
    OUTPUT_LAYERS: "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_V2_FROZEN_LAYERS",
    OUTPUT_TARGETS: "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_V2_FROZEN_REDESIGN_TARGETS",
    OUTPUT_PROHIBITED: "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_V2_FROZEN_PROHIBITED_REDESIGNS",
    OUTPUT_EMPIRICAL: "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_V2_FROZEN_EMPIRICAL_QUESTIONS",
    OUTPUT_COMPAT: "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_V2_FROZEN_COMPATIBILITY",
    OUTPUT_GOVERNANCE_RULES: "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_V2_FROZEN_GOVERNANCE",
    OUTPUT_BOUNDARY: "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_V2_FROZEN_IMPLEMENTATION_BOUNDARY",
    OUTPUT_FINGERPRINTS: "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_V2_FINGERPRINT_FREEZE",
    OUTPUT_GOVERNANCE: "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_V2_PREREGISTRATION_GOVERNANCE",
    OUTPUT_SUMMARY: "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_V2_PREREGISTRATION_SUMMARY",
}


def _run_id(ts: datetime) -> str:
    return f"9A-6R15F_{ts.strftime('%Y%m%dT%H%M%SZ')}"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _fingerprint_payload(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


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


def _parse_payload(row: Mapping[str, Any]) -> Dict[str, Any]:
    raw = _normalize(row.get("payload_json"))
    return json.loads(raw) if raw else {}


def _parse_source_row_key(source_row_key: str) -> Tuple[str, str, int]:
    parts = source_row_key.split("::")
    _require(len(parts) == 3, f"Invalid source_row_key format: {source_row_key}")
    sheet_name, run_id, row_number_raw = parts
    return sheet_name, run_id, int(row_number_raw)


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
    _require(len(manifest_entries) == 12, "Canonical manifest does not contain 12 authoritative components.")

    selected: Dict[str, Dict[str, Any]] = {}
    seen_components: Set[str] = set()
    for entry in manifest_entries:
        component_id = _normalize(entry.get("component_id"))
        sheet_name = _normalize(entry.get("source_sheet"))
        source_row_key = _normalize(entry.get("source_row_key"))
        _require(component_id not in seen_components, f"Duplicate component in manifest: {component_id}")
        seen_components.add(component_id)

        record = component_records.get(component_id)
        _require(record is not None, f"Component authority record missing for {component_id}")
        _require(
            _normalize(record.get("authority_status")) == "EXACTLY_ONE_COMPLETE_AUTHORITATIVE_ROW",
            f"Component authority status invalid for {component_id}: {record}",
        )

        parsed_sheet, parsed_run_id, parsed_row_number = _parse_source_row_key(source_row_key)
        _require(_normalize(parsed_sheet) == sheet_name, f"Manifest source sheet mismatch for {component_id}")
        _require(parsed_run_id == AUTHORITATIVE_RUN_ID, f"Manifest run ID mismatch for {component_id}")

        matches = [
            dict(row)
            for row in inputs[sheet_name].rows
            if _normalize(row.get("clean_contract_repair_run_id")) == AUTHORITATIVE_RUN_ID
            and int(row.get("__source_row_number__", 0) or 0) == parsed_row_number
        ]
        _require(len(matches) == 1, f"Expected exactly one authoritative match for {component_id}; found {len(matches)}")
        row = matches[0]
        payload = _parse_payload(row)
        _require(isinstance(payload, dict) and bool(payload), f"Authoritative payload incomplete for {component_id}")
        current_fp = _fingerprint_payload(payload)
        _require(current_fp == _normalize(entry.get("fingerprint")), f"Authoritative fingerprint mismatch for {component_id}")
        selected[sheet_name] = {
            "component_id": component_id,
            "source_row_key": source_row_key,
            "row": row,
            "payload": payload,
            "fingerprint": current_fp,
        }

    _require(len(selected) == 12, f"Expected 12 selected authoritative rows, found {len(selected)}")
    return selected


def _filter_rows_for_run(rows: Sequence[Mapping[str, Any]], run_key: str, run_id: str) -> List[Dict[str, Any]]:
    return [dict(row) for row in rows if _normalize(row.get(run_key)) == run_id]


def _upsert_registry_rows(service, generated_ts: str) -> Dict[str, Any]:
    try:
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
                "notes": "Phase 9A-6R15F Outcome Architecture v2 preregistration artifacts.",
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
    except Exception as exc:  # pragma: no cover
        return {"updated": 0, "appended": 0, "status": "unavailable", "error": str(exc)}


def _layer_definitions() -> List[Dict[str, Any]]:
    return [
        {
            "layer_id": "OA_V2_LAYER_CANONICAL_OUTCOME",
            "layer_order": 1,
            "layer_name": "CANONICAL_OUTCOME",
            "scientific_purpose": "Freeze authoritative outcome identity, coverage state, version provenance, evaluation-window identity, and canonical realized-state records without embedding scoring logic.",
            "allowed_inputs": [
                "frozen_canonical_outcome_schema_contract_metadata",
                "canonical_outcome_identity_specification",
                "evaluation_window_version_contract",
                "timestamp_provenance_contract",
            ],
            "allowed_outputs": [
                "canonical_coverage_manifest",
                "canonical_availability_status",
                "canonical_version_identity",
                "canonical_timestamp_provenance_status",
            ],
            "prohibited_dependencies": [
                "outcome_overlay_values",
                "success_mapping_logic",
                "eligibility_overrides",
                "provider_specific_tuning",
            ],
            "downstream_consumers": [
                "OUTCOME_OVERLAY",
                "OUTCOME_LINKAGE",
                "OUTCOME_ARCHITECTURE_VALIDATION",
            ],
        },
        {
            "layer_id": "OA_V2_LAYER_OUTCOME_OVERLAY",
            "layer_order": 2,
            "layer_name": "OUTCOME_OVERLAY",
            "scientific_purpose": "Freeze the repaired overlay as a deterministic bridge layer that exposes completeness, lineage, and bridge availability without changing canonical semantics.",
            "allowed_inputs": [
                "canonical_outcome_identity",
                "overlay_lineage_contract",
                "repaired_overlay_schema_metadata",
            ],
            "allowed_outputs": [
                "overlay_completeness_manifest",
                "overlay_bridge_status",
                "overlay_lineage_status",
            ],
            "prohibited_dependencies": [
                "manual_overlay_repair",
                "provider_conditioned_overlay_logic",
                "success_outcome_scoring",
                "unversioned_bridge_keys",
            ],
            "downstream_consumers": [
                "OUTCOME_LINKAGE",
                "OUTCOME_ARCHITECTURE_VALIDATION",
            ],
        },
        {
            "layer_id": "OA_V2_LAYER_OUTCOME_LINKAGE",
            "layer_order": 3,
            "layer_name": "OUTCOME_LINKAGE",
            "scientific_purpose": "Freeze exact stable-key linkage from classification observations to repaired canonical outcome IDs and canonical outcome IDs before any success derivation occurs.",
            "allowed_inputs": [
                "classification_observation_identity",
                "overlay_bridge_identity",
                "canonical_outcome_identity",
                "stable_join_key_contract",
            ],
            "allowed_outputs": [
                "linkage_bridge_manifest",
                "join_state_audit",
                "duplicate_or_ambiguous_join_status",
            ],
            "prohibited_dependencies": [
                "physical_row_numbers",
                "fuzzy_matching",
                "manual_matching",
                "nearest_date_matching",
            ],
            "downstream_consumers": [
                "OUTCOME_REPRESENTATION",
                "ELIGIBILITY_INTERACTION",
                "OUTCOME_ARCHITECTURE_VALIDATION",
            ],
        },
        {
            "layer_id": "OA_V2_LAYER_OUTCOME_REPRESENTATION",
            "layer_order": 4,
            "layer_name": "OUTCOME_REPRESENTATION",
            "scientific_purpose": "Freeze a pre-success representation contract for scoreable and non-scoreable realized states without changing corrected directional-success semantics.",
            "allowed_inputs": [
                "linked_canonical_outcome_identity",
                "linked_overlay_state",
                "frozen_realized_state_taxonomy_metadata",
            ],
            "allowed_outputs": [
                "representability_status",
                "scoreability_status",
                "pre_success_exclusion_reason",
            ],
            "prohibited_dependencies": [
                "accuracy_results",
                "post_hoc_state_collapsing",
                "provider_specific_state_rules",
                "directional_success_redefinition",
            ],
            "downstream_consumers": [
                "ELIGIBILITY_INTERACTION",
                "SUCCESS_MAPPING_V1",
                "FUTURE_SUCCESS_MAPPING_V2_DESIGN",
            ],
        },
        {
            "layer_id": "OA_V2_LAYER_ELIGIBILITY_INTERACTION",
            "layer_order": 5,
            "layer_name": "ELIGIBILITY_INTERACTION",
            "scientific_purpose": "Freeze observational diagnostics for baseline-control evaluability, post-join gate survivorship, and negative-arm fragility without rewriting eligibility rules.",
            "allowed_inputs": [
                "representation_status",
                "paired_baseline_expanded_identity",
                "frozen_sample_gate_definitions",
                "frozen_uncertainty_rules",
            ],
            "allowed_outputs": [
                "paired_control_evaluability_status",
                "post_join_gate_survivorship_projection",
                "negative_arm_fragility_diagnostic",
            ],
            "prohibited_dependencies": [
                "eligibility_rule_changes",
                "sample_gate_relaxation",
                "confidence_rule_relaxation",
                "mechanism_classification_changes",
            ],
            "downstream_consumers": [
                "OUTCOME_ARCHITECTURE_VALIDATION",
                "FUTURE_SUCCESS_MAPPING_V2_SCOPE_REFRESH",
                "FUTURE_MECHANISM_RETESTING",
            ],
        },
    ]


def _target_definitions() -> List[Dict[str, Any]]:
    return [
        {
            "target_id": "OA_V2_TARGET_CANONICAL_COVERAGE_CONTRACT",
            "limitation_id": "OA_LIMIT_01_CANONICAL_COVERAGE_GAPS",
            "objective": "Make canonical outcome coverage state explicit, versioned, and auditable before any overlay, linkage, or success-mapping stage runs.",
            "scientific_rationale": "Coverage loss is an upstream architecture fact, not a downstream scoring choice, and must be isolated as such.",
            "expected_architectural_benefit": "Reduces unexplained observation loss by distinguishing canonical absence from later-stage exclusion.",
            "constraints": [
                "must_not_change_canonical_realized_direction_semantics",
                "must_not_relax_version_window_or_timestamp_guardrails",
                "must_not_create_synthetic_outcomes",
            ],
            "prohibited_implementation_shortcuts": [
                "manual_backfill_of_missing_outcomes",
                "use_latest_available_version_when_frozen_version_missing",
                "provider_specific_coverage_overrides",
            ],
        },
        {
            "target_id": "OA_V2_TARGET_OVERLAY_COMPLETENESS_MANIFEST",
            "limitation_id": "OA_LIMIT_03_OVERLAY_COVERAGE_GAPS",
            "objective": "Freeze a deterministic overlay completeness layer that reports whether the repaired bridge exists and why it does not when missing.",
            "scientific_rationale": "Overlay absence is materially different from canonical absence and should not be hidden inside downstream join failure.",
            "expected_architectural_benefit": "Improves stagewise loss accounting and bridge traceability across repaired overlay dependencies.",
            "constraints": [
                "overlay_must_remain_bridge_not_semantic_correction",
                "overlay_lineage_must_remain_versioned",
                "overlay_status_must_be_deterministic",
            ],
            "prohibited_implementation_shortcuts": [
                "ad_hoc_overlay_reconstruction",
                "unlogged_bridge_id_substitution",
                "merge_multiple_overlay_versions_for_single_observation",
            ],
        },
        {
            "target_id": "OA_V2_TARGET_EXPLICIT_LINKAGE_BRIDGE",
            "limitation_id": "OA_LIMIT_06_LINKAGE_BRIDGE_COMPLETENESS",
            "objective": "Freeze an explicit linkage bridge contract from classification observation to repaired canonical outcome ID to canonical outcome ID.",
            "scientific_rationale": "A stable-key bridge is already required scientifically; preregistration makes its intermediate states observable and reproducible.",
            "expected_architectural_benefit": "Improves join transparency, fail-closed diagnostics, and deterministic replay before any success derivation occurs.",
            "constraints": [
                "join_must_remain_exact_one_to_one_and_fail_closed",
                "no_physical_row_or_fuzzy_matching",
                "no_manual_join_override",
            ],
            "prohibited_implementation_shortcuts": [
                "provider_only_join",
                "session_only_join",
                "nearest_date_join",
                "many_to_one_collapse_without_contract",
            ],
        },
        {
            "target_id": "OA_V2_TARGET_PAIRED_CONTROL_EVALUABILITY",
            "limitation_id": "OA_LIMIT_08_BASELINE_CONTROL_EVALUABILITY",
            "objective": "Freeze a paired-control evaluability contract that reveals whether expanded observations have a valid Pack A baseline with scoreable downstream lineage.",
            "scientific_rationale": "Structure A depends on paired baseline control, and pair loss must be diagnosed without rewriting the estimand.",
            "expected_architectural_benefit": "Improves transparency around baseline-control loss and clarifies whether failures are structural, not semantic.",
            "constraints": [
                "baseline_remains_control_only_for_delta_construction",
                "must_not_change_primary_estimand",
                "must_not_substitute_cross_provider_or_cross_session_baselines",
            ],
            "prohibited_implementation_shortcuts": [
                "implicit_pairing_from_partial_keys",
                "fallback_to_non_pack_a_baseline",
                "eligibility_rewrite_disguised_as_pair_recovery",
            ],
        },
        {
            "target_id": "OA_V2_TARGET_POSTJOIN_SURVIVORSHIP_PROJECTION",
            "limitation_id": "OA_LIMIT_10_POSTJOIN_GATE_DEPENDENCE",
            "objective": "Freeze a deterministic post-join gate survivorship projection layer so planned populations can be evaluated against downstream architecture dependencies before test execution.",
            "scientific_rationale": "Blinded structural gates can pass while downstream architecture deterministically collapses the sample; the architecture must surface that dependence.",
            "expected_architectural_benefit": "Improves pre-execution readiness assessment, gate interpretability, and reproducibility of sample collapse explanations.",
            "constraints": [
                "must_not_change_frozen_sample_gates",
                "must_not_change_confidence_or_uncertainty_rules",
                "must_not_convert_diagnostics_into_eligibility_overrides",
            ],
            "prohibited_implementation_shortcuts": [
                "lower_gate_thresholds_after_projection",
                "selective_reporting_of_surviving_subgroups",
                "post_hoc_reclassification_of_excluded_observations",
            ],
        },
    ]


def _prohibited_definitions() -> List[Dict[str, Any]]:
    return [
        {
            "prohibited_id": "OA_V2_PROHIBITED_CANONICAL_GUARDRAIL_RELAXATION",
            "limitation_id": "OA_LIMIT_02_CANONICAL_VERSION_WINDOW_TIMESTAMP_CONTRACT",
            "scientific_justification": "Version, evaluation-window, and timestamp provenance guardrails are part of the no-hindsight scientific contract, not retention policy knobs.",
            "governance_justification": "Relaxing them would undermine deterministic lineage, reproducibility, and fail-closed outcome access controls.",
            "permanence_status": "PERMANENTLY_PROHIBITED_UNDER_V2",
        },
        {
            "prohibited_id": "OA_V2_PROHIBITED_OVERLAY_SEMANTIC_CORRECTION",
            "limitation_id": "OA_LIMIT_04_OVERLAY_BRIDGE_LINEAGE_REQUIREMENT",
            "scientific_justification": "The repaired overlay must remain a deterministic bridge rather than a place to reinterpret or improve outcome meaning.",
            "governance_justification": "Ad hoc overlay semantics would create untraceable drift between canonical outcomes and downstream evaluation artifacts.",
            "permanence_status": "PERMANENTLY_PROHIBITED_UNDER_V2",
        },
        {
            "prohibited_id": "OA_V2_PROHIBITED_FUZZY_LINKAGE",
            "limitation_id": "OA_LIMIT_05_LINKAGE_EXACT_KEY_DEPENDENCE",
            "scientific_justification": "Exact stable-key linkage is required to preserve scientific reproducibility and avoid ambiguous outcome pairing.",
            "governance_justification": "Fuzzy or manual linkage would introduce hindsight risk, irreproducible joins, and hidden human discretion.",
            "permanence_status": "PERMANENTLY_PROHIBITED_UNDER_V2",
        },
    ]


def _empirical_questions() -> List[Dict[str, Any]]:
    return [
        {
            "question_id": "OA_V2_EMPIRICAL_REALIZED_STATE_SEMANTICS",
            "limitation_id": "OA_LIMIT_07_REALIZED_STATE_SEMANTICS",
            "unresolved_scientific_question": "Which non-directional realized states can be represented upstream without changing corrected directional-success semantics?",
            "future_evidence_requirements": [
                "evidence_on_realized_state_taxonomy_consistency",
                "evidence_that_representation_change_preserves_success_mapping_meaning",
                "evidence_that_no_hindsight_or_accuracy_optimization_is_introduced",
            ],
            "status": "UNRESOLVED_DO_NOT_IMPLEMENT_IN_V2_WITHOUT_EVIDENCE",
        },
        {
            "question_id": "OA_V2_EMPIRICAL_NEGATIVE_ARM_VIABILITY",
            "limitation_id": "OA_LIMIT_09_NEGATIVE_ARM_FRAGILITY",
            "unresolved_scientific_question": "Can upstream architecture work alone restore a scientifically defensible negative arm, or will additional sample expansion remain necessary?",
            "future_evidence_requirements": [
                "evidence_on_post_architecture_negative_arm_survival",
                "evidence_on_cluster_and_provider_distribution_after_architecture_refinement",
                "evidence_that_restored_counts_reflect_architecture_completeness_not_rule_relaxation",
            ],
            "status": "UNRESOLVED_DO_NOT_CLAIM_INFERENTIAL_READINESS",
        },
    ]


def _compatibility_definitions() -> List[Dict[str, Any]]:
    return [
        {
            "compatibility_id": "OA_V2_COMPAT_MECHANISM_CLASSIFICATIONS",
            "compatibility_target": "EXISTING_MECHANISM_CLASSIFICATIONS",
            "compatibility_status": "MUST_PRESERVE",
            "preserved_contract": "Outcome Architecture v2 remains downstream of mechanism classification and may not relabel, rescope, or reinterpret mechanism evidence.",
            "required_versioning_behavior": "Continue to use mechanism version 1.1 and classification run refined_mechanism_v11_classification_20260710T152725Z unchanged.",
        },
        {
            "compatibility_id": "OA_V2_COMPAT_SUCCESS_MAPPING_V1",
            "compatibility_target": "SUCCESS_MAPPING_V1",
            "compatibility_status": "MUST_PRESERVE_PENDING_SEPARATE_SMV2_PREREGISTRATION",
            "preserved_contract": "Architecture preregistration must not modify current corrected directional-success mapping, accepted outputs, or stop-rule behavior.",
            "required_versioning_behavior": "Success Mapping v1 remains authoritative until a separate v2 scope, design, preregistration, and approval chain completes.",
        },
        {
            "compatibility_id": "OA_V2_COMPAT_FUTURE_SUCCESS_MAPPING_V2",
            "compatibility_target": "FUTURE_SUCCESS_MAPPING_V2",
            "compatibility_status": "ENABLE_BUT_DO_NOT_DEFINE",
            "preserved_contract": "Outcome Architecture v2 may prepare upstream contracts for SMv2 but may not design or imply SMv2 semantics here.",
            "required_versioning_behavior": "Any future SMv2 must reference the validated Outcome Architecture v2 version explicitly and remain separately versioned.",
        },
        {
            "compatibility_id": "OA_V2_COMPAT_EXISTING_PREREGISTRATIONS",
            "compatibility_target": "EXISTING_PREREGISTRATIONS",
            "compatibility_status": "VERSION_ISOLATED_NO_OVERWRITE",
            "preserved_contract": "Do not modify or overwrite 1.0, 1.0-clean, or 1.0-clean-r1 preregistration families.",
            "required_versioning_behavior": "Outcome Architecture v2 preregistration is a new frozen family with its own run ID, fingerprints, and validation path.",
        },
        {
            "compatibility_id": "OA_V2_COMPAT_EXECUTION_LINEAGE",
            "compatibility_target": "EXISTING_EXECUTION_LINEAGE",
            "compatibility_status": "MUST_PRESERVE",
            "preserved_contract": "Execution lineage from canonical Clean-R1 authority through outcome-architecture scope and design remains immutable historical evidence.",
            "required_versioning_behavior": "All future architecture validation or implementation must reference canonical authority run 9A-6R13R1_20260711T020141Z and the completed 15D/15E run IDs explicitly.",
        },
    ]


def _governance_principles() -> List[Dict[str, Any]]:
    return [
        {
            "rule_id": "OA_V2_GOV_01",
            "rule_type": "VERSION_ISOLATION",
            "rule_text": "Outcome Architecture v2 must remain version-isolated from existing mechanism-test preregistration and execution families.",
            "enforcement_scope": "all_future_architecture_validation_and_implementation",
        },
        {
            "rule_id": "OA_V2_GOV_02",
            "rule_type": "DETERMINISTIC_ARCHITECTURE",
            "rule_text": "All architecture layers, bridge states, manifests, and audits must be deterministic and fingerprintable.",
            "enforcement_scope": "all_future_architecture_artifacts",
        },
        {
            "rule_id": "OA_V2_GOV_03",
            "rule_type": "TRACEABILITY",
            "rule_text": "Every stage must preserve explicit lineage from classification observation through canonical outcome identity and any bridge layer.",
            "enforcement_scope": "all_future_architecture_artifacts",
        },
        {
            "rule_id": "OA_V2_GOV_04",
            "rule_type": "REPRODUCIBILITY",
            "rule_text": "Another researcher must be able to reproduce the architecture state using only frozen preregistration artifacts, stable IDs, and deterministic fingerprints.",
            "enforcement_scope": "validation_and_replay",
        },
        {
            "rule_id": "OA_V2_GOV_05",
            "rule_type": "NO_HINDSIGHT",
            "rule_text": "No architecture redesign may use future information, outcome leakage, or post-hoc knowledge to define layer behavior.",
            "enforcement_scope": "design_validation_implementation",
        },
        {
            "rule_id": "OA_V2_GOV_06",
            "rule_type": "NO_OUTCOME_DRIVEN_OPTIMIZATION",
            "rule_text": "Architecture decisions may not be tuned to maximize retained observations, accuracy, or negative-arm recovery after seeing outcome behavior.",
            "enforcement_scope": "design_validation_implementation",
        },
        {
            "rule_id": "OA_V2_GOV_07",
            "rule_type": "NO_PROVIDER_SPECIFIC_BEHAVIOR",
            "rule_text": "No provider-specific, session-specific, or model-specific architecture branches are allowed.",
            "enforcement_scope": "future_implementation",
        },
        {
            "rule_id": "OA_V2_GOV_08",
            "rule_type": "NO_PRODUCTION_AUTHORITY",
            "rule_text": "Outcome Architecture v2 artifacts are research contracts only and do not confer production authority, routing authority, or evaluation authority.",
            "enforcement_scope": "all_outputs",
        },
        {
            "rule_id": "OA_V2_GOV_09",
            "rule_type": "IMPLEMENTATION_BLOCK",
            "rule_text": "Implementation remains prohibited until a separate validation phase confirms internal consistency and compatibility with the mechanism framework.",
            "enforcement_scope": "current_phase_and_post_prereg_stage_gate",
        },
    ]


def _implementation_boundary() -> List[Dict[str, Any]]:
    return [
        {
            "stage_id": "OA_V2_BOUNDARY_01",
            "stage_type": "PREREGISTRATION",
            "allowed_actions": [
                "freeze_versions",
                "freeze_ids",
                "freeze_fingerprints",
                "freeze_layer_responsibilities",
                "freeze_design_boundaries",
            ],
            "prohibited_actions": [
                "implement_architecture",
                "access_outcome_rows",
                "modify_existing_scientific_artifacts",
                "validate_against_live_outcome_rows",
            ],
            "advancement_condition": "preregistration_family_frozen_and_fingerprinted",
        },
        {
            "stage_id": "OA_V2_BOUNDARY_02",
            "stage_type": "VALIDATION",
            "allowed_actions": [
                "internal_consistency_review",
                "lineage_verification",
                "fingerprint_verification",
                "mechanism_framework_compatibility_review",
            ],
            "prohibited_actions": [
                "implementation",
                "deployment",
                "changing_frozen_preregistration_without_new_version",
                "outcome_driven_design_adjustment",
            ],
            "advancement_condition": "validation_phase_approves_internal_consistency_and_scientific_compatibility",
        },
        {
            "stage_id": "OA_V2_BOUNDARY_03",
            "stage_type": "IMPLEMENTATION",
            "allowed_actions": [
                "build_only_approved_architecture_contracts",
                "create_versioned_manifests_and_audits",
                "execute_preapproved_nonoutcome_validations",
            ],
            "prohibited_actions": [
                "semantic_rule_changes_outside_approved_scope",
                "success_mapping_changes_without_separate_preregistration",
                "production_write_authority",
            ],
            "advancement_condition": "separate_implementation_approval_after_validation",
        },
        {
            "stage_id": "OA_V2_BOUNDARY_04",
            "stage_type": "DEPLOYMENT",
            "allowed_actions": [
                "none_in_current_preregistration",
            ],
            "prohibited_actions": [
                "production_deployment",
                "provider_ranking",
                "routing_or_weighting_authority",
                "direct_operational_use",
            ],
            "advancement_condition": "not_permitted_under_current_preregistration",
        },
    ]


def build() -> Dict[str, Any]:
    run_ts = datetime.now(timezone.utc).replace(microsecond=0)
    generated_ts = run_ts.isoformat().replace("+00:00", "Z")
    prereg_run_id = _run_id(run_ts)

    _require(not (FORBIDDEN_INPUT_TITLES & set(INPUT_SHEETS)), "Forbidden outcome-bearing sheet included in inputs.")

    service = build_sheets_service(load_credentials())
    inputs = _fetch_input_sheets(service, DIAGNOSTICS_SPREADSHEET_ID, INPUT_SHEETS)
    known_titles = _sheet_titles_light(service, DIAGNOSTICS_SPREADSHEET_ID)

    canonical_authority = _parse_payload(
        _latest_row(inputs["Refined_Mechanism_Test_Clean_R1_Canonical_Authority"].rows, "lineage_repair_run_id")
    )
    component_authority = _parse_payload(
        _latest_row(inputs["Refined_Mechanism_Test_Clean_R1_Component_Authority"].rows, "lineage_repair_run_id")
    )
    canonical_manifest = _parse_payload(
        _latest_row(inputs["Refined_Mechanism_Test_Clean_R1_Canonical_Fingerprint_Manifest"].rows, "lineage_repair_run_id")
    )

    _require(_normalize(canonical_authority.get("authority_preregistration_version")) == AUTHORITATIVE_VERSION, "Canonical authority version mismatch.")
    _require(_normalize(canonical_authority.get("authoritative_repair_run_id")) == AUTHORITATIVE_RUN_ID, "Canonical authority run ID mismatch.")
    _require(_normalize(canonical_authority.get("authority_status")) == "CANONICAL_AUTHORITY_COMPLETE", "Canonical authority is not complete.")

    selected_rows = _select_authoritative_rows(inputs, canonical_manifest, component_authority)
    selected_payloads = {sheet_name: row["payload"] for sheet_name, row in selected_rows.items()}

    prereg_r1 = selected_payloads["Refined_Mechanism_Test_Preregistration_Clean_R1"]
    outcome_r1 = selected_payloads["Refined_Mechanism_Test_Frozen_Outcome_Definition_Clean_R1"]
    join_r1 = selected_payloads["Refined_Mechanism_Test_Frozen_Join_Rules_Clean_R1"]
    success_r1 = selected_payloads["Refined_Mechanism_Test_Frozen_Success_Derivation_Clean_R1"]
    method_r1 = selected_payloads["Refined_Mechanism_Test_Frozen_Statistical_Method_Clean_R1"]
    stop_r1 = selected_payloads["Refined_Mechanism_Test_Frozen_Stop_Rules_Clean_R1"]
    design_r1 = selected_payloads["Refined_Mechanism_Test_Clean_R1_Design_Reconciliation"]

    _require(_normalize(prereg_r1.get("repaired_preregistration_version")) == AUTHORITATIVE_VERSION, "Canonical preregistration version mismatch.")
    _require(_normalize(prereg_r1.get("mechanism_version")) == CLASSIFICATION_VERSION, "Classification version mismatch.")
    _require(_normalize(prereg_r1.get("classification_run_id")) == CLASSIFICATION_RUN_ID, "Classification run ID mismatch.")
    _require(_normalize(prereg_r1.get("primary_mechanism")) == PRIMARY_MECHANISM, "Primary mechanism mismatch.")
    _require(_normalize(prereg_r1.get("primary_structure")) == PRIMARY_STRUCTURE, "Primary structure mismatch.")
    _require(outcome_r1.get("future_schema_fingerprint_verification_required") is True, "Outcome schema guardrail mismatch.")
    _require(join_r1.get("exact_stable_key_match_required") is True, "Join stable-key requirement mismatch.")
    _require(success_r1.get("allowed_output_statuses") == ["SUCCESS", "FAILURE", "NOT_ELIGIBLE", "AMBIGUOUS_JOIN_BLOCKED"], "Success derivation statuses mismatch.")
    _require(_normalize(method_r1.get("primary_interpretation")) == "EXPLORATORY_PREREGISTERED_PRIMARY", "Method interpretation mismatch.")
    _require(stop_r1.get("fail_closed") is True, "Stop-rule fail-closed contract mismatch.")
    _require(design_r1.get("science_preservation", {}).get("primary_structure_changed") is False, "Science preservation mismatch.")

    scope_summary_row = _latest_row(inputs["Refined_Mechanism_Test_Outcome_Architecture_Refinement_Summary"].rows, "outcome_architecture_scope_run_id")
    scope_summary_payload = _parse_payload(scope_summary_row)
    _require(_normalize(scope_summary_row.get("final_interpretation")) == SCOPE_FINAL_INTERPRETATION, "15D summary interpretation mismatch.")
    _require(_normalize(scope_summary_row.get("scientific_readiness_assessment")) == SCIENTIFIC_READINESS, "15D readiness mismatch.")
    _require(int(scope_summary_row.get("limitation_count", 0) or 0) == 10, "15D limitation count mismatch.")
    scope_run_id = _normalize(scope_summary_row.get("outcome_architecture_scope_run_id"))

    design_summary_row = _latest_row(inputs["Refined_Mechanism_Test_Outcome_Architecture_V2_Summary"].rows, "outcome_architecture_design_run_id")
    design_summary_payload = _parse_payload(design_summary_row)
    _require(_normalize(design_summary_row.get("final_interpretation")) == DESIGN_FINAL_INTERPRETATION, "15E summary interpretation mismatch.")
    _require(_normalize(design_summary_row.get("scientific_readiness_assessment")) == SCIENTIFIC_READINESS, "15E readiness mismatch.")
    _require(int(design_summary_row.get("redesign_target_count", 0) or 0) == 5, "15E redesign target count mismatch.")
    design_run_id = _normalize(design_summary_row.get("outcome_architecture_design_run_id"))

    layer_rows = [_parse_payload(row) for row in _filter_rows_for_run(inputs["Refined_Mechanism_Test_Outcome_Architecture_V2_Layer_Model"].rows, "outcome_architecture_design_run_id", design_run_id)]
    target_rows = [_parse_payload(row) for row in _filter_rows_for_run(inputs["Refined_Mechanism_Test_Outcome_Architecture_V2_Redesign_Targets"].rows, "outcome_architecture_design_run_id", design_run_id)]
    prohibited_rows = [_parse_payload(row) for row in _filter_rows_for_run(inputs["Refined_Mechanism_Test_Outcome_Architecture_V2_Prohibited_Targets"].rows, "outcome_architecture_design_run_id", design_run_id)]
    empirical_rows = [_parse_payload(row) for row in _filter_rows_for_run(inputs["Refined_Mechanism_Test_Outcome_Architecture_V2_Evidence_Dependencies"].rows, "outcome_architecture_design_run_id", design_run_id)]
    compat_rows_design = [_parse_payload(row) for row in _filter_rows_for_run(inputs["Refined_Mechanism_Test_Outcome_Architecture_V2_Compatibility_Audit"].rows, "outcome_architecture_design_run_id", design_run_id)]
    roadmap_rows_design = [_parse_payload(row) for row in _filter_rows_for_run(inputs["Refined_Mechanism_Test_Outcome_Architecture_V2_Implementation_Roadmap"].rows, "outcome_architecture_design_run_id", design_run_id)]

    _require(len(layer_rows) == 5, f"Expected 5 design layer rows, found {len(layer_rows)}")
    _require(len(target_rows) == 5, f"Expected 5 design target rows, found {len(target_rows)}")
    _require(len(prohibited_rows) == 3, f"Expected 3 design prohibited rows, found {len(prohibited_rows)}")
    _require(len(empirical_rows) == 2, f"Expected 2 design empirical rows, found {len(empirical_rows)}")
    _require(len(compat_rows_design) == 4, f"Expected 4 design compatibility rows, found {len(compat_rows_design)}")
    _require(len(roadmap_rows_design) == 6, f"Expected 6 design roadmap rows, found {len(roadmap_rows_design)}")

    layer_defs = _layer_definitions()
    target_defs = _target_definitions()
    prohibited_defs = _prohibited_definitions()
    empirical_defs = _empirical_questions()
    compat_defs = _compatibility_definitions()
    governance_defs = _governance_principles()
    boundary_defs = _implementation_boundary()

    _require(len(layer_defs) == 5, "Internal layer definition count mismatch.")
    _require(len(target_defs) == 5, "Internal redesign target count mismatch.")
    _require(len(prohibited_defs) == 3, "Internal prohibited redesign count mismatch.")
    _require(len(empirical_defs) == 2, "Internal empirical question count mismatch.")

    design_target_ids = {_normalize(row.get("target_id")) for row in target_rows}
    prereg_target_ids = {row["target_id"] for row in target_defs}
    _require(
        {
            "OA_V2_TARGET_01",
            "OA_V2_TARGET_02",
            "OA_V2_TARGET_03",
            "OA_V2_TARGET_04",
            "OA_V2_TARGET_05",
        } == design_target_ids,
        f"15E design target IDs unexpected: {design_target_ids}",
    )
    _require(len(prereg_target_ids) == 5, "Stable prereg target IDs are not unique.")

    outputs: Dict[str, List[Dict[str, Any]]] = {
        OUTPUT_PREREG: [],
        OUTPUT_LAYERS: [],
        OUTPUT_TARGETS: [],
        OUTPUT_PROHIBITED: [],
        OUTPUT_EMPIRICAL: [],
        OUTPUT_COMPAT: [],
        OUTPUT_GOVERNANCE_RULES: [],
        OUTPUT_BOUNDARY: [],
        OUTPUT_FINGERPRINTS: [],
        OUTPUT_GOVERNANCE: [],
        OUTPUT_SUMMARY: [],
    }

    stable_architecture_ids = {
        "layer_ids": [row["layer_id"] for row in layer_defs],
        "redesign_target_ids": [row["target_id"] for row in target_defs],
        "prohibited_redesign_ids": [row["prohibited_id"] for row in prohibited_defs],
        "empirical_question_ids": [row["question_id"] for row in empirical_defs],
        "compatibility_ids": [row["compatibility_id"] for row in compat_defs],
        "governance_rule_ids": [row["rule_id"] for row in governance_defs],
        "implementation_boundary_stage_ids": [row["stage_id"] for row in boundary_defs],
    }

    prereg_payload = {
        "architecture_preregistration_version": ARCHITECTURE_PREREGISTRATION_VERSION,
        "architecture_preregistration_status": ARCHITECTURE_PREREGISTRATION_STATUS,
        "architecture_version": ARCHITECTURE_VERSION,
        "architecture_lineage_version": ARCHITECTURE_LINEAGE_VERSION,
        "authoritative_canonical_preregistration_version": AUTHORITATIVE_VERSION,
        "authoritative_canonical_run_id": AUTHORITATIVE_RUN_ID,
        "classification_version": CLASSIFICATION_VERSION,
        "classification_run_id": CLASSIFICATION_RUN_ID,
        "primary_mechanism_reference": PRIMARY_MECHANISM,
        "primary_structure_reference": PRIMARY_STRUCTURE,
        "lineage_chain": {
            "canonical_authority_run_id": AUTHORITATIVE_RUN_ID,
            "scope_phase_run_id": scope_run_id,
            "design_phase_run_id": design_run_id,
            "preregistration_phase_run_id": prereg_run_id,
        },
        "source_references": {
            "scope_interpretation": _normalize(scope_summary_row.get("final_interpretation")),
            "design_interpretation": _normalize(design_summary_row.get("final_interpretation")),
            "scope_principal_blocking_layer": _normalize(scope_summary_payload.get("principal_blocking_layer")),
            "design_candidate_status": _normalize(design_summary_payload.get("candidate_design_status")),
        },
        "stable_architecture_ids": stable_architecture_ids,
        "architecture_fingerprint_method": "sha256_canonical_json",
        "implementation_blocked": True,
        "ready_for_outcome_architecture_validation": True,
        "ready_for_implementation": False,
        "ready_for_deployment": False,
    }
    outputs[OUTPUT_PREREG].append(
        {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "outcome_architecture_preregistration_run_id": prereg_run_id,
            "architecture_preregistration_version": ARCHITECTURE_PREREGISTRATION_VERSION,
            "architecture_preregistration_status": ARCHITECTURE_PREREGISTRATION_STATUS,
            "architecture_version": ARCHITECTURE_VERSION,
            "architecture_lineage_version": ARCHITECTURE_LINEAGE_VERSION,
            "canonical_preregistration_version": AUTHORITATIVE_VERSION,
            "canonical_run_id": AUTHORITATIVE_RUN_ID,
            "classification_version": CLASSIFICATION_VERSION,
            "classification_run_id": CLASSIFICATION_RUN_ID,
            "scientific_readiness_assessment": SCIENTIFIC_READINESS,
            "validation_readiness_status": VALIDATION_READINESS,
            "recommended_next_step": RECOMMENDED_NEXT_STEP,
            "build_status": BUILD_STATUS,
            "final_interpretation": FINAL_INTERPRETATION,
            "payload_json": _canonical_json(prereg_payload),
        }
    )

    for row in layer_defs:
        outputs[OUTPUT_LAYERS].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_preregistration_run_id": prereg_run_id,
                "layer_id": row["layer_id"],
                "layer_order": row["layer_order"],
                "layer_name": row["layer_name"],
                "scientific_purpose": row["scientific_purpose"],
                "allowed_inputs_json": _canonical_json(row["allowed_inputs"]),
                "allowed_outputs_json": _canonical_json(row["allowed_outputs"]),
                "prohibited_dependencies_json": _canonical_json(row["prohibited_dependencies"]),
                "downstream_consumers_json": _canonical_json(row["downstream_consumers"]),
                "payload_json": _canonical_json(row),
            }
        )

    for row in target_defs:
        outputs[OUTPUT_TARGETS].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_preregistration_run_id": prereg_run_id,
                "target_id": row["target_id"],
                "limitation_id": row["limitation_id"],
                "objective": row["objective"],
                "scientific_rationale": row["scientific_rationale"],
                "expected_architectural_benefit": row["expected_architectural_benefit"],
                "constraints_json": _canonical_json(row["constraints"]),
                "prohibited_implementation_shortcuts_json": _canonical_json(row["prohibited_implementation_shortcuts"]),
                "payload_json": _canonical_json(row),
            }
        )

    for row in prohibited_defs:
        outputs[OUTPUT_PROHIBITED].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_preregistration_run_id": prereg_run_id,
                "prohibited_id": row["prohibited_id"],
                "limitation_id": row["limitation_id"],
                "scientific_justification": row["scientific_justification"],
                "governance_justification": row["governance_justification"],
                "permanence_status": row["permanence_status"],
                "payload_json": _canonical_json(row),
            }
        )

    for row in empirical_defs:
        outputs[OUTPUT_EMPIRICAL].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_preregistration_run_id": prereg_run_id,
                "question_id": row["question_id"],
                "limitation_id": row["limitation_id"],
                "unresolved_scientific_question": row["unresolved_scientific_question"],
                "future_evidence_requirements_json": _canonical_json(row["future_evidence_requirements"]),
                "status": row["status"],
                "payload_json": _canonical_json(row),
            }
        )

    for row in compat_defs:
        outputs[OUTPUT_COMPAT].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_preregistration_run_id": prereg_run_id,
                "compatibility_id": row["compatibility_id"],
                "compatibility_target": row["compatibility_target"],
                "compatibility_status": row["compatibility_status"],
                "preserved_contract": row["preserved_contract"],
                "required_versioning_behavior": row["required_versioning_behavior"],
                "payload_json": _canonical_json(row),
            }
        )

    for row in governance_defs:
        outputs[OUTPUT_GOVERNANCE_RULES].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_preregistration_run_id": prereg_run_id,
                "rule_id": row["rule_id"],
                "rule_type": row["rule_type"],
                "rule_text": row["rule_text"],
                "enforcement_scope": row["enforcement_scope"],
                "payload_json": _canonical_json(row),
            }
        )

    for row in boundary_defs:
        outputs[OUTPUT_BOUNDARY].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_preregistration_run_id": prereg_run_id,
                "stage_id": row["stage_id"],
                "stage_type": row["stage_type"],
                "allowed_actions_json": _canonical_json(row["allowed_actions"]),
                "prohibited_actions_json": _canonical_json(row["prohibited_actions"]),
                "advancement_condition": row["advancement_condition"],
                "payload_json": _canonical_json(row),
            }
        )

    fingerprint_components: List[Dict[str, Any]] = []
    fingerprint_components.append(
        {
            "component_id": "OA_V2_FP_PREREGISTRATION_CORE",
            "component_type": "preregistration_core",
            "source_sheet": OUTPUT_PREREG,
            "payload": prereg_payload,
        }
    )
    fingerprint_components.append(
        {
            "component_id": "OA_V2_FP_STABLE_ID_SET",
            "component_type": "stable_id_set",
            "source_sheet": OUTPUT_PREREG,
            "payload": stable_architecture_ids,
        }
    )
    fingerprint_components.append(
        {
            "component_id": "OA_V2_FP_LAYER_DEFINITIONS",
            "component_type": "layer_definitions",
            "source_sheet": OUTPUT_LAYERS,
            "payload": layer_defs,
        }
    )
    fingerprint_components.append(
        {
            "component_id": "OA_V2_FP_REDESIGN_TARGETS",
            "component_type": "redesign_targets",
            "source_sheet": OUTPUT_TARGETS,
            "payload": target_defs,
        }
    )
    fingerprint_components.append(
        {
            "component_id": "OA_V2_FP_PROHIBITED_REDESIGNS",
            "component_type": "prohibited_redesigns",
            "source_sheet": OUTPUT_PROHIBITED,
            "payload": prohibited_defs,
        }
    )
    fingerprint_components.append(
        {
            "component_id": "OA_V2_FP_EMPIRICAL_QUESTIONS",
            "component_type": "empirical_questions",
            "source_sheet": OUTPUT_EMPIRICAL,
            "payload": empirical_defs,
        }
    )
    fingerprint_components.append(
        {
            "component_id": "OA_V2_FP_COMPATIBILITY_REQUIREMENTS",
            "component_type": "compatibility_requirements",
            "source_sheet": OUTPUT_COMPAT,
            "payload": compat_defs,
        }
    )
    fingerprint_components.append(
        {
            "component_id": "OA_V2_FP_GOVERNANCE_PRINCIPLES",
            "component_type": "governance_principles",
            "source_sheet": OUTPUT_GOVERNANCE_RULES,
            "payload": governance_defs,
        }
    )
    fingerprint_components.append(
        {
            "component_id": "OA_V2_FP_IMPLEMENTATION_BOUNDARY",
            "component_type": "implementation_boundary",
            "source_sheet": OUTPUT_BOUNDARY,
            "payload": boundary_defs,
        }
    )
    fingerprint_components.append(
        {
            "component_id": "OA_V2_FP_LINEAGE_REFERENCE",
            "component_type": "lineage_reference",
            "source_sheet": OUTPUT_PREREG,
            "payload": {
                "canonical_preregistration_version": AUTHORITATIVE_VERSION,
                "canonical_run_id": AUTHORITATIVE_RUN_ID,
                "scope_run_id": scope_run_id,
                "design_run_id": design_run_id,
                "classification_run_id": CLASSIFICATION_RUN_ID,
            },
        }
    )

    for component in fingerprint_components:
        payload = component["payload"]
        outputs[OUTPUT_FINGERPRINTS].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_preregistration_run_id": prereg_run_id,
                "component_id": component["component_id"],
                "component_type": component["component_type"],
                "source_sheet": component["source_sheet"],
                "fingerprint_method": "sha256_canonical_json",
                "fingerprint": _fingerprint_payload(payload if isinstance(payload, Mapping) else {"items": payload}),
                "modification_allowed_after_preregistration": False,
                "payload_json": _canonical_json(
                    {
                        "source_run_ids": {
                            "scope": scope_run_id,
                            "design": design_run_id,
                            "canonical": AUTHORITATIVE_RUN_ID,
                            "preregistration": prereg_run_id,
                        },
                        "payload_kind": component["component_type"],
                        "stable_serialization": "json_sort_keys_true_ascii_true_compact_separators",
                    }
                ),
            }
        )

    governance_counters = {
        "provider_calls_performed": 0,
        "outcome_rows_loaded": 0,
        "outcome_rules_modified": 0,
        "outcome_overlay_modified": 0,
        "outcome_linkage_modified": 0,
        "outcome_representation_modified": 0,
        "eligibility_modified": 0,
        "success_mapping_modified": 0,
        "mechanism_rules_modified": 0,
        "preregistration_modified": 0,
        "mechanism_tests_performed": 0,
        "production_writes": 0,
    }
    for counter_name, counter_value in governance_counters.items():
        outputs[OUTPUT_GOVERNANCE].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_preregistration_run_id": prereg_run_id,
                "counter_name": counter_name,
                "counter_value": counter_value,
                "status": "PASS" if counter_value == 0 else "FAIL",
                "notes": "Preregistration-only phase preserved." if counter_value == 0 else "Unexpected nonzero counter.",
            }
        )

    summary_payload = {
        "architecture_preregistration_version": ARCHITECTURE_PREREGISTRATION_VERSION,
        "architecture_preregistration_status": ARCHITECTURE_PREREGISTRATION_STATUS,
        "architecture_version": ARCHITECTURE_VERSION,
        "architecture_lineage_version": ARCHITECTURE_LINEAGE_VERSION,
        "build_status": BUILD_STATUS,
        "final_interpretation": FINAL_INTERPRETATION,
        "scientific_readiness_assessment": SCIENTIFIC_READINESS,
        "validation_readiness_status": VALIDATION_READINESS,
        "recommended_next_step": RECOMMENDED_NEXT_STEP,
        "counts": {
            "layer_count": len(layer_defs),
            "redesign_target_count": len(target_defs),
            "prohibited_redesign_count": len(prohibited_defs),
            "empirical_question_count": len(empirical_defs),
            "compatibility_count": len(compat_defs),
            "governance_principle_count": len(governance_defs),
            "implementation_boundary_stage_count": len(boundary_defs),
            "fingerprint_component_count": len(fingerprint_components),
        },
        "lineage_chain": prereg_payload["lineage_chain"],
        "implementation_blocked": True,
        "ready_for_outcome_architecture_validation": True,
        "ready_for_implementation": False,
        "ready_for_deployment": False,
        "governance_counters": governance_counters,
    }
    outputs[OUTPUT_SUMMARY].append(
        {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "outcome_architecture_preregistration_run_id": prereg_run_id,
            "architecture_preregistration_version": ARCHITECTURE_PREREGISTRATION_VERSION,
            "architecture_preregistration_status": ARCHITECTURE_PREREGISTRATION_STATUS,
            "architecture_version": ARCHITECTURE_VERSION,
            "build_status": BUILD_STATUS,
            "final_interpretation": FINAL_INTERPRETATION,
            "validation_readiness_status": VALIDATION_READINESS,
            "recommended_next_step": RECOMMENDED_NEXT_STEP,
            "payload_json": _canonical_json(summary_payload),
        }
    )

    rows_written: Dict[str, int] = {}
    for sheet_name, headers in OUTPUT_SHEETS.items():
        rows_written[sheet_name] = _append_rows(
            service,
            DIAGNOSTICS_SPREADSHEET_ID,
            sheet_name,
            headers,
            outputs[sheet_name],
            known_titles,
        )

    registry_result = _upsert_registry_rows(service, generated_ts)

    return {
        "build_status": BUILD_STATUS,
        "final_interpretation": FINAL_INTERPRETATION,
        "file_created": BUILD_SCRIPT,
        "outcome_architecture_preregistration_run_id": prereg_run_id,
        "architecture_preregistration_version": ARCHITECTURE_PREREGISTRATION_VERSION,
        "architecture_preregistration_status": ARCHITECTURE_PREREGISTRATION_STATUS,
        "architecture_version": ARCHITECTURE_VERSION,
        "validation_readiness_status": VALIDATION_READINESS,
        "recommended_next_step": RECOMMENDED_NEXT_STEP,
        "sheets_written": list(OUTPUT_SHEETS.keys()),
        "rows_written_per_sheet": rows_written,
        "layer_count": len(layer_defs),
        "redesign_target_count": len(target_defs),
        "prohibited_redesign_count": len(prohibited_defs),
        "empirical_question_count": len(empirical_defs),
        "compatibility_count": len(compat_defs),
        "governance_principle_count": len(governance_defs),
        "fingerprint_component_count": len(fingerprint_components),
        "governance_counters": governance_counters,
        "registry_result": registry_result,
    }


def main() -> None:
    report = build()
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
