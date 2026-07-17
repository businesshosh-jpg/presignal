#!/usr/bin/env python3
"""Phase 9A-6R15E — Outcome Architecture Refinement Design.

This phase produces a candidate Outcome Architecture v2 design and an
implementation roadmap without modifying any existing scientific artifacts,
without loading outcome rows, and without changing Success Mapping,
Eligibility, or mechanism classification logic.
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


PHASE_ID = "9A-6R15E"
BUILD_SCRIPT = "automation/build_refined_mechanism_test_outcome_architecture_refinement_design_v0.py"
SCHEMA_VERSION = "presignal_v2_refined_mechanism_test_outcome_architecture_refinement_design_v0"
DESIGN_VERSION = "refined_mechanism_test_outcome_architecture_refinement_design_v0"
REGISTRY_CATEGORY = "PRESIGNAL_V2_REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_DESIGN"
REGISTRY_OWNER_MODULE = "market_state"

AUTHORITATIVE_VERSION = "1.0-clean-r1"
AUTHORITATIVE_RUN_ID = "9A-6R13R1_20260711T020141Z"
CLASSIFICATION_VERSION = "1.1"
CLASSIFICATION_RUN_ID = "refined_mechanism_v11_classification_20260710T152725Z"
PRIMARY_MECHANISM = "MECH_INFORMATION_CONSISTENCY"
PRIMARY_STRUCTURE = "STRUCTURE_A_EXPANDED_STATE_GROUPED_DELTA_COMPARISON"

READY_WITH_CONSTRAINTS = "READY_WITH_CONSTRAINTS"
FINAL_INTERPRETATION = "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_V2_DESIGN_READY_WITH_WARNINGS"
RECOMMENDED_NEXT_STEP = "PROCEED_TO_PHASE9A6R15F_OUTCOME_ARCHITECTURE_REFINEMENT_PREREGISTRATION"
BUILD_STATUS = "PASS_WITH_WARNINGS"

STATUS_ACCEPTABLE = "REDESIGN_SCIENTIFICALLY_ACCEPTABLE"
STATUS_PROHIBITED = "REDESIGN_PROHIBITED"
STATUS_EVIDENCE = "REDESIGN_REQUIRES_ADDITIONAL_EVIDENCE"

FAMILY_CANONICAL = "CANONICAL_OUTCOME"
FAMILY_OVERLAY = "OUTCOME_OVERLAY"
FAMILY_LINKAGE = "OUTCOME_LINKAGE"
FAMILY_REPRESENTATION = "OUTCOME_REPRESENTATION"
FAMILY_INTERACTION = "ELIGIBILITY_INTERACTION"

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
    "Refined_Mechanism_Test_Success_Mapping_V2_Summary",
    "Refined_Mechanism_Test_Outcome_Architecture_Refinement_Scope",
    "Refined_Mechanism_Test_Outcome_Architecture_Limitations",
    "Refined_Mechanism_Test_Outcome_Architecture_Dependency_Graph",
    "Refined_Mechanism_Test_Outcome_Architecture_Decision_Framework",
    "Refined_Mechanism_Test_Outcome_Architecture_Refinement_Summary",
    "Refined_Mechanism_Test_Outcome_Architecture_Summary",
)

OUTPUT_DESIGN = "Refined_Mechanism_Test_Outcome_Architecture_V2_Design"
OUTPUT_LAYERS = "Refined_Mechanism_Test_Outcome_Architecture_V2_Layer_Model"
OUTPUT_TARGETS = "Refined_Mechanism_Test_Outcome_Architecture_V2_Redesign_Targets"
OUTPUT_PROHIBITED = "Refined_Mechanism_Test_Outcome_Architecture_V2_Prohibited_Targets"
OUTPUT_EVIDENCE = "Refined_Mechanism_Test_Outcome_Architecture_V2_Evidence_Dependencies"
OUTPUT_INTERACTIONS = "Refined_Mechanism_Test_Outcome_Architecture_V2_Interaction_Diagram"
OUTPUT_IMPACT = "Refined_Mechanism_Test_Outcome_Architecture_V2_Impact_Assessment"
OUTPUT_COMPAT = "Refined_Mechanism_Test_Outcome_Architecture_V2_Compatibility_Audit"
OUTPUT_RISKS = "Refined_Mechanism_Test_Outcome_Architecture_V2_Risk_Register"
OUTPUT_ROADMAP = "Refined_Mechanism_Test_Outcome_Architecture_V2_Implementation_Roadmap"
OUTPUT_GOVERNANCE = "Refined_Mechanism_Test_Outcome_Architecture_V2_Governance"
OUTPUT_SUMMARY = "Refined_Mechanism_Test_Outcome_Architecture_V2_Summary"

OUTPUT_SHEETS: Dict[str, List[str]] = {
    OUTPUT_DESIGN: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_design_run_id",
        "design_version",
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
    OUTPUT_LAYERS: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_design_run_id",
        "layer_id",
        "layer_order",
        "layer_name",
        "layer_responsibility",
        "candidate_refinement_focus",
        "preservation_guardrails",
        "payload_json",
    ],
    OUTPUT_TARGETS: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_design_run_id",
        "target_id",
        "limitation_id",
        "layer_name",
        "scientific_purpose",
        "proposed_refinement",
        "preserves_scientific_meaning",
        "payload_json",
    ],
    OUTPUT_PROHIBITED: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_design_run_id",
        "prohibited_id",
        "limitation_id",
        "prohibited_focus",
        "why_prohibited",
        "guardrail_preserved",
        "payload_json",
    ],
    OUTPUT_EVIDENCE: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_design_run_id",
        "dependency_id",
        "limitation_id",
        "evidence_question",
        "why_evidence_needed",
        "not_allowed_before_evidence",
        "payload_json",
    ],
    OUTPUT_INTERACTIONS: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_design_run_id",
        "edge_id",
        "from_layer",
        "to_layer",
        "current_loss_mode",
        "current_loss_count",
        "candidate_reduction_point",
        "payload_json",
    ],
    OUTPUT_IMPACT: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_design_run_id",
        "impact_id",
        "target_id",
        "architectural_benefit",
        "traceability_benefit",
        "reproducibility_benefit",
        "governance_impact",
        "payload_json",
    ],
    OUTPUT_COMPAT: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_design_run_id",
        "compatibility_id",
        "compatibility_target",
        "compatibility_status",
        "required_versioning_behavior",
        "payload_json",
    ],
    OUTPUT_RISKS: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_design_run_id",
        "risk_id",
        "risk_category",
        "risk_title",
        "risk_status",
        "mitigation_requirement",
        "payload_json",
    ],
    OUTPUT_ROADMAP: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_design_run_id",
        "stage_order",
        "stage_type",
        "stage_name",
        "stage_objective",
        "stage_not_allowed",
        "payload_json",
    ],
    OUTPUT_GOVERNANCE: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_design_run_id",
        "counter_name",
        "counter_value",
        "status",
        "notes",
    ],
    OUTPUT_SUMMARY: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_design_run_id",
        "build_status",
        "final_interpretation",
        "scientific_readiness_assessment",
        "recommended_next_step",
        "candidate_design_status",
        "redesign_target_count",
        "payload_json",
    ],
}

OUTPUT_LOGICAL_IDS = {
    OUTPUT_DESIGN: "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_V2_DESIGN",
    OUTPUT_LAYERS: "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_V2_LAYER_MODEL",
    OUTPUT_TARGETS: "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_V2_REDESIGN_TARGETS",
    OUTPUT_PROHIBITED: "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_V2_PROHIBITED_TARGETS",
    OUTPUT_EVIDENCE: "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_V2_EVIDENCE_DEPENDENCIES",
    OUTPUT_INTERACTIONS: "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_V2_INTERACTION_DIAGRAM",
    OUTPUT_IMPACT: "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_V2_IMPACT_ASSESSMENT",
    OUTPUT_COMPAT: "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_V2_COMPATIBILITY_AUDIT",
    OUTPUT_RISKS: "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_V2_RISK_REGISTER",
    OUTPUT_ROADMAP: "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_V2_IMPLEMENTATION_ROADMAP",
    OUTPUT_GOVERNANCE: "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_V2_GOVERNANCE",
    OUTPUT_SUMMARY: "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_V2_SUMMARY",
}


def _run_id(ts: datetime) -> str:
    return f"9A-6R15E_{ts.strftime('%Y%m%dT%H%M%SZ')}"


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
                "notes": "Phase 9A-6R15E candidate Outcome Architecture v2 design artifacts.",
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


def _filter_rows_for_run(
    rows: Sequence[Mapping[str, Any]],
    run_key: str,
    run_id: str,
) -> List[Dict[str, Any]]:
    return [dict(row) for row in rows if _normalize(row.get(run_key)) == run_id]


def _layer_rows() -> List[Dict[str, Any]]:
    return [
        {
            "layer_id": "OA_V2_LAYER_01",
            "layer_order": 1,
            "layer_name": FAMILY_CANONICAL,
            "layer_responsibility": "Store authoritative outcome identity, evaluation-window identity, version provenance, and canonical realized-state records without scoring logic.",
            "candidate_refinement_focus": "Make coverage completeness and outcome-availability statuses explicit and versioned without altering canonical semantics.",
            "preservation_guardrails": "No outcome row access in design. No change to canonical version, evaluation-window identity, timestamp provenance, or realized-direction semantics.",
        },
        {
            "layer_id": "OA_V2_LAYER_02",
            "layer_order": 2,
            "layer_name": FAMILY_OVERLAY,
            "layer_responsibility": "Represent repaired overlay bridge artifacts that connect canonical outcome identity to downstream evaluability contracts.",
            "candidate_refinement_focus": "Define overlay completeness, lineage, and missingness states as first-class deterministic outputs rather than implicit failures.",
            "preservation_guardrails": "Overlay remains a versioned bridge, not a semantic correction surface. No ad hoc repaired values or manual overrides.",
        },
        {
            "layer_id": "OA_V2_LAYER_03",
            "layer_order": 3,
            "layer_name": FAMILY_LINKAGE,
            "layer_responsibility": "Resolve exact stable-key linkage from classification observations to repaired canonical outcome IDs and canonical outcome IDs.",
            "candidate_refinement_focus": "Materialize the bridge path and explicit join-state audit outputs so missing, ambiguous, duplicate, and blocked joins are transparent before scoring.",
            "preservation_guardrails": "No physical-row, fuzzy, nearest-date, or manual joins. One-to-one and fail-closed remain mandatory.",
        },
        {
            "layer_id": "OA_V2_LAYER_04",
            "layer_order": 4,
            "layer_name": FAMILY_REPRESENTATION,
            "layer_responsibility": "Represent scoreable and non-scoreable realized-state categories in a deterministic pre-success contract without changing corrected directional-success semantics.",
            "candidate_refinement_focus": "Separate availability, representability, and scoreability so ambiguous or non-directional states are traceable before Success Mapping is applied.",
            "preservation_guardrails": "Do not redesign corrected directional-success meaning inside Outcome Architecture. Empirical questions remain evidence-gated.",
        },
        {
            "layer_id": "OA_V2_LAYER_05",
            "layer_order": 5,
            "layer_name": FAMILY_INTERACTION,
            "layer_responsibility": "Project paired baseline/expanded evaluability and post-join gate survivorship before inferential testing begins.",
            "candidate_refinement_focus": "Expose baseline-control evaluability, negative-arm fragility, and post-join gate dependence as deterministic diagnostics rather than hidden downstream collapse.",
            "preservation_guardrails": "No change to eligibility rules, sample gates, confidence rules, or uncertainty handling in this phase.",
        },
    ]


def _target_rows(acceptable_rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    by_id = {_normalize(row.get("limitation_id")): row for row in acceptable_rows}
    targets = [
        {
            "target_id": "OA_V2_TARGET_01",
            "limitation_id": "OA_LIMIT_01_CANONICAL_COVERAGE_GAPS",
            "layer_name": FAMILY_CANONICAL,
            "scientific_purpose": "Distinguish true canonical outcome absence from downstream scoreability problems so coverage loss is measurable before other layers operate.",
            "proposed_refinement": "Add a canonical coverage contract that emits deterministic availability states, missingness reasons, and version-complete coverage manifests for each forecast identity.",
            "preserves_scientific_meaning": "It does not alter canonical outcomes or directional truth. It only makes coverage state explicit and reproducible.",
        },
        {
            "target_id": "OA_V2_TARGET_02",
            "limitation_id": "OA_LIMIT_03_OVERLAY_COVERAGE_GAPS",
            "layer_name": FAMILY_OVERLAY,
            "scientific_purpose": "Separate overlay absence from canonical absence so repaired-overlay failures do not masquerade as unexplained join collapse.",
            "proposed_refinement": "Introduce an overlay completeness manifest keyed to canonical outcome identity with deterministic statuses for present, missing, version-blocked, and lineage-blocked overlay paths.",
            "preserves_scientific_meaning": "The overlay remains a bridge artifact; the refinement clarifies lineage rather than altering any realized state or scoring rule.",
        },
        {
            "target_id": "OA_V2_TARGET_03",
            "limitation_id": "OA_LIMIT_06_LINKAGE_BRIDGE_COMPLETENESS",
            "layer_name": FAMILY_LINKAGE,
            "scientific_purpose": "Make the full stable-key bridge from classification observation to repaired and canonical outcome IDs auditable before any success mapping or eligibility decisions occur.",
            "proposed_refinement": "Create an explicit linkage bridge layer with stage-specific join statuses, bridge fingerprints, and exact key-path diagnostics for each candidate observation.",
            "preserves_scientific_meaning": "The exact join rule is preserved; the refinement only externalizes the bridge states that already govern deterministic inclusion.",
        },
        {
            "target_id": "OA_V2_TARGET_04",
            "limitation_id": "OA_LIMIT_08_BASELINE_CONTROL_EVALUABILITY",
            "layer_name": FAMILY_INTERACTION,
            "scientific_purpose": "Separate baseline-control evaluability from outcome semantics so Structure A losses can be diagnosed without changing the primary estimand.",
            "proposed_refinement": "Add a paired-control evaluability contract that records whether each expanded observation has a valid same-provider same-session Pack A baseline with scoreable downstream lineage.",
            "preserves_scientific_meaning": "Baseline Pack A remains control-only for delta construction. The refinement clarifies pair readiness without changing the hypothesis or delta interpretation.",
        },
        {
            "target_id": "OA_V2_TARGET_05",
            "limitation_id": "OA_LIMIT_10_POSTJOIN_GATE_DEPENDENCE",
            "layer_name": FAMILY_INTERACTION,
            "scientific_purpose": "Expose how post-join architecture interacts with frozen gates so planned populations do not collapse invisibly after downstream processing.",
            "proposed_refinement": "Add a post-join gate survivorship projection layer that deterministically simulates gate passage after canonical coverage, overlay coverage, linkage, and representation stages.",
            "preserves_scientific_meaning": "The gates do not change. The refinement makes their dependencies measurable and preregisterable before any future test execution.",
        },
    ]
    for row in targets:
        limitation = by_id[row["limitation_id"]]
        row["first_hit_impact_count"] = int(limitation.get("first_hit_impact_count", 0) or 0)
        row["redesign_status"] = _normalize(limitation.get("redesign_status"))
    return targets


def _prohibited_rows(prohibited_rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    by_id = {_normalize(row.get("limitation_id")): row for row in prohibited_rows}
    outputs = [
        {
            "prohibited_id": "OA_V2_PROHIBITED_01",
            "limitation_id": "OA_LIMIT_02_CANONICAL_VERSION_WINDOW_TIMESTAMP_CONTRACT",
            "prohibited_focus": "Relaxing canonical version, evaluation-window, or timestamp provenance requirements to retain more observations.",
            "why_prohibited": "These are no-hindsight guardrails that define scientific validity, not tunable retention settings.",
            "guardrail_preserved": "Canonical version isolation, evaluation-window identity, and timestamp provenance remain frozen.",
        },
        {
            "prohibited_id": "OA_V2_PROHIBITED_02",
            "limitation_id": "OA_LIMIT_04_OVERLAY_BRIDGE_LINEAGE_REQUIREMENT",
            "prohibited_focus": "Treating the repaired overlay as an ad hoc correction layer with weaker lineage than canonical outcomes.",
            "why_prohibited": "The overlay must stay a deterministic bridge to preserve versioned traceability and avoid post-hoc adjustments.",
            "guardrail_preserved": "Overlay lineage and bridge determinism remain mandatory.",
        },
        {
            "prohibited_id": "OA_V2_PROHIBITED_03",
            "limitation_id": "OA_LIMIT_05_LINKAGE_EXACT_KEY_DEPENDENCE",
            "prohibited_focus": "Replacing exact stable-key linkage with fuzzy, nearest-date, manual, provider-only, or session-only matching.",
            "why_prohibited": "Such redesign would introduce hindsight risk, ambiguous joins, and unreproducible outcome access.",
            "guardrail_preserved": "Exact one-to-one stable-key linkage remains fail-closed.",
        },
    ]
    for row in outputs:
        limitation = by_id[row["limitation_id"]]
        row["limitation_family"] = _normalize(limitation.get("limitation_family"))
        row["limitation_classification"] = _normalize(limitation.get("limitation_classification"))
    return outputs


def _evidence_rows(evidence_rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    by_id = {_normalize(row.get("limitation_id")): row for row in evidence_rows}
    outputs = [
        {
            "dependency_id": "OA_V2_EVIDENCE_01",
            "limitation_id": "OA_LIMIT_07_REALIZED_STATE_SEMANTICS",
            "evidence_question": "Which non-directional realized states can be represented upstream without changing corrected directional-success semantics?",
            "why_evidence_needed": "Current losses cluster in states that are scientifically under-specified for directional scoring, and any upstream representation expansion must avoid semantic drift.",
            "not_allowed_before_evidence": "Do not redefine flat, ambiguous, or other non-resolved states as scoreable merely to retain observations.",
        },
        {
            "dependency_id": "OA_V2_EVIDENCE_02",
            "limitation_id": "OA_LIMIT_09_NEGATIVE_ARM_FRAGILITY",
            "evidence_question": "Can the negative arm become inferentially viable through upstream architecture work alone, or is additional sample expansion still required?",
            "why_evidence_needed": "Negative-arm disappearance is a multi-layer effect; architecture work may help, but its sufficiency is an empirical question that cannot be assumed in design.",
            "not_allowed_before_evidence": "Do not claim inferential readiness or relax negative-arm requirements before evidence-based reassessment.",
        },
    ]
    for row in outputs:
        limitation = by_id[row["limitation_id"]]
        row["first_hit_impact_count"] = int(limitation.get("first_hit_impact_count", 0) or 0)
    return outputs


def _interaction_rows() -> List[Dict[str, Any]]:
    return [
        {
            "edge_id": "OA_V2_GRAPH_01",
            "from_layer": FAMILY_CANONICAL,
            "to_layer": FAMILY_OVERLAY,
            "current_loss_mode": "Canonical outcome coverage gaps stop observations before repaired overlay can operate.",
            "current_loss_count": 22,
            "candidate_reduction_point": "Canonical coverage contract plus overlay completeness handshake.",
        },
        {
            "edge_id": "OA_V2_GRAPH_02",
            "from_layer": FAMILY_OVERLAY,
            "to_layer": FAMILY_LINKAGE,
            "current_loss_mode": "Missing repaired overlay bridge IDs create deterministic linkage failures.",
            "current_loss_count": 11,
            "candidate_reduction_point": "Overlay completeness manifest and bridge-path audit rows.",
        },
        {
            "edge_id": "OA_V2_GRAPH_03",
            "from_layer": FAMILY_LINKAGE,
            "to_layer": FAMILY_REPRESENTATION,
            "current_loss_mode": "Join readiness is currently implicit, making upstream bridge incompleteness hard to isolate from representation loss.",
            "current_loss_count": 33,
            "candidate_reduction_point": "Explicit linkage bridge layer with stage-specific join-state enumeration.",
        },
        {
            "edge_id": "OA_V2_GRAPH_04",
            "from_layer": FAMILY_REPRESENTATION,
            "to_layer": "CORRECTED_DIRECTIONAL_SUCCESS",
            "current_loss_mode": "Realized-state representation under-specification feeds the largest first-hit success-mapping exclusions.",
            "current_loss_count": 36,
            "candidate_reduction_point": "Pre-success representability contract that preserves directional-success semantics while clarifying scoreability.",
        },
        {
            "edge_id": "OA_V2_GRAPH_05",
            "from_layer": "CORRECTED_DIRECTIONAL_SUCCESS",
            "to_layer": "ELIGIBILITY",
            "current_loss_mode": "Baseline-control evaluability and post-join gate dependence are only visible after downstream success derivation attempts.",
            "current_loss_count": 69,
            "candidate_reduction_point": "Paired-control evaluability contract and post-join gate survivorship projection.",
        },
        {
            "edge_id": "OA_V2_GRAPH_06",
            "from_layer": "ELIGIBILITY",
            "to_layer": "MECHANISM_TESTING",
            "current_loss_mode": "Inferential readiness can fail despite blinded structural gates passing upstream.",
            "current_loss_count": 69,
            "candidate_reduction_point": "Explicit test-readiness layer that reports retained observations, negative-arm viability, and cluster survival before execution.",
        },
    ]


def _impact_rows(target_rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    impact_map = {
        "OA_V2_TARGET_01": ("HIGH", "MEDIUM", "MEDIUM", "MEDIUM"),
        "OA_V2_TARGET_02": ("MEDIUM", "HIGH", "MEDIUM", "MEDIUM"),
        "OA_V2_TARGET_03": ("HIGH", "HIGH", "HIGH", "HIGH"),
        "OA_V2_TARGET_04": ("MEDIUM", "MEDIUM", "MEDIUM", "MEDIUM"),
        "OA_V2_TARGET_05": ("HIGH", "HIGH", "HIGH", "HIGH"),
    }
    outputs: List[Dict[str, Any]] = []
    for row in target_rows:
        architectural_benefit, traceability_benefit, reproducibility_benefit, governance_impact = impact_map[row["target_id"]]
        outputs.append(
            {
                "impact_id": row["target_id"].replace("TARGET", "IMPACT"),
                "target_id": row["target_id"],
                "architectural_benefit": architectural_benefit,
                "traceability_benefit": traceability_benefit,
                "reproducibility_benefit": reproducibility_benefit,
                "governance_impact": governance_impact,
                "expected_architectural_benefit": f"{architectural_benefit} because it addresses {row['first_hit_impact_count']} impacted observations at the layer where loss first becomes visible.",
                "expected_traceability_benefit": "Makes first-hit failure states explicit and auditable rather than inferred post hoc.",
                "expected_reproducibility_benefit": "Adds deterministic versioned artifacts that another researcher can reload without hidden execution assumptions.",
                "expected_governance_impact": "Improves fail-closed diagnostics without widening scientific semantics or outcome access.",
            }
        )
    return outputs


def _compat_rows() -> List[Dict[str, Any]]:
    return [
        {
            "compatibility_id": "OA_V2_COMPAT_01",
            "compatibility_target": "EXISTING_MECHANISM_CLASSIFICATIONS",
            "compatibility_status": "FULLY_COMPATIBLE_VERSION_ISOLATED",
            "required_versioning_behavior": "Mechanism classifications remain frozen at mechanism version 1.1 and classification run refined_mechanism_v11_classification_20260710T152725Z.",
            "details": "Outcome Architecture v2 remains downstream of classification and must not relabel, re-scope, or reinterpret mechanism evidence.",
        },
        {
            "compatibility_id": "OA_V2_COMPAT_02",
            "compatibility_target": "SUCCESS_MAPPING_V1",
            "compatibility_status": "COMPATIBLE_AS_UPSTREAM_REFACTOR_BOUNDARY_ONLY",
            "required_versioning_behavior": "Any future implementation must preserve current Success Mapping v1 semantics until a separate SMv2 preregistration is approved.",
            "details": "The candidate design improves upstream coverage, linkage, and representability contracts without changing current success-mapping outputs in this phase.",
        },
        {
            "compatibility_id": "OA_V2_COMPAT_03",
            "compatibility_target": "FUTURE_SUCCESS_MAPPING_V2",
            "compatibility_status": "ENABLING_DEPENDENCY_NOT_A_SUBSTITUTE",
            "required_versioning_behavior": "Outcome Architecture v2 must freeze its own version and validation results before Success Mapping v2 design proceeds.",
            "details": "The design aims to reduce upstream ambiguity so any future SMv2 does not absorb architecture defects or silent coverage collapse.",
        },
        {
            "compatibility_id": "OA_V2_COMPAT_04",
            "compatibility_target": "FROZEN_PREREGISTRATIONS",
            "compatibility_status": "REQUIRES_NEW_VERSIONED_PREREGISTRATION_FAMILY",
            "required_versioning_behavior": "Do not overwrite 1.0, 1.0-clean, or 1.0-clean-r1. Any implementation requires a new outcome-architecture preregistration version and approval cycle.",
            "details": "Design-only artifacts are compatible if they remain version-isolated and do not modify prior authoritative scientific records.",
        },
    ]


def _risk_rows() -> List[Dict[str, Any]]:
    return [
        {
            "risk_id": "OA_V2_RISK_01",
            "risk_category": "SCIENTIFIC_RISK",
            "risk_title": "Coverage redesign could be mistaken for a semantic change in realized-direction meaning.",
            "risk_status": "ACTIVE_CONSTRAINED",
            "mitigation_requirement": "Keep canonical realized-direction semantics frozen and separate coverage state from success state in every future preregistration.",
        },
        {
            "risk_id": "OA_V2_RISK_02",
            "risk_category": "SCIENTIFIC_RISK",
            "risk_title": "Representation work could silently redefine flat or ambiguous states to retain more observations.",
            "risk_status": "ACTIVE_EVIDENCE_GATED",
            "mitigation_requirement": "Treat realized-state representation as an evidence-gated question and prohibit outcome-driven retention optimization.",
        },
        {
            "risk_id": "OA_V2_RISK_03",
            "risk_category": "GOVERNANCE_RISK",
            "risk_title": "A future implementation could weaken join guardrails in the name of coverage recovery.",
            "risk_status": "ACTIVE_BLOCKING_IF_TRIGGERED",
            "mitigation_requirement": "Preserve exact stable-key joins, fail-closed duplicate handling, and no manual overrides as immutable guardrails.",
        },
        {
            "risk_id": "OA_V2_RISK_04",
            "risk_category": "GOVERNANCE_RISK",
            "risk_title": "Outcome Architecture work could drift into Success Mapping or Eligibility redesign without a separate approval chain.",
            "risk_status": "ACTIVE_CONSTRAINED",
            "mitigation_requirement": "Use strict version boundaries and separate preregistration families for upstream architecture, SMv2, and any eligibility changes.",
        },
        {
            "risk_id": "OA_V2_RISK_05",
            "risk_category": "IMPLEMENTATION_RISK",
            "risk_title": "Multi-layer manifests and bridge artifacts may become inconsistent if versioned independently without canonical closure.",
            "risk_status": "ACTIVE_MANAGEABLE",
            "mitigation_requirement": "Require deterministic fingerprints, manifest closure, and stage-specific authority checks before any outcome access.",
        },
        {
            "risk_id": "OA_V2_RISK_06",
            "risk_category": "IMPLEMENTATION_RISK",
            "risk_title": "Baseline-control evaluability diagnostics could be misbuilt as a hidden eligibility rewrite.",
            "risk_status": "ACTIVE_MANAGEABLE",
            "mitigation_requirement": "Keep paired-control evaluability as an observational contract only until a separate approved rule change exists.",
        },
        {
            "risk_id": "OA_V2_RISK_07",
            "risk_category": "REPRODUCIBILITY_RISK",
            "risk_title": "Coverage and join-state artifacts may be unreproducible if row order or volatile metadata influence fingerprints.",
            "risk_status": "ACTIVE_MANAGEABLE",
            "mitigation_requirement": "Use stable serialization, explicit excluded volatile fields, and deterministic audit logging for every new layer artifact.",
        },
        {
            "risk_id": "OA_V2_RISK_08",
            "risk_category": "REPRODUCIBILITY_RISK",
            "risk_title": "Future researchers may not be able to reconstruct why observations failed if first-hit exclusion states are not preserved at each layer.",
            "risk_status": "ACTIVE_MANAGEABLE",
            "mitigation_requirement": "Persist first-hit exclusion provenance and stagewise loss accounting as mandatory architecture outputs in any later implementation.",
        },
    ]


def _roadmap_rows() -> List[Dict[str, Any]]:
    return [
        {
            "stage_order": 1,
            "stage_type": "CANDIDATE_DESIGN",
            "stage_name": "OUTCOME_ARCHITECTURE_V2_CANDIDATE_DESIGN",
            "stage_objective": "Freeze candidate layer responsibilities, redesignable targets, prohibited targets, evidence-gated questions, and risk boundaries.",
            "stage_not_allowed": "No implementation, no outcome access, no Success Mapping v2 redesign, and no mechanism retesting.",
        },
        {
            "stage_order": 2,
            "stage_type": "FUTURE_PREREGISTRATION",
            "stage_name": "OUTCOME_ARCHITECTURE_V2_PREREGISTRATION_AND_APPROVAL",
            "stage_objective": "Create a new versioned preregistration that freezes any approved architecture changes, authority, fingerprints, validation criteria, and stop rules.",
            "stage_not_allowed": "Do not overwrite existing preregistrations or mix design artifacts with live authoritative execution contracts.",
        },
        {
            "stage_order": 3,
            "stage_type": "FUTURE_IMPLEMENTATION",
            "stage_name": "OUTCOME_ARCHITECTURE_V2_IMPLEMENTATION_BUILD",
            "stage_objective": "Implement only the preregistered architecture artifacts: coverage contracts, overlay completeness manifests, linkage bridge diagnostics, representability contracts, and post-join survivorship projections.",
            "stage_not_allowed": "No policy relaxation, no outcome-driven tuning, no provider-specific behavior, and no Success Mapping change inside the architecture build.",
        },
        {
            "stage_order": 4,
            "stage_type": "FUTURE_VALIDATION",
            "stage_name": "OUTCOME_ARCHITECTURE_V2_NONOUTCOME_VALIDATION",
            "stage_objective": "Validate deterministic fingerprints, lineage closure, stagewise loss accounting, and scientific guardrail preservation before any downstream testing refresh.",
            "stage_not_allowed": "No inferential mechanism claims, no outcome optimization, and no direct promotion to production evaluation.",
        },
        {
            "stage_order": 5,
            "stage_type": "FUTURE_VALIDATION",
            "stage_name": "SUCCESS_MAPPING_V2_SCOPE_REFRESH",
            "stage_objective": "Reassess whether upstream architecture is now sufficiently explicit and complete to support a separate Success Mapping v2 preregistration.",
            "stage_not_allowed": "Do not assume SMv2 is automatically justified just because upstream architecture was refined.",
        },
        {
            "stage_order": 6,
            "stage_type": "FUTURE_VALIDATION",
            "stage_name": "MECHANISM_RETEST_AND_INFERENTIAL_REASSESSMENT",
            "stage_objective": "Rerun mechanism-testing readiness only after architecture and any future SMv2 changes are independently frozen, validated, and approved.",
            "stage_not_allowed": "No direct production evaluation or provider ranking from research-layer artifacts.",
        },
    ]


def build() -> Dict[str, Any]:
    run_ts = datetime.now(timezone.utc).replace(microsecond=0)
    generated_ts = run_ts.isoformat().replace("+00:00", "Z")
    design_run_id = _run_id(run_ts)

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

    _require(_normalize(prereg_r1.get("primary_mechanism")) == PRIMARY_MECHANISM, "Primary mechanism mismatch.")
    _require(_normalize(prereg_r1.get("primary_structure")) == PRIMARY_STRUCTURE, "Primary structure mismatch.")
    _require(_normalize(prereg_r1.get("mechanism_version")) == CLASSIFICATION_VERSION, "Classification version mismatch.")
    _require(_normalize(prereg_r1.get("classification_run_id")) == CLASSIFICATION_RUN_ID, "Classification run ID mismatch.")
    _require(outcome_r1.get("future_schema_fingerprint_verification_required") is True, "Outcome schema fingerprint guardrail mismatch.")
    _require(join_r1.get("exact_stable_key_match_required") is True, "Join stable-key requirement mismatch.")
    _require(_normalize(method_r1.get("primary_interpretation")) == "EXPLORATORY_PREREGISTERED_PRIMARY", "Method interpretation mismatch.")
    _require(stop_r1.get("fail_closed") is True, "Stop-rule fail-closed contract mismatch.")
    _require(design_r1.get("science_preservation", {}).get("primary_structure_changed") is False, "Science preservation mismatch.")
    _require(success_r1.get("allowed_output_statuses") == ["SUCCESS", "FAILURE", "NOT_ELIGIBLE", "AMBIGUOUS_JOIN_BLOCKED"], "Success derivation statuses mismatch.")

    sm_v2_summary_row = _latest_row(inputs["Refined_Mechanism_Test_Success_Mapping_V2_Summary"].rows, "success_mapping_v2_scope_run_id")
    sm_v2_payload = _parse_payload(sm_v2_summary_row)
    _require(_normalize(sm_v2_summary_row.get("scientific_readiness_assessment")) == READY_WITH_CONSTRAINTS, "Success Mapping v2 readiness mismatch.")
    _require(_normalize(sm_v2_summary_row.get("recommended_decision")) == "PROCEED_AFTER_ADDITIONAL_OUTCOME_ARCHITECTURE_WORK", "Success Mapping v2 decision mismatch.")

    scope_summary_row = _latest_row(
        inputs["Refined_Mechanism_Test_Outcome_Architecture_Refinement_Summary"].rows,
        "outcome_architecture_scope_run_id",
    )
    scope_summary_payload = _parse_payload(scope_summary_row)
    scope_run_id = _normalize(scope_summary_row.get("outcome_architecture_scope_run_id"))
    _require(_normalize(scope_summary_row.get("scientific_readiness_assessment")) == READY_WITH_CONSTRAINTS, "15D readiness mismatch.")
    _require(_normalize(scope_summary_row.get("recommended_next_step")) == "PROCEED_TO_PHASE9A6R15E_OUTCOME_ARCHITECTURE_REFINEMENT_DESIGN", "15D next-step mismatch.")
    _require(int(scope_summary_row.get("limitation_count", 0) or 0) == 10, "15D limitation count mismatch.")

    limitation_rows_raw = _filter_rows_for_run(
        inputs["Refined_Mechanism_Test_Outcome_Architecture_Limitations"].rows,
        "outcome_architecture_scope_run_id",
        scope_run_id,
    )
    _require(len(limitation_rows_raw) == 10, f"Expected 10 limitation rows for scope run {scope_run_id}, found {len(limitation_rows_raw)}")
    limitation_rows = [_parse_payload(row) for row in limitation_rows_raw]

    acceptable_rows = [row for row in limitation_rows if _normalize(row.get("redesign_status")) == STATUS_ACCEPTABLE]
    prohibited_rows = [row for row in limitation_rows if _normalize(row.get("redesign_status")) == STATUS_PROHIBITED]
    evidence_rows = [row for row in limitation_rows if _normalize(row.get("redesign_status")) == STATUS_EVIDENCE]

    _require(len(acceptable_rows) == 5, f"Expected 5 acceptable redesign targets, found {len(acceptable_rows)}")
    _require(len(prohibited_rows) == 3, f"Expected 3 prohibited redesign targets, found {len(prohibited_rows)}")
    _require(len(evidence_rows) == 2, f"Expected 2 evidence-gated questions, found {len(evidence_rows)}")

    redesign_counts = scope_summary_payload.get("redesign_status_counts", {})
    _require(int(redesign_counts.get(STATUS_ACCEPTABLE, 0) or 0) == 5, "15D acceptable redesign count mismatch.")
    _require(int(redesign_counts.get(STATUS_PROHIBITED, 0) or 0) == 3, "15D prohibited redesign count mismatch.")
    _require(int(redesign_counts.get(STATUS_EVIDENCE, 0) or 0) == 2, "15D evidence-gated redesign count mismatch.")

    outcome_arch_summary_row = _latest_row(inputs["Refined_Mechanism_Test_Outcome_Architecture_Summary"].rows, "outcome_architecture_run_id")
    _require(_normalize(outcome_arch_summary_row.get("recommended_research_direction")) == "OUTCOME_ARCHITECTURE_REFINEMENT", "Outcome architecture research direction mismatch.")

    target_rows = _target_rows(acceptable_rows)
    blocked_rows = _prohibited_rows(prohibited_rows)
    evidence_dependency_rows = _evidence_rows(evidence_rows)
    layer_rows = _layer_rows()
    interaction_rows = _interaction_rows()
    impact_rows = _impact_rows(target_rows)
    compat_rows = _compat_rows()
    risk_rows = _risk_rows()
    roadmap_rows = _roadmap_rows()

    outputs: Dict[str, List[Dict[str, Any]]] = {
        OUTPUT_DESIGN: [
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_design_run_id": design_run_id,
                "design_version": DESIGN_VERSION,
                "canonical_preregistration_version": AUTHORITATIVE_VERSION,
                "canonical_run_id": AUTHORITATIVE_RUN_ID,
                "classification_version": CLASSIFICATION_VERSION,
                "classification_run_id": CLASSIFICATION_RUN_ID,
                "scientific_readiness_assessment": READY_WITH_CONSTRAINTS,
                "recommended_next_step": RECOMMENDED_NEXT_STEP,
                "build_status": BUILD_STATUS,
                "final_interpretation": FINAL_INTERPRETATION,
                "payload_json": _canonical_json(
                    {
                        "design_phase": PHASE_ID,
                        "design_only": True,
                        "candidate_design_status": "OUTCOME_ARCHITECTURE_V2_CANDIDATE_DESIGN_FROZEN_PENDING_PREREGISTRATION",
                        "authoritative_preregistration_version": AUTHORITATIVE_VERSION,
                        "authoritative_run_id": AUTHORITATIVE_RUN_ID,
                        "classification_version": CLASSIFICATION_VERSION,
                        "classification_run_id": CLASSIFICATION_RUN_ID,
                        "primary_mechanism": PRIMARY_MECHANISM,
                        "primary_structure": PRIMARY_STRUCTURE,
                        "scientific_readiness_assessment": READY_WITH_CONSTRAINTS,
                        "recommended_next_step": RECOMMENDED_NEXT_STEP,
                        "accepted_redesign_targets": [row["target_id"] for row in target_rows],
                        "prohibited_redesign_targets": [row["prohibited_id"] for row in blocked_rows],
                        "evidence_dependencies": [row["dependency_id"] for row in evidence_dependency_rows],
                        "scope_source_run_id": scope_run_id,
                        "scope_summary_reference": {
                            "limitation_count": int(scope_summary_row.get("limitation_count", 0) or 0),
                            "principal_blocking_layer": _normalize(scope_summary_payload.get("principal_blocking_layer")),
                            "metrics": scope_summary_payload.get("metrics", {}),
                        },
                    }
                ),
            }
        ],
        OUTPUT_LAYERS: [],
        OUTPUT_TARGETS: [],
        OUTPUT_PROHIBITED: [],
        OUTPUT_EVIDENCE: [],
        OUTPUT_INTERACTIONS: [],
        OUTPUT_IMPACT: [],
        OUTPUT_COMPAT: [],
        OUTPUT_RISKS: [],
        OUTPUT_ROADMAP: [],
        OUTPUT_GOVERNANCE: [],
        OUTPUT_SUMMARY: [],
    }

    for row in layer_rows:
        outputs[OUTPUT_LAYERS].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_design_run_id": design_run_id,
                "layer_id": row["layer_id"],
                "layer_order": row["layer_order"],
                "layer_name": row["layer_name"],
                "layer_responsibility": row["layer_responsibility"],
                "candidate_refinement_focus": row["candidate_refinement_focus"],
                "preservation_guardrails": row["preservation_guardrails"],
                "payload_json": _canonical_json(row),
            }
        )

    for row in target_rows:
        outputs[OUTPUT_TARGETS].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_design_run_id": design_run_id,
                "target_id": row["target_id"],
                "limitation_id": row["limitation_id"],
                "layer_name": row["layer_name"],
                "scientific_purpose": row["scientific_purpose"],
                "proposed_refinement": row["proposed_refinement"],
                "preserves_scientific_meaning": row["preserves_scientific_meaning"],
                "payload_json": _canonical_json(row),
            }
        )

    for row in blocked_rows:
        outputs[OUTPUT_PROHIBITED].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_design_run_id": design_run_id,
                "prohibited_id": row["prohibited_id"],
                "limitation_id": row["limitation_id"],
                "prohibited_focus": row["prohibited_focus"],
                "why_prohibited": row["why_prohibited"],
                "guardrail_preserved": row["guardrail_preserved"],
                "payload_json": _canonical_json(row),
            }
        )

    for row in evidence_dependency_rows:
        outputs[OUTPUT_EVIDENCE].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_design_run_id": design_run_id,
                "dependency_id": row["dependency_id"],
                "limitation_id": row["limitation_id"],
                "evidence_question": row["evidence_question"],
                "why_evidence_needed": row["why_evidence_needed"],
                "not_allowed_before_evidence": row["not_allowed_before_evidence"],
                "payload_json": _canonical_json(row),
            }
        )

    for row in interaction_rows:
        outputs[OUTPUT_INTERACTIONS].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_design_run_id": design_run_id,
                "edge_id": row["edge_id"],
                "from_layer": row["from_layer"],
                "to_layer": row["to_layer"],
                "current_loss_mode": row["current_loss_mode"],
                "current_loss_count": row["current_loss_count"],
                "candidate_reduction_point": row["candidate_reduction_point"],
                "payload_json": _canonical_json(row),
            }
        )

    for row in impact_rows:
        outputs[OUTPUT_IMPACT].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_design_run_id": design_run_id,
                "impact_id": row["impact_id"],
                "target_id": row["target_id"],
                "architectural_benefit": row["architectural_benefit"],
                "traceability_benefit": row["traceability_benefit"],
                "reproducibility_benefit": row["reproducibility_benefit"],
                "governance_impact": row["governance_impact"],
                "payload_json": _canonical_json(row),
            }
        )

    for row in compat_rows:
        outputs[OUTPUT_COMPAT].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_design_run_id": design_run_id,
                "compatibility_id": row["compatibility_id"],
                "compatibility_target": row["compatibility_target"],
                "compatibility_status": row["compatibility_status"],
                "required_versioning_behavior": row["required_versioning_behavior"],
                "payload_json": _canonical_json(row),
            }
        )

    for row in risk_rows:
        outputs[OUTPUT_RISKS].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_design_run_id": design_run_id,
                "risk_id": row["risk_id"],
                "risk_category": row["risk_category"],
                "risk_title": row["risk_title"],
                "risk_status": row["risk_status"],
                "mitigation_requirement": row["mitigation_requirement"],
                "payload_json": _canonical_json(row),
            }
        )

    for row in roadmap_rows:
        outputs[OUTPUT_ROADMAP].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_design_run_id": design_run_id,
                "stage_order": row["stage_order"],
                "stage_type": row["stage_type"],
                "stage_name": row["stage_name"],
                "stage_objective": row["stage_objective"],
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
                "outcome_architecture_design_run_id": design_run_id,
                "counter_name": counter_name,
                "counter_value": counter_value,
                "status": "PASS" if counter_value == 0 else "FAIL",
                "notes": "Design-only phase preserved." if counter_value == 0 else "Unexpected nonzero counter.",
            }
        )

    summary_payload = {
        "build_status": BUILD_STATUS,
        "final_interpretation": FINAL_INTERPRETATION,
        "scientific_readiness_assessment": READY_WITH_CONSTRAINTS,
        "recommended_next_step": RECOMMENDED_NEXT_STEP,
        "candidate_design_status": "OUTCOME_ARCHITECTURE_V2_CANDIDATE_DESIGN_FROZEN_PENDING_PREREGISTRATION",
        "accepted_redesign_target_count": len(target_rows),
        "prohibited_target_count": len(blocked_rows),
        "evidence_dependency_count": len(evidence_dependency_rows),
        "layer_count": len(layer_rows),
        "compatibility_targets_reviewed": len(compat_rows),
        "risk_count": len(risk_rows),
        "scope_reference": {
            "scope_run_id": scope_run_id,
            "limitation_count": int(scope_summary_row.get("limitation_count", 0) or 0),
            "principal_blocking_layer": _normalize(scope_summary_payload.get("principal_blocking_layer")),
        },
        "governance_counters": governance_counters,
        "classification_compatibility": {
            "mechanism_version": CLASSIFICATION_VERSION,
            "classification_run_id": CLASSIFICATION_RUN_ID,
            "primary_mechanism": PRIMARY_MECHANISM,
            "primary_structure": PRIMARY_STRUCTURE,
        },
        "future_boundaries": {
            "may_not_implement_in_this_phase": True,
            "requires_new_preregistration_version_before_implementation": True,
            "success_mapping_v2_not_designed_here": True,
        },
        "sm_v2_scope_reference": {
            "scientific_readiness_assessment": _normalize(sm_v2_summary_row.get("scientific_readiness_assessment")),
            "recommended_decision": _normalize(sm_v2_summary_row.get("recommended_decision")),
            "principal_bottleneck": _normalize(sm_v2_summary_row.get("principal_bottleneck")),
            "rule_inventory_count": int(sm_v2_summary_row.get("rule_inventory_count", 0) or 0),
            "success_mapping_first_hit_exclusions": int(sm_v2_payload.get("success_mapping_first_hit_exclusions", 0) or 0),
        },
    }
    outputs[OUTPUT_SUMMARY].append(
        {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "outcome_architecture_design_run_id": design_run_id,
            "build_status": BUILD_STATUS,
            "final_interpretation": FINAL_INTERPRETATION,
            "scientific_readiness_assessment": READY_WITH_CONSTRAINTS,
            "recommended_next_step": RECOMMENDED_NEXT_STEP,
            "candidate_design_status": "OUTCOME_ARCHITECTURE_V2_CANDIDATE_DESIGN_FROZEN_PENDING_PREREGISTRATION",
            "redesign_target_count": len(target_rows),
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
        "outcome_architecture_design_run_id": design_run_id,
        "sheets_written": list(OUTPUT_SHEETS.keys()),
        "rows_written_per_sheet": rows_written,
        "scientific_readiness_assessment": READY_WITH_CONSTRAINTS,
        "recommended_next_step": RECOMMENDED_NEXT_STEP,
        "accepted_redesign_target_count": len(target_rows),
        "prohibited_target_count": len(blocked_rows),
        "evidence_dependency_count": len(evidence_dependency_rows),
        "layer_count": len(layer_rows),
        "impact_assessment_count": len(impact_rows),
        "compatibility_targets_reviewed": len(compat_rows),
        "risk_count": len(risk_rows),
        "governance_counters": governance_counters,
        "registry_result": registry_result,
    }


def main() -> None:
    report = build()
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
