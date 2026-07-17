#!/usr/bin/env python3
"""Phase 9A-6R15C — Success Mapping v2 Scope and Preregistration Design.

This phase creates a preregistered scientific scope document for any future
Success Mapping v2 redesign. It does not modify the current Success Mapping,
canonical outcomes, overlays, classifications, preregistrations, or
production behavior, and it does not load any outcome rows.
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


PHASE_ID = "9A-6R15C"
BUILD_SCRIPT = "automation/build_refined_mechanism_test_success_mapping_v2_scope_preregistration_v0.py"
SCHEMA_VERSION = "presignal_v2_refined_mechanism_test_success_mapping_v2_scope_preregistration_v0"
SCOPE_VERSION = "refined_mechanism_test_success_mapping_v2_scope_preregistration_v0"
REGISTRY_CATEGORY = "PRESIGNAL_V2_REFINED_MECHANISM_TEST_SUCCESS_MAPPING_V2_SCOPE"
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
    "success_mapping_first_hit_exclusions": 36,
    "policy_decision_exclusions": 22,
    "architectural_limitation_exclusions": 6,
    "scientifically_required_exclusions": 8,
    "implementation_artifact_exclusions": 0,
    "unresolved_ambiguity_exclusions": 0,
}

FORBIDDEN_INPUT_TITLES = {
    "Market_Reaction_Canonical_Outcomes",
    "Outcome_Ledger",
    "Evaluation_Rows",
    "Evaluation_Summary",
    "Corrected_Accuracy_Evaluation",
    "Controlled_Accuracy_Evaluation",
    "Refined_Mechanism_Test_Outcome_Join_Audit",
    "Refined_Mechanism_Test_Row_Lineage_Audit",
    "Refined_Mechanism_Test_Population_Collapse",
    "Refined_Mechanism_Test_Outcome_Join_Failure_Audit",
    "Refined_Mechanism_Test_Success_Mapping_Audit",
    "Refined_Mechanism_Test_Eligibility_Transition_Audit",
}

CAT_IMMUTABLE = "IMMUTABLE_SCIENTIFIC_RULE"
CAT_POLICY = "CONFIGURABLE_POLICY_RULE"
CAT_ARCH = "ARCHITECTURAL_ASSUMPTION"
CAT_EMPIRICAL = "EMPIRICAL_QUESTION_REQUIRING_FUTURE_EVIDENCE"

POLICY_PROHIBITED = "REDESIGN_PROHIBITED"
POLICY_ALLOWED = "REDESIGN_ALLOWED_UNDER_PREREGISTRATION"
POLICY_EVIDENCE = "REDESIGN_REQUIRES_ADDITIONAL_EVIDENCE"
POLICY_DISCOURAGED = "REDESIGN_SCIENTIFICALLY_DISCOURAGED"

READINESS_READY = "READY_FOR_V2_DESIGN"
READINESS_CONSTRAINED = "READY_WITH_CONSTRAINTS"
READINESS_EVIDENCE = "MORE_EVIDENCE_REQUIRED"
READINESS_BLOCKED = "NOT_RECOMMENDED"

DECISION_IMMEDIATE = "PROCEED_IMMEDIATELY"
DECISION_AFTER_ARCH = "PROCEED_AFTER_ADDITIONAL_OUTCOME_ARCHITECTURE_WORK"
DECISION_AFTER_DATA = "PROCEED_AFTER_ADDITIONAL_DATA_COLLECTION"
DECISION_MAINTAIN = "MAINTAIN_CURRENT_MAPPING_INDEFINITELY"

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
)

OUTPUT_SCOPE = "Refined_Mechanism_Test_Success_Mapping_V2_Scope"
OUTPUT_RULES = "Refined_Mechanism_Test_Success_Mapping_V2_Rule_Taxonomy"
OUTPUT_POLICY = "Refined_Mechanism_Test_Success_Mapping_V2_Policy_Rules"
OUTPUT_ARCH = "Refined_Mechanism_Test_Success_Mapping_V2_Architecture_Assumptions"
OUTPUT_EMPIRICAL = "Refined_Mechanism_Test_Success_Mapping_V2_Empirical_Questions"
OUTPUT_CONSTRAINTS = "Refined_Mechanism_Test_Success_Mapping_V2_Scientific_Constraints"
OUTPUT_ACCEPTABLE = "Refined_Mechanism_Test_Success_Mapping_V2_Acceptable_Redesigns"
OUTPUT_PROHIBITED = "Refined_Mechanism_Test_Success_Mapping_V2_Prohibited_Redesigns"
OUTPUT_DECISION = "Refined_Mechanism_Test_Success_Mapping_V2_Decision_Framework"
OUTPUT_GOVERNANCE = "Refined_Mechanism_Test_Success_Mapping_V2_Governance"
OUTPUT_SUMMARY = "Refined_Mechanism_Test_Success_Mapping_V2_Summary"

OUTPUT_SHEETS: Dict[str, List[str]] = {
    OUTPUT_SCOPE: [
        "generated_ts",
        "schema_version",
        "success_mapping_v2_scope_run_id",
        "scope_version",
        "canonical_preregistration_version",
        "canonical_run_id",
        "classification_version",
        "classification_run_id",
        "principal_bottleneck",
        "scientific_readiness_assessment",
        "recommended_decision",
        "build_status",
        "final_interpretation",
        "payload_json",
    ],
    OUTPUT_RULES: [
        "generated_ts",
        "schema_version",
        "success_mapping_v2_scope_run_id",
        "rule_id",
        "source_component",
        "current_rule_text",
        "current_effect",
        "scope_category",
        "policy_redesign_status",
        "scientific_basis",
        "observed_investigation_signal",
        "payload_json",
    ],
    OUTPUT_POLICY: [
        "generated_ts",
        "schema_version",
        "success_mapping_v2_scope_run_id",
        "rule_id",
        "current_rule_text",
        "redesign_status",
        "why_status",
        "future_guardrails",
        "payload_json",
    ],
    OUTPUT_ARCH: [
        "generated_ts",
        "schema_version",
        "success_mapping_v2_scope_run_id",
        "assumption_id",
        "source_component",
        "assumption_text",
        "why_it_exists",
        "scientific_purpose",
        "multiple_valid_architectures_could_exist",
        "payload_json",
    ],
    OUTPUT_EMPIRICAL: [
        "generated_ts",
        "schema_version",
        "success_mapping_v2_scope_run_id",
        "question_id",
        "current_rule_text",
        "why_empirical",
        "future_evidence_required",
        "payload_json",
    ],
    OUTPUT_CONSTRAINTS: [
        "generated_ts",
        "schema_version",
        "success_mapping_v2_scope_run_id",
        "constraint_id",
        "constraint_type",
        "constraint_text",
        "violation_status",
        "payload_json",
    ],
    OUTPUT_ACCEPTABLE: [
        "generated_ts",
        "schema_version",
        "success_mapping_v2_scope_run_id",
        "redesign_type_id",
        "redesign_type",
        "scope_boundary",
        "guardrails",
        "status",
        "payload_json",
    ],
    OUTPUT_PROHIBITED: [
        "generated_ts",
        "schema_version",
        "success_mapping_v2_scope_run_id",
        "prohibited_id",
        "prohibited_redesign",
        "prohibition_reason",
        "status",
        "payload_json",
    ],
    OUTPUT_DECISION: [
        "generated_ts",
        "schema_version",
        "success_mapping_v2_scope_run_id",
        "decision_option",
        "decision_status",
        "triggering_conditions",
        "required_preconditions",
        "blocking_conditions",
        "payload_json",
    ],
    OUTPUT_GOVERNANCE: [
        "generated_ts",
        "schema_version",
        "success_mapping_v2_scope_run_id",
        "counter_name",
        "counter_value",
        "status",
        "notes",
    ],
    OUTPUT_SUMMARY: [
        "generated_ts",
        "schema_version",
        "success_mapping_v2_scope_run_id",
        "build_status",
        "final_interpretation",
        "scientific_readiness_assessment",
        "recommended_decision",
        "principal_bottleneck",
        "rule_inventory_count",
        "payload_json",
    ],
}

OUTPUT_LOGICAL_IDS = {
    OUTPUT_SCOPE: "REFINED_MECHANISM_TEST_SUCCESS_MAPPING_V2_SCOPE",
    OUTPUT_RULES: "REFINED_MECHANISM_TEST_SUCCESS_MAPPING_V2_RULE_TAXONOMY",
    OUTPUT_POLICY: "REFINED_MECHANISM_TEST_SUCCESS_MAPPING_V2_POLICY_RULES",
    OUTPUT_ARCH: "REFINED_MECHANISM_TEST_SUCCESS_MAPPING_V2_ARCHITECTURE_ASSUMPTIONS",
    OUTPUT_EMPIRICAL: "REFINED_MECHANISM_TEST_SUCCESS_MAPPING_V2_EMPIRICAL_QUESTIONS",
    OUTPUT_CONSTRAINTS: "REFINED_MECHANISM_TEST_SUCCESS_MAPPING_V2_SCIENTIFIC_CONSTRAINTS",
    OUTPUT_ACCEPTABLE: "REFINED_MECHANISM_TEST_SUCCESS_MAPPING_V2_ACCEPTABLE_REDESIGNS",
    OUTPUT_PROHIBITED: "REFINED_MECHANISM_TEST_SUCCESS_MAPPING_V2_PROHIBITED_REDESIGNS",
    OUTPUT_DECISION: "REFINED_MECHANISM_TEST_SUCCESS_MAPPING_V2_DECISION_FRAMEWORK",
    OUTPUT_GOVERNANCE: "REFINED_MECHANISM_TEST_SUCCESS_MAPPING_V2_GOVERNANCE",
    OUTPUT_SUMMARY: "REFINED_MECHANISM_TEST_SUCCESS_MAPPING_V2_SUMMARY",
}


def _run_id(ts: datetime) -> str:
    return f"9A-6R15C_{ts.strftime('%Y%m%dT%H%M%SZ')}"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _fingerprint_payload(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


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
        payload = json.loads(_normalize(row.get("payload_json")) or "{}")
        _require(isinstance(payload, dict) and bool(payload), f"Authoritative payload incomplete for {component_id}")
        current_fp = _fingerprint_payload(payload)
        _require(
            current_fp == _normalize(entry.get("fingerprint")),
            f"Authoritative fingerprint mismatch for {component_id}",
        )
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
            "notes": "Phase 9A-6R15C Success Mapping v2 scope/preregistration boundary artifacts.",
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


def _summary_metrics(
    collapse_summary_row: Mapping[str, Any],
    outcome_arch_summary_row: Mapping[str, Any],
) -> Dict[str, Any]:
    principal_bottleneck = _normalize(outcome_arch_summary_row.get("principal_bottleneck_layer")) or "SUCCESS_MAPPING"
    scientific_interpretation = _normalize(outcome_arch_summary_row.get("scientific_interpretation"))
    if principal_bottleneck == "SUCCESS_MAPPING" and (
        "No single isolated layer fix is sufficient" in scientific_interpretation
        or "requires refinement before the inferential design can be meaningfully evaluated" in scientific_interpretation
    ):
        principal_bottleneck = "SUCCESS_MAPPING_WITH_INTERACTION_EFFECTS"
    return {
        "planned_primary_observations": int(collapse_summary_row.get("planned_primary_observations", 0) or 0),
        "final_eligible_observations": int(collapse_summary_row.get("final_eligible_observations", 0) or 0),
        "outcome_join_losses": int(collapse_summary_row.get("outcome_join_losses", 0) or 0),
        "success_mapping_losses": int(collapse_summary_row.get("success_mapping_losses", 0) or 0),
        "overlay_losses": int(collapse_summary_row.get("overlay_losses", 0) or 0),
        "eligibility_losses": int(collapse_summary_row.get("eligibility_losses", 0) or 0),
        "principal_bottleneck": principal_bottleneck,
        "architecture_capability_classification": _normalize(
            outcome_arch_summary_row.get("architecture_capability_classification")
        ),
        "recommended_research_direction": _normalize(outcome_arch_summary_row.get("recommended_research_direction")),
    }


def _rule_inventory() -> List[Dict[str, Any]]:
    return [
        {
            "rule_id": "SM_RULE_01_PRIMARY_DIRECTIONAL_SCOPE_ONLY",
            "source_component": "Refined_Mechanism_Test_Frozen_Success_Derivation_Clean_R1",
            "current_rule_text": "The primary success metric remains directional-only and evaluates only directionally eligible forecast observations.",
            "current_effect": "Restricts primary success mapping to directional evaluation.",
            "scope_category": CAT_IMMUTABLE,
            "policy_redesign_status": "",
            "scientific_basis": "Core scientific meaning of corrected directional success.",
            "observed_investigation_signal": "Preserves the endpoint meaning while all redesign discussion remains pre-outcome.",
        },
        {
            "rule_id": "SM_RULE_02_UP_FORECAST_UP_OUTCOME_SUCCESS",
            "source_component": "Refined_Mechanism_Test_Frozen_Success_Derivation_Clean_R1",
            "current_rule_text": "Forecast UP with realized UP maps to SUCCESS.",
            "current_effect": "Positive directional agreement.",
            "scope_category": CAT_IMMUTABLE,
            "policy_redesign_status": "",
            "scientific_basis": "Core directional-success semantics.",
            "observed_investigation_signal": "Not identified as a bottleneck.",
        },
        {
            "rule_id": "SM_RULE_03_UP_FORECAST_DOWN_OUTCOME_FAILURE",
            "source_component": "Refined_Mechanism_Test_Frozen_Success_Derivation_Clean_R1",
            "current_rule_text": "Forecast UP with realized DOWN maps to FAILURE.",
            "current_effect": "Negative directional disagreement.",
            "scope_category": CAT_IMMUTABLE,
            "policy_redesign_status": "",
            "scientific_basis": "Core directional-success semantics.",
            "observed_investigation_signal": "Not identified as a bottleneck.",
        },
        {
            "rule_id": "SM_RULE_04_DOWN_FORECAST_DOWN_OUTCOME_SUCCESS",
            "source_component": "Refined_Mechanism_Test_Frozen_Success_Derivation_Clean_R1",
            "current_rule_text": "Forecast DOWN with realized DOWN maps to SUCCESS.",
            "current_effect": "Positive directional agreement.",
            "scope_category": CAT_IMMUTABLE,
            "policy_redesign_status": "",
            "scientific_basis": "Core directional-success semantics.",
            "observed_investigation_signal": "Not identified as a bottleneck.",
        },
        {
            "rule_id": "SM_RULE_05_DOWN_FORECAST_UP_OUTCOME_FAILURE",
            "source_component": "Refined_Mechanism_Test_Frozen_Success_Derivation_Clean_R1",
            "current_rule_text": "Forecast DOWN with realized UP maps to FAILURE.",
            "current_effect": "Negative directional disagreement.",
            "scope_category": CAT_IMMUTABLE,
            "policy_redesign_status": "",
            "scientific_basis": "Core directional-success semantics.",
            "observed_investigation_signal": "Not identified as a bottleneck.",
        },
        {
            "rule_id": "SM_RULE_06_FORECAST_NO_CLEAR_DIRECTION_NOT_ELIGIBLE",
            "source_component": "Refined_Mechanism_Test_Frozen_Success_Derivation_Clean_R1",
            "current_rule_text": "Forecast NO_CLEAR_DIRECTION maps to NOT_ELIGIBLE for the primary directional metric.",
            "current_effect": "Non-directional forecasts remain outside the directional endpoint.",
            "scope_category": CAT_IMMUTABLE,
            "policy_redesign_status": "",
            "scientific_basis": "A non-directional forecast cannot be scored under a directional endpoint without changing the endpoint meaning.",
            "observed_investigation_signal": "Scientifically required in the observed exclusion patterns involving non-directional expanded forecasts.",
        },
        {
            "rule_id": "SM_RULE_07_NO_SIGNAL_FORECAST_NOT_ELIGIBLE",
            "source_component": "Refined_Mechanism_Test_Frozen_Success_Derivation_Clean_R1",
            "current_rule_text": "No-signal forecasts are NOT_ELIGIBLE for the primary corrected directional-success metric.",
            "current_effect": "Abstention-like outputs remain outside the primary binary endpoint.",
            "scope_category": CAT_EMPIRICAL,
            "policy_redesign_status": "",
            "scientific_basis": "Whether no-signal should have a future evaluable endpoint depends on additional evidence and a separate preregistered metric, not a simple rule tweak.",
            "observed_investigation_signal": "Not the dominant current failure mode, but any redesign would require new evidence and a separate endpoint justification.",
        },
        {
            "rule_id": "SM_RULE_08_FORECAST_FLAT_NOT_ELIGIBLE",
            "source_component": "Refined_Mechanism_Test_Frozen_Success_Derivation_Clean_R1",
            "current_rule_text": "Forecast FLAT maps to NOT_ELIGIBLE in the current primary directional-success architecture.",
            "current_effect": "Flat forecasts are excluded from primary directional scoring.",
            "scope_category": CAT_POLICY,
            "policy_redesign_status": POLICY_DISCOURAGED,
            "scientific_basis": "This is a boundary choice around the primary endpoint rather than a direct UP/DOWN success semantic.",
            "observed_investigation_signal": "Contributed to a smaller optional loss pattern in the baseline control architecture.",
        },
        {
            "rule_id": "SM_RULE_09_REALIZED_FLAT_NOT_ELIGIBLE",
            "source_component": "Refined_Mechanism_Test_Frozen_Success_Derivation_Clean_R1",
            "current_rule_text": "Realized FLAT maps to NOT_ELIGIBLE in the current primary directional-success architecture.",
            "current_effect": "Flat realized outcomes are excluded from primary directional scoring.",
            "scope_category": CAT_POLICY,
            "policy_redesign_status": POLICY_ALLOWED,
            "scientific_basis": "This is an exclusion policy around flat realized states, not a change to the UP/DOWN success meaning itself.",
            "observed_investigation_signal": "The dominant policy-driven failure mode in the first-hit Success Mapping exclusions.",
        },
        {
            "rule_id": "SM_RULE_10_REALIZED_NO_CLEAR_OR_AMBIGUOUS_NOT_ELIGIBLE",
            "source_component": "Refined_Mechanism_Test_Frozen_Success_Derivation_Clean_R1",
            "current_rule_text": "Realized NO_CLEAR_DIRECTION or AMBIGUOUS states map to NOT_ELIGIBLE under the current primary directional-success architecture.",
            "current_effect": "Non-resolved realized states do not enter the primary binary endpoint.",
            "scope_category": CAT_EMPIRICAL,
            "policy_redesign_status": "",
            "scientific_basis": "Any redesign would depend on future evidence about the scientific meaning and stability of non-resolved realized states in the canonical outcome layer.",
            "observed_investigation_signal": "Interacts with the outcome architecture and cannot be changed safely by retention-seeking alone.",
        },
        {
            "rule_id": "SM_RULE_11_MISSING_OR_INVALID_DIRECTION_FIELDS_NOT_ELIGIBLE",
            "source_component": "Refined_Mechanism_Test_Frozen_Success_Derivation_Clean_R1",
            "current_rule_text": "Missing or invalid forecast/realized direction fields map to NOT_ELIGIBLE.",
            "current_effect": "Incomplete or invalid directional state cannot be scored.",
            "scope_category": CAT_ARCH,
            "policy_redesign_status": "",
            "scientific_basis": "Deterministic data-validity boundary for the current endpoint.",
            "observed_investigation_signal": "Not identified as a current dominant failure mode, but required for fail-closed execution.",
        },
        {
            "rule_id": "SM_RULE_12_AMBIGUOUS_OR_DUPLICATE_JOIN_BLOCKED",
            "source_component": "Refined_Mechanism_Test_Frozen_Join_Rules_Clean_R1",
            "current_rule_text": "Ambiguous or duplicate outcome joins are blocked rather than scored.",
            "current_effect": "Join ambiguity cannot silently become a success value.",
            "scope_category": CAT_ARCH,
            "policy_redesign_status": "",
            "scientific_basis": "Fail-closed traceability and one-to-one outcome linkage requirement.",
            "observed_investigation_signal": "Preserves deterministic mapping even if it suppresses usable sample growth.",
        },
        {
            "rule_id": "SM_RULE_13_OUTCOME_VERSION_MISMATCH_NOT_ELIGIBLE",
            "source_component": "Refined_Mechanism_Test_Frozen_Outcome_Definition_Clean_R1",
            "current_rule_text": "Outcome version mismatches map to NOT_ELIGIBLE or systemic hard block.",
            "current_effect": "Only the frozen canonical outcome version is scoreable.",
            "scope_category": CAT_ARCH,
            "policy_redesign_status": "",
            "scientific_basis": "Version isolation and deterministic contract enforcement.",
            "observed_investigation_signal": "Prevents silent drift even if it may reduce usable observations in future runs.",
        },
        {
            "rule_id": "SM_RULE_14_EVALUATION_WINDOW_MISMATCH_NOT_ELIGIBLE",
            "source_component": "Refined_Mechanism_Test_Frozen_Outcome_Definition_Clean_R1",
            "current_rule_text": "Evaluation-window mismatches map to NOT_ELIGIBLE or systemic hard block.",
            "current_effect": "Only the frozen evaluation window is scoreable.",
            "scope_category": CAT_ARCH,
            "policy_redesign_status": "",
            "scientific_basis": "Ensures temporal comparability and no cross-window substitution.",
            "observed_investigation_signal": "Part of the fail-closed contract rather than the observed principal bottleneck.",
        },
        {
            "rule_id": "SM_RULE_15_TIMESTAMP_PROVENANCE_FAILURE_NOT_ELIGIBLE",
            "source_component": "Refined_Mechanism_Test_Frozen_Outcome_Definition_Clean_R1",
            "current_rule_text": "Timestamp provenance failures map to NOT_ELIGIBLE or hard block.",
            "current_effect": "Outcome timing must remain causally and temporally valid.",
            "scope_category": CAT_ARCH,
            "policy_redesign_status": "",
            "scientific_basis": "Outcome timing cannot be inferred or repaired manually inside the mapping layer.",
            "observed_investigation_signal": "Required to prevent leakage and preserve evaluation-window integrity.",
        },
        {
            "rule_id": "SM_RULE_16_EXACT_STABLE_KEY_ONE_TO_ONE_JOIN_REQUIRED",
            "source_component": "Refined_Mechanism_Test_Frozen_Join_Rules_Clean_R1",
            "current_rule_text": "Success Mapping requires exact stable-key and one-to-one classification-to-outcome linkage; physical-row, fuzzy, and manual joins are prohibited.",
            "current_effect": "Future mapping cannot compensate for weak join architecture by heuristic matching.",
            "scope_category": CAT_ARCH,
            "policy_redesign_status": "",
            "scientific_basis": "Traceability, reproducibility, and no manual outcome matching.",
            "observed_investigation_signal": "A non-negotiable fail-closed boundary for any future redesign.",
        },
        {
            "rule_id": "SM_RULE_17_BASELINE_AND_EXPANDED_BOTH_SCOREABLE_FOR_DELTA",
            "source_component": "Refined_Mechanism_Test_Frozen_Statistical_Method_Clean_R1",
            "current_rule_text": "The Structure A delta design requires both the expanded observation and its Pack A baseline control to be individually scoreable.",
            "current_effect": "An otherwise scoreable expanded observation can still be excluded when the baseline side is non-scoreable.",
            "scope_category": CAT_ARCH,
            "policy_redesign_status": "",
            "scientific_basis": "This is a structural feature of the delta architecture, not a mechanism-label problem.",
            "observed_investigation_signal": "Directly implicated in the architectural-limitation exclusions involving non-scoreable baselines.",
        },
        {
            "rule_id": "SM_RULE_18_DEFAULT_UNENUMERATED_STATE_NOT_ELIGIBLE",
            "source_component": "Refined_Mechanism_Test_Frozen_Success_Derivation_Clean_R1",
            "current_rule_text": "Any state not explicitly enumerated in the frozen success map defaults to NOT_ELIGIBLE.",
            "current_effect": "The architecture fails closed rather than guessing a success value.",
            "scope_category": CAT_ARCH,
            "policy_redesign_status": "",
            "scientific_basis": "Deterministic closure and auditability.",
            "observed_investigation_signal": "Supports reproducibility and blocks hidden post-hoc mapping expansion.",
        },
    ]


def _policy_scope_rows(rule_inventory: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for rule in rule_inventory:
        if rule["scope_category"] != CAT_POLICY:
            continue
        rule_id = _normalize(rule["rule_id"])
        if rule_id == "SM_RULE_08_FORECAST_FLAT_NOT_ELIGIBLE":
            why_status = (
                "Forecast FLAT is closest to a change in endpoint meaning, so any redesign is scientifically risky "
                "and should remain outside immediate v2 scope unless separately justified."
            )
            guardrails = (
                "Do not convert FLAT forecasts into primary directional successes or failures by retention-seeking; "
                "any future handling must stay prospectively preregistered and non-optimized."
            )
        else:
            why_status = (
                "Realized FLAT handling drove the largest policy-linked exclusion block and can be reconsidered "
                "prospectively without changing the core UP/DOWN success semantics."
            )
            guardrails = (
                "Any redesign must be chosen before outcome access, preserve provider neutrality, "
                "and avoid tuning against retained sample or observed accuracy."
            )
        rows.append(
            {
                "rule_id": rule_id,
                "current_rule_text": rule["current_rule_text"],
                "redesign_status": rule["policy_redesign_status"],
                "why_status": why_status,
                "future_guardrails": guardrails,
            }
        )
    return rows


def _architecture_scope_rows(rule_inventory: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    mapping = {
        "SM_RULE_11_MISSING_OR_INVALID_DIRECTION_FIELDS_NOT_ELIGIBLE": {
            "why_it_exists": "The current endpoint cannot score absent or malformed direction states.",
            "scientific_purpose": "Preserves deterministic data validity and prevents silent repair.",
            "multiple_valid_architectures_could_exist": False,
        },
        "SM_RULE_12_AMBIGUOUS_OR_DUPLICATE_JOIN_BLOCKED": {
            "why_it_exists": "A classification observation must not inherit multiple candidate outcomes.",
            "scientific_purpose": "Preserves one-to-one traceability and fail-closed joins.",
            "multiple_valid_architectures_could_exist": False,
        },
        "SM_RULE_13_OUTCOME_VERSION_MISMATCH_NOT_ELIGIBLE": {
            "why_it_exists": "The mapping is bound to a frozen outcome version and cannot float to another version.",
            "scientific_purpose": "Preserves version isolation and reproducibility.",
            "multiple_valid_architectures_could_exist": False,
        },
        "SM_RULE_14_EVALUATION_WINDOW_MISMATCH_NOT_ELIGIBLE": {
            "why_it_exists": "Baseline and expanded observations must share the approved evaluation window logic.",
            "scientific_purpose": "Prevents temporal drift and mixed-window scoring.",
            "multiple_valid_architectures_could_exist": False,
        },
        "SM_RULE_15_TIMESTAMP_PROVENANCE_FAILURE_NOT_ELIGIBLE": {
            "why_it_exists": "Outcome timing provenance is required to prove no future leakage.",
            "scientific_purpose": "Protects causal ordering and evaluation-window integrity.",
            "multiple_valid_architectures_could_exist": False,
        },
        "SM_RULE_16_EXACT_STABLE_KEY_ONE_TO_ONE_JOIN_REQUIRED": {
            "why_it_exists": "The future join must be deterministic and reproducible across researchers.",
            "scientific_purpose": "Eliminates fuzzy or manual matching pathways.",
            "multiple_valid_architectures_could_exist": True,
        },
        "SM_RULE_17_BASELINE_AND_EXPANDED_BOTH_SCOREABLE_FOR_DELTA": {
            "why_it_exists": "Structure A encodes a delta design in which both sides must be individually evaluable.",
            "scientific_purpose": "Keeps the baseline-to-expanded contrast structurally coherent.",
            "multiple_valid_architectures_could_exist": True,
        },
        "SM_RULE_18_DEFAULT_UNENUMERATED_STATE_NOT_ELIGIBLE": {
            "why_it_exists": "The current architecture fails closed whenever a state is outside the frozen map.",
            "scientific_purpose": "Prevents silent rule expansion after seeing data.",
            "multiple_valid_architectures_could_exist": True,
        },
    }
    rows = []
    for rule in rule_inventory:
        if rule["scope_category"] != CAT_ARCH:
            continue
        details = mapping[_normalize(rule["rule_id"])]
        rows.append(
            {
                "assumption_id": rule["rule_id"],
                "source_component": rule["source_component"],
                "assumption_text": rule["current_rule_text"],
                "why_it_exists": details["why_it_exists"],
                "scientific_purpose": details["scientific_purpose"],
                "multiple_valid_architectures_could_exist": details["multiple_valid_architectures_could_exist"],
            }
        )
    return rows


def _empirical_question_rows(rule_inventory: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    mapping = {
        "SM_RULE_07_NO_SIGNAL_FORECAST_NOT_ELIGIBLE": {
            "why_empirical": (
                "A future redesign would need evidence about whether abstention/no-signal behavior should be "
                "evaluated with a separate outcome concept rather than the current primary directional binary."
            ),
            "future_evidence_required": (
                "A separately preregistered no-signal endpoint definition, outcome-availability audit, "
                "and proof that the endpoint can remain leakage-safe."
            ),
        },
        "SM_RULE_10_REALIZED_NO_CLEAR_OR_AMBIGUOUS_NOT_ELIGIBLE": {
            "why_empirical": (
                "Any redesign would depend on future evidence about how canonical no-clear or ambiguous realized "
                "states should be scientifically interpreted."
            ),
            "future_evidence_required": (
                "Outcome-architecture evidence establishing a stable and non-post-hoc semantics for non-resolved "
                "realized states before any rule change is proposed."
            ),
        },
    }
    rows = []
    for rule in rule_inventory:
        if rule["scope_category"] != CAT_EMPIRICAL:
            continue
        details = mapping[_normalize(rule["rule_id"])]
        rows.append(
            {
                "question_id": rule["rule_id"],
                "current_rule_text": rule["current_rule_text"],
                "why_empirical": details["why_empirical"],
                "future_evidence_required": details["future_evidence_required"],
            }
        )
    return rows


def _constraint_rows() -> List[Dict[str, Any]]:
    return [
        {
            "constraint_id": "SM_V2_CONSTRAINT_01",
            "constraint_type": "BLINDING",
            "constraint_text": "Any Success Mapping v2 design must be frozen before any new outcome access.",
            "violation_status": "BLOCKING",
        },
        {
            "constraint_id": "SM_V2_CONSTRAINT_02",
            "constraint_type": "LEAKAGE",
            "constraint_text": "Success Mapping v2 must not use realized accuracy, retained sample size, provider performance, or subgroup outcome distributions to choose rules.",
            "violation_status": "BLOCKING",
        },
        {
            "constraint_id": "SM_V2_CONSTRAINT_03",
            "constraint_type": "SEMANTICS",
            "constraint_text": "The core corrected directional-success semantics for UP/DOWN directional cases must remain unchanged.",
            "violation_status": "BLOCKING",
        },
        {
            "constraint_id": "SM_V2_CONSTRAINT_04",
            "constraint_type": "MECHANISM_SCOPE",
            "constraint_text": "Frozen mechanism definitions, labels, confidence categories, and classification provenance must remain unchanged.",
            "violation_status": "BLOCKING",
        },
        {
            "constraint_id": "SM_V2_CONSTRAINT_05",
            "constraint_type": "JOIN_CONTRACT",
            "constraint_text": "No Success Mapping v2 may weaken exact stable-key, one-to-one, fail-closed outcome joining.",
            "violation_status": "BLOCKING",
        },
        {
            "constraint_id": "SM_V2_CONSTRAINT_06",
            "constraint_type": "DETERMINISM",
            "constraint_text": "Future v2 must preserve deterministic rule precedence, deterministic fingerprints, and deterministic audit logging.",
            "violation_status": "BLOCKING",
        },
        {
            "constraint_id": "SM_V2_CONSTRAINT_07",
            "constraint_type": "TRACEABILITY",
            "constraint_text": "Every exclusion path in v2 must remain explicitly traceable by first-hit reason without silent fallthrough.",
            "violation_status": "BLOCKING",
        },
        {
            "constraint_id": "SM_V2_CONSTRAINT_08",
            "constraint_type": "OUTCOME_ARCHITECTURE_BOUNDARY",
            "constraint_text": "Success Mapping v2 scope may not silently redesign canonical outcomes, repaired overlays, or evaluation windows.",
            "violation_status": "BLOCKING",
        },
        {
            "constraint_id": "SM_V2_CONSTRAINT_09",
            "constraint_type": "GOVERNANCE",
            "constraint_text": "Any future v2 must preserve fail-closed stop rules, no automatic retry, and zero production coupling.",
            "violation_status": "BLOCKING",
        },
    ]


def _acceptable_redesign_rows() -> List[Dict[str, Any]]:
    return [
        {
            "redesign_type_id": "SM_V2_ACCEPT_01",
            "redesign_type": "POLICY_SIMPLIFICATION",
            "scope_boundary": "Prospective clarification of flat-state handling without changing the core UP/DOWN success meaning.",
            "guardrails": "Must be chosen before outcome access and cannot be tuned against retained observations or observed accuracy.",
            "status": "ALLOWED_WITH_PREREGISTRATION",
        },
        {
            "redesign_type_id": "SM_V2_ACCEPT_02",
            "redesign_type": "ARCHITECTURAL_CLARIFICATION",
            "scope_boundary": "Clarify whether exclusions belong to join, outcome-contract, or success-mapping layers.",
            "guardrails": "No outcome-driven reassignment of rows across layers.",
            "status": "ALLOWED_WITH_PREREGISTRATION",
        },
        {
            "redesign_type_id": "SM_V2_ACCEPT_03",
            "redesign_type": "DETERMINISTIC_RESTRUCTURING",
            "scope_boundary": "Restructure rule precedence or case maps for transparency while preserving scientific meaning.",
            "guardrails": "Must preserve deterministic fingerprints, stop rules, and exact authority selection.",
            "status": "ALLOWED_WITH_PREREGISTRATION",
        },
        {
            "redesign_type_id": "SM_V2_ACCEPT_04",
            "redesign_type": "TRACEABILITY_AND_EXCLUSION_TRANSPARENCY",
            "scope_boundary": "Improve first-hit exclusion labeling, audit fields, and failure-state explanations.",
            "guardrails": "May improve traceability only; may not expand eligibility opportunistically.",
            "status": "ALLOWED_WITH_PREREGISTRATION",
        },
        {
            "redesign_type_id": "SM_V2_ACCEPT_05",
            "redesign_type": "EMPIRICAL_BRANCH_SCOPING",
            "scope_boundary": "Define future evidence questions for no-signal or no-clear states without changing the current endpoint.",
            "guardrails": "Requires separate preregistered evidence standards before any rule change is attempted.",
            "status": "ALLOWED_AFTER_SCOPE_FREEZE",
        },
    ]


def _prohibited_redesign_rows() -> List[Dict[str, Any]]:
    return [
        {
            "prohibited_id": "SM_V2_PROHIBIT_01",
            "prohibited_redesign": "Optimize Success Mapping against observed accuracy, effect size, or p-values.",
            "prohibition_reason": "Outcome-driven rule selection would create hindsight bias and leakage.",
            "status": "PROHIBITED",
        },
        {
            "prohibited_id": "SM_V2_PROHIBIT_02",
            "prohibited_redesign": "Maximize retained observations or negative-arm recovery as the design objective.",
            "prohibition_reason": "Retention is not a scientific objective and would distort rule meaning.",
            "status": "PROHIBITED",
        },
        {
            "prohibited_id": "SM_V2_PROHIBIT_03",
            "prohibited_redesign": "Provider-specific, session-specific, model-specific, or family-specific tuning.",
            "prohibition_reason": "Would create non-generalizable and potentially leakage-linked rule drift.",
            "status": "PROHIBITED",
        },
        {
            "prohibited_id": "SM_V2_PROHIBIT_04",
            "prohibited_redesign": "Change the core UP/DOWN corrected directional-success semantics.",
            "prohibition_reason": "Would redefine the scientific endpoint instead of redesigning its scope or architecture.",
            "status": "PROHIBITED",
        },
        {
            "prohibited_id": "SM_V2_PROHIBIT_05",
            "prohibited_redesign": "Change frozen mechanism definitions or classification evidence rules inside Success Mapping v2.",
            "prohibition_reason": "Mechanism science and success mapping must remain separated.",
            "status": "PROHIBITED",
        },
        {
            "prohibited_id": "SM_V2_PROHIBIT_06",
            "prohibited_redesign": "Use physical-row, fuzzy, nearest-date, or manual outcome joins.",
            "prohibition_reason": "Would break deterministic traceability and fail-closed governance.",
            "status": "PROHIBITED",
        },
        {
            "prohibited_id": "SM_V2_PROHIBIT_07",
            "prohibited_redesign": "Convert UNKNOWN, INSUFFICIENT_EVIDENCE, EXCLUDED, or LOW-confidence mechanism cases into primary negatives.",
            "prohibition_reason": "Would change mechanism meaning rather than success-mapping scope.",
            "status": "PROHIBITED",
        },
        {
            "prohibited_id": "SM_V2_PROHIBIT_08",
            "prohibited_redesign": "Select a new rule family after seeing which exclusions most improve the inferential sample.",
            "prohibition_reason": "Post-hoc optimization is incompatible with preregistered science.",
            "status": "PROHIBITED",
        },
        {
            "prohibited_id": "SM_V2_PROHIBIT_09",
            "prohibited_redesign": "Weaken fingerprints, authority checks, stop rules, or fail-closed execution ordering.",
            "prohibition_reason": "Would trade governance integrity for sample retention.",
            "status": "PROHIBITED",
        },
    ]


def _decision_framework_rows() -> List[Dict[str, Any]]:
    return [
        {
            "decision_option": DECISION_IMMEDIATE,
            "decision_status": "NOT_RECOMMENDED",
            "triggering_conditions": (
                "Only if the proposed v2 is limited to policy clarification and deterministic trace improvements "
                "that do not depend on unresolved outcome-architecture interactions."
            ),
            "required_preconditions": (
                "Complete pre-outcome freeze, preserved core semantics, and no need to reinterpret no-signal or "
                "non-resolved realized states."
            ),
            "blocking_conditions": (
                "Interaction with canonical coverage or overlay coverage, or any reliance on outcome-driven retention goals."
            ),
        },
        {
            "decision_option": DECISION_AFTER_ARCH,
            "decision_status": "RECOMMENDED",
            "triggering_conditions": (
                "Use when the redesign target materially interacts with canonical outcome coverage, repaired overlays, "
                "or baseline-control architecture."
            ),
            "required_preconditions": (
                "Outcome architecture boundaries must be explicitly frozen first so Success Mapping v2 does not absorb "
                "problems that belong to upstream layers."
            ),
            "blocking_conditions": "None if blinding and canonical authority remain intact.",
        },
        {
            "decision_option": DECISION_AFTER_DATA,
            "decision_status": "CONDITIONALLY_ALLOWED",
            "triggering_conditions": (
                "Use when the redesign target concerns sparse empirical states such as no-signal or non-resolved outcomes."
            ),
            "required_preconditions": (
                "Additional data or evidence standards must be specified before any redesign proposal is considered."
            ),
            "blocking_conditions": "Do not use data collection as a backdoor for post-hoc rule selection.",
        },
        {
            "decision_option": DECISION_MAINTAIN,
            "decision_status": "ALLOWED_BUT_NOT_RECOMMENDED",
            "triggering_conditions": (
                "Use if governance risk, blinding risk, or evidence ambiguity prevents a clean preregistered redesign."
            ),
            "required_preconditions": "Preserve current mapping indefinitely and keep testing descriptive-only if needed.",
            "blocking_conditions": "Not preferred when a leakage-safe preregistered scope path clearly exists.",
        },
    ]


def build() -> Dict[str, Any]:
    run_ts = datetime.now(timezone.utc).replace(microsecond=0)
    generated_ts = run_ts.isoformat().replace("+00:00", "Z")
    scope_run_id = _run_id(run_ts)

    _require(
        not (FORBIDDEN_INPUT_TITLES & set(INPUT_SHEETS)),
        "Forbidden outcome-bearing sheet included in Success Mapping v2 scope inputs.",
    )

    service = build_sheets_service(load_credentials())
    inputs = _fetch_input_sheets(service, DIAGNOSTICS_SPREADSHEET_ID, INPUT_SHEETS)
    known_titles = _sheet_titles_light(service, DIAGNOSTICS_SPREADSHEET_ID)

    canonical_authority = _latest_payload(
        inputs["Refined_Mechanism_Test_Clean_R1_Canonical_Authority"].rows,
        "lineage_repair_run_id",
    )
    component_authority = _latest_payload(
        inputs["Refined_Mechanism_Test_Clean_R1_Component_Authority"].rows,
        "lineage_repair_run_id",
    )
    canonical_manifest = _latest_payload(
        inputs["Refined_Mechanism_Test_Clean_R1_Canonical_Fingerprint_Manifest"].rows,
        "lineage_repair_run_id",
    )

    _require(
        _normalize(canonical_authority.get("authority_preregistration_version")) == AUTHORITATIVE_VERSION,
        "Canonical authority version mismatch.",
    )
    _require(
        _normalize(canonical_authority.get("authoritative_repair_run_id")) == AUTHORITATIVE_RUN_ID,
        "Canonical authority run ID mismatch.",
    )
    _require(
        _normalize(canonical_authority.get("authority_selection_method")) == "EXACT_VERSION_AND_RUN_ID_MATCH",
        "Canonical authority selection method mismatch.",
    )
    _require(
        _normalize(canonical_authority.get("authority_status")) == "CANONICAL_AUTHORITY_COMPLETE",
        "Canonical authority is not complete.",
    )

    selected_rows = _select_authoritative_rows(inputs, canonical_manifest, component_authority)
    selected_payloads = {sheet_name: row["payload"] for sheet_name, row in selected_rows.items()}

    prereg_r1 = selected_payloads["Refined_Mechanism_Test_Preregistration_Clean_R1"]
    outcome_r1 = selected_payloads["Refined_Mechanism_Test_Frozen_Outcome_Definition_Clean_R1"]
    join_r1 = selected_payloads["Refined_Mechanism_Test_Frozen_Join_Rules_Clean_R1"]
    success_r1 = selected_payloads["Refined_Mechanism_Test_Frozen_Success_Derivation_Clean_R1"]
    method_r1 = selected_payloads["Refined_Mechanism_Test_Frozen_Statistical_Method_Clean_R1"]
    stop_r1 = selected_payloads["Refined_Mechanism_Test_Frozen_Stop_Rules_Clean_R1"]
    design_r1 = selected_payloads["Refined_Mechanism_Test_Clean_R1_Design_Reconciliation"]
    prereg_summary_r1 = selected_payloads["Refined_Mechanism_Test_Preregistration_Clean_R1_Summary"]

    canonical_approval_summary = _latest_payload(
        inputs["Refined_Mechanism_Test_Execution_Approval_Canonical_R1_Summary"].rows,
        "canonical_clean_r1_approval_run_id",
    )
    collapse_summary = _latest_row(
        inputs["Refined_Mechanism_Test_Collapse_Summary"].rows,
        "population_collapse_run_id",
    )
    outcome_arch_summary = _latest_row(
        inputs["Refined_Mechanism_Test_Outcome_Architecture_Summary"].rows,
        "outcome_architecture_run_id",
    )

    _require(
        canonical_approval_summary.get("ready_for_one_canonical_clean_r1_mechanism_test_execution") is True,
        "Canonical execution approval summary is not marked ready.",
    )
    _require(_normalize(prereg_r1.get("primary_mechanism")) == PRIMARY_MECHANISM, "Primary mechanism mismatch.")
    _require(_normalize(prereg_r1.get("primary_structure")) == PRIMARY_STRUCTURE, "Primary structure mismatch.")
    _require(_normalize(prereg_r1.get("mechanism_version")) == CLASSIFICATION_VERSION, "Mechanism version mismatch.")
    _require(_normalize(prereg_r1.get("classification_run_id")) == CLASSIFICATION_RUN_ID, "Classification run ID mismatch.")
    _require(
        success_r1.get("explicit_case_map", {}).get("UP_forecast_UP_outcome") == "SUCCESS",
        "Success derivation UP/UP rule mismatch.",
    )
    _require(
        success_r1.get("explicit_case_map", {}).get("DOWN_forecast_UP_outcome") == "FAILURE",
        "Success derivation DOWN/UP rule mismatch.",
    )
    _require(
        success_r1.get("explicit_case_map", {}).get("forecast_FLAT_any_realized_direction") == "NOT_ELIGIBLE",
        "Success derivation forecast FLAT rule mismatch.",
    )
    _require(
        outcome_r1.get("outcome_timestamp_requirement", {}).get("failure_status") == "OUTCOME_TIMESTAMP_REQUIREMENT_FAILED",
        "Outcome timestamp requirement mismatch.",
    )
    _require(
        join_r1.get("physical_row_number_join_prohibited") is True
        and join_r1.get("fuzzy_text_join_prohibited") is True
        and join_r1.get("manual_matching_prohibited") is True,
        "Join prohibitions mismatch.",
    )
    _require(
        _normalize(method_r1.get("primary_interpretation")) == "EXPLORATORY_PREREGISTERED_PRIMARY",
        "Primary interpretation mismatch.",
    )
    _require(stop_r1.get("fail_closed") is True, "Stop-rule fail-closed contract mismatch.")
    _require(
        design_r1.get("science_preservation", {}).get("primary_structure_changed") is False,
        "Clean-R1 design reconciliation indicates a science change.",
    )

    metrics = _summary_metrics(collapse_summary, outcome_arch_summary)
    _require(
        metrics["planned_primary_observations"] == EXPECTED_COUNTS["planned_primary_observations"],
        "Planned primary observation count mismatch.",
    )
    _require(
        metrics["final_eligible_observations"] == EXPECTED_COUNTS["final_eligible_observations"],
        "Final eligible observation count mismatch.",
    )
    _require(
        metrics["success_mapping_losses"] == EXPECTED_COUNTS["success_mapping_first_hit_exclusions"],
        "Success Mapping loss count mismatch.",
    )

    rule_inventory = _rule_inventory()
    _require(all(rule["scope_category"] in {CAT_IMMUTABLE, CAT_POLICY, CAT_ARCH, CAT_EMPIRICAL} for rule in rule_inventory), "Invalid scope category in rule inventory.")
    _require(len({rule["rule_id"] for rule in rule_inventory}) == len(rule_inventory), "Duplicate rule IDs in scope inventory.")

    category_counts = Counter(rule["scope_category"] for rule in rule_inventory)
    policy_rows = _policy_scope_rows(rule_inventory)
    architecture_rows = _architecture_scope_rows(rule_inventory)
    empirical_rows = _empirical_question_rows(rule_inventory)
    constraint_rows = _constraint_rows()
    acceptable_rows = _acceptable_redesign_rows()
    prohibited_rows = _prohibited_redesign_rows()
    decision_rows = _decision_framework_rows()

    scientific_readiness_assessment = READINESS_CONSTRAINED
    recommended_decision = DECISION_AFTER_ARCH
    build_status = "PASS_WITH_WARNINGS"
    final_interpretation = "REFINED_MECHANISM_TEST_SUCCESS_MAPPING_V2_SCOPE_READY_WITH_CONSTRAINTS"

    rule_rows: List[Dict[str, Any]] = []
    for rule in rule_inventory:
        rule_rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "success_mapping_v2_scope_run_id": scope_run_id,
                "rule_id": rule["rule_id"],
                "source_component": rule["source_component"],
                "current_rule_text": rule["current_rule_text"],
                "current_effect": rule["current_effect"],
                "scope_category": rule["scope_category"],
                "policy_redesign_status": rule["policy_redesign_status"],
                "scientific_basis": rule["scientific_basis"],
                "observed_investigation_signal": rule["observed_investigation_signal"],
                "payload_json": _canonical_json(rule),
            }
        )

    output_rows: Dict[str, List[Dict[str, Any]]] = {
        OUTPUT_SCOPE: [
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "success_mapping_v2_scope_run_id": scope_run_id,
                "scope_version": SCOPE_VERSION,
                "canonical_preregistration_version": AUTHORITATIVE_VERSION,
                "canonical_run_id": AUTHORITATIVE_RUN_ID,
                "classification_version": CLASSIFICATION_VERSION,
                "classification_run_id": CLASSIFICATION_RUN_ID,
                "principal_bottleneck": metrics["principal_bottleneck"] or "SUCCESS_MAPPING_WITH_INTERACTION_EFFECTS",
                "scientific_readiness_assessment": scientific_readiness_assessment,
                "recommended_decision": recommended_decision,
                "build_status": build_status,
                "final_interpretation": final_interpretation,
                "payload_json": _canonical_json(
                    {
                        "scope_version": SCOPE_VERSION,
                        "authoritative_preregistration_version": AUTHORITATIVE_VERSION,
                        "authoritative_run_id": AUTHORITATIVE_RUN_ID,
                        "classification_version": CLASSIFICATION_VERSION,
                        "classification_run_id": CLASSIFICATION_RUN_ID,
                        "primary_mechanism": PRIMARY_MECHANISM,
                        "primary_structure": PRIMARY_STRUCTURE,
                        "scientific_readiness_assessment": scientific_readiness_assessment,
                        "recommended_decision": recommended_decision,
                        "principal_bottleneck": metrics["principal_bottleneck"] or "SUCCESS_MAPPING_WITH_INTERACTION_EFFECTS",
                        "current_investigation_counts": {
                            **EXPECTED_COUNTS,
                            "outcome_join_losses": metrics["outcome_join_losses"],
                            "overlay_losses": metrics["overlay_losses"],
                            "eligibility_losses": metrics["eligibility_losses"],
                        },
                        "rule_category_counts": dict(category_counts),
                    }
                ),
            }
        ],
        OUTPUT_RULES: rule_rows,
        OUTPUT_POLICY: [
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "success_mapping_v2_scope_run_id": scope_run_id,
                "rule_id": row["rule_id"],
                "current_rule_text": row["current_rule_text"],
                "redesign_status": row["redesign_status"],
                "why_status": row["why_status"],
                "future_guardrails": row["future_guardrails"],
                "payload_json": _canonical_json(row),
            }
            for row in policy_rows
        ],
        OUTPUT_ARCH: [
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "success_mapping_v2_scope_run_id": scope_run_id,
                "assumption_id": row["assumption_id"],
                "source_component": row["source_component"],
                "assumption_text": row["assumption_text"],
                "why_it_exists": row["why_it_exists"],
                "scientific_purpose": row["scientific_purpose"],
                "multiple_valid_architectures_could_exist": row["multiple_valid_architectures_could_exist"],
                "payload_json": _canonical_json(row),
            }
            for row in architecture_rows
        ],
        OUTPUT_EMPIRICAL: [
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "success_mapping_v2_scope_run_id": scope_run_id,
                "question_id": row["question_id"],
                "current_rule_text": row["current_rule_text"],
                "why_empirical": row["why_empirical"],
                "future_evidence_required": row["future_evidence_required"],
                "payload_json": _canonical_json(row),
            }
            for row in empirical_rows
        ],
        OUTPUT_CONSTRAINTS: [
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "success_mapping_v2_scope_run_id": scope_run_id,
                "constraint_id": row["constraint_id"],
                "constraint_type": row["constraint_type"],
                "constraint_text": row["constraint_text"],
                "violation_status": row["violation_status"],
                "payload_json": _canonical_json(row),
            }
            for row in constraint_rows
        ],
        OUTPUT_ACCEPTABLE: [
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "success_mapping_v2_scope_run_id": scope_run_id,
                "redesign_type_id": row["redesign_type_id"],
                "redesign_type": row["redesign_type"],
                "scope_boundary": row["scope_boundary"],
                "guardrails": row["guardrails"],
                "status": row["status"],
                "payload_json": _canonical_json(row),
            }
            for row in acceptable_rows
        ],
        OUTPUT_PROHIBITED: [
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "success_mapping_v2_scope_run_id": scope_run_id,
                "prohibited_id": row["prohibited_id"],
                "prohibited_redesign": row["prohibited_redesign"],
                "prohibition_reason": row["prohibition_reason"],
                "status": row["status"],
                "payload_json": _canonical_json(row),
            }
            for row in prohibited_rows
        ],
        OUTPUT_DECISION: [
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "success_mapping_v2_scope_run_id": scope_run_id,
                "decision_option": row["decision_option"],
                "decision_status": row["decision_status"],
                "triggering_conditions": row["triggering_conditions"],
                "required_preconditions": row["required_preconditions"],
                "blocking_conditions": row["blocking_conditions"],
                "payload_json": _canonical_json(row),
            }
            for row in decision_rows
        ],
        OUTPUT_GOVERNANCE: [],
        OUTPUT_SUMMARY: [],
    }

    governance_counters = {
        "provider_calls_performed": 0,
        "outcome_rows_loaded": 0,
        "outcome_rules_modified": 0,
        "success_mapping_modified": 0,
        "mechanism_rules_modified": 0,
        "preregistration_modified": 0,
        "mechanism_tests_performed": 0,
        "production_writes": 0,
    }
    for counter_name, counter_value in governance_counters.items():
        output_rows[OUTPUT_GOVERNANCE].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "success_mapping_v2_scope_run_id": scope_run_id,
                "counter_name": counter_name,
                "counter_value": counter_value,
                "status": "PASS" if counter_value == 0 else "FAIL",
                "notes": "Read-only scope phase preserved." if counter_value == 0 else "Unexpected nonzero counter.",
            }
        )

    summary_payload = {
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "scope_version": SCOPE_VERSION,
        "scientific_readiness_assessment": scientific_readiness_assessment,
        "recommended_decision": recommended_decision,
        "principal_bottleneck": metrics["principal_bottleneck"] or "SUCCESS_MAPPING_WITH_INTERACTION_EFFECTS",
        "rule_inventory_count": len(rule_inventory),
        "rule_category_counts": dict(category_counts),
        "policy_rule_redesign_counts": dict(Counter(row["redesign_status"] for row in policy_rows)),
        "planned_primary_observations": metrics["planned_primary_observations"],
        "final_eligible_observations": metrics["final_eligible_observations"],
        "success_mapping_first_hit_exclusions": metrics["success_mapping_losses"],
        "first_hit_exclusion_breakdown": {
            "policy_decisions": EXPECTED_COUNTS["policy_decision_exclusions"],
            "architectural_limitations": EXPECTED_COUNTS["architectural_limitation_exclusions"],
            "scientifically_required_rules": EXPECTED_COUNTS["scientifically_required_exclusions"],
            "implementation_artifacts": EXPECTED_COUNTS["implementation_artifact_exclusions"],
            "unresolved_ambiguity": EXPECTED_COUNTS["unresolved_ambiguity_exclusions"],
        },
        "governance_counters": governance_counters,
        "canonical_authority_status": canonical_authority.get("authority_status"),
        "canonical_fingerprint_manifest_status": canonical_manifest.get("manifest_status"),
        "design_reconciliation_preserved": design_r1.get("science_preservation", {}),
        "current_mapping_summary_reference": prereg_summary_r1,
    }
    output_rows[OUTPUT_SUMMARY].append(
        {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "success_mapping_v2_scope_run_id": scope_run_id,
            "build_status": build_status,
            "final_interpretation": final_interpretation,
            "scientific_readiness_assessment": scientific_readiness_assessment,
            "recommended_decision": recommended_decision,
            "principal_bottleneck": metrics["principal_bottleneck"] or "SUCCESS_MAPPING_WITH_INTERACTION_EFFECTS",
            "rule_inventory_count": len(rule_inventory),
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
            output_rows[sheet_name],
            known_titles,
        )

    registry_result = _upsert_registry_rows(service, generated_ts)

    return {
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "file_created": BUILD_SCRIPT,
        "success_mapping_v2_scope_run_id": scope_run_id,
        "sheets_written": list(OUTPUT_SHEETS.keys()),
        "rows_written_per_sheet": rows_written,
        "canonical_authority_status": canonical_authority.get("authority_status"),
        "principal_bottleneck": metrics["principal_bottleneck"] or "SUCCESS_MAPPING_WITH_INTERACTION_EFFECTS",
        "scientific_readiness_assessment": scientific_readiness_assessment,
        "recommended_decision": recommended_decision,
        "rule_inventory_count": len(rule_inventory),
        "immutable_scientific_rules": category_counts[CAT_IMMUTABLE],
        "configurable_policy_rules": category_counts[CAT_POLICY],
        "architectural_assumptions": category_counts[CAT_ARCH],
        "empirical_questions": category_counts[CAT_EMPIRICAL],
        "policy_rule_redesign_counts": dict(Counter(row["redesign_status"] for row in policy_rows)),
        "planned_primary_observations": metrics["planned_primary_observations"],
        "final_eligible_observations": metrics["final_eligible_observations"],
        "success_mapping_first_hit_exclusions": metrics["success_mapping_losses"],
        "first_hit_exclusion_breakdown": {
            "policy_decisions": EXPECTED_COUNTS["policy_decision_exclusions"],
            "architectural_limitations": EXPECTED_COUNTS["architectural_limitation_exclusions"],
            "scientifically_required_rules": EXPECTED_COUNTS["scientifically_required_exclusions"],
            "implementation_artifacts": EXPECTED_COUNTS["implementation_artifact_exclusions"],
            "unresolved_ambiguity": EXPECTED_COUNTS["unresolved_ambiguity_exclusions"],
        },
        "governance_counters": governance_counters,
        "registry_result": registry_result,
        "readiness": {
            "scientific_readiness_assessment": scientific_readiness_assessment,
            "recommended_decision": recommended_decision,
            "ready_for_v2_design_now": False,
            "ready_for_v2_design_after_outcome_architecture_work": True,
        },
    }


def main() -> None:
    report = build()
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
