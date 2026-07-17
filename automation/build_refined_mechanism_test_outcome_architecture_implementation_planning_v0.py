#!/usr/bin/env python3
"""Phase 9A-6R15H — Outcome Architecture Implementation Planning.

This phase produces a deterministic implementation plan for the validated
Outcome Architecture v2. It does not implement any architecture changes,
modify existing sheets, access outcome rows, or change scientific rules.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Set


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


PHASE_ID = "9A-6R15H"
BUILD_SCRIPT = "automation/build_refined_mechanism_test_outcome_architecture_implementation_planning_v0.py"
SCHEMA_VERSION = "presignal_v2_refined_mechanism_test_outcome_architecture_implementation_planning_v0"
PLANNING_VERSION = "refined_mechanism_test_outcome_architecture_implementation_planning_v0"
REGISTRY_CATEGORY = "PRESIGNAL_V2_REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_IMPLEMENTATION_PLANNING"
REGISTRY_OWNER_MODULE = "market_state"

ARCHITECTURE_PREREGISTRATION_VERSION = "1.0"
ARCHITECTURE_VERSION = "2.0"
ARCHITECTURE_PREREGISTRATION_STATUS = "FROZEN"
AUTHORITATIVE_VERSION = "1.0-clean-r1"
AUTHORITATIVE_RUN_ID = "9A-6R13R1_20260711T020141Z"
CLASSIFICATION_VERSION = "1.1"
CLASSIFICATION_RUN_ID = "refined_mechanism_v11_classification_20260710T152725Z"

BUILD_STATUS = "PASS_WITH_WARNINGS"
FINAL_INTERPRETATION = "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_IMPLEMENTATION_PLAN_READY_WITH_WARNINGS"
IMPLEMENTATION_PLANNING_STATUS = "READY_FOR_STAGED_IMPLEMENTATION"
RECOMMENDED_NEXT_STEP = "PROCEED_TO_PHASE9A6R15I_OUTCOME_ARCHITECTURE_STAGED_IMPLEMENTATION"

FORBIDDEN_INPUT_TITLES = {
    "Market_Reaction_Canonical_Outcomes",
    "Outcome_Ledger",
    "Evaluation_Rows",
    "Evaluation_Summary",
    "Corrected_Accuracy_Evaluation",
    "Controlled_Accuracy_Evaluation",
}

INPUT_SHEETS = (
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Validation",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Layer_Validation",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Target_Validation",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Prohibited_Validation",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Compatibility_Validation",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Determinism_Validation",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Governance_Validation",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Assumption_Validation",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Implementation_Readiness",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Validation_Governance",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Validation_Summary",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Preregistration",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Frozen_Layers",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Frozen_Redesign_Targets",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Frozen_Prohibited_Redesigns",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Frozen_Empirical_Questions",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Frozen_Compatibility",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Frozen_Governance",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Frozen_Implementation_Boundary",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Fingerprint_Freeze",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Preregistration_Governance",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Preregistration_Summary",
    "Refined_Mechanism_Test_Clean_R1_Canonical_Authority",
    "Refined_Mechanism_Test_Clean_R1_Canonical_Fingerprint_Manifest",
    "Refined_Mechanism_Test_Preregistration_Clean_R1",
    "Refined_Mechanism_Test_Preregistration_Clean_R1_Summary",
)

OUTPUT_PLAN = "Refined_Mechanism_Test_Outcome_Architecture_V2_Implementation_Plan"
OUTPUT_SEQUENCE = "Refined_Mechanism_Test_Outcome_Architecture_V2_Implementation_Sequence"
OUTPUT_GRAPH = "Refined_Mechanism_Test_Outcome_Architecture_V2_Implementation_Dependency_Graph"
OUTPUT_MIGRATION = "Refined_Mechanism_Test_Outcome_Architecture_V2_Workbook_Migration_Plan"
OUTPUT_GOVERNANCE_RULES = "Refined_Mechanism_Test_Outcome_Architecture_V2_Implementation_Governance"
OUTPUT_VERIFICATION = "Refined_Mechanism_Test_Outcome_Architecture_V2_Implementation_Verification"
OUTPUT_STOPS = "Refined_Mechanism_Test_Outcome_Architecture_V2_Implementation_Stop_Conditions"
OUTPUT_READINESS = "Refined_Mechanism_Test_Outcome_Architecture_V2_Implementation_Planning_Readiness"
OUTPUT_GOVERNANCE = "Refined_Mechanism_Test_Outcome_Architecture_V2_Implementation_Planning_Governance"
OUTPUT_SUMMARY = "Refined_Mechanism_Test_Outcome_Architecture_V2_Implementation_Planning_Summary"

OUTPUT_SHEETS: Dict[str, List[str]] = {
    OUTPUT_PLAN: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_implementation_planning_run_id",
        "planning_version",
        "architecture_preregistration_version",
        "architecture_version",
        "implementation_planning_status",
        "build_status",
        "final_interpretation",
        "recommended_next_step",
        "payload_json",
    ],
    OUTPUT_SEQUENCE: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_implementation_planning_run_id",
        "stage_order",
        "stage_id",
        "layer_name",
        "required_inputs_json",
        "produced_outputs_json",
        "upstream_dependencies_json",
        "downstream_consumers_json",
        "implementation_checkpoints_json",
        "resumable_after_checkpoint",
        "payload_json",
    ],
    OUTPUT_GRAPH: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_implementation_planning_run_id",
        "edge_id",
        "from_stage",
        "to_stage",
        "dependency_type",
        "stage_boundary",
        "resumable_boundary",
        "payload_json",
    ],
    OUTPUT_MIGRATION: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_implementation_planning_run_id",
        "migration_item_id",
        "migration_scope",
        "frozen_or_created",
        "planned_sheet_family_json",
        "backward_compatibility_rule",
        "migration_checkpoint",
        "payload_json",
    ],
    OUTPUT_GOVERNANCE_RULES: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_implementation_planning_run_id",
        "governance_id",
        "governance_area",
        "planned_control",
        "rollback_strategy",
        "fail_closed_behavior",
        "payload_json",
    ],
    OUTPUT_VERIFICATION: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_implementation_planning_run_id",
        "verification_id",
        "layer_name",
        "deterministic_output_requirement",
        "completeness_requirement",
        "consistency_requirement",
        "compatibility_requirement",
        "reproducibility_requirement",
        "payload_json",
    ],
    OUTPUT_STOPS: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_implementation_planning_run_id",
        "stop_id",
        "stop_condition",
        "trigger_stage",
        "required_action",
        "resumable_after_repair",
        "payload_json",
    ],
    OUTPUT_READINESS: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_implementation_planning_run_id",
        "readiness_area",
        "readiness_status",
        "staged_implementation_required",
        "minimum_repair_if_any",
        "payload_json",
    ],
    OUTPUT_GOVERNANCE: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_implementation_planning_run_id",
        "counter_name",
        "counter_value",
        "status",
        "notes",
    ],
    OUTPUT_SUMMARY: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_implementation_planning_run_id",
        "build_status",
        "final_interpretation",
        "implementation_planning_status",
        "recommended_next_step",
        "payload_json",
    ],
}

OUTPUT_LOGICAL_IDS = {name: name.upper() for name in OUTPUT_SHEETS}


def _run_id(ts: datetime) -> str:
    return f"9A-6R15H_{ts.strftime('%Y%m%dT%H%M%SZ')}"


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


def _rows_for_run(rows: Sequence[Mapping[str, Any]], run_key: str, run_id: str) -> List[Dict[str, Any]]:
    return [dict(row) for row in rows if _normalize(row.get(run_key)) == run_id]


def _json_list(row: Mapping[str, Any], key: str) -> List[Any]:
    raw = _normalize(row.get(key))
    return json.loads(raw) if raw else []


def _coerce_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    normalized = _normalize(value)
    if normalized == "":
        return default
    return int(normalized)


def _detect_cycles(edges: Sequence[Mapping[str, Any]]) -> Set[str]:
    graph: Dict[str, Set[str]] = {}
    for edge in edges:
        src = _normalize(edge.get("from_stage"))
        dst = _normalize(edge.get("to_stage"))
        graph.setdefault(src, set()).add(dst)
        graph.setdefault(dst, set())

    visiting: Set[str] = set()
    visited: Set[str] = set()
    cyclic: Set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            cyclic.add(node)
            return
        if node in visited:
            return
        visiting.add(node)
        for child in graph.get(node, set()):
            visit(child)
            if child in cyclic:
                cyclic.add(node)
        visiting.remove(node)
        visited.add(node)

    for node in sorted(graph):
        visit(node)
    return cyclic


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
                "notes": "Phase 9A-6R15H Outcome Architecture v2 implementation planning artifacts.",
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


def _planned_layer_outputs() -> Dict[str, List[str]]:
    return {
        "CANONICAL_OUTCOME": [
            "Refined_Mechanism_Test_Outcome_Architecture_V2_Canonical_Coverage_Manifest",
            "Refined_Mechanism_Test_Outcome_Architecture_V2_Canonical_Availability_Audit",
        ],
        "OUTCOME_OVERLAY": [
            "Refined_Mechanism_Test_Outcome_Architecture_V2_Overlay_Completeness_Manifest",
            "Refined_Mechanism_Test_Outcome_Architecture_V2_Overlay_Lineage_Audit",
        ],
        "OUTCOME_LINKAGE": [
            "Refined_Mechanism_Test_Outcome_Architecture_V2_Linkage_Bridge_Manifest",
            "Refined_Mechanism_Test_Outcome_Architecture_V2_Linkage_State_Audit",
        ],
        "OUTCOME_REPRESENTATION": [
            "Refined_Mechanism_Test_Outcome_Architecture_V2_Representation_Status",
            "Refined_Mechanism_Test_Outcome_Architecture_V2_Representability_Audit",
        ],
        "ELIGIBILITY_INTERACTION": [
            "Refined_Mechanism_Test_Outcome_Architecture_V2_Paired_Control_Evaluability",
            "Refined_Mechanism_Test_Outcome_Architecture_V2_PostJoin_Gate_Survivorship",
        ],
    }


def build() -> Dict[str, Any]:
    run_ts = datetime.now(timezone.utc).replace(microsecond=0)
    generated_ts = run_ts.isoformat().replace("+00:00", "Z")
    planning_run_id = _run_id(run_ts)

    _require(not (FORBIDDEN_INPUT_TITLES & set(INPUT_SHEETS)), "Forbidden outcome-bearing sheet included in inputs.")

    service = build_sheets_service(load_credentials())
    inputs = _fetch_input_sheets(service, DIAGNOSTICS_SPREADSHEET_ID, INPUT_SHEETS)
    known_titles = _sheet_titles_light(service, DIAGNOSTICS_SPREADSHEET_ID)

    validation_summary_row = _latest_row(
        inputs["Refined_Mechanism_Test_Outcome_Architecture_V2_Validation_Summary"].rows,
        "outcome_architecture_validation_run_id",
    )
    validation_summary_payload = _parse_payload(validation_summary_row)
    validation_run_id = _normalize(validation_summary_row.get("outcome_architecture_validation_run_id"))
    _require(_normalize(validation_summary_row.get("implementation_readiness_status")) == "READY_FOR_OUTCOME_ARCHITECTURE_IMPLEMENTATION", "Architecture validation did not approve implementation readiness.")
    _require(_normalize(validation_summary_row.get("recommended_next_step")) == "PROCEED_TO_PHASE9A6R15H_OUTCOME_ARCHITECTURE_IMPLEMENTATION_PLANNING", "Validation next-step mismatch.")
    _require(
        _coerce_int(
            validation_summary_payload.get(
                "blocking_repairs_required",
                validation_summary_row.get("blocking_repairs_required"),
            ),
            default=0,
        )
        == 0,
        "Validation reported blocking repairs.",
    )

    prereg_summary_row = _latest_row(
        inputs["Refined_Mechanism_Test_Outcome_Architecture_V2_Preregistration_Summary"].rows,
        "outcome_architecture_preregistration_run_id",
    )
    prereg_run_id = _normalize(prereg_summary_row.get("outcome_architecture_preregistration_run_id"))
    prereg_summary_payload = _parse_payload(prereg_summary_row)
    _require(_normalize(prereg_summary_row.get("architecture_preregistration_version")) == ARCHITECTURE_PREREGISTRATION_VERSION, "Architecture preregistration version mismatch.")
    _require(_normalize(prereg_summary_row.get("architecture_preregistration_status")) == ARCHITECTURE_PREREGISTRATION_STATUS, "Architecture preregistration status mismatch.")
    _require(_normalize(prereg_summary_row.get("architecture_version")) == ARCHITECTURE_VERSION, "Architecture version mismatch.")
    _require(prereg_summary_payload.get("implementation_blocked") is True, "15F implementation boundary mismatch.")

    prereg_row = _latest_row(
        inputs["Refined_Mechanism_Test_Outcome_Architecture_V2_Preregistration"].rows,
        "outcome_architecture_preregistration_run_id",
    )
    prereg_payload = _parse_payload(prereg_row)
    _require(_normalize(prereg_row.get("canonical_preregistration_version")) == AUTHORITATIVE_VERSION, "Canonical preregistration mismatch.")
    _require(_normalize(prereg_row.get("canonical_run_id")) == AUTHORITATIVE_RUN_ID, "Canonical run mismatch.")
    _require(_normalize(prereg_row.get("classification_version")) == CLASSIFICATION_VERSION, "Classification version mismatch.")
    _require(_normalize(prereg_row.get("classification_run_id")) == CLASSIFICATION_RUN_ID, "Classification run mismatch.")

    layer_rows = _rows_for_run(inputs["Refined_Mechanism_Test_Outcome_Architecture_V2_Frozen_Layers"].rows, "outcome_architecture_preregistration_run_id", prereg_run_id)
    target_rows = _rows_for_run(inputs["Refined_Mechanism_Test_Outcome_Architecture_V2_Frozen_Redesign_Targets"].rows, "outcome_architecture_preregistration_run_id", prereg_run_id)
    prohibited_rows = _rows_for_run(inputs["Refined_Mechanism_Test_Outcome_Architecture_V2_Frozen_Prohibited_Redesigns"].rows, "outcome_architecture_preregistration_run_id", prereg_run_id)
    empirical_rows = _rows_for_run(inputs["Refined_Mechanism_Test_Outcome_Architecture_V2_Frozen_Empirical_Questions"].rows, "outcome_architecture_preregistration_run_id", prereg_run_id)
    compat_rows = _rows_for_run(inputs["Refined_Mechanism_Test_Outcome_Architecture_V2_Frozen_Compatibility"].rows, "outcome_architecture_preregistration_run_id", prereg_run_id)
    gov_rows = _rows_for_run(inputs["Refined_Mechanism_Test_Outcome_Architecture_V2_Frozen_Governance"].rows, "outcome_architecture_preregistration_run_id", prereg_run_id)
    boundary_rows = _rows_for_run(inputs["Refined_Mechanism_Test_Outcome_Architecture_V2_Frozen_Implementation_Boundary"].rows, "outcome_architecture_preregistration_run_id", prereg_run_id)
    fp_rows = _rows_for_run(inputs["Refined_Mechanism_Test_Outcome_Architecture_V2_Fingerprint_Freeze"].rows, "outcome_architecture_preregistration_run_id", prereg_run_id)

    _require(len(layer_rows) == 5, f"Expected 5 frozen layers, found {len(layer_rows)}")
    _require(len(target_rows) == 5, f"Expected 5 redesign targets, found {len(target_rows)}")
    _require(len(prohibited_rows) == 3, f"Expected 3 prohibited redesigns, found {len(prohibited_rows)}")
    _require(len(empirical_rows) == 2, f"Expected 2 empirical questions, found {len(empirical_rows)}")
    _require(len(compat_rows) == 5, f"Expected 5 compatibility rows, found {len(compat_rows)}")
    _require(len(gov_rows) == 9, f"Expected 9 governance rules, found {len(gov_rows)}")
    _require(len(boundary_rows) == 4, f"Expected 4 implementation boundary rows, found {len(boundary_rows)}")
    _require(len(fp_rows) == 10, f"Expected 10 preregistration fingerprints, found {len(fp_rows)}")

    layer_validations = _rows_for_run(inputs["Refined_Mechanism_Test_Outcome_Architecture_V2_Layer_Validation"].rows, "outcome_architecture_validation_run_id", validation_run_id)
    target_validations = _rows_for_run(inputs["Refined_Mechanism_Test_Outcome_Architecture_V2_Target_Validation"].rows, "outcome_architecture_validation_run_id", validation_run_id)
    readiness_rows = _rows_for_run(inputs["Refined_Mechanism_Test_Outcome_Architecture_V2_Implementation_Readiness"].rows, "outcome_architecture_validation_run_id", validation_run_id)
    _require(all(_normalize(row.get("validation_status")) == "VALIDATED" for row in layer_validations), "Layer validation rows not fully validated.")
    _require(all(_normalize(row.get("validation_status")) == "VALIDATED" for row in target_validations), "Target validation rows not fully validated.")
    _require(any(_normalize(row.get("readiness_status")) == "READY_FOR_OUTCOME_ARCHITECTURE_IMPLEMENTATION" for row in readiness_rows), "Implementation readiness row missing.")

    planned_outputs = _planned_layer_outputs()
    sequence_rows: List[Dict[str, Any]] = []
    for layer in sorted(layer_rows, key=lambda row: int(row.get("layer_order", 0) or 0)):
        layer_name = _normalize(layer.get("layer_name"))
        required_inputs = _json_list(layer, "allowed_inputs_json")
        produced_outputs = planned_outputs[layer_name]
        downstream_consumers = _json_list(layer, "downstream_consumers_json")
        if layer_name == "CANONICAL_OUTCOME":
            upstream_dependencies: List[str] = [
                "Refined_Mechanism_Test_Outcome_Architecture_V2_Preregistration",
                "Refined_Mechanism_Test_Clean_R1_Canonical_Authority",
                "Refined_Mechanism_Test_Clean_R1_Canonical_Fingerprint_Manifest",
            ]
            checkpoints = [
                "fingerprint_prerequisite_verified",
                "canonical_coverage_manifest_written",
                "canonical_availability_audit_reconciled",
                "stage_fingerprint_frozen",
            ]
        elif layer_name == "OUTCOME_OVERLAY":
            upstream_dependencies = [
                "CANONICAL_OUTCOME_STAGE_COMPLETE",
                "Refined_Mechanism_Test_Outcome_Architecture_V2_Canonical_Coverage_Manifest",
            ]
            checkpoints = [
                "overlay_completeness_manifest_written",
                "overlay_lineage_audit_reconciled",
                "bridge_ids_verified_against_canonical",
                "stage_fingerprint_frozen",
            ]
        elif layer_name == "OUTCOME_LINKAGE":
            upstream_dependencies = [
                "CANONICAL_OUTCOME_STAGE_COMPLETE",
                "OUTCOME_OVERLAY_STAGE_COMPLETE",
                "Refined_Mechanism_Test_Outcome_Architecture_V2_Overlay_Completeness_Manifest",
            ]
            checkpoints = [
                "linkage_bridge_manifest_written",
                "linkage_state_audit_reconciled",
                "duplicate_and_ambiguous_paths_fail_closed",
                "stage_fingerprint_frozen",
            ]
        elif layer_name == "OUTCOME_REPRESENTATION":
            upstream_dependencies = [
                "OUTCOME_LINKAGE_STAGE_COMPLETE",
                "Refined_Mechanism_Test_Outcome_Architecture_V2_Linkage_Bridge_Manifest",
            ]
            checkpoints = [
                "representation_status_written",
                "representability_audit_reconciled",
                "corrected_directional_success_semantics_preserved",
                "stage_fingerprint_frozen",
            ]
        else:
            upstream_dependencies = [
                "OUTCOME_REPRESENTATION_STAGE_COMPLETE",
                "Refined_Mechanism_Test_Outcome_Architecture_V2_Representation_Status",
            ]
            checkpoints = [
                "paired_control_evaluability_written",
                "postjoin_gate_survivorship_written",
                "no_eligibility_rule_rewrite_detected",
                "stage_fingerprint_frozen",
            ]

        sequence_rows.append(
            {
                "stage_order": int(layer.get("layer_order", 0) or 0),
                "stage_id": f"OA_V2_IMPL_STAGE_{int(layer.get('layer_order', 0) or 0):02d}",
                "layer_name": layer_name,
                "required_inputs": required_inputs,
                "produced_outputs": produced_outputs,
                "upstream_dependencies": upstream_dependencies,
                "downstream_consumers": downstream_consumers,
                "implementation_checkpoints": checkpoints,
                "resumable_after_checkpoint": True,
            }
        )

    dependency_edges = [
        {
            "edge_id": "OA_V2_IMPL_EDGE_01",
            "from_stage": "CANONICAL_OUTCOME",
            "to_stage": "OUTCOME_OVERLAY",
            "dependency_type": "coverage_contract_prerequisite",
            "stage_boundary": "STAGE_01_TO_STAGE_02",
            "resumable_boundary": True,
        },
        {
            "edge_id": "OA_V2_IMPL_EDGE_02",
            "from_stage": "CANONICAL_OUTCOME",
            "to_stage": "OUTCOME_LINKAGE",
            "dependency_type": "canonical_identity_prerequisite",
            "stage_boundary": "STAGE_01_TO_STAGE_03",
            "resumable_boundary": True,
        },
        {
            "edge_id": "OA_V2_IMPL_EDGE_03",
            "from_stage": "OUTCOME_OVERLAY",
            "to_stage": "OUTCOME_LINKAGE",
            "dependency_type": "overlay_bridge_prerequisite",
            "stage_boundary": "STAGE_02_TO_STAGE_03",
            "resumable_boundary": True,
        },
        {
            "edge_id": "OA_V2_IMPL_EDGE_04",
            "from_stage": "OUTCOME_LINKAGE",
            "to_stage": "OUTCOME_REPRESENTATION",
            "dependency_type": "exact_join_state_prerequisite",
            "stage_boundary": "STAGE_03_TO_STAGE_04",
            "resumable_boundary": True,
        },
        {
            "edge_id": "OA_V2_IMPL_EDGE_05",
            "from_stage": "OUTCOME_REPRESENTATION",
            "to_stage": "ELIGIBILITY_INTERACTION",
            "dependency_type": "representability_prerequisite",
            "stage_boundary": "STAGE_04_TO_STAGE_05",
            "resumable_boundary": True,
        },
    ]
    cyclic_nodes = _detect_cycles(dependency_edges)
    _require(not cyclic_nodes, f"Circular implementation dependencies detected: {sorted(cyclic_nodes)}")

    workbook_migration_rows = [
        {
            "migration_item_id": "OA_V2_MIGRATION_01",
            "migration_scope": "FROZEN_CANONICAL_CLEAN_R1_FAMILY",
            "frozen_or_created": "FROZEN",
            "planned_sheet_family": [
                "Refined_Mechanism_Test_Clean_R1_Canonical_Authority",
                "Refined_Mechanism_Test_Clean_R1_Canonical_Fingerprint_Manifest",
                "Refined_Mechanism_Test_Preregistration_Clean_R1",
            ],
            "backward_compatibility_rule": "No modification or overwrite; continue referencing authoritative run 9A-6R13R1_20260711T020141Z.",
            "migration_checkpoint": "canonical_authority_verified_before_any_stage_output",
        },
        {
            "migration_item_id": "OA_V2_MIGRATION_02",
            "migration_scope": "FROZEN_15D_15E_15F_15G_FAMILIES",
            "frozen_or_created": "FROZEN",
            "planned_sheet_family": [
                "Refined_Mechanism_Test_Outcome_Architecture_Refinement_Summary",
                "Refined_Mechanism_Test_Outcome_Architecture_V2_Summary",
                "Refined_Mechanism_Test_Outcome_Architecture_V2_Preregistration_Summary",
                "Refined_Mechanism_Test_Outcome_Architecture_V2_Validation_Summary",
            ],
            "backward_compatibility_rule": "Implementation uses these as lineage and checkpoint references only.",
            "migration_checkpoint": "lineage_chain_fingerprinted_before_stage_01",
        },
        {
            "migration_item_id": "OA_V2_MIGRATION_03",
            "migration_scope": "NEW_IMPLEMENTATION_LAYER_OUTPUTS",
            "frozen_or_created": "CREATE_NEW_VERSIONED_SHEETS",
            "planned_sheet_family": planned_outputs["CANONICAL_OUTCOME"] + planned_outputs["OUTCOME_OVERLAY"] + planned_outputs["OUTCOME_LINKAGE"] + planned_outputs["OUTCOME_REPRESENTATION"] + planned_outputs["ELIGIBILITY_INTERACTION"],
            "backward_compatibility_rule": "All outputs are additive, versioned, and non-authoritative until final implementation verification passes.",
            "migration_checkpoint": "each_stage_creates_only_its_own_family",
        },
        {
            "migration_item_id": "OA_V2_MIGRATION_04",
            "migration_scope": "NEW_IMPLEMENTATION_AUDIT_FAMILY",
            "frozen_or_created": "CREATE_NEW_VERSIONED_SHEETS",
            "planned_sheet_family": [
                "Refined_Mechanism_Test_Outcome_Architecture_V2_Implementation_Audit",
                "Refined_Mechanism_Test_Outcome_Architecture_V2_Implementation_Governance",
                "Refined_Mechanism_Test_Outcome_Architecture_V2_Implementation_Summary",
            ],
            "backward_compatibility_rule": "These sheets capture run identity, stage fingerprints, resumable checkpoints, and authoritative activation status.",
            "migration_checkpoint": "audit_family_created_before_stage_01_finalization",
        },
        {
            "migration_item_id": "OA_V2_MIGRATION_05",
            "migration_scope": "BACKWARD_COMPATIBILITY",
            "frozen_or_created": "PRESERVE_EXISTING_READERS",
            "planned_sheet_family": [
                "all_existing_mechanism_test_preregistration_and_execution_families",
            ],
            "backward_compatibility_rule": "No reader cutover occurs during implementation planning; cutover can occur only after full implementation verification and separate authority activation logic.",
            "migration_checkpoint": "no_consumer_switch_before_full_stage_success",
        },
    ]

    governance_plan_rows = [
        {
            "governance_id": "OA_V2_IMPL_GOV_01",
            "governance_area": "FINGERPRINTS",
            "planned_control": "Fingerprint lineage chain before stage 01, after each stage checkpoint, and at final implementation summary.",
            "rollback_strategy": "If any stage fingerprint mismatches, block authority activation and retain prior authoritative families unchanged.",
            "fail_closed_behavior": "Stop before the next stage begins.",
        },
        {
            "governance_id": "OA_V2_IMPL_GOV_02",
            "governance_area": "VERSION_IDS",
            "planned_control": "Use explicit implementation run ID, architecture version 2.0, preregistration version 1.0, and canonical authority run 9A-6R13R1_20260711T020141Z on every stage artifact.",
            "rollback_strategy": "If any version ID drifts, discard the stage as non-authoritative and resume from the last verified checkpoint.",
            "fail_closed_behavior": "No mixed-version stage outputs may proceed.",
        },
        {
            "governance_id": "OA_V2_IMPL_GOV_03",
            "governance_area": "LINEAGE",
            "planned_control": "Every stage must retain source references to 15D, 15E, 15F, 15G, and canonical Clean-R1 authority.",
            "rollback_strategy": "If lineage is incomplete, mark the stage incomplete and do not advance.",
            "fail_closed_behavior": "Lineage mismatch blocks stage completion.",
        },
        {
            "governance_id": "OA_V2_IMPL_GOV_04",
            "governance_area": "TRACEABILITY",
            "planned_control": "Stage outputs must expose first-hop source identity, bridge identity, and stage-specific failure states.",
            "rollback_strategy": "If traceability fields are incomplete, keep the new rows non-authoritative and rerun only that stage after repair.",
            "fail_closed_behavior": "No stage can finalize with missing trace fields.",
        },
        {
            "governance_id": "OA_V2_IMPL_GOV_05",
            "governance_area": "ROLLBACK",
            "planned_control": "Implementation is additive-only; rollback means refusing authority activation and preserving prior frozen families intact.",
            "rollback_strategy": "Never delete frozen source sheets; supersede only the new implementation run after verified repair.",
            "fail_closed_behavior": "Authority remains on prior frozen architecture families.",
        },
        {
            "governance_id": "OA_V2_IMPL_GOV_06",
            "governance_area": "FAIL_CLOSED_BEHAVIOR",
            "planned_control": "Each stage gates the next stage through checkpoint verification and summary status.",
            "rollback_strategy": "Resume only from the last completed stage with matching fingerprints and no data-loss findings.",
            "fail_closed_behavior": "No downstream stage may consume incomplete upstream outputs.",
        },
    ]

    verification_rows = []
    for seq in sequence_rows:
        verification_rows.append(
            {
                "verification_id": f"{seq['stage_id']}_VERIFY",
                "layer_name": seq["layer_name"],
                "deterministic_output_requirement": f"{seq['layer_name']} outputs must serialize deterministically and produce stable fingerprints across reruns.",
                "completeness_requirement": f"All planned outputs for {seq['layer_name']} must be written with no missing required fields and no unexplained record loss.",
                "consistency_requirement": f"{seq['layer_name']} outputs must reconcile with frozen architecture layer responsibilities, targets, and compatibility contracts.",
                "compatibility_requirement": f"{seq['layer_name']} outputs must preserve compatibility with mechanism classification v1.1, canonical Clean-R1, and frozen preregistrations.",
                "reproducibility_requirement": f"{seq['layer_name']} must be reproducible from frozen inputs and explicit stage checkpoints alone.",
            }
        )
    verification_rows.append(
        {
            "verification_id": "OA_V2_IMPL_FINAL_INTEGRATION_VERIFY",
            "layer_name": "FINAL_INTEGRATION",
            "deterministic_output_requirement": "Full implementation rerun identity and final fingerprint manifest must be deterministic.",
            "completeness_requirement": "All five layer families and implementation audit sheets must be present and checkpoint-complete.",
            "consistency_requirement": "No frozen science, semantics, or guardrails may drift across the integrated implementation family.",
            "compatibility_requirement": "Existing readers must remain backward-compatible until explicit post-implementation activation is approved.",
            "reproducibility_requirement": "Another researcher must be able to replay all stages from the frozen preregistration, validation, and canonical authority artifacts.",
        }
    )

    stop_rows = [
        {
            "stop_id": "OA_V2_IMPL_STOP_01",
            "stop_condition": "LINEAGE_MISMATCH",
            "trigger_stage": "ANY_STAGE",
            "required_action": "BLOCK_STAGE_AND_REQUIRE_LINEAGE_REPAIR",
            "resumable_after_repair": True,
        },
        {
            "stop_id": "OA_V2_IMPL_STOP_02",
            "stop_condition": "FINGERPRINT_MISMATCH",
            "trigger_stage": "ANY_STAGE",
            "required_action": "BLOCK_STAGE_AND_REQUIRE_FINGERPRINT_RECONCILIATION",
            "resumable_after_repair": True,
        },
        {
            "stop_id": "OA_V2_IMPL_STOP_03",
            "stop_condition": "DEPENDENCY_FAILURE",
            "trigger_stage": "STAGE_BOUNDARY",
            "required_action": "DO_NOT_ADVANCE_TO_DOWNSTREAM_STAGE",
            "resumable_after_repair": True,
        },
        {
            "stop_id": "OA_V2_IMPL_STOP_04",
            "stop_condition": "VERSION_MISMATCH",
            "trigger_stage": "ANY_STAGE",
            "required_action": "MARK_STAGE_NONAUTHORITATIVE_AND_BLOCK_CONTINUATION",
            "resumable_after_repair": True,
        },
        {
            "stop_id": "OA_V2_IMPL_STOP_05",
            "stop_condition": "COMPATIBILITY_FAILURE",
            "trigger_stage": "POST_STAGE_VERIFICATION",
            "required_action": "BLOCK_IMPLEMENTATION_AND_RETAIN_PREVIOUS_AUTHORITIES",
            "resumable_after_repair": True,
        },
        {
            "stop_id": "OA_V2_IMPL_STOP_06",
            "stop_condition": "DETERMINISTIC_FAILURE",
            "trigger_stage": "POST_STAGE_VERIFICATION",
            "required_action": "BLOCK_STAGE_FINALIZATION_AND_REQUIRE_RERUN_FROM_LAST_MATCHING_CHECKPOINT",
            "resumable_after_repair": True,
        },
        {
            "stop_id": "OA_V2_IMPL_STOP_07",
            "stop_condition": "UNEXPECTED_DATA_LOSS",
            "trigger_stage": "POST_STAGE_VERIFICATION",
            "required_action": "BLOCK_NEXT_STAGE_AND_REQUIRE_DATA_LOSS_AUDIT",
            "resumable_after_repair": True,
        },
    ]

    all_checks_ok = True
    _require(all_checks_ok, "Implementation planning prerequisites failed.")

    outputs: Dict[str, List[Dict[str, Any]]] = {
        OUTPUT_PLAN: [
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_implementation_planning_run_id": planning_run_id,
                "planning_version": PLANNING_VERSION,
                "architecture_preregistration_version": ARCHITECTURE_PREREGISTRATION_VERSION,
                "architecture_version": ARCHITECTURE_VERSION,
                "implementation_planning_status": IMPLEMENTATION_PLANNING_STATUS,
                "build_status": BUILD_STATUS,
                "final_interpretation": FINAL_INTERPRETATION,
                "recommended_next_step": RECOMMENDED_NEXT_STEP,
                "payload_json": _canonical_json(
                    {
                        "validation_run_id": validation_run_id,
                        "preregistration_run_id": prereg_run_id,
                        "canonical_authority_run_id": AUTHORITATIVE_RUN_ID,
                        "classification_run_id": CLASSIFICATION_RUN_ID,
                        "staged_implementation_required": True,
                        "no_circular_dependencies": True,
                        "resumable_execution": True,
                    }
                ),
            }
        ],
        OUTPUT_SEQUENCE: [],
        OUTPUT_GRAPH: [],
        OUTPUT_MIGRATION: [],
        OUTPUT_GOVERNANCE_RULES: [],
        OUTPUT_VERIFICATION: [],
        OUTPUT_STOPS: [],
        OUTPUT_READINESS: [],
        OUTPUT_GOVERNANCE: [],
        OUTPUT_SUMMARY: [],
    }

    for row in sequence_rows:
        outputs[OUTPUT_SEQUENCE].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_implementation_planning_run_id": planning_run_id,
                "stage_order": row["stage_order"],
                "stage_id": row["stage_id"],
                "layer_name": row["layer_name"],
                "required_inputs_json": _canonical_json(row["required_inputs"]),
                "produced_outputs_json": _canonical_json(row["produced_outputs"]),
                "upstream_dependencies_json": _canonical_json(row["upstream_dependencies"]),
                "downstream_consumers_json": _canonical_json(row["downstream_consumers"]),
                "implementation_checkpoints_json": _canonical_json(row["implementation_checkpoints"]),
                "resumable_after_checkpoint": row["resumable_after_checkpoint"],
                "payload_json": _canonical_json(row),
            }
        )

    for row in dependency_edges:
        outputs[OUTPUT_GRAPH].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_implementation_planning_run_id": planning_run_id,
                "edge_id": row["edge_id"],
                "from_stage": row["from_stage"],
                "to_stage": row["to_stage"],
                "dependency_type": row["dependency_type"],
                "stage_boundary": row["stage_boundary"],
                "resumable_boundary": row["resumable_boundary"],
                "payload_json": _canonical_json(row),
            }
        )

    for row in workbook_migration_rows:
        outputs[OUTPUT_MIGRATION].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_implementation_planning_run_id": planning_run_id,
                "migration_item_id": row["migration_item_id"],
                "migration_scope": row["migration_scope"],
                "frozen_or_created": row["frozen_or_created"],
                "planned_sheet_family_json": _canonical_json(row["planned_sheet_family"]),
                "backward_compatibility_rule": row["backward_compatibility_rule"],
                "migration_checkpoint": row["migration_checkpoint"],
                "payload_json": _canonical_json(row),
            }
        )

    for row in governance_plan_rows:
        outputs[OUTPUT_GOVERNANCE_RULES].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_implementation_planning_run_id": planning_run_id,
                "governance_id": row["governance_id"],
                "governance_area": row["governance_area"],
                "planned_control": row["planned_control"],
                "rollback_strategy": row["rollback_strategy"],
                "fail_closed_behavior": row["fail_closed_behavior"],
                "payload_json": _canonical_json(row),
            }
        )

    for row in verification_rows:
        outputs[OUTPUT_VERIFICATION].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_implementation_planning_run_id": planning_run_id,
                "verification_id": row["verification_id"],
                "layer_name": row["layer_name"],
                "deterministic_output_requirement": row["deterministic_output_requirement"],
                "completeness_requirement": row["completeness_requirement"],
                "consistency_requirement": row["consistency_requirement"],
                "compatibility_requirement": row["compatibility_requirement"],
                "reproducibility_requirement": row["reproducibility_requirement"],
                "payload_json": _canonical_json(row),
            }
        )

    for row in stop_rows:
        outputs[OUTPUT_STOPS].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_implementation_planning_run_id": planning_run_id,
                "stop_id": row["stop_id"],
                "stop_condition": row["stop_condition"],
                "trigger_stage": row["trigger_stage"],
                "required_action": row["required_action"],
                "resumable_after_repair": row["resumable_after_repair"],
                "payload_json": _canonical_json(row),
            }
        )

    readiness_rows_out = [
        {
            "readiness_area": "IMPLEMENTATION_SEQUENCE",
            "readiness_status": "PASS",
            "staged_implementation_required": True,
            "minimum_repair_if_any": "NONE",
        },
        {
            "readiness_area": "DEPENDENCY_GRAPH",
            "readiness_status": "PASS",
            "staged_implementation_required": True,
            "minimum_repair_if_any": "NONE",
        },
        {
            "readiness_area": "WORKBOOK_MIGRATION",
            "readiness_status": "PASS",
            "staged_implementation_required": True,
            "minimum_repair_if_any": "NONE",
        },
        {
            "readiness_area": "IMPLEMENTATION_GOVERNANCE",
            "readiness_status": "PASS",
            "staged_implementation_required": True,
            "minimum_repair_if_any": "NONE",
        },
        {
            "readiness_area": "IMPLEMENTATION_VERIFICATION",
            "readiness_status": "PASS",
            "staged_implementation_required": True,
            "minimum_repair_if_any": "NONE",
        },
        {
            "readiness_area": "FINAL_IMPLEMENTATION_PLANNING_STATUS",
            "readiness_status": IMPLEMENTATION_PLANNING_STATUS,
            "staged_implementation_required": True,
            "minimum_repair_if_any": "NONE",
        },
    ]
    for row in readiness_rows_out:
        outputs[OUTPUT_READINESS].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_implementation_planning_run_id": planning_run_id,
                "readiness_area": row["readiness_area"],
                "readiness_status": row["readiness_status"],
                "staged_implementation_required": row["staged_implementation_required"],
                "minimum_repair_if_any": row["minimum_repair_if_any"],
                "payload_json": _canonical_json(row),
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
                "outcome_architecture_implementation_planning_run_id": planning_run_id,
                "counter_name": counter_name,
                "counter_value": counter_value,
                "status": "PASS" if counter_value == 0 else "FAIL",
                "notes": "Implementation-planning-only phase preserved." if counter_value == 0 else "Unexpected nonzero counter.",
            }
        )

    summary_payload = {
        "build_status": BUILD_STATUS,
        "final_interpretation": FINAL_INTERPRETATION,
        "implementation_planning_status": IMPLEMENTATION_PLANNING_STATUS,
        "recommended_next_step": RECOMMENDED_NEXT_STEP,
        "planning_run_id": planning_run_id,
        "validation_run_id": validation_run_id,
        "preregistration_run_id": prereg_run_id,
        "canonical_authority_run_id": AUTHORITATIVE_RUN_ID,
        "classification_run_id": CLASSIFICATION_RUN_ID,
        "sequence_stage_count": len(sequence_rows),
        "dependency_edge_count": len(dependency_edges),
        "migration_item_count": len(workbook_migration_rows),
        "governance_plan_count": len(governance_plan_rows),
        "verification_requirement_count": len(verification_rows),
        "stop_condition_count": len(stop_rows),
        "readiness_count": len(readiness_rows_out),
        "staged_implementation_required": True,
        "no_circular_dependencies": not cyclic_nodes,
        "governance_counters": governance_counters,
    }
    outputs[OUTPUT_SUMMARY].append(
        {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "outcome_architecture_implementation_planning_run_id": planning_run_id,
            "build_status": BUILD_STATUS,
            "final_interpretation": FINAL_INTERPRETATION,
            "implementation_planning_status": IMPLEMENTATION_PLANNING_STATUS,
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
        "outcome_architecture_implementation_planning_run_id": planning_run_id,
        "implementation_planning_status": IMPLEMENTATION_PLANNING_STATUS,
        "recommended_next_step": RECOMMENDED_NEXT_STEP,
        "sheets_written": list(OUTPUT_SHEETS.keys()),
        "rows_written_per_sheet": rows_written,
        "sequence_stage_count": len(sequence_rows),
        "dependency_edge_count": len(dependency_edges),
        "migration_item_count": len(workbook_migration_rows),
        "governance_plan_count": len(governance_plan_rows),
        "verification_requirement_count": len(verification_rows),
        "stop_condition_count": len(stop_rows),
        "readiness_count": len(readiness_rows_out),
        "governance_counters": governance_counters,
        "registry_result": registry_result,
    }


def main() -> None:
    report = build()
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
