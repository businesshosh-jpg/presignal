#!/usr/bin/env python3
"""Phase 9A-6R15D — Outcome Architecture Refinement Scoping.

This phase defines the preregistered scientific scope required before any
Outcome Architecture redesign begins. It remains fully read-only with respect
to outcome rows, mechanism rules, preregistrations, and production outputs.
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


PHASE_ID = "9A-6R15D"
BUILD_SCRIPT = "automation/build_refined_mechanism_test_outcome_architecture_refinement_scoping_v0.py"
SCHEMA_VERSION = "presignal_v2_refined_mechanism_test_outcome_architecture_refinement_scoping_v0"
SCOPE_VERSION = "refined_mechanism_test_outcome_architecture_refinement_scoping_v0"
REGISTRY_CATEGORY = "PRESIGNAL_V2_REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_SCOPE"
REGISTRY_OWNER_MODULE = "market_state"

AUTHORITATIVE_VERSION = "1.0-clean-r1"
AUTHORITATIVE_RUN_ID = "9A-6R13R1_20260711T020141Z"
CLASSIFICATION_VERSION = "1.1"
CLASSIFICATION_RUN_ID = "refined_mechanism_v11_classification_20260710T152725Z"
PRIMARY_MECHANISM = "MECH_INFORMATION_CONSISTENCY"
PRIMARY_STRUCTURE = "STRUCTURE_A_EXPANDED_STATE_GROUPED_DELTA_COMPARISON"

EXPECTED_COUNTS = {
    "planned_primary_observations": 72,
    "final_eligible_observations": 3,
    "outcome_join_losses": 22,
    "overlay_losses": 11,
    "success_mapping_losses": 36,
}

READINESS_READY = "READY_FOR_OUTCOME_ARCHITECTURE_DESIGN"
READINESS_CONSTRAINED = "READY_WITH_CONSTRAINTS"
READINESS_RESEARCH = "MORE_RESEARCH_REQUIRED"
READINESS_BLOCKED = "DO_NOT_REDESIGN"

CLASS_SCI_REQUIRED = "SCIENTIFICALLY_REQUIRED"
CLASS_POLICY = "POLICY_DECISION"
CLASS_HISTORY = "IMPLEMENTATION_HISTORY"
CLASS_EMPIRICAL = "UNRESOLVED_EMPIRICAL_QUESTION"

STATUS_PROHIBITED = "REDESIGN_PROHIBITED"
STATUS_ACCEPTABLE = "REDESIGN_SCIENTIFICALLY_ACCEPTABLE"
STATUS_EVIDENCE = "REDESIGN_REQUIRES_ADDITIONAL_EVIDENCE"

SEQUENCE_BEFORE = "BEFORE_SUCCESS_MAPPING_V2"
SEQUENCE_AFTER = "AFTER_SUCCESS_MAPPING_V2"
SEQUENCE_GUARDRAIL = "NOT_A_REDESIGN_TARGET"

FAMILY_CANONICAL = "CANONICAL_OUTCOME_LIMITATION"
FAMILY_OVERLAY = "OUTCOME_OVERLAY_LIMITATION"
FAMILY_LINKAGE = "OUTCOME_LINKAGE_LIMITATION"
FAMILY_REPRESENTATION = "OUTCOME_REPRESENTATION_LIMITATION"
FAMILY_INTERACTION = "ELIGIBILITY_INTERACTION_LIMITATION"

FORBIDDEN_INPUT_TITLES = {
    "Market_Reaction_Canonical_Outcomes",
    "Outcome_Ledger",
    "Evaluation_Rows",
    "Evaluation_Summary",
    "Corrected_Accuracy_Evaluation",
    "Controlled_Accuracy_Evaluation",
    "Refined_Mechanism_Test_Population_Collapse",
    "Refined_Mechanism_Test_Row_Lineage_Audit",
    "Refined_Mechanism_Test_Outcome_Join_Audit",
    "Refined_Mechanism_Test_Outcome_Join_Failure_Audit",
    "Refined_Mechanism_Test_Success_Mapping_Audit",
    "Refined_Mechanism_Test_Eligibility_Transition_Audit",
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
    "Refined_Mechanism_Test_Execution_Approval_Canonical_R1_Summary",
    "Refined_Mechanism_Test_Collapse_Summary",
    "Refined_Mechanism_Test_Outcome_Architecture_Summary",
    "Refined_Mechanism_Test_Success_Mapping_V2_Summary",
)

OUTPUT_SCOPE = "Refined_Mechanism_Test_Outcome_Architecture_Refinement_Scope"
OUTPUT_LIMITATIONS = "Refined_Mechanism_Test_Outcome_Architecture_Limitations"
OUTPUT_GRAPH = "Refined_Mechanism_Test_Outcome_Architecture_Dependency_Graph"
OUTPUT_PATHS = "Refined_Mechanism_Test_Outcome_Architecture_Refinement_Paths"
OUTPUT_CONSTRAINTS = "Refined_Mechanism_Test_Outcome_Architecture_Scientific_Constraints"
OUTPUT_DECISIONS = "Refined_Mechanism_Test_Outcome_Architecture_Decision_Framework"
OUTPUT_ROADMAP = "Refined_Mechanism_Test_Outcome_Architecture_Research_Roadmap"
OUTPUT_GOVERNANCE = "Refined_Mechanism_Test_Outcome_Architecture_Refinement_Governance"
OUTPUT_SUMMARY = "Refined_Mechanism_Test_Outcome_Architecture_Refinement_Summary"

OUTPUT_SHEETS: Dict[str, List[str]] = {
    OUTPUT_SCOPE: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_scope_run_id",
        "scope_version",
        "canonical_preregistration_version",
        "canonical_run_id",
        "classification_version",
        "classification_run_id",
        "scientific_readiness_assessment",
        "recommended_next_step",
        "build_status",
        "final_interpretation",
        "payload_json",
    ],
    OUTPUT_LIMITATIONS: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_scope_run_id",
        "limitation_id",
        "limitation_family",
        "limitation_title",
        "blocking_role",
        "first_hit_impact_count",
        "limitation_classification",
        "redesign_status",
        "preferred_sequence",
        "should_occur_before_success_mapping_v2",
        "should_occur_after_success_mapping_v2",
        "payload_json",
    ],
    OUTPUT_GRAPH: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_scope_run_id",
        "edge_id",
        "from_layer",
        "to_layer",
        "dependency_type",
        "blocking_inference",
        "blocking_reason",
        "payload_json",
    ],
    OUTPUT_PATHS: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_scope_run_id",
        "path_id",
        "refinement_path",
        "current_problem",
        "readiness_status",
        "relation_to_success_mapping_v2",
        "payload_json",
    ],
    OUTPUT_CONSTRAINTS: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_scope_run_id",
        "constraint_id",
        "constraint_type",
        "constraint_text",
        "violation_status",
        "payload_json",
    ],
    OUTPUT_DECISIONS: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_scope_run_id",
        "decision_option",
        "decision_status",
        "triggering_conditions",
        "required_preconditions",
        "payload_json",
    ],
    OUTPUT_ROADMAP: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_scope_run_id",
        "stage_order",
        "stage_name",
        "stage_objective",
        "stage_prerequisite",
        "stage_not_allowed",
        "payload_json",
    ],
    OUTPUT_GOVERNANCE: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_scope_run_id",
        "counter_name",
        "counter_value",
        "status",
        "notes",
    ],
    OUTPUT_SUMMARY: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_scope_run_id",
        "build_status",
        "final_interpretation",
        "scientific_readiness_assessment",
        "recommended_next_step",
        "principal_blocking_layer",
        "limitation_count",
        "payload_json",
    ],
}

OUTPUT_LOGICAL_IDS = {
    OUTPUT_SCOPE: "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_REFINEMENT_SCOPE",
    OUTPUT_LIMITATIONS: "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_LIMITATIONS",
    OUTPUT_GRAPH: "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_DEPENDENCY_GRAPH",
    OUTPUT_PATHS: "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_REFINEMENT_PATHS",
    OUTPUT_CONSTRAINTS: "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_SCIENTIFIC_CONSTRAINTS",
    OUTPUT_DECISIONS: "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_DECISION_FRAMEWORK",
    OUTPUT_ROADMAP: "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_RESEARCH_ROADMAP",
    OUTPUT_GOVERNANCE: "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_REFINEMENT_GOVERNANCE",
    OUTPUT_SUMMARY: "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_REFINEMENT_SUMMARY",
}


def _run_id(ts: datetime) -> str:
    return f"9A-6R15D_{ts.strftime('%Y%m%dT%H%M%SZ')}"


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
                "notes": "Phase 9A-6R15D preregistered scoping artifacts for Outcome Architecture refinement research.",
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
    except Exception as exc:  # pragma: no cover - network flake tolerance
        return {"updated": 0, "appended": 0, "status": "unavailable", "error": str(exc)}


def _metrics(
    collapse_summary_row: Mapping[str, Any],
    outcome_arch_summary_row: Mapping[str, Any],
    sm_v2_summary_row: Mapping[str, Any],
) -> Dict[str, Any]:
    outcome_payload = _parse_payload(outcome_arch_summary_row)
    collapse_payload = _parse_payload(collapse_summary_row)
    return {
        "planned_primary_observations": int(collapse_summary_row.get("planned_primary_observations", 0) or 0),
        "final_eligible_observations": int(collapse_summary_row.get("final_eligible_observations", 0) or 0),
        "outcome_join_losses": int(collapse_summary_row.get("outcome_join_losses", 0) or 0),
        "overlay_losses": int(collapse_summary_row.get("overlay_losses", 0) or 0),
        "success_mapping_losses": int(collapse_summary_row.get("success_mapping_losses", 0) or 0),
        "principal_bottleneck_layer": _normalize(outcome_arch_summary_row.get("principal_bottleneck_layer")) or "SUCCESS_MAPPING",
        "architecture_capability_classification": _normalize(outcome_arch_summary_row.get("architecture_capability_classification")),
        "recommended_research_direction": _normalize(outcome_arch_summary_row.get("recommended_research_direction")),
        "negative_disappearance_classification": _normalize(outcome_arch_summary_row.get("negative_disappearance_classification")),
        "scenario_summaries": outcome_payload.get("scenario_summaries", {}),
        "negative_first_hit_counts": outcome_payload.get("negative_first_hit_counts", {}),
        "collapse_payload": collapse_payload,
        "sm_v2_readiness": _normalize(sm_v2_summary_row.get("scientific_readiness_assessment")),
        "sm_v2_recommended_decision": _normalize(sm_v2_summary_row.get("recommended_decision")),
        "sm_v2_principal_bottleneck": _normalize(sm_v2_summary_row.get("principal_bottleneck")),
    }


def _limitations(metrics: Mapping[str, Any]) -> List[Dict[str, Any]]:
    return [
        {
            "limitation_id": "OA_LIMIT_01_CANONICAL_COVERAGE_GAPS",
            "limitation_family": FAMILY_CANONICAL,
            "limitation_title": "Canonical outcome coverage gaps remove planned observations before any success mapping can occur.",
            "blocking_role": "DIRECT_BLOCK",
            "first_hit_impact_count": metrics["outcome_join_losses"],
            "limitation_classification": CLASS_HISTORY,
            "redesign_status": STATUS_ACCEPTABLE,
            "preferred_sequence": SEQUENCE_BEFORE,
            "should_occur_before_success_mapping_v2": True,
            "should_occur_after_success_mapping_v2": False,
            "details": {
                "rationale": "Outcome join failures eliminate 22 planned observations before overlay or success mapping can operate.",
                "scientific_meaning": "Coverage repair belongs upstream of Success Mapping v2 because missing canonical outcomes are not a success-mapping choice.",
            },
        },
        {
            "limitation_id": "OA_LIMIT_02_CANONICAL_VERSION_WINDOW_TIMESTAMP_CONTRACT",
            "limitation_family": FAMILY_CANONICAL,
            "limitation_title": "Canonical outcome version, evaluation-window, and timestamp provenance are frozen guardrails, not retention levers.",
            "blocking_role": "FOUNDATIONAL_CONSTRAINT",
            "first_hit_impact_count": 0,
            "limitation_classification": CLASS_SCI_REQUIRED,
            "redesign_status": STATUS_PROHIBITED,
            "preferred_sequence": SEQUENCE_GUARDRAIL,
            "should_occur_before_success_mapping_v2": False,
            "should_occur_after_success_mapping_v2": False,
            "details": {
                "rationale": "Outcome Architecture redesign may not weaken version isolation, window identity, or provenance checks.",
                "scientific_meaning": "These controls preserve no-hindsight timing and reproducibility.",
            },
        },
        {
            "limitation_id": "OA_LIMIT_03_OVERLAY_COVERAGE_GAPS",
            "limitation_family": FAMILY_OVERLAY,
            "limitation_title": "Missing repaired outcome overlay coverage removes observations that already survived the canonical layer.",
            "blocking_role": "DIRECT_BLOCK",
            "first_hit_impact_count": metrics["overlay_losses"],
            "limitation_classification": CLASS_HISTORY,
            "redesign_status": STATUS_ACCEPTABLE,
            "preferred_sequence": SEQUENCE_BEFORE,
            "should_occur_before_success_mapping_v2": True,
            "should_occur_after_success_mapping_v2": False,
            "details": {
                "rationale": "Eleven first-hit losses occur because the repaired overlay is unavailable even after upstream lineage exists.",
                "scientific_meaning": "Overlay completeness is an upstream architecture dependency, not a mechanism-rule question.",
            },
        },
        {
            "limitation_id": "OA_LIMIT_04_OVERLAY_BRIDGE_LINEAGE_REQUIREMENT",
            "limitation_family": FAMILY_OVERLAY,
            "limitation_title": "The repaired overlay must remain versioned, deterministic, and traceable back to canonical outcome identities.",
            "blocking_role": "FOUNDATIONAL_CONSTRAINT",
            "first_hit_impact_count": 0,
            "limitation_classification": CLASS_SCI_REQUIRED,
            "redesign_status": STATUS_PROHIBITED,
            "preferred_sequence": SEQUENCE_GUARDRAIL,
            "should_occur_before_success_mapping_v2": False,
            "should_occur_after_success_mapping_v2": False,
            "details": {
                "rationale": "A redesign cannot treat the overlay as an ad hoc convenience layer or break versioned traceability.",
                "scientific_meaning": "Future overlay work must remain a deterministic bridge, not a post-hoc correction surface.",
            },
        },
        {
            "limitation_id": "OA_LIMIT_05_LINKAGE_EXACT_KEY_DEPENDENCE",
            "limitation_family": FAMILY_LINKAGE,
            "limitation_title": "Outcome linkage must remain exact, stable-keyed, one-to-one, and fail-closed.",
            "blocking_role": "FOUNDATIONAL_CONSTRAINT",
            "first_hit_impact_count": 0,
            "limitation_classification": CLASS_SCI_REQUIRED,
            "redesign_status": STATUS_PROHIBITED,
            "preferred_sequence": SEQUENCE_GUARDRAIL,
            "should_occur_before_success_mapping_v2": False,
            "should_occur_after_success_mapping_v2": False,
            "details": {
                "rationale": "No fuzzy, nearest-date, provider-only, session-only, or manual linkage is allowed.",
                "scientific_meaning": "Deterministic joins are prerequisite to any future architecture work and may not be traded for retention.",
            },
        },
        {
            "limitation_id": "OA_LIMIT_06_LINKAGE_BRIDGE_COMPLETENESS",
            "limitation_family": FAMILY_LINKAGE,
            "limitation_title": "Linkage completeness depends on the bridge path from classification keys to repaired and canonical outcome IDs.",
            "blocking_role": "DIRECT_BLOCK",
            "first_hit_impact_count": metrics["outcome_join_losses"] + metrics["overlay_losses"],
            "limitation_classification": CLASS_HISTORY,
            "redesign_status": STATUS_ACCEPTABLE,
            "preferred_sequence": SEQUENCE_BEFORE,
            "should_occur_before_success_mapping_v2": True,
            "should_occur_after_success_mapping_v2": False,
            "details": {
                "rationale": "Coverage and overlay gaps together show that the bridge path is not yet complete enough for inferential testing.",
                "scientific_meaning": "Bridge refinement belongs before Success Mapping v2 because SMv2 cannot recover observations that never link deterministically.",
            },
        },
        {
            "limitation_id": "OA_LIMIT_07_REALIZED_STATE_SEMANTICS",
            "limitation_family": FAMILY_REPRESENTATION,
            "limitation_title": "Current outcome representation leaves flat, ambiguous, and other non-resolved realized states scientifically under-specified for directional scoring.",
            "blocking_role": "INTERACTION_BLOCK",
            "first_hit_impact_count": metrics["success_mapping_losses"],
            "limitation_classification": CLASS_EMPIRICAL,
            "redesign_status": STATUS_EVIDENCE,
            "preferred_sequence": SEQUENCE_BEFORE,
            "should_occur_before_success_mapping_v2": True,
            "should_occur_after_success_mapping_v2": False,
            "details": {
                "rationale": "Success Mapping losses are concentrated in states that the current architecture does not represent as scoreable directional outcomes.",
                "scientific_meaning": "Any upstream representation change needs evidence and semantics work before SMv2 can safely use it.",
            },
        },
        {
            "limitation_id": "OA_LIMIT_08_BASELINE_CONTROL_EVALUABILITY",
            "limitation_family": FAMILY_INTERACTION,
            "limitation_title": "The Structure A delta design depends on both expanded and Pack A baseline observations being outcome-evaluable.",
            "blocking_role": "INTERACTION_BLOCK",
            "first_hit_impact_count": 9,
            "limitation_classification": CLASS_HISTORY,
            "redesign_status": STATUS_ACCEPTABLE,
            "preferred_sequence": SEQUENCE_BEFORE,
            "should_occur_before_success_mapping_v2": True,
            "should_occur_after_success_mapping_v2": False,
            "details": {
                "rationale": "Baseline non-directional or flat control states create losses even when expanded observations are otherwise scoreable.",
                "scientific_meaning": "Outcome Architecture must clarify whether the current paired-control architecture is fit for inferential delta testing.",
            },
        },
        {
            "limitation_id": "OA_LIMIT_09_NEGATIVE_ARM_FRAGILITY",
            "limitation_family": FAMILY_INTERACTION,
            "limitation_title": "The inferential negative arm is fragile across canonical coverage, overlay coverage, and outcome representation layers.",
            "blocking_role": "DIRECT_BLOCK",
            "first_hit_impact_count": 15,
            "limitation_classification": CLASS_EMPIRICAL,
            "redesign_status": STATUS_EVIDENCE,
            "preferred_sequence": SEQUENCE_BEFORE,
            "should_occur_before_success_mapping_v2": True,
            "should_occur_after_success_mapping_v2": False,
            "details": {
                "rationale": "No single isolated layer fix restores an adequate negative arm, and the current outcome architecture is not yet testable inferentially.",
                "scientific_meaning": "Future redesign must be judged by whether it supports a scientifically valid negative comparison without outcome-driven optimization.",
            },
        },
        {
            "limitation_id": "OA_LIMIT_10_POSTJOIN_GATE_DEPENDENCE",
            "limitation_family": FAMILY_INTERACTION,
            "limitation_title": "Primary inferential sample gates are structurally dependent on post-join outcome architecture, not only pre-outcome classified counts.",
            "blocking_role": "INTERACTION_BLOCK",
            "first_hit_impact_count": metrics["planned_primary_observations"] - metrics["final_eligible_observations"],
            "limitation_classification": CLASS_HISTORY,
            "redesign_status": STATUS_ACCEPTABLE,
            "preferred_sequence": SEQUENCE_BEFORE,
            "should_occur_before_success_mapping_v2": True,
            "should_occur_after_success_mapping_v2": False,
            "details": {
                "rationale": "Blinded gates passed structurally but collapsed after outcome linkage and representation rules were applied.",
                "scientific_meaning": "Outcome Architecture redesign must make these dependencies explicit before SMv2 is attempted.",
            },
        },
    ]


def _dependency_graph() -> List[Dict[str, Any]]:
    return [
        {
            "edge_id": "OA_GRAPH_01",
            "from_layer": "CANONICAL_OUTCOME",
            "to_layer": "OUTCOME_OVERLAY",
            "dependency_type": "coverage_and_version_source",
            "blocking_inference": True,
            "blocking_reason": "Overlay construction cannot exceed canonical outcome coverage or violate canonical version lineage.",
        },
        {
            "edge_id": "OA_GRAPH_02",
            "from_layer": "CANONICAL_OUTCOME",
            "to_layer": "OUTCOME_LINKAGE",
            "dependency_type": "stable_identity_and_provenance_source",
            "blocking_inference": True,
            "blocking_reason": "Outcome linkage depends on canonical IDs, version identity, evaluation window identity, and timestamp provenance.",
        },
        {
            "edge_id": "OA_GRAPH_03",
            "from_layer": "OUTCOME_OVERLAY",
            "to_layer": "OUTCOME_LINKAGE",
            "dependency_type": "bridge_key_availability",
            "blocking_inference": True,
            "blocking_reason": "Missing repaired overlay bridge IDs create deterministic join failures before scoring begins.",
        },
        {
            "edge_id": "OA_GRAPH_04",
            "from_layer": "CANONICAL_OUTCOME",
            "to_layer": "OUTCOME_REPRESENTATION",
            "dependency_type": "realized_state_semantics",
            "blocking_inference": True,
            "blocking_reason": "Flat, ambiguous, or non-resolved outcome states must be represented before they can support directional success semantics.",
        },
        {
            "edge_id": "OA_GRAPH_05",
            "from_layer": "OUTCOME_LINKAGE",
            "to_layer": "CORRECTED_DIRECTIONAL_SUCCESS",
            "dependency_type": "join_validity_gate",
            "blocking_inference": True,
            "blocking_reason": "No success value can be derived unless the future outcome join is exact, unique, and version-valid.",
        },
        {
            "edge_id": "OA_GRAPH_06",
            "from_layer": "OUTCOME_REPRESENTATION",
            "to_layer": "CORRECTED_DIRECTIONAL_SUCCESS",
            "dependency_type": "scoreability_semantics",
            "blocking_inference": True,
            "blocking_reason": "Directional success depends on whether represented states are scientifically scoreable under the endpoint.",
        },
        {
            "edge_id": "OA_GRAPH_07",
            "from_layer": "CORRECTED_DIRECTIONAL_SUCCESS",
            "to_layer": "ELIGIBILITY",
            "dependency_type": "post_join_sample_gate_dependency",
            "blocking_inference": True,
            "blocking_reason": "Eligibility and inferential gates operate only after corrected directional success has been deterministically derived.",
        },
        {
            "edge_id": "OA_GRAPH_08",
            "from_layer": "ELIGIBILITY",
            "to_layer": "MECHANISM_TESTING",
            "dependency_type": "analysis_population_gate",
            "blocking_inference": True,
            "blocking_reason": "Mechanism testing is blocked when the post-join eligible population collapses below frozen inferential gates.",
        },
        {
            "edge_id": "OA_GRAPH_09",
            "from_layer": "OUTCOME_ARCHITECTURE_INTERACTION",
            "to_layer": "SUCCESS_MAPPING_V2",
            "dependency_type": "upstream_design_prerequisite",
            "blocking_inference": True,
            "blocking_reason": "Success Mapping v2 cannot be cleanly scoped until upstream outcome coverage, overlay, linkage, and representation dependencies are clarified.",
        },
    ]


def _refinement_paths(metrics: Mapping[str, Any]) -> List[Dict[str, Any]]:
    return [
        {
            "path_id": "OA_PATH_01",
            "refinement_path": "CANONICAL_OUTCOME_V2",
            "current_problem": f"{metrics['outcome_join_losses']} first-hit losses from missing canonical outcome coverage and identity availability.",
            "readiness_status": READINESS_CONSTRAINED,
            "relation_to_success_mapping_v2": "MUST_PRECEDE_SUCCESS_MAPPING_V2",
        },
        {
            "path_id": "OA_PATH_02",
            "refinement_path": "OUTCOME_OVERLAY_V2",
            "current_problem": f"{metrics['overlay_losses']} first-hit losses from missing repaired overlay coverage and bridge completeness.",
            "readiness_status": READINESS_CONSTRAINED,
            "relation_to_success_mapping_v2": "MUST_PRECEDE_SUCCESS_MAPPING_V2",
        },
        {
            "path_id": "OA_PATH_03",
            "refinement_path": "LINKAGE_REFINEMENT",
            "current_problem": "Deterministic bridge completeness must improve without weakening exact stable-key linkage.",
            "readiness_status": READINESS_CONSTRAINED,
            "relation_to_success_mapping_v2": "MUST_PRECEDE_SUCCESS_MAPPING_V2",
        },
        {
            "path_id": "OA_PATH_04",
            "refinement_path": "REPRESENTATION_REFINEMENT",
            "current_problem": "Flat and other non-resolved states remain scientifically under-specified for future directional scoring.",
            "readiness_status": READINESS_RESEARCH,
            "relation_to_success_mapping_v2": "PRECEDES_OR_PARALLELS_SUCCESS_MAPPING_V2_DEPENDING_ON_EVIDENCE",
        },
        {
            "path_id": "OA_PATH_05",
            "refinement_path": "LAYER_INTERACTION_REFINEMENT",
            "current_problem": "Baseline-control evaluability and post-join gate dependence show that multiple layers jointly block inference.",
            "readiness_status": READINESS_CONSTRAINED,
            "relation_to_success_mapping_v2": "MUST_BE_SCOPED_BEFORE_SUCCESS_MAPPING_V2",
        },
    ]


def _constraints() -> List[Dict[str, Any]]:
    return [
        {
            "constraint_id": "OA_CONSTRAINT_01",
            "constraint_type": "OUTCOME_INDEPENDENCE",
            "constraint_text": "Outcome Architecture redesign may not use realized performance to choose coverage, overlay, linkage, or representation rules.",
            "violation_status": "BLOCKING",
        },
        {
            "constraint_id": "OA_CONSTRAINT_02",
            "constraint_type": "NO_HINDSIGHT",
            "constraint_text": "No redesign may optimize against retained observations, recovered negatives, effect sizes, or accuracy rates after outcome access.",
            "violation_status": "BLOCKING",
        },
        {
            "constraint_id": "OA_CONSTRAINT_03",
            "constraint_type": "DETERMINISTIC_JOINS",
            "constraint_text": "Outcome linkage must remain exact, one-to-one, stable-keyed, and fail-closed with no fuzzy or manual matching.",
            "violation_status": "BLOCKING",
        },
        {
            "constraint_id": "OA_CONSTRAINT_04",
            "constraint_type": "REPRODUCIBILITY",
            "constraint_text": "Every refinement candidate must preserve deterministic fingerprints, deterministic run identity, and deterministic audit logs.",
            "violation_status": "BLOCKING",
        },
        {
            "constraint_id": "OA_CONSTRAINT_05",
            "constraint_type": "VERSION_TRACEABILITY",
            "constraint_text": "Canonical outcomes, overlays, bridge IDs, evaluation windows, and repaired mappings must remain versioned and lineage-complete.",
            "violation_status": "BLOCKING",
        },
        {
            "constraint_id": "OA_CONSTRAINT_06",
            "constraint_type": "FROZEN_SEMANTICS",
            "constraint_text": "Core corrected directional-success semantics and frozen mechanism definitions may not be altered inside Outcome Architecture work.",
            "violation_status": "BLOCKING",
        },
        {
            "constraint_id": "OA_CONSTRAINT_07",
            "constraint_type": "NO_PROVIDER_TUNING",
            "constraint_text": "No provider-specific, session-specific, or model-specific optimization is allowed in Outcome Architecture redesign.",
            "violation_status": "BLOCKING",
        },
        {
            "constraint_id": "OA_CONSTRAINT_08",
            "constraint_type": "NO_MANUAL_OVERRIDE",
            "constraint_text": "Missing or ambiguous outcome linkage may not be repaired through manual overrides or analyst discretion.",
            "violation_status": "BLOCKING",
        },
        {
            "constraint_id": "OA_CONSTRAINT_09",
            "constraint_type": "UPSTREAM_BOUNDARY",
            "constraint_text": "Outcome Architecture work must remain upstream of Success Mapping v2 and must not silently redesign eligibility or mechanism science.",
            "violation_status": "BLOCKING",
        },
    ]


def _decisions() -> List[Dict[str, Any]]:
    return [
        {
            "decision_option": "PROCEED_TO_OUTCOME_ARCHITECTURE_REFINEMENT_DESIGN",
            "decision_status": "RECOMMENDED_WITH_CONSTRAINTS",
            "triggering_conditions": "Use when the redesign target is coverage, overlay completeness, deterministic linkage, or layer interaction diagnostics.",
            "required_preconditions": "Preserve canonical guardrails, no outcome-row access for scoping, and no weakening of deterministic joins or version contracts.",
        },
        {
            "decision_option": "DEFER_REPRESENTATION_REDESIGN_PENDING_EVIDENCE",
            "decision_status": "CONDITIONALLY_REQUIRED",
            "triggering_conditions": "Use when the issue concerns flat, ambiguous, or non-resolved outcome-state semantics rather than missing coverage alone.",
            "required_preconditions": "Separate evidence plan before any semantic redesign is proposed.",
        },
        {
            "decision_option": "DEFER_SUCCESS_MAPPING_V2_UNTIL_OUTCOME_ARCHITECTURE_SCOPE_IS_CLOSED",
            "decision_status": "REQUIRED",
            "triggering_conditions": "Use when upstream architecture still determines whether observations ever reach Success Mapping.",
            "required_preconditions": "Outcome Architecture scope must be frozen first so Success Mapping v2 does not absorb upstream defects.",
        },
        {
            "decision_option": "DO_NOT_WEAKEN_GUARDRAILS",
            "decision_status": "MANDATORY",
            "triggering_conditions": "Applies to canonical version, window, timestamp, and exact-join constraints.",
            "required_preconditions": "None; these remain non-negotiable.",
        },
    ]


def _roadmap() -> List[Dict[str, Any]]:
    return [
        {
            "stage_order": 1,
            "stage_name": "OUTCOME_ARCHITECTURE_REFINEMENT_DESIGN",
            "stage_objective": "Freeze the redesign candidates, boundaries, and validation targets for canonical coverage, overlay coverage, linkage, representation, and layer interaction.",
            "stage_prerequisite": "Phase 9A-6R15D outcome architecture scoping complete.",
            "stage_not_allowed": "No Success Mapping v2 redesign or mechanism retesting yet.",
        },
        {
            "stage_order": 2,
            "stage_name": "OUTCOME_ARCHITECTURE_REFINEMENT_APPROVAL_AND_IMPLEMENTATION",
            "stage_objective": "Approve and implement the frozen outcome-architecture refinement under fail-closed governance.",
            "stage_prerequisite": "Outcome Architecture design preregistration and approval complete.",
            "stage_not_allowed": "No post-hoc accuracy optimization or provider-specific tuning.",
        },
        {
            "stage_order": 3,
            "stage_name": "SUCCESS_MAPPING_V2_SCOPE_REFRESH_AND_DESIGN",
            "stage_objective": "Reassess whether the upstream architecture is now stable enough to support a clean Success Mapping v2 preregistration.",
            "stage_prerequisite": "Outcome Architecture refinement validated and version-frozen.",
            "stage_not_allowed": "No direct carryover of old bottleneck assumptions without re-auditing upstream changes.",
        },
        {
            "stage_order": 4,
            "stage_name": "MECHANISM_RETESTING",
            "stage_objective": "Rerun the mechanism test stack only after revised outcome architecture and any approved SMv2 are frozen.",
            "stage_prerequisite": "Outcome Architecture and Success Mapping changes fully approved and implemented.",
            "stage_not_allowed": "No inferential claims before the retest population and contracts are revalidated.",
        },
        {
            "stage_order": 5,
            "stage_name": "INFERENTIAL_TESTING_REASSESSMENT_AND_EXECUTION",
            "stage_objective": "Evaluate whether the retested population supports inferential mechanism testing under frozen gates and then execute only if justified.",
            "stage_prerequisite": "Mechanism retesting complete with adequate eligible sample.",
            "stage_not_allowed": "No forced inferential testing if the revised architecture still yields descriptive-only evidence.",
        },
        {
            "stage_order": 6,
            "stage_name": "PRODUCTION_EVALUATION",
            "stage_objective": "Consider production-facing evaluation only after a separate evidence chain demonstrates scientific validity, operational robustness, and governance approval.",
            "stage_prerequisite": "Successful inferential testing and separate production governance review.",
            "stage_not_allowed": "No direct production coupling from architecture research artifacts.",
        },
    ]


def build() -> Dict[str, Any]:
    run_ts = datetime.now(timezone.utc).replace(microsecond=0)
    generated_ts = run_ts.isoformat().replace("+00:00", "Z")
    scope_run_id = _run_id(run_ts)

    _require(not (FORBIDDEN_INPUT_TITLES & set(INPUT_SHEETS)), "Forbidden outcome-bearing sheet included in inputs.")

    service = build_sheets_service(load_credentials())
    inputs = _fetch_input_sheets(service, DIAGNOSTICS_SPREADSHEET_ID, INPUT_SHEETS)
    known_titles = _sheet_titles_light(service, DIAGNOSTICS_SPREADSHEET_ID)

    canonical_authority = _parse_payload(
        _latest_row(
            inputs["Refined_Mechanism_Test_Clean_R1_Canonical_Authority"].rows,
            "lineage_repair_run_id",
        )
    )
    component_authority = _parse_payload(
        _latest_row(inputs["Refined_Mechanism_Test_Clean_R1_Component_Authority"].rows, "lineage_repair_run_id")
    )
    canonical_manifest = _parse_payload(
        _latest_row(inputs["Refined_Mechanism_Test_Clean_R1_Canonical_Fingerprint_Manifest"].rows, "lineage_repair_run_id")
    )

    _require(_normalize(canonical_authority.get("authority_preregistration_version")) == AUTHORITATIVE_VERSION, "Canonical authority version mismatch.")
    _require(_normalize(canonical_authority.get("authoritative_repair_run_id")) == AUTHORITATIVE_RUN_ID, "Canonical authority run ID mismatch.")
    _require(_normalize(canonical_authority.get("authority_selection_method")) == "EXACT_VERSION_AND_RUN_ID_MATCH", "Canonical authority selection method mismatch.")
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

    canonical_approval_summary = _parse_payload(
        _latest_row(inputs["Refined_Mechanism_Test_Execution_Approval_Canonical_R1_Summary"].rows, "approval_canonical_r1_run_id")
    )
    collapse_summary_row = _latest_row(inputs["Refined_Mechanism_Test_Collapse_Summary"].rows, "population_collapse_run_id")
    outcome_arch_summary_row = _latest_row(inputs["Refined_Mechanism_Test_Outcome_Architecture_Summary"].rows, "outcome_architecture_run_id")
    sm_v2_summary_row = _latest_row(inputs["Refined_Mechanism_Test_Success_Mapping_V2_Summary"].rows, "success_mapping_v2_scope_run_id")

    _require(canonical_approval_summary.get("ready_for_one_canonical_clean_r1_mechanism_test_execution") is True, "Canonical approval summary is not ready.")
    _require(_normalize(prereg_r1.get("primary_mechanism")) == PRIMARY_MECHANISM, "Primary mechanism mismatch.")
    _require(_normalize(prereg_r1.get("primary_structure")) == PRIMARY_STRUCTURE, "Primary structure mismatch.")
    _require(_normalize(prereg_r1.get("mechanism_version")) == CLASSIFICATION_VERSION, "Classification version mismatch.")
    _require(_normalize(prereg_r1.get("classification_run_id")) == CLASSIFICATION_RUN_ID, "Classification run ID mismatch.")
    _require(outcome_r1.get("future_schema_fingerprint_verification_required") is True, "Outcome schema fingerprint guardrail mismatch.")
    _require(join_r1.get("exact_stable_key_match_required") is True, "Join stable-key requirement mismatch.")
    _require(success_r1.get("allowed_output_statuses") == ["SUCCESS", "FAILURE", "NOT_ELIGIBLE", "AMBIGUOUS_JOIN_BLOCKED"], "Success mapping output status mismatch.")
    _require(_normalize(method_r1.get("primary_interpretation")) == "EXPLORATORY_PREREGISTERED_PRIMARY", "Method interpretation mismatch.")
    _require(stop_r1.get("fail_closed") is True, "Stop-rule fail-closed contract mismatch.")
    _require(design_r1.get("science_preservation", {}).get("primary_structure_changed") is False, "Design reconciliation indicates science changed.")

    metrics = _metrics(collapse_summary_row, outcome_arch_summary_row, sm_v2_summary_row)
    _require(metrics["planned_primary_observations"] == EXPECTED_COUNTS["planned_primary_observations"], "Planned observation count mismatch.")
    _require(metrics["final_eligible_observations"] == EXPECTED_COUNTS["final_eligible_observations"], "Final eligible observation count mismatch.")
    _require(metrics["outcome_join_losses"] == EXPECTED_COUNTS["outcome_join_losses"], "Outcome join loss count mismatch.")
    _require(metrics["overlay_losses"] == EXPECTED_COUNTS["overlay_losses"], "Overlay loss count mismatch.")
    _require(metrics["success_mapping_losses"] == EXPECTED_COUNTS["success_mapping_losses"], "Success mapping loss count mismatch.")
    _require(metrics["sm_v2_recommended_decision"] == "PROCEED_AFTER_ADDITIONAL_OUTCOME_ARCHITECTURE_WORK", "Success Mapping v2 scope does not point to Outcome Architecture work.")

    limitation_rows = _limitations(metrics)
    graph_rows = _dependency_graph()
    path_rows = _refinement_paths(metrics)
    constraint_rows = _constraints()
    decision_rows = _decisions()
    roadmap_rows = _roadmap()

    scientific_readiness_assessment = READINESS_CONSTRAINED
    recommended_next_step = "PROCEED_TO_PHASE9A6R15E_OUTCOME_ARCHITECTURE_REFINEMENT_DESIGN"
    build_status = "PASS_WITH_WARNINGS"
    final_interpretation = "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_SCOPE_READY_WITH_CONSTRAINTS"

    outputs: Dict[str, List[Dict[str, Any]]] = {
        OUTPUT_SCOPE: [
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_scope_run_id": scope_run_id,
                "scope_version": SCOPE_VERSION,
                "canonical_preregistration_version": AUTHORITATIVE_VERSION,
                "canonical_run_id": AUTHORITATIVE_RUN_ID,
                "classification_version": CLASSIFICATION_VERSION,
                "classification_run_id": CLASSIFICATION_RUN_ID,
                "scientific_readiness_assessment": scientific_readiness_assessment,
                "recommended_next_step": recommended_next_step,
                "build_status": build_status,
                "final_interpretation": final_interpretation,
                "payload_json": _canonical_json(
                    {
                        "authoritative_preregistration_version": AUTHORITATIVE_VERSION,
                        "authoritative_run_id": AUTHORITATIVE_RUN_ID,
                        "classification_version": CLASSIFICATION_VERSION,
                        "classification_run_id": CLASSIFICATION_RUN_ID,
                        "primary_mechanism": PRIMARY_MECHANISM,
                        "primary_structure": PRIMARY_STRUCTURE,
                        "success_mapping_v2_readiness": metrics["sm_v2_readiness"],
                        "success_mapping_v2_recommended_decision": metrics["sm_v2_recommended_decision"],
                        "principal_bottleneck_layer": metrics["principal_bottleneck_layer"],
                        "architecture_capability_classification": metrics["architecture_capability_classification"],
                        "scenario_summaries": metrics["scenario_summaries"],
                    }
                ),
            }
        ],
        OUTPUT_LIMITATIONS: [],
        OUTPUT_GRAPH: [],
        OUTPUT_PATHS: [],
        OUTPUT_CONSTRAINTS: [],
        OUTPUT_DECISIONS: [],
        OUTPUT_ROADMAP: [],
        OUTPUT_GOVERNANCE: [],
        OUTPUT_SUMMARY: [],
    }

    for row in limitation_rows:
        outputs[OUTPUT_LIMITATIONS].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_scope_run_id": scope_run_id,
                "limitation_id": row["limitation_id"],
                "limitation_family": row["limitation_family"],
                "limitation_title": row["limitation_title"],
                "blocking_role": row["blocking_role"],
                "first_hit_impact_count": row["first_hit_impact_count"],
                "limitation_classification": row["limitation_classification"],
                "redesign_status": row["redesign_status"],
                "preferred_sequence": row["preferred_sequence"],
                "should_occur_before_success_mapping_v2": row["should_occur_before_success_mapping_v2"],
                "should_occur_after_success_mapping_v2": row["should_occur_after_success_mapping_v2"],
                "payload_json": _canonical_json(row),
            }
        )

    for row in graph_rows:
        outputs[OUTPUT_GRAPH].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_scope_run_id": scope_run_id,
                "edge_id": row["edge_id"],
                "from_layer": row["from_layer"],
                "to_layer": row["to_layer"],
                "dependency_type": row["dependency_type"],
                "blocking_inference": row["blocking_inference"],
                "blocking_reason": row["blocking_reason"],
                "payload_json": _canonical_json(row),
            }
        )

    for row in path_rows:
        outputs[OUTPUT_PATHS].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_scope_run_id": scope_run_id,
                "path_id": row["path_id"],
                "refinement_path": row["refinement_path"],
                "current_problem": row["current_problem"],
                "readiness_status": row["readiness_status"],
                "relation_to_success_mapping_v2": row["relation_to_success_mapping_v2"],
                "payload_json": _canonical_json(row),
            }
        )

    for row in constraint_rows:
        outputs[OUTPUT_CONSTRAINTS].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_scope_run_id": scope_run_id,
                "constraint_id": row["constraint_id"],
                "constraint_type": row["constraint_type"],
                "constraint_text": row["constraint_text"],
                "violation_status": row["violation_status"],
                "payload_json": _canonical_json(row),
            }
        )

    for row in decision_rows:
        outputs[OUTPUT_DECISIONS].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_scope_run_id": scope_run_id,
                "decision_option": row["decision_option"],
                "decision_status": row["decision_status"],
                "triggering_conditions": row["triggering_conditions"],
                "required_preconditions": row["required_preconditions"],
                "payload_json": _canonical_json(row),
            }
        )

    for row in roadmap_rows:
        outputs[OUTPUT_ROADMAP].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_scope_run_id": scope_run_id,
                "stage_order": row["stage_order"],
                "stage_name": row["stage_name"],
                "stage_objective": row["stage_objective"],
                "stage_prerequisite": row["stage_prerequisite"],
                "stage_not_allowed": row["stage_not_allowed"],
                "payload_json": _canonical_json(row),
            }
        )

    governance_counters = {
        "provider_calls_performed": 0,
        "outcome_rows_loaded": 0,
        "outcome_rules_modified": 0,
        "outcome_overlay_modified": 0,
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
                "outcome_architecture_scope_run_id": scope_run_id,
                "counter_name": counter_name,
                "counter_value": counter_value,
                "status": "PASS" if counter_value == 0 else "FAIL",
                "notes": "Read-only scoping phase preserved." if counter_value == 0 else "Unexpected nonzero counter.",
            }
        )

    summary_payload = {
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "scientific_readiness_assessment": scientific_readiness_assessment,
        "recommended_next_step": recommended_next_step,
        "principal_blocking_layer": "OUTCOME_ARCHITECTURE_WITH_UPSTREAM_DEPENDENCY_INTERACTIONS",
        "limitation_count": len(limitation_rows),
        "limitation_family_counts": dict(Counter(row["limitation_family"] for row in limitation_rows)),
        "limitation_classification_counts": dict(Counter(row["limitation_classification"] for row in limitation_rows)),
        "redesign_status_counts": dict(Counter(row["redesign_status"] for row in limitation_rows)),
        "pre_success_mapping_v2_dependencies": sum(1 for row in limitation_rows if row["should_occur_before_success_mapping_v2"]),
        "post_success_mapping_v2_dependencies": sum(1 for row in limitation_rows if row["should_occur_after_success_mapping_v2"]),
        "metrics": {
            "planned_primary_observations": metrics["planned_primary_observations"],
            "final_eligible_observations": metrics["final_eligible_observations"],
            "outcome_join_losses": metrics["outcome_join_losses"],
            "overlay_losses": metrics["overlay_losses"],
            "success_mapping_losses": metrics["success_mapping_losses"],
            "principal_bottleneck_layer": metrics["principal_bottleneck_layer"],
            "negative_disappearance_classification": metrics["negative_disappearance_classification"],
        },
        "governance_counters": governance_counters,
    }
    outputs[OUTPUT_SUMMARY].append(
        {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "outcome_architecture_scope_run_id": scope_run_id,
            "build_status": build_status,
            "final_interpretation": final_interpretation,
            "scientific_readiness_assessment": scientific_readiness_assessment,
            "recommended_next_step": recommended_next_step,
            "principal_blocking_layer": "OUTCOME_ARCHITECTURE_WITH_UPSTREAM_DEPENDENCY_INTERACTIONS",
            "limitation_count": len(limitation_rows),
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
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "file_created": BUILD_SCRIPT,
        "outcome_architecture_scope_run_id": scope_run_id,
        "sheets_written": list(OUTPUT_SHEETS.keys()),
        "rows_written_per_sheet": rows_written,
        "scientific_readiness_assessment": scientific_readiness_assessment,
        "recommended_next_step": recommended_next_step,
        "principal_bottleneck_layer": metrics["principal_bottleneck_layer"],
        "limitation_count": len(limitation_rows),
        "limitation_family_counts": dict(Counter(row["limitation_family"] for row in limitation_rows)),
        "limitation_classification_counts": dict(Counter(row["limitation_classification"] for row in limitation_rows)),
        "redesign_status_counts": dict(Counter(row["redesign_status"] for row in limitation_rows)),
        "planned_primary_observations": metrics["planned_primary_observations"],
        "final_eligible_observations": metrics["final_eligible_observations"],
        "outcome_join_losses": metrics["outcome_join_losses"],
        "overlay_losses": metrics["overlay_losses"],
        "success_mapping_losses": metrics["success_mapping_losses"],
        "governance_counters": governance_counters,
        "registry_result": registry_result,
    }


def main() -> None:
    report = build()
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
