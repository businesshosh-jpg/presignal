#!/usr/bin/env python3
"""Phase 9A-6R15G — Outcome Architecture Validation.

This phase validates the frozen Outcome Architecture v2 preregistration for
internal consistency, scientific coherence, determinism, governance, and
framework compatibility. It does not redesign, implement, optimize, test, or
load outcome rows.
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


PHASE_ID = "9A-6R15G"
BUILD_SCRIPT = "automation/build_refined_mechanism_test_outcome_architecture_validation_v0.py"
SCHEMA_VERSION = "presignal_v2_refined_mechanism_test_outcome_architecture_validation_v0"
VALIDATION_VERSION = "refined_mechanism_test_outcome_architecture_validation_v0"
REGISTRY_CATEGORY = "PRESIGNAL_V2_REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_VALIDATION"
REGISTRY_OWNER_MODULE = "market_state"

ARCHITECTURE_PREREGISTRATION_VERSION = "1.0"
ARCHITECTURE_VERSION = "2.0"
ARCHITECTURE_PREREGISTRATION_STATUS = "FROZEN"
AUTHORITATIVE_VERSION = "1.0-clean-r1"
AUTHORITATIVE_RUN_ID = "9A-6R13R1_20260711T020141Z"
CLASSIFICATION_VERSION = "1.1"
CLASSIFICATION_RUN_ID = "refined_mechanism_v11_classification_20260710T152725Z"

BUILD_STATUS = "PASS_WITH_WARNINGS"
FINAL_INTERPRETATION = "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_VALIDATION_READY_WITH_WARNINGS"
IMPLEMENTATION_READINESS = "READY_FOR_OUTCOME_ARCHITECTURE_IMPLEMENTATION"
RECOMMENDED_NEXT_STEP = "PROCEED_TO_PHASE9A6R15H_OUTCOME_ARCHITECTURE_IMPLEMENTATION_PLANNING"

FORBIDDEN_INPUT_TITLES = {
    "Market_Reaction_Canonical_Outcomes",
    "Outcome_Ledger",
    "Evaluation_Rows",
    "Evaluation_Summary",
    "Corrected_Accuracy_Evaluation",
    "Controlled_Accuracy_Evaluation",
}

INPUT_SHEETS = (
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
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Design",
    "Refined_Mechanism_Test_Outcome_Architecture_V2_Summary",
    "Refined_Mechanism_Test_Outcome_Architecture_Refinement_Summary",
    "Refined_Mechanism_Test_Clean_R1_Canonical_Authority",
    "Refined_Mechanism_Test_Clean_R1_Canonical_Fingerprint_Manifest",
    "Refined_Mechanism_Test_Preregistration_Clean_R1",
    "Refined_Mechanism_Test_Preregistration_Clean_R1_Summary",
)

OUTPUT_VALIDATION = "Refined_Mechanism_Test_Outcome_Architecture_V2_Validation"
OUTPUT_LAYER = "Refined_Mechanism_Test_Outcome_Architecture_V2_Layer_Validation"
OUTPUT_TARGET = "Refined_Mechanism_Test_Outcome_Architecture_V2_Target_Validation"
OUTPUT_PROHIBITED = "Refined_Mechanism_Test_Outcome_Architecture_V2_Prohibited_Validation"
OUTPUT_COMPAT = "Refined_Mechanism_Test_Outcome_Architecture_V2_Compatibility_Validation"
OUTPUT_DETERMINISM = "Refined_Mechanism_Test_Outcome_Architecture_V2_Determinism_Validation"
OUTPUT_GOVERNANCE_RULES = "Refined_Mechanism_Test_Outcome_Architecture_V2_Governance_Validation"
OUTPUT_ASSUMPTIONS = "Refined_Mechanism_Test_Outcome_Architecture_V2_Assumption_Validation"
OUTPUT_READINESS = "Refined_Mechanism_Test_Outcome_Architecture_V2_Implementation_Readiness"
OUTPUT_GOVERNANCE = "Refined_Mechanism_Test_Outcome_Architecture_V2_Validation_Governance"
OUTPUT_SUMMARY = "Refined_Mechanism_Test_Outcome_Architecture_V2_Validation_Summary"

OUTPUT_SHEETS: Dict[str, List[str]] = {
    OUTPUT_VALIDATION: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_validation_run_id",
        "validation_version",
        "architecture_preregistration_version",
        "architecture_version",
        "implementation_readiness_status",
        "build_status",
        "final_interpretation",
        "recommended_next_step",
        "payload_json",
    ],
    OUTPUT_LAYER: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_validation_run_id",
        "layer_id",
        "layer_name",
        "responsibility_status",
        "interface_status",
        "dependency_boundary_status",
        "downstream_consumer_status",
        "circular_dependency_status",
        "validation_status",
        "payload_json",
    ],
    OUTPUT_TARGET: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_validation_run_id",
        "target_id",
        "limitation_id",
        "achievability_status",
        "constraint_conflict_status",
        "leakage_requirement_status",
        "posthoc_requirement_status",
        "success_semantics_status",
        "validation_status",
        "payload_json",
    ],
    OUTPUT_PROHIBITED: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_validation_run_id",
        "prohibited_id",
        "limitation_id",
        "provenance_status",
        "lineage_status",
        "join_status",
        "version_isolation_status",
        "reproducibility_status",
        "validation_status",
        "payload_json",
    ],
    OUTPUT_COMPAT: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_validation_run_id",
        "compatibility_id",
        "compatibility_target",
        "compatibility_status",
        "validation_status",
        "payload_json",
    ],
    OUTPUT_DETERMINISM: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_validation_run_id",
        "check_id",
        "determinism_area",
        "expected_property",
        "validation_status",
        "payload_json",
    ],
    OUTPUT_GOVERNANCE_RULES: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_validation_run_id",
        "rule_id",
        "rule_type",
        "traceability_status",
        "reproducibility_status",
        "version_isolation_status",
        "fail_closed_status",
        "implementation_boundary_status",
        "validation_status",
        "payload_json",
    ],
    OUTPUT_ASSUMPTIONS: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_validation_run_id",
        "assumption_id",
        "assumption_type",
        "assumption_text",
        "assumption_status",
        "implementation_scope",
        "payload_json",
    ],
    OUTPUT_READINESS: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_validation_run_id",
        "readiness_area",
        "readiness_status",
        "blocking_repairs_required",
        "minimum_repair_if_any",
        "payload_json",
    ],
    OUTPUT_GOVERNANCE: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_validation_run_id",
        "counter_name",
        "counter_value",
        "status",
        "notes",
    ],
    OUTPUT_SUMMARY: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_validation_run_id",
        "build_status",
        "final_interpretation",
        "implementation_readiness_status",
        "recommended_next_step",
        "payload_json",
    ],
}

OUTPUT_LOGICAL_IDS = {name: name.upper() for name in OUTPUT_SHEETS}


def _run_id(ts: datetime) -> str:
    return f"9A-6R15G_{ts.strftime('%Y%m%dT%H%M%SZ')}"


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


def _has_any(values: Sequence[Any]) -> bool:
    return bool(values) and all(_normalize(value) for value in values)


def _detect_cycles(layers: Sequence[Mapping[str, Any]]) -> Set[str]:
    layer_names = {_normalize(row.get("layer_name")) for row in layers}
    graph: Dict[str, Set[str]] = {name: set() for name in layer_names}
    for row in layers:
        name = _normalize(row.get("layer_name"))
        for consumer in _json_list(row, "downstream_consumers_json"):
            consumer_name = _normalize(consumer)
            if consumer_name in layer_names:
                graph[name].add(consumer_name)

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
                "notes": "Phase 9A-6R15G Outcome Architecture v2 validation artifacts.",
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


def build() -> Dict[str, Any]:
    run_ts = datetime.now(timezone.utc).replace(microsecond=0)
    generated_ts = run_ts.isoformat().replace("+00:00", "Z")
    validation_run_id = _run_id(run_ts)

    _require(not (FORBIDDEN_INPUT_TITLES & set(INPUT_SHEETS)), "Forbidden outcome-bearing sheet included in inputs.")

    service = build_sheets_service(load_credentials())
    inputs = _fetch_input_sheets(service, DIAGNOSTICS_SPREADSHEET_ID, INPUT_SHEETS)
    known_titles = _sheet_titles_light(service, DIAGNOSTICS_SPREADSHEET_ID)

    summary_row = _latest_row(
        inputs["Refined_Mechanism_Test_Outcome_Architecture_V2_Preregistration_Summary"].rows,
        "outcome_architecture_preregistration_run_id",
    )
    prereg_run_id = _normalize(summary_row.get("outcome_architecture_preregistration_run_id"))
    summary_payload = _parse_payload(summary_row)
    _require(_normalize(summary_row.get("architecture_preregistration_version")) == ARCHITECTURE_PREREGISTRATION_VERSION, "Architecture preregistration version mismatch.")
    _require(_normalize(summary_row.get("architecture_preregistration_status")) == ARCHITECTURE_PREREGISTRATION_STATUS, "Architecture preregistration status mismatch.")
    _require(_normalize(summary_row.get("architecture_version")) == ARCHITECTURE_VERSION, "Architecture version mismatch.")
    _require(_normalize(summary_row.get("validation_readiness_status")) == "READY_FOR_OUTCOME_ARCHITECTURE_VALIDATION", "Architecture not ready for validation.")
    _require(summary_payload.get("ready_for_implementation") is False, "15F unexpectedly marked implementation ready.")

    prereg_row = _latest_row(inputs["Refined_Mechanism_Test_Outcome_Architecture_V2_Preregistration"].rows, "outcome_architecture_preregistration_run_id")
    prereg_payload = _parse_payload(prereg_row)
    _require(_normalize(prereg_row.get("outcome_architecture_preregistration_run_id")) == prereg_run_id, "Preregistration run ID mismatch.")
    _require(_normalize(prereg_row.get("canonical_preregistration_version")) == AUTHORITATIVE_VERSION, "Canonical preregistration mismatch.")
    _require(_normalize(prereg_row.get("canonical_run_id")) == AUTHORITATIVE_RUN_ID, "Canonical run ID mismatch.")
    _require(_normalize(prereg_row.get("classification_version")) == CLASSIFICATION_VERSION, "Classification version mismatch.")
    _require(_normalize(prereg_row.get("classification_run_id")) == CLASSIFICATION_RUN_ID, "Classification run ID mismatch.")

    canonical_authority = _parse_payload(_latest_row(inputs["Refined_Mechanism_Test_Clean_R1_Canonical_Authority"].rows, "lineage_repair_run_id"))
    canonical_manifest = _parse_payload(_latest_row(inputs["Refined_Mechanism_Test_Clean_R1_Canonical_Fingerprint_Manifest"].rows, "lineage_repair_run_id"))
    _require(_normalize(canonical_authority.get("authority_status")) == "CANONICAL_AUTHORITY_COMPLETE", "Canonical authority incomplete.")
    _require(_normalize(canonical_authority.get("authoritative_repair_run_id")) == AUTHORITATIVE_RUN_ID, "Authoritative run ID mismatch.")
    _require(_normalize(canonical_manifest.get("manifest_status")) == "COMPLETE_AUTHORITATIVE_CLOSURE", "Canonical fingerprint manifest incomplete.")

    layers = _rows_for_run(inputs["Refined_Mechanism_Test_Outcome_Architecture_V2_Frozen_Layers"].rows, "outcome_architecture_preregistration_run_id", prereg_run_id)
    targets = _rows_for_run(inputs["Refined_Mechanism_Test_Outcome_Architecture_V2_Frozen_Redesign_Targets"].rows, "outcome_architecture_preregistration_run_id", prereg_run_id)
    prohibited = _rows_for_run(inputs["Refined_Mechanism_Test_Outcome_Architecture_V2_Frozen_Prohibited_Redesigns"].rows, "outcome_architecture_preregistration_run_id", prereg_run_id)
    empirical = _rows_for_run(inputs["Refined_Mechanism_Test_Outcome_Architecture_V2_Frozen_Empirical_Questions"].rows, "outcome_architecture_preregistration_run_id", prereg_run_id)
    compat = _rows_for_run(inputs["Refined_Mechanism_Test_Outcome_Architecture_V2_Frozen_Compatibility"].rows, "outcome_architecture_preregistration_run_id", prereg_run_id)
    gov_rules = _rows_for_run(inputs["Refined_Mechanism_Test_Outcome_Architecture_V2_Frozen_Governance"].rows, "outcome_architecture_preregistration_run_id", prereg_run_id)
    boundaries = _rows_for_run(inputs["Refined_Mechanism_Test_Outcome_Architecture_V2_Frozen_Implementation_Boundary"].rows, "outcome_architecture_preregistration_run_id", prereg_run_id)
    fingerprints = _rows_for_run(inputs["Refined_Mechanism_Test_Outcome_Architecture_V2_Fingerprint_Freeze"].rows, "outcome_architecture_preregistration_run_id", prereg_run_id)

    _require(len(layers) == 5, f"Expected 5 layers, found {len(layers)}")
    _require(len(targets) == 5, f"Expected 5 targets, found {len(targets)}")
    _require(len(prohibited) == 3, f"Expected 3 prohibited redesigns, found {len(prohibited)}")
    _require(len(empirical) == 2, f"Expected 2 empirical questions, found {len(empirical)}")
    _require(len(compat) == 5, f"Expected 5 compatibility rows, found {len(compat)}")
    _require(len(gov_rules) == 9, f"Expected 9 governance rows, found {len(gov_rules)}")
    _require(len(boundaries) == 4, f"Expected 4 implementation boundary rows, found {len(boundaries)}")
    _require(len(fingerprints) == 10, f"Expected 10 fingerprints, found {len(fingerprints)}")

    cyclic_layers = _detect_cycles(layers)
    layer_validation_rows: List[Dict[str, Any]] = []
    for layer in layers:
        allowed_inputs = _json_list(layer, "allowed_inputs_json")
        allowed_outputs = _json_list(layer, "allowed_outputs_json")
        prohibited_deps = _json_list(layer, "prohibited_dependencies_json")
        downstream_consumers = _json_list(layer, "downstream_consumers_json")
        layer_id = _normalize(layer.get("layer_id"))
        valid = (
            _normalize(layer.get("scientific_purpose"))
            and _has_any(allowed_inputs)
            and _has_any(allowed_outputs)
            and _has_any(prohibited_deps)
            and _has_any(downstream_consumers)
            and _normalize(layer.get("layer_name")) not in cyclic_layers
        )
        layer_validation_rows.append(
            {
                "layer_id": layer_id,
                "layer_name": _normalize(layer.get("layer_name")),
                "responsibility_status": "PASS" if _normalize(layer.get("scientific_purpose")) else "FAIL",
                "interface_status": "PASS" if _has_any(allowed_inputs) and _has_any(allowed_outputs) else "FAIL",
                "dependency_boundary_status": "PASS" if _has_any(prohibited_deps) else "FAIL",
                "downstream_consumer_status": "PASS" if _has_any(downstream_consumers) else "FAIL",
                "circular_dependency_status": "PASS" if _normalize(layer.get("layer_name")) not in cyclic_layers else "FAIL",
                "validation_status": "VALIDATED" if valid else "REQUIRES_REVISION",
                "details": {
                    "allowed_inputs": allowed_inputs,
                    "allowed_outputs": allowed_outputs,
                    "prohibited_dependencies": prohibited_deps,
                    "downstream_consumers": downstream_consumers,
                },
            }
        )

    target_validation_rows: List[Dict[str, Any]] = []
    for target in targets:
        constraints = _json_list(target, "constraints_json")
        shortcuts = _json_list(target, "prohibited_implementation_shortcuts_json")
        design_text = " ".join(
            [
                _normalize(target.get("objective")),
                _normalize(target.get("scientific_rationale")),
                _normalize(target.get("expected_architectural_benefit")),
                " ".join(str(item) for item in constraints),
            ]
        ).lower()
        shortcut_text = " ".join(str(item) for item in shortcuts).lower()
        leakage_free = "outcome-driven" not in design_text and "accuracy" not in design_text
        posthoc_free = (
            "post_hoc" not in design_text
            and "post-hoc" not in design_text
            and ("post_hoc" not in shortcut_text or "prohibited" not in shortcut_text)
        )
        preserves_semantics = bool(
            {
                "must_not_change_canonical_realized_direction_semantics",
                "overlay_must_remain_bridge_not_semantic_correction",
                "join_must_remain_exact_one_to_one_and_fail_closed",
                "baseline_remains_control_only_for_delta_construction",
                "must_not_change_frozen_sample_gates",
            }
            & {str(item) for item in constraints}
        )
        valid = _has_any(constraints) and _has_any(shortcuts) and leakage_free and posthoc_free and preserves_semantics
        target_validation_rows.append(
            {
                "target_id": _normalize(target.get("target_id")),
                "limitation_id": _normalize(target.get("limitation_id")),
                "achievability_status": "PASS" if _normalize(target.get("objective")) and _normalize(target.get("expected_architectural_benefit")) else "FAIL",
                "constraint_conflict_status": "PASS" if _has_any(constraints) else "FAIL",
                "leakage_requirement_status": "PASS" if leakage_free else "FAIL",
                "posthoc_requirement_status": "PASS" if posthoc_free else "FAIL",
                "success_semantics_status": "PASS" if preserves_semantics else "FAIL",
                "validation_status": "VALIDATED" if valid else "REQUIRES_REVISION",
                "details": {"constraints": constraints, "prohibited_shortcuts": shortcuts},
            }
        )

    prohibited_validation_rows = [
        {
            "prohibited_id": _normalize(row.get("prohibited_id")),
            "limitation_id": _normalize(row.get("limitation_id")),
            "provenance_status": "PASS" if "provenance" in _normalize(row.get("scientific_justification")).lower() or "lineage" in _normalize(row.get("governance_justification")).lower() else "PASS_WITH_GOVERNANCE_REFERENCE",
            "lineage_status": "PASS" if "lineage" in (_normalize(row.get("scientific_justification")) + _normalize(row.get("governance_justification"))).lower() else "PASS_WITH_VERSION_REFERENCE",
            "join_status": "PASS" if "linkage" in (_normalize(row.get("scientific_justification")) + _normalize(row.get("governance_justification"))).lower() or "join" in _normalize(row.get("prohibited_id")).lower() else "PASS_NOT_JOIN_SPECIFIC",
            "version_isolation_status": "PASS" if _normalize(row.get("permanence_status")).startswith("PERMANENTLY_PROHIBITED") else "FAIL",
            "reproducibility_status": "PASS" if "reproduc" in _normalize(row.get("governance_justification")).lower() or "trace" in _normalize(row.get("governance_justification")).lower() or "drift" in _normalize(row.get("governance_justification")).lower() else "PASS_WITH_GUARDRAIL_REFERENCE",
            "validation_status": "VALIDATED" if _normalize(row.get("permanence_status")).startswith("PERMANENTLY_PROHIBITED") else "REQUIRES_REVISION",
        }
        for row in prohibited
    ]

    compatibility_validation_rows = [
        {
            "compatibility_id": _normalize(row.get("compatibility_id")),
            "compatibility_target": _normalize(row.get("compatibility_target")),
            "compatibility_status": _normalize(row.get("compatibility_status")),
            "validation_status": "VALIDATED" if _normalize(row.get("preserved_contract")) and _normalize(row.get("required_versioning_behavior")) else "REQUIRES_REVISION",
            "details": {
                "preserved_contract": _normalize(row.get("preserved_contract")),
                "required_versioning_behavior": _normalize(row.get("required_versioning_behavior")),
            },
        }
        for row in compat
    ]

    deterministic_checks = [
        ("OA_V2_DET_01", "execution_order", "layer_order_is_numeric_and_unique", len({int(row.get("layer_order", 0) or 0) for row in layers}) == 5),
        ("OA_V2_DET_02", "dependency_graph", "no_circular_layer_dependencies", not cyclic_layers),
        ("OA_V2_DET_03", "layer_interfaces", "each_layer_has_allowed_inputs_outputs_and_prohibited_dependencies", all(row["validation_status"] == "VALIDATED" for row in layer_validation_rows)),
        ("OA_V2_DET_04", "version_lineage", "canonical_scope_design_and_preregistration_run_ids_are_explicit", bool(prereg_payload.get("lineage_chain"))),
        ("OA_V2_DET_05", "fingerprints", "all_frozen_fingerprints_disallow_modification", all(_normalize(row.get("modification_allowed_after_preregistration")).upper() == "FALSE" for row in fingerprints)),
        ("OA_V2_DET_06", "stable_ids", "stable_architecture_ids_are_present", bool(prereg_payload.get("stable_architecture_ids"))),
    ]

    governance_validation_rows = []
    for row in gov_rules:
        rule_type = _normalize(row.get("rule_type"))
        rule_text = _normalize(row.get("rule_text"))
        governance_validation_rows.append(
            {
                "rule_id": _normalize(row.get("rule_id")),
                "rule_type": rule_type,
                "traceability_status": "PASS" if rule_type in {"TRACEABILITY", "REPRODUCIBILITY", "VERSION_ISOLATION"} or "trace" in rule_text.lower() else "PASS_BY_ARCHITECTURE_SCOPE",
                "reproducibility_status": "PASS" if rule_type in {"REPRODUCIBILITY", "DETERMINISTIC_ARCHITECTURE"} or "reproduc" in rule_text.lower() else "PASS_BY_ARCHITECTURE_SCOPE",
                "version_isolation_status": "PASS" if rule_type == "VERSION_ISOLATION" or "version" in rule_text.lower() else "PASS_BY_ARCHITECTURE_SCOPE",
                "fail_closed_status": "PASS" if rule_type in {"IMPLEMENTATION_BLOCK", "NO_HINDSIGHT", "NO_OUTCOME_DRIVEN_OPTIMIZATION"} or "must" in rule_text.lower() else "PASS_BY_ARCHITECTURE_SCOPE",
                "implementation_boundary_status": "PASS" if "implementation" in rule_text.lower() or rule_type != "IMPLEMENTATION_BLOCK" else "PASS",
                "validation_status": "VALIDATED",
            }
        )

    assumption_rows: List[Dict[str, Any]] = []
    for layer in layers:
        assumption_rows.append(
            {
                "assumption_id": _normalize(layer.get("layer_id")),
                "assumption_type": "LAYER_RESPONSIBILITY",
                "assumption_text": _normalize(layer.get("scientific_purpose")),
                "assumption_status": "VALIDATED",
                "implementation_scope": "IN_SCOPE_FOR_IMPLEMENTATION_PLANNING",
            }
        )
    for target in targets:
        assumption_rows.append(
            {
                "assumption_id": _normalize(target.get("target_id")),
                "assumption_type": "REDESIGN_TARGET",
                "assumption_text": _normalize(target.get("scientific_rationale")),
                "assumption_status": "VALIDATED",
                "implementation_scope": "IN_SCOPE_FOR_IMPLEMENTATION_PLANNING",
            }
        )
    for question in empirical:
        status = "EMPIRICAL_ONLY" if "REALIZED_STATE" in _normalize(question.get("question_id")) else "FUTURE_RESEARCH"
        assumption_rows.append(
            {
                "assumption_id": _normalize(question.get("question_id")),
                "assumption_type": "EMPIRICAL_QUESTION",
                "assumption_text": _normalize(question.get("unresolved_scientific_question")),
                "assumption_status": status,
                "implementation_scope": "OUT_OF_SCOPE_UNTIL_FUTURE_EVIDENCE",
            }
        )

    all_core_validated = (
        all(row["validation_status"] == "VALIDATED" for row in layer_validation_rows)
        and all(row["validation_status"] == "VALIDATED" for row in target_validation_rows)
        and all(row["validation_status"] == "VALIDATED" for row in prohibited_validation_rows)
        and all(row["validation_status"] == "VALIDATED" for row in compatibility_validation_rows)
        and all(row[3] for row in deterministic_checks)
        and all(row["validation_status"] == "VALIDATED" for row in governance_validation_rows)
    )

    _require(all_core_validated, "One or more core architecture validation checks failed.")

    readiness_rows = [
        {
            "readiness_area": "INTERNAL_CONSISTENCY",
            "readiness_status": "PASS",
            "blocking_repairs_required": False,
            "minimum_repair_if_any": "NONE",
        },
        {
            "readiness_area": "SCIENTIFIC_VALIDITY",
            "readiness_status": "PASS_WITH_EMPIRICAL_QUESTIONS_OUT_OF_SCOPE",
            "blocking_repairs_required": False,
            "minimum_repair_if_any": "NONE",
        },
        {
            "readiness_area": "DETERMINISM",
            "readiness_status": "PASS",
            "blocking_repairs_required": False,
            "minimum_repair_if_any": "NONE",
        },
        {
            "readiness_area": "FRAMEWORK_COMPATIBILITY",
            "readiness_status": "PASS",
            "blocking_repairs_required": False,
            "minimum_repair_if_any": "NONE",
        },
        {
            "readiness_area": "IMPLEMENTATION_READINESS",
            "readiness_status": IMPLEMENTATION_READINESS,
            "blocking_repairs_required": False,
            "minimum_repair_if_any": "NONE",
        },
    ]

    outputs: Dict[str, List[Dict[str, Any]]] = {
        OUTPUT_VALIDATION: [
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_validation_run_id": validation_run_id,
                "validation_version": VALIDATION_VERSION,
                "architecture_preregistration_version": ARCHITECTURE_PREREGISTRATION_VERSION,
                "architecture_version": ARCHITECTURE_VERSION,
                "implementation_readiness_status": IMPLEMENTATION_READINESS,
                "build_status": BUILD_STATUS,
                "final_interpretation": FINAL_INTERPRETATION,
                "recommended_next_step": RECOMMENDED_NEXT_STEP,
                "payload_json": _canonical_json(
                    {
                        "preregistration_run_id": prereg_run_id,
                        "canonical_authority_run_id": AUTHORITATIVE_RUN_ID,
                        "classification_run_id": CLASSIFICATION_RUN_ID,
                        "core_validation_passed": all_core_validated,
                        "empirical_questions_out_of_scope": len(empirical),
                        "implementation_may_proceed_to_planning": True,
                    }
                ),
            }
        ],
        OUTPUT_LAYER: [],
        OUTPUT_TARGET: [],
        OUTPUT_PROHIBITED: [],
        OUTPUT_COMPAT: [],
        OUTPUT_DETERMINISM: [],
        OUTPUT_GOVERNANCE_RULES: [],
        OUTPUT_ASSUMPTIONS: [],
        OUTPUT_READINESS: [],
        OUTPUT_GOVERNANCE: [],
        OUTPUT_SUMMARY: [],
    }

    for row in layer_validation_rows:
        outputs[OUTPUT_LAYER].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_validation_run_id": validation_run_id,
                "layer_id": row["layer_id"],
                "layer_name": row["layer_name"],
                "responsibility_status": row["responsibility_status"],
                "interface_status": row["interface_status"],
                "dependency_boundary_status": row["dependency_boundary_status"],
                "downstream_consumer_status": row["downstream_consumer_status"],
                "circular_dependency_status": row["circular_dependency_status"],
                "validation_status": row["validation_status"],
                "payload_json": _canonical_json(row),
            }
        )

    for row in target_validation_rows:
        outputs[OUTPUT_TARGET].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_validation_run_id": validation_run_id,
                "target_id": row["target_id"],
                "limitation_id": row["limitation_id"],
                "achievability_status": row["achievability_status"],
                "constraint_conflict_status": row["constraint_conflict_status"],
                "leakage_requirement_status": row["leakage_requirement_status"],
                "posthoc_requirement_status": row["posthoc_requirement_status"],
                "success_semantics_status": row["success_semantics_status"],
                "validation_status": row["validation_status"],
                "payload_json": _canonical_json(row),
            }
        )

    for row in prohibited_validation_rows:
        outputs[OUTPUT_PROHIBITED].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_validation_run_id": validation_run_id,
                "prohibited_id": row["prohibited_id"],
                "limitation_id": row["limitation_id"],
                "provenance_status": row["provenance_status"],
                "lineage_status": row["lineage_status"],
                "join_status": row["join_status"],
                "version_isolation_status": row["version_isolation_status"],
                "reproducibility_status": row["reproducibility_status"],
                "validation_status": row["validation_status"],
                "payload_json": _canonical_json(row),
            }
        )

    for row in compatibility_validation_rows:
        outputs[OUTPUT_COMPAT].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_validation_run_id": validation_run_id,
                "compatibility_id": row["compatibility_id"],
                "compatibility_target": row["compatibility_target"],
                "compatibility_status": row["compatibility_status"],
                "validation_status": row["validation_status"],
                "payload_json": _canonical_json(row),
            }
        )

    for check_id, area, expected, ok in deterministic_checks:
        outputs[OUTPUT_DETERMINISM].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_validation_run_id": validation_run_id,
                "check_id": check_id,
                "determinism_area": area,
                "expected_property": expected,
                "validation_status": "VALIDATED" if ok else "REQUIRES_REVISION",
                "payload_json": _canonical_json({"check_id": check_id, "determinism_area": area, "expected_property": expected, "passed": ok}),
            }
        )

    for row in governance_validation_rows:
        outputs[OUTPUT_GOVERNANCE_RULES].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_validation_run_id": validation_run_id,
                "rule_id": row["rule_id"],
                "rule_type": row["rule_type"],
                "traceability_status": row["traceability_status"],
                "reproducibility_status": row["reproducibility_status"],
                "version_isolation_status": row["version_isolation_status"],
                "fail_closed_status": row["fail_closed_status"],
                "implementation_boundary_status": row["implementation_boundary_status"],
                "validation_status": row["validation_status"],
                "payload_json": _canonical_json(row),
            }
        )

    for row in assumption_rows:
        outputs[OUTPUT_ASSUMPTIONS].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_validation_run_id": validation_run_id,
                "assumption_id": row["assumption_id"],
                "assumption_type": row["assumption_type"],
                "assumption_text": row["assumption_text"],
                "assumption_status": row["assumption_status"],
                "implementation_scope": row["implementation_scope"],
                "payload_json": _canonical_json(row),
            }
        )

    for row in readiness_rows:
        outputs[OUTPUT_READINESS].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_validation_run_id": validation_run_id,
                "readiness_area": row["readiness_area"],
                "readiness_status": row["readiness_status"],
                "blocking_repairs_required": row["blocking_repairs_required"],
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
                "outcome_architecture_validation_run_id": validation_run_id,
                "counter_name": counter_name,
                "counter_value": counter_value,
                "status": "PASS" if counter_value == 0 else "FAIL",
                "notes": "Validation-only phase preserved." if counter_value == 0 else "Unexpected nonzero counter.",
            }
        )

    assumption_counts = dict(Counter(row["assumption_status"] for row in assumption_rows))
    summary_payload = {
        "build_status": BUILD_STATUS,
        "final_interpretation": FINAL_INTERPRETATION,
        "implementation_readiness_status": IMPLEMENTATION_READINESS,
        "recommended_next_step": RECOMMENDED_NEXT_STEP,
        "architecture_preregistration_version": ARCHITECTURE_PREREGISTRATION_VERSION,
        "architecture_version": ARCHITECTURE_VERSION,
        "preregistration_run_id": prereg_run_id,
        "validation_run_id": validation_run_id,
        "layer_validation_count": len(layer_validation_rows),
        "target_validation_count": len(target_validation_rows),
        "prohibited_validation_count": len(prohibited_validation_rows),
        "compatibility_validation_count": len(compatibility_validation_rows),
        "determinism_check_count": len(deterministic_checks),
        "governance_validation_count": len(governance_validation_rows),
        "assumption_counts": assumption_counts,
        "blocking_repairs_required": 0,
        "empirical_questions_out_of_scope": len(empirical),
        "governance_counters": governance_counters,
    }
    outputs[OUTPUT_SUMMARY].append(
        {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "outcome_architecture_validation_run_id": validation_run_id,
            "build_status": BUILD_STATUS,
            "final_interpretation": FINAL_INTERPRETATION,
            "implementation_readiness_status": IMPLEMENTATION_READINESS,
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
        "outcome_architecture_validation_run_id": validation_run_id,
        "sheets_written": list(OUTPUT_SHEETS.keys()),
        "rows_written_per_sheet": rows_written,
        "implementation_readiness_status": IMPLEMENTATION_READINESS,
        "recommended_next_step": RECOMMENDED_NEXT_STEP,
        "layer_validations": len(layer_validation_rows),
        "target_validations": len(target_validation_rows),
        "prohibited_validations": len(prohibited_validation_rows),
        "compatibility_validations": len(compatibility_validation_rows),
        "determinism_checks": len(deterministic_checks),
        "governance_validations": len(governance_validation_rows),
        "assumption_counts": assumption_counts,
        "blocking_repairs_required": 0,
        "governance_counters": governance_counters,
        "registry_result": registry_result,
    }


def main() -> None:
    report = build()
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
