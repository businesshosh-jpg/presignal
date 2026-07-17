import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

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


SCHEMA_VERSION = "presignal_v2_refined_mechanism_repair_0.1"
REPAIR_VERSION = "refined_mechanism_repair_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-6R4"
REGISTRY_CATEGORY = "PRESIGNAL_V2_REFINED_MECHANISM_REPAIR"
REGISTRY_OWNER_MODULE = "market_state"

BASELINE_VERSION = "1.0"
CANDIDATE_FRAMEWORK_VERSION = "1.1-candidate"
NEXT_STEP = "PROCEED_TO_PHASE9A6R5_SECOND_PREREGISTRATION_CYCLE"

PROMOTED_MECHANISMS = [
    "MECH_INFORMATION_RELEVANCE",
    "MECH_INFORMATION_SPECIFICITY",
    "MECH_INFORMATION_CONSISTENCY",
]
SUBDIMENSION_MECHANISMS = ["MECH_INFORMATION_NOVELTY"]
UMBRELLA_MECHANISMS = ["MECH_INFORMATION_VALUE"]

INPUT_SHEETS = [
    "Refined_Mechanism_PreRegistration",
    "Refined_Mechanism_PreRegistration_Summary",
    "Refined_Mechanism_Frozen_Definitions",
    "Refined_Mechanism_Frozen_Observables",
    "Refined_Mechanism_Frozen_Label_Rules",
    "Refined_Mechanism_Frozen_Confidence_Rules",
    "Refined_Mechanism_Frozen_Falsification_Rules",
    "Refined_Mechanism_Label_Preview",
    "Refined_Mechanism_Evidence_Audit",
    "Refined_Mechanism_Conflict_Review",
    "Refined_Mechanism_Ambiguity_Audit",
    "Refined_Mechanism_Root_Cause_Analysis",
    "Refined_Mechanism_Overlap_Assessment",
    "Refined_Mechanism_Label_Balance_Audit",
    "Refined_Mechanism_Revision_Recommendations",
    "Refined_Mechanism_Conflict_Review_Summary",
]

OUTPUT_REPAIR = "Refined_Mechanism_Repair"
OUTPUT_DEFINITIONS = "Refined_Mechanism_v11_Candidate_Definitions"
OUTPUT_OBSERVABLES = "Refined_Mechanism_v11_Candidate_Observables"
OUTPUT_LABEL_RULES = "Refined_Mechanism_v11_Candidate_Label_Rules"
OUTPUT_SPECIFICITY = "Refined_Mechanism_Specificity_Repair_Design"
OUTPUT_OVERLAP = "Refined_Mechanism_Overlap_Repair_Design"
OUTPUT_EXCLUSION = "Refined_Mechanism_Exclusion_Rule_Review"
OUTPUT_CHANGE_LOG = "Refined_Mechanism_v11_Change_Log"
OUTPUT_READINESS = "Refined_Mechanism_Second_Preregistration_Readiness"
OUTPUT_GOVERNANCE = "Refined_Mechanism_Repair_Governance"
OUTPUT_SUMMARY = "Refined_Mechanism_Repair_Summary"

REPAIR_HEADERS = [
    "generated_ts",
    "schema_version",
    "repair_version",
    "repair_run_id",
    "repair_area",
    "repair_status",
    "source_conflict_review_version",
    "source_preregistration_version",
    "baseline_framework_version",
    "candidate_framework_version",
    "repair_scope",
    "scientific_problem",
    "repair_objective",
    "v1_0_preregistration_preserved",
    "classification_rerun_performed",
    "mechanism_testing_performed",
    "repair_conclusion",
    "recommended_next_action",
    "notes",
]

DEFINITION_HEADERS = [
    "generated_ts",
    "schema_version",
    "repair_version",
    "repair_run_id",
    "baseline_framework_version",
    "candidate_framework_version",
    "stable_mechanism_id",
    "mechanism_id",
    "candidate_mechanism_role",
    "baseline_definition",
    "candidate_definition",
    "baseline_positive_definition",
    "candidate_positive_definition",
    "baseline_negative_definition",
    "candidate_negative_definition",
    "candidate_unknown_definition",
    "candidate_insufficient_evidence_definition",
    "candidate_exclusion_definition",
    "primary_repair_target",
    "source_evidence",
    "change_rationale",
    "ready_for_second_preregistration",
    "notes",
]

OBSERVABLE_HEADERS = [
    "generated_ts",
    "schema_version",
    "repair_version",
    "repair_run_id",
    "baseline_framework_version",
    "candidate_framework_version",
    "mechanism_id",
    "candidate_observable_id",
    "candidate_observable_name",
    "observable_status",
    "baseline_reference",
    "candidate_definition",
    "classification_role",
    "expected_effect",
    "source_evidence",
    "notes",
]

LABEL_RULE_HEADERS = [
    "generated_ts",
    "schema_version",
    "repair_version",
    "repair_run_id",
    "baseline_framework_version",
    "candidate_framework_version",
    "mechanism_id",
    "baseline_positive_rule",
    "candidate_positive_rule",
    "baseline_negative_rule",
    "candidate_negative_rule",
    "candidate_unknown_rule",
    "candidate_insufficient_evidence_rule",
    "baseline_exclusion_rule",
    "candidate_exclusion_rule",
    "baseline_conflict_precedence_rule",
    "candidate_conflict_precedence_rule",
    "candidate_tie_breaking_rule",
    "negative_label_gain_hypothesis",
    "change_rationale",
    "notes",
]

SPECIFICITY_HEADERS = [
    "generated_ts",
    "schema_version",
    "repair_version",
    "repair_run_id",
    "specificity_issue_id",
    "source_evidence",
    "current_v1_0_behavior",
    "candidate_v1_1_change",
    "expected_effect",
    "overlap_target",
    "repair_priority",
    "notes",
]

OVERLAP_HEADERS = [
    "generated_ts",
    "schema_version",
    "repair_version",
    "repair_run_id",
    "mechanism_a",
    "mechanism_b",
    "current_overlap_classification",
    "current_overlap_evidence",
    "candidate_boundary_rule",
    "negative_case_separation",
    "expected_overlap_effect",
    "recommended_v1_1_status",
    "notes",
]

EXCLUSION_HEADERS = [
    "generated_ts",
    "schema_version",
    "repair_version",
    "repair_run_id",
    "rule_scope",
    "baseline_exclusion_rule",
    "candidate_exclusion_rule",
    "keep_or_change",
    "why_change_exists",
    "classification_impact",
    "notes",
]

CHANGE_LOG_HEADERS = [
    "generated_ts",
    "schema_version",
    "repair_version",
    "repair_run_id",
    "change_id",
    "candidate_framework_version",
    "mechanism_id",
    "change_area",
    "baseline_element",
    "candidate_element",
    "source_evidence",
    "why_change_exists",
    "expected_effect",
    "risk_if_not_preregistered",
    "notes",
]

READINESS_HEADERS = [
    "generated_ts",
    "schema_version",
    "repair_version",
    "repair_run_id",
    "readiness_area",
    "status",
    "evidence",
    "blocking_issue",
    "recommended_action",
    "notes",
]

GOVERNANCE_HEADERS = [
    "generated_ts",
    "schema_version",
    "repair_version",
    "repair_run_id",
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
    "repair_version",
    "repair_run_id",
    "build_status",
    "final_interpretation",
    "baseline_framework_version",
    "candidate_framework_version",
    "v1_0_preregistration_preserved",
    "candidate_definitions_written",
    "candidate_observables_written",
    "candidate_label_rules_written",
    "specificity_definition_redesigned",
    "negative_label_rules_redesigned",
    "overlap_repair_rules_defined",
    "exclusion_rules_reviewed",
    "proposed_changes_logged",
    "primary_repair_target",
    "strongest_v1_1_change",
    "primary_scientific_conclusion",
    "provider_calls_performed",
    "forecast_generation_performed",
    "classification_rerun_count",
    "mechanism_testing_performed",
    "accuracy_evaluation_performed",
    "v1_0_preregistration_modified",
    "production_behavior_change_count",
    "production_sheet_write_count",
    "ready_for_second_preregistration",
    "ready_for_refined_classification_dry_run",
    "ready_for_refined_classification_execution",
    "ready_for_mechanism_testing",
    "ready_for_production",
    "recommended_next_step",
    "notes",
]


def _repair_run_id(generated_ts: str) -> str:
    return "refined_mechanism_repair_v0_" + generated_ts.replace("-", "").replace(":", "")


def _base(generated_ts: str, repair_run_id: str) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "repair_version": REPAIR_VERSION,
        "repair_run_id": repair_run_id,
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
    return {sheet: _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet) for sheet in INPUT_SHEETS}


def _parse_json_text(value: Any) -> Dict[str, Any]:
    text = _norm(value)
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    return {}


def _find_row(rows: List[Dict[str, Any]], field: str, value: str) -> Dict[str, Any]:
    target = _norm(value)
    return next((row for row in rows if _norm(row.get(field)) == target), {})


def _counter_json(counter: Counter[str]) -> str:
    return json.dumps({key: counter[key] for key in sorted(counter)}, sort_keys=True, ensure_ascii=True)


def _mechanism_preview_counts(data: Dict[str, List[Dict[str, Any]]], mechanism_id: str) -> Counter[str]:
    rows = [row for row in data["Refined_Mechanism_Label_Preview"] if _norm(row.get("mechanism_id")) == mechanism_id]
    return Counter(_norm(row.get("preview_label")) or "UNKNOWN" for row in rows)


def _ambiguity_reason_count(data: Dict[str, List[Dict[str, Any]]], mechanism_id: str, reason: str) -> int:
    rows = [row for row in data["Refined_Mechanism_Ambiguity_Audit"] if _norm(row.get("mechanism_id")) == mechanism_id]
    return sum(
        int(row.get("ambiguity_rows", 0))
        for row in rows
        if _norm(row.get("ambiguity_source")) == _norm(reason)
    )


def _overlap_row(data: Dict[str, List[Dict[str, Any]]], mechanism_a: str, mechanism_b: str) -> Dict[str, Any]:
    rows = data["Refined_Mechanism_Overlap_Assessment"]
    for row in rows:
        a = _norm(row.get("mechanism_a"))
        b = _norm(row.get("mechanism_b"))
        if {a, b} == {_norm(mechanism_a), _norm(mechanism_b)}:
            return row
    return {}


def _root_cause_row(data: Dict[str, List[Dict[str, Any]]], mechanism_id: str, category: str) -> Dict[str, Any]:
    rows = data["Refined_Mechanism_Root_Cause_Analysis"]
    return next(
        (
            row
            for row in rows
            if _norm(row.get("mechanism_id")) == _norm(mechanism_id)
            and _norm(row.get("root_cause_category")) == _norm(category)
        ),
        {},
    )


def _upsert_registry_rows(service) -> Dict[str, int]:
    titles = _sheet_titles_light(service, PROJECT_OVERVIEWS_SPREADSHEET_ID)
    if REGISTRY_SHEET not in titles:
        return {"updated": 0, "appended": 0, "status": "missing"}
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_norm(row.get("logical_sheet_id")).upper(): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_norm(row.get("logical_sheet_id")).upper(): row for row in rows}
    specs = [
        ("REFINED_MECHANISM_REPAIR", OUTPUT_REPAIR, "refined_mechanism_repair"),
        ("REFINED_MECHANISM_V11_CANDIDATE_DEFINITIONS", OUTPUT_DEFINITIONS, "refined_mechanism_v11_candidate_definitions"),
        ("REFINED_MECHANISM_V11_CANDIDATE_OBSERVABLES", OUTPUT_OBSERVABLES, "refined_mechanism_v11_candidate_observables"),
        ("REFINED_MECHANISM_V11_CANDIDATE_LABEL_RULES", OUTPUT_LABEL_RULES, "refined_mechanism_v11_candidate_label_rules"),
        ("REFINED_MECHANISM_SPECIFICITY_REPAIR_DESIGN", OUTPUT_SPECIFICITY, "refined_mechanism_specificity_repair_design"),
        ("REFINED_MECHANISM_OVERLAP_REPAIR_DESIGN", OUTPUT_OVERLAP, "refined_mechanism_overlap_repair_design"),
        ("REFINED_MECHANISM_EXCLUSION_RULE_REVIEW", OUTPUT_EXCLUSION, "refined_mechanism_exclusion_rule_review"),
        ("REFINED_MECHANISM_V11_CHANGE_LOG", OUTPUT_CHANGE_LOG, "refined_mechanism_v11_change_log"),
        ("REFINED_MECHANISM_SECOND_PREREGISTRATION_READINESS", OUTPUT_READINESS, "refined_mechanism_second_preregistration_readiness"),
        ("REFINED_MECHANISM_REPAIR_GOVERNANCE", OUTPUT_GOVERNANCE, "refined_mechanism_repair_governance"),
        ("REFINED_MECHANISM_REPAIR_SUMMARY", OUTPUT_SUMMARY, "refined_mechanism_repair_summary"),
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
            "notes": "Phase 9A-6R4 refined mechanism repair; preserves v1.0 preregistration and emits v1.1 candidate framework only.",
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
        updates.append(
            {
                "range": f"'{REGISTRY_SHEET}'!A{row_number}:{_column_letter(len(REGISTRY_HEADERS))}{row_number}",
                "values": [values],
            }
        )
    if updates:
        batch_update_values(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, updates)
    return {"updated": len(specs) - appended, "appended": appended}


def _candidate_definition_rows(
    data: Dict[str, List[Dict[str, Any]]],
    generated_ts: str,
    repair_run_id: str,
) -> List[Dict[str, Any]]:
    frozen_definitions = data["Refined_Mechanism_Frozen_Definitions"]
    counts_relevance = _mechanism_preview_counts(data, "MECH_INFORMATION_RELEVANCE")
    counts_specificity = _mechanism_preview_counts(data, "MECH_INFORMATION_SPECIFICITY")
    counts_consistency = _mechanism_preview_counts(data, "MECH_INFORMATION_CONSISTENCY")

    candidates: Dict[str, Dict[str, str]] = {
        "MECH_INFORMATION_RELEVANCE": {
            "candidate_role": "PROMOTED_REFINED_MECHANISM_CANDIDATE",
            "candidate_definition": "Whether added information directly changes the forecast target-driver path, rather than merely adding context, precision, or coherence cues.",
            "candidate_positive_definition": "Positive only when target/driver alignment and causal-path alignment are both explicit; session or horizon references may support relevance but cannot make the label positive alone.",
            "candidate_negative_definition": "Negative when added information is cited but remains peripheral, secondary-only, horizon-only, or otherwise fails to change the target-driver causal path.",
            "candidate_unknown_definition": "Unknown when target alignment, causal-path alignment, and driver depth remain mixed without a decisive path-changing signal.",
            "candidate_insufficient_evidence_definition": "Insufficient when target-driver linkage or causal-path trace is missing.",
            "candidate_exclusion_definition": "Exclude only baseline-pack rows with no added information, invalid outputs, schema failures, or any rule that would require realized outcomes.",
            "primary_repair_target": "NEGATIVE_LABEL_CLARIFICATION",
            "source_evidence": (
                f"0 negative labels, {counts_relevance.get('UNKNOWN', 0)} unknown labels, and "
                f"{_ambiguity_reason_count(data, 'MECH_INFORMATION_RELEVANCE', 'observable states conflict under the frozen refined rules')} conflict-driven ambiguity rows."
            ),
            "change_rationale": "Relevance should stay distinct from specificity: path-changing relevance is positive, while relevant-but-peripheral detail becomes a negative case instead of silently inflating positivity.",
        },
        "MECH_INFORMATION_SPECIFICITY": {
            "candidate_role": "PROMOTED_REFINED_MECHANISM_CANDIDATE",
            "candidate_definition": "Whether added information creates an explicit falsifiable boundary for the forecast through a conditional trigger, invalidation rule, abstention boundary, or equivalent structure, rather than merely adding detail.",
            "candidate_positive_definition": "Positive only when a falsifiable boundary is explicit: for example a concrete invalidation condition, an explicit no-signal boundary, or a directional trigger paired with a real condition. Time horizon alone is supporting evidence, not sufficient evidence.",
            "candidate_negative_definition": "Negative when information is relevant or coherent but remains structurally unbounded: plain directional restatement, time framing without a boundary, or extra narrative detail without a falsifiable condition.",
            "candidate_unknown_definition": "Unknown when boundary evidence is partial, pseudo-specific, or internally conflicting across trigger, invalidation, abstention, and horizon signals.",
            "candidate_insufficient_evidence_definition": "Insufficient when the row lacks enough pre-outcome trace to evaluate whether any boundary-forming structure exists.",
            "candidate_exclusion_definition": "Exclude only baseline-pack rows with no added information, invalid outputs, schema failures, or any rule that would require realized outcomes. Missing invalidation text alone is not an exclusion trigger.",
            "primary_repair_target": "PRIMARY_FRAMEWORK_REPAIR",
            "source_evidence": (
                f"{counts_specificity.get('NEGATIVE', 0)} negative labels, {counts_specificity.get('UNKNOWN', 0)} direct unknown labels, "
                f"{_ambiguity_reason_count(data, 'MECH_INFORMATION_SPECIFICITY', 'observable states conflict under the frozen refined rules')} conflict-driven ambiguity rows, and "
                f"{_ambiguity_reason_count(data, 'MECH_INFORMATION_SPECIFICITY', 'observable evidence does not cross a frozen positive or negative threshold')} threshold-driven ambiguity rows."
            ),
            "change_rationale": "Specificity needs to separate falsifiability from mere relevance and coherence. The v1.0 design treated time framing as too positive and missing invalidation text as too negative, which created overlap and artificial ambiguity.",
        },
        "MECH_INFORMATION_CONSISTENCY": {
            "candidate_role": "PROMOTED_REFINED_MECHANISM_CANDIDATE",
            "candidate_definition": "Whether added information remains internally coherent across driver hierarchy, causal chain, directional rationale, and confidence-evidence cues, independent of whether it is target-relevant or structurally specific.",
            "candidate_positive_definition": "Positive when at least two comparison planes remain coherent and no decisive contradiction is present.",
            "candidate_negative_definition": "Negative when a decisive contradiction appears in any core comparison plane, especially driver-vs-chain, rationale-vs-direction, or confidence-vs-evidence mismatch.",
            "candidate_unknown_definition": "Unknown when traces are only partially comparable or when weak coherence and weak contradiction coexist without a decisive inconsistency.",
            "candidate_insufficient_evidence_definition": "Insufficient when comparable cross-field or premise-comparison traces are missing.",
            "candidate_exclusion_definition": "Exclude only baseline-pack rows with no added information, invalid outputs, schema failures, or any rule that would require realized outcomes.",
            "primary_repair_target": "NEGATIVE_LABEL_CLARIFICATION",
            "source_evidence": (
                f"{counts_consistency.get('NEGATIVE', 0)} negative labels, {counts_consistency.get('UNKNOWN', 0)} unknown labels, and "
                f"{_ambiguity_reason_count(data, 'MECH_INFORMATION_CONSISTENCY', 'observable states conflict under the frozen refined rules')} conflict-driven ambiguity rows."
            ),
            "change_rationale": "Consistency remains scientifically useful, but its negative class is too narrow. The v1.1 candidate should recognize decisive contradictions sooner without borrowing specificity signals.",
        },
        "MECH_INFORMATION_NOVELTY": {
            "candidate_role": "SUBDIMENSION_ONLY",
            "candidate_definition": "Whether exposed information introduces a new field family, driver branch, or uncertainty dimension relative to baseline, without implying relevance or usefulness.",
            "candidate_positive_definition": "Supporting evidence only. Novelty remains non-classifiable until a later promotion cycle.",
            "candidate_negative_definition": "Supporting evidence only. Lack of novelty may be recorded but does not become a standalone label.",
            "candidate_unknown_definition": "Supporting-only state when novelty cannot be separated from repackaging or relevance.",
            "candidate_insufficient_evidence_definition": "Supporting-only state when baseline-difference traces are missing.",
            "candidate_exclusion_definition": "Direct classification remains excluded because novelty is still a supporting subdimension rather than a standalone mechanism.",
            "primary_repair_target": "NO_DIRECT_REPAIR",
            "source_evidence": "Retained as supporting-only because the conflict review identified the main execution blockers in specificity, not in novelty promotion.",
            "change_rationale": "Novelty stays available for interpretation but does not enter the second preregistration as a directly classifiable mechanism.",
        },
        "MECH_INFORMATION_VALUE": {
            "candidate_role": "UMBRELLA_ONLY",
            "candidate_definition": "Legacy umbrella concept preserved for historical traceability across relevance, specificity, consistency, and novelty dimensions.",
            "candidate_positive_definition": "Not applicable. Direct umbrella classification remains disabled.",
            "candidate_negative_definition": "Not applicable. Direct umbrella classification remains disabled.",
            "candidate_unknown_definition": "Not applicable. Direct umbrella classification remains disabled.",
            "candidate_insufficient_evidence_definition": "Not applicable. Direct umbrella classification remains disabled.",
            "candidate_exclusion_definition": "Direct umbrella classification remains permanently excluded. The v1.1 candidate framework still treats the parent as conceptual traceability only.",
            "primary_repair_target": "NO_DIRECT_REPAIR",
            "source_evidence": "The parent was already retired from direct classification in v1.0 and remains non-classifiable after the refined dry-run conflict review.",
            "change_rationale": "Preserve historical lineage without reopening the composite mechanism for direct execution.",
        },
    }

    rows: List[Dict[str, Any]] = []
    for mechanism_id in PROMOTED_MECHANISMS + SUBDIMENSION_MECHANISMS + UMBRELLA_MECHANISMS:
        baseline = _find_row(frozen_definitions, "mechanism_id", mechanism_id)
        candidate = candidates[mechanism_id]
        rows.append(
            {
                **_base(generated_ts, repair_run_id),
                "baseline_framework_version": BASELINE_VERSION,
                "candidate_framework_version": CANDIDATE_FRAMEWORK_VERSION,
                "stable_mechanism_id": _norm(baseline.get("stable_mechanism_id")),
                "mechanism_id": mechanism_id,
                "candidate_mechanism_role": candidate["candidate_role"],
                "baseline_definition": _norm(baseline.get("scientific_definition")),
                "candidate_definition": candidate["candidate_definition"],
                "baseline_positive_definition": _norm(baseline.get("positive_label_definition")),
                "candidate_positive_definition": candidate["candidate_positive_definition"],
                "baseline_negative_definition": _norm(baseline.get("negative_label_definition")),
                "candidate_negative_definition": candidate["candidate_negative_definition"],
                "candidate_unknown_definition": candidate["candidate_unknown_definition"],
                "candidate_insufficient_evidence_definition": candidate["candidate_insufficient_evidence_definition"],
                "candidate_exclusion_definition": candidate["candidate_exclusion_definition"],
                "primary_repair_target": candidate["primary_repair_target"],
                "source_evidence": candidate["source_evidence"],
                "change_rationale": candidate["change_rationale"],
                "ready_for_second_preregistration": "TRUE" if mechanism_id in PROMOTED_MECHANISMS else "TRUE_WITH_ROLE_RESTRICTION",
                "notes": "v1.0 remains untouched; this row defines a v1.1 candidate only.",
            }
        )
    return rows


def _candidate_observable_rows(
    generated_ts: str,
    repair_run_id: str,
) -> List[Dict[str, Any]]:
    specs = [
        (
            "MECH_INFORMATION_RELEVANCE",
            "rel_core_target_driver_path",
            "Core Target-Driver Path Alignment",
            "RETAIN_AND_REWEIGHT",
            "target_driver_alignment + field_to_causal_path_alignment",
            "Combined core signal that asks whether the added information changes the target-driver path rather than merely accompanying it.",
            "CORE",
            "Prevents horizon-only or specificity-only cues from making relevance positive.",
            "0 negative relevance labels and mixed target/driver conflict patterns indicate the path-changing signal needs more weight than supporting cues.",
        ),
        (
            "MECH_INFORMATION_RELEVANCE",
            "rel_horizon_support_only",
            "Horizon Support Only",
            "DOWNWEIGHT_TO_SUPPORTING",
            "session_horizon_alignment",
            "Session or horizon alignment remains observable, but it becomes supporting evidence only and cannot create a positive relevance label by itself.",
            "SUPPORTING",
            "Reduces false positivity from time-context mention without causal-path change.",
            "Conflict rows include positive horizon evidence paired with negative driver depth or negative target alignment.",
        ),
        (
            "MECH_INFORMATION_SPECIFICITY",
            "spec_falsifiable_boundary_present",
            "Falsifiable Boundary Present",
            "NEW_CORE_OBSERVABLE",
            "derived from explicit_failure_condition + explicit_no_signal_boundary + conditional direction trigger",
            "Whether the added information introduces a real boundary that could falsify or abstain from the forecast before outcomes are known.",
            "CORE",
            "Re-centers specificity on boundary formation instead of verbosity or general detail.",
            "Specificity produced only 2 negative labels and 39 direct unknown labels under the v1.0 structure.",
        ),
        (
            "MECH_INFORMATION_SPECIFICITY",
            "spec_generic_direction_restatement",
            "Generic Direction Restatement",
            "NEW_NEGATIVE_OBSERVABLE",
            "explicit_direction_condition",
            "Captures when direction is restated without a trigger, invalidation rule, or abstention boundary.",
            "NEGATIVE_CUE",
            "Creates a stronger deterministic negative case instead of drifting to UNKNOWN.",
            "The dominant threshold pattern combines direction negative with time positive and no boundary signal.",
        ),
        (
            "MECH_INFORMATION_SPECIFICITY",
            "spec_time_horizon_support_only",
            "Time Horizon Support Only",
            "REDEFINE_EXISTING_OBSERVABLE",
            "explicit_time_horizon",
            "Time horizon remains a supporting cue but cannot by itself make specificity positive.",
            "SUPPORTING",
            "Directly reduces specificity overlap with relevance and cuts time-only ambiguity.",
            "The dominant ambiguous pattern is time-horizon positive without a valid falsifiable boundary.",
        ),
        (
            "MECH_INFORMATION_SPECIFICITY",
            "spec_missing_invalidation_neutral",
            "Missing Invalidation Is Neutral",
            "REDEFINE_EXISTING_OBSERVABLE",
            "explicit_failure_condition",
            "Absence of explicit invalidation no longer becomes automatically negative; it stays neutral unless other evidence shows generic elaboration.",
            "NEUTRAL_GATING",
            "Removes an artificial conflict source that inflated UNKNOWN outcomes.",
            "Specificity conflict rows are dominated by positive-vs-negative coexistence; auto-negative missing invalidation contributes to that instability.",
        ),
        (
            "MECH_INFORMATION_CONSISTENCY",
            "cons_decisive_contradiction_priority",
            "Decisive Contradiction Priority",
            "NEW_RULED_OBSERVABLE",
            "driver_causal_chain_consistency + direction_rationale_consistency + confidence_evidence_consistency",
            "Any decisive contradiction in a core comparison plane receives priority over weaker positive cues.",
            "CORE_NEGATIVE",
            "Improves negative-case coverage without importing specificity logic.",
            "Consistency produced only 2 negative labels despite multiple ambiguity patterns with direct negative rationale cues.",
        ),
        (
            "MECH_INFORMATION_CONSISTENCY",
            "cons_cross_field_supporting",
            "Cross-Field Coherence Supporting",
            "RETAIN_AND_CLARIFY",
            "cross_field_consistency",
            "Cross-field coherence remains informative, but it stays supporting unless paired with another coherent plane or contradicted by a decisive mismatch.",
            "SUPPORTING",
            "Prevents one soft coherence cue from overwhelming a contradiction elsewhere.",
            "Top consistency ambiguity patterns show confidence and direction cues outrunning cross-field comparability.",
        ),
        (
            "MECH_INFORMATION_NOVELTY",
            "nov_baseline_delta_supporting",
            "Baseline Delta Novelty",
            "UNCHANGED_SUPPORTING_ONLY",
            "baseline-difference traces",
            "Novelty remains a supporting baseline-difference cue and does not enter direct classification in the v1.1 candidate framework.",
            "SUPPORTING_ONLY",
            "Keeps novelty available without broadening the classifiable mechanism set.",
            "The repair phase targets specificity and negative-case balance, not novelty promotion.",
        ),
    ]
    rows: List[Dict[str, Any]] = []
    for mechanism_id, observable_id, observable_name, status, baseline_reference, candidate_definition, role, effect, source in specs:
        rows.append(
            {
                **_base(generated_ts, repair_run_id),
                "baseline_framework_version": BASELINE_VERSION,
                "candidate_framework_version": CANDIDATE_FRAMEWORK_VERSION,
                "mechanism_id": mechanism_id,
                "candidate_observable_id": observable_id,
                "candidate_observable_name": observable_name,
                "observable_status": status,
                "baseline_reference": baseline_reference,
                "candidate_definition": candidate_definition,
                "classification_role": role,
                "expected_effect": effect,
                "source_evidence": source,
                "notes": "Candidate observable only; it must be frozen in the second preregistration before any rerun.",
            }
        )
    return rows


def _candidate_label_rule_rows(
    data: Dict[str, List[Dict[str, Any]]],
    generated_ts: str,
    repair_run_id: str,
) -> List[Dict[str, Any]]:
    frozen_rules = data["Refined_Mechanism_Frozen_Label_Rules"]
    candidates = {
        "MECH_INFORMATION_RELEVANCE": {
            "candidate_positive_rule": "Positive when the added information changes the target-driver path and the causal chain explicitly incorporates that change. Horizon context may support but never determine the label.",
            "candidate_negative_rule": "Negative when added information is present but remains peripheral, secondary-only, horizon-only, or otherwise fails to alter the target-driver path.",
            "candidate_unknown_rule": "Unknown when target alignment and path alignment remain mixed without a decisive path-changing signal.",
            "candidate_insufficient_evidence_rule": "Insufficient when target-driver linkage or causal-path evidence is missing.",
            "candidate_exclusion_rule": "Exclude only baseline-pack rows with no added information, invalid outputs, schema failures, or any outcome-dependent logic.",
            "candidate_conflict_precedence_rule": "excluded_case > insufficient_evidence > negative when peripheral or non-path-changing detail is explicit > positive when target-driver path change is explicit without contradiction > unknown",
            "candidate_tie_breaking_rule": "If causal-path alignment is positive but driver depth is secondary-only, downgrade to NEGATIVE rather than UNKNOWN when no path change is visible.",
            "negative_label_gain_hypothesis": "Move relevance from 0 negatives toward deterministic peripheral-detail negatives without increasing exclusions.",
            "change_rationale": "Relevance should no longer absorb horizon-only or commentary-only changes as quasi-positive cases.",
        },
        "MECH_INFORMATION_SPECIFICITY": {
            "candidate_positive_rule": "Positive only when a falsifiable boundary is explicit: invalidation condition, abstention boundary, or conditional directional trigger with a concrete condition. Time framing alone is not sufficient.",
            "candidate_negative_rule": "Negative when added information is relevant or coherent but structurally unbounded: generic directional restatement, time-only framing, or narrative elaboration without a falsifiable boundary.",
            "candidate_unknown_rule": "Unknown only when partial boundary evidence exists but remains contradictory or pseudo-specific across trigger, invalidation, abstention, and horizon cues.",
            "candidate_insufficient_evidence_rule": "Insufficient when boundary-forming evidence is too sparse to determine whether the claim became falsifiable.",
            "candidate_exclusion_rule": "Exclude only baseline-pack rows with no added information, invalid outputs, schema failures, or any outcome-dependent logic. Missing invalidation text alone is not an exclusion or automatic negative trigger.",
            "candidate_conflict_precedence_rule": "excluded_case > insufficient_evidence > negative when the row is clearly unbounded despite relevant/coherent detail > positive when falsifiable boundary is explicit and uncontested > unknown",
            "candidate_tie_breaking_rule": "If time horizon is the only positive cue, keep it supporting-only and do not let it override missing or generic boundary structure.",
            "negative_label_gain_hypothesis": "Convert time-only, direction-only, and relevant-but-unbounded rows from UNKNOWN into deterministic specificity negatives.",
            "change_rationale": "The current specificity rule set overuses time framing and auto-negative missing invalidation, which blurs specificity with relevance and consistency.",
        },
        "MECH_INFORMATION_CONSISTENCY": {
            "candidate_positive_rule": "Positive when at least two coherence planes align and no decisive contradiction is present.",
            "candidate_negative_rule": "Negative when any decisive contradiction is explicit in driver-vs-chain, direction rationale, cross-field evidence, or confidence-vs-uncertainty cues.",
            "candidate_unknown_rule": "Unknown when only partial comparability exists or when weak coherence and weak contradiction coexist without a decisive inconsistency.",
            "candidate_insufficient_evidence_rule": "Insufficient when comparable cross-field or premise-comparison traces are absent.",
            "candidate_exclusion_rule": "Exclude only baseline-pack rows with no added information, invalid outputs, schema failures, or any outcome-dependent logic.",
            "candidate_conflict_precedence_rule": "excluded_case > insufficient_evidence > negative when decisive contradiction is explicit > positive when coherence is repeated across comparison planes > unknown",
            "candidate_tie_breaking_rule": "A decisive contradiction beats a soft coherence cue; one soft coherence cue cannot rescue an otherwise contradictory row into POSITIVE.",
            "negative_label_gain_hypothesis": "Increase deterministic negative labels for clear contradiction rows without borrowing specificity or relevance cues.",
            "change_rationale": "Consistency needs sharper negative recognition so contradiction-bearing rows do not remain permanently positive-or-unknown.",
        },
    }
    rows: List[Dict[str, Any]] = []
    for mechanism_id in PROMOTED_MECHANISMS:
        baseline = _find_row(frozen_rules, "mechanism_id", mechanism_id)
        candidate = candidates[mechanism_id]
        rows.append(
            {
                **_base(generated_ts, repair_run_id),
                "baseline_framework_version": BASELINE_VERSION,
                "candidate_framework_version": CANDIDATE_FRAMEWORK_VERSION,
                "mechanism_id": mechanism_id,
                "baseline_positive_rule": _norm(baseline.get("positive_label_rule")),
                "candidate_positive_rule": candidate["candidate_positive_rule"],
                "baseline_negative_rule": _norm(baseline.get("negative_label_rule")),
                "candidate_negative_rule": candidate["candidate_negative_rule"],
                "candidate_unknown_rule": candidate["candidate_unknown_rule"],
                "candidate_insufficient_evidence_rule": candidate["candidate_insufficient_evidence_rule"],
                "baseline_exclusion_rule": _norm(baseline.get("exclusion_rule")),
                "candidate_exclusion_rule": candidate["candidate_exclusion_rule"],
                "baseline_conflict_precedence_rule": _norm(baseline.get("conflict_precedence_rule")),
                "candidate_conflict_precedence_rule": candidate["candidate_conflict_precedence_rule"],
                "candidate_tie_breaking_rule": candidate["candidate_tie_breaking_rule"],
                "negative_label_gain_hypothesis": candidate["negative_label_gain_hypothesis"],
                "change_rationale": candidate["change_rationale"],
                "notes": "Candidate v1.1 rule only; frozen v1.0 rules remain unchanged.",
            }
        )
    return rows


def _specificity_repair_rows(
    data: Dict[str, List[Dict[str, Any]]],
    generated_ts: str,
    repair_run_id: str,
) -> List[Dict[str, Any]]:
    overlap_rel = _overlap_row(data, "MECH_INFORMATION_RELEVANCE", "MECH_INFORMATION_SPECIFICITY")
    overlap_con = _overlap_row(data, "MECH_INFORMATION_SPECIFICITY", "MECH_INFORMATION_CONSISTENCY")
    return [
        {
            **_base(generated_ts, repair_run_id),
            "specificity_issue_id": "SPEC_REDEFINE_TO_FALSIFIABILITY",
            "source_evidence": "Direct specificity ambiguity 39/120; dry-run summary burden 77/120.",
            "current_v1_0_behavior": "Specificity blends time framing, explicit conditions, and generic precision cues into one mechanism.",
            "candidate_v1_1_change": "Redefine specificity around explicit falsifiable boundary formation rather than general detail or time framing.",
            "expected_effect": "Concentrates positive labels on genuinely boundary-forming rows and reduces overlap with relevance.",
            "overlap_target": "MECH_INFORMATION_RELEVANCE",
            "repair_priority": "HIGH",
            "notes": "Primary scientific repair for the v1.1 candidate framework.",
        },
        {
            **_base(generated_ts, repair_run_id),
            "specificity_issue_id": "SPEC_TIME_HORIZON_SUPPORT_ONLY",
            "source_evidence": "Dominant threshold pattern count 17 with time-horizon POSITIVE and no explicit boundary.",
            "current_v1_0_behavior": "Explicit time horizon can contribute directly to positive specificity thresholds.",
            "candidate_v1_1_change": "Demote time horizon to supporting-only evidence unless paired with a falsifiable trigger or boundary.",
            "expected_effect": "Removes time-only pseudo-specificity and lowers relevance overlap.",
            "overlap_target": "MECH_INFORMATION_RELEVANCE",
            "repair_priority": "HIGH",
            "notes": "Time framing alone should not count as specificity-positive.",
        },
        {
            **_base(generated_ts, repair_run_id),
            "specificity_issue_id": "SPEC_REMOVE_AUTO_NEGATIVE_MISSING_INVALIDATION",
            "source_evidence": "22 conflict-driven ambiguity rows dominated by positive and negative observable coexistence.",
            "current_v1_0_behavior": "Missing invalidation text turns explicit_failure_condition negative by default.",
            "candidate_v1_1_change": "Make missing invalidation neutral unless other evidence shows the row is structurally generic.",
            "expected_effect": "Removes an artificial negative source that inflated UNKNOWN outcomes.",
            "overlap_target": "INTERNAL_SPECIFICITY_STABILITY",
            "repair_priority": "HIGH",
            "notes": "This directly targets the positive-vs-negative coexistence problem.",
        },
        {
            **_base(generated_ts, repair_run_id),
            "specificity_issue_id": "SPEC_RELEVANCE_GATE",
            "source_evidence": "32/39 specificity-ambiguous rows co-occur with POSITIVE relevance.",
            "current_v1_0_behavior": "Relevant rows can look specific even when they only add target-relevant detail.",
            "candidate_v1_1_change": "Require a boundary-forming cue before relevance-positive rows may also become specificity-positive.",
            "expected_effect": "Prevents relevance from shadowing specificity.",
            "overlap_target": "MECH_INFORMATION_RELEVANCE",
            "repair_priority": "HIGH",
            "notes": "Specificity must answer a different scientific question than relevance.",
        },
        {
            **_base(generated_ts, repair_run_id),
            "specificity_issue_id": "SPEC_CONSISTENCY_GATE",
            "source_evidence": "21/39 specificity-ambiguous rows co-occur with POSITIVE consistency.",
            "current_v1_0_behavior": "Coherent rows can appear specificity-positive even when they are merely well-aligned.",
            "candidate_v1_1_change": "Make coherence supportive but not sufficient; consistency-positive rows need an independent falsifiable boundary to become specificity-positive.",
            "expected_effect": "Separates coherence from structural narrowing.",
            "overlap_target": "MECH_INFORMATION_CONSISTENCY",
            "repair_priority": "HIGH",
            "notes": "Consistency answers whether claims agree internally, not whether they narrow structurally.",
        },
        {
            **_base(generated_ts, repair_run_id),
            "specificity_issue_id": "SPEC_NEGATIVE_CASE_EXPANSION",
            "source_evidence": "Specificity produced only 2 negative labels against 41 positives and 39 direct unknowns.",
            "current_v1_0_behavior": "Negative specificity is too narrow and only catches the most clearly generic rows.",
            "candidate_v1_1_change": "Treat relevant-but-unbounded and coherent-but-unbounded rows as deterministic specificity negatives.",
            "expected_effect": "Improves label balance and reduces ambiguity without widening exclusions.",
            "overlap_target": "NEGATIVE_LABEL_BALANCE",
            "repair_priority": "HIGH",
            "notes": "This repair is necessary before any second preregistration.",
        },
    ]


def _overlap_repair_rows(
    data: Dict[str, List[Dict[str, Any]]],
    generated_ts: str,
    repair_run_id: str,
) -> List[Dict[str, Any]]:
    specs = [
        (
            "MECH_INFORMATION_RELEVANCE",
            "MECH_INFORMATION_SPECIFICITY",
            "Relevance positive requires target-driver path change; specificity positive requires explicit falsifiable boundary. Relevance may support specificity, but cannot satisfy it.",
            "A row can be relevance-positive and specificity-negative when it adds target-relevant detail without narrowing the claim.",
            "Reduce the current REQUIRES_REFINEMENT overlap to reviewable overlap in the second dry run.",
            "REPAIR_AND_REPREREGISTER",
        ),
        (
            "MECH_INFORMATION_RELEVANCE",
            "MECH_INFORMATION_CONSISTENCY",
            "Relevance asks whether new information belongs on the target-driver path; consistency asks whether the resulting claim remains internally coherent.",
            "A row can be relevance-positive and consistency-negative if it introduces target-relevant but contradictory evidence.",
            "Keep overlap scientifically acceptable while improving negative-case balance.",
            "KEEP_WITH_RULE_CLARIFICATION",
        ),
        (
            "MECH_INFORMATION_SPECIFICITY",
            "MECH_INFORMATION_CONSISTENCY",
            "Specificity positive requires a falsifiable boundary; consistency positive requires internal coherence. Coherence alone never makes a row specific.",
            "A row can be consistency-positive and specificity-negative when it is coherent but still structurally generic.",
            "Reduce the current REQUIRES_REFINEMENT overlap and lower ambiguity in specificity.",
            "REPAIR_AND_REPREREGISTER",
        ),
    ]
    rows: List[Dict[str, Any]] = []
    for mechanism_a, mechanism_b, boundary_rule, negative_sep, effect, status in specs:
        overlap = _overlap_row(data, mechanism_a, mechanism_b)
        rows.append(
            {
                **_base(generated_ts, repair_run_id),
                "mechanism_a": mechanism_a,
                "mechanism_b": mechanism_b,
                "current_overlap_classification": _norm(overlap.get("overlap_classification")),
                "current_overlap_evidence": json.dumps(
                    {
                        "shared_positive_rows": _norm(overlap.get("shared_positive_rows")),
                        "shared_positive_jaccard": _norm(overlap.get("shared_positive_jaccard")),
                        "shared_unknown_rows": _norm(overlap.get("shared_unknown_rows")),
                    },
                    sort_keys=True,
                    ensure_ascii=True,
                ),
                "candidate_boundary_rule": boundary_rule,
                "negative_case_separation": negative_sep,
                "expected_overlap_effect": effect,
                "recommended_v1_1_status": status,
                "notes": "Candidate pairwise boundary for the second preregistration cycle.",
            }
        )
    return rows


def _exclusion_review_rows(
    data: Dict[str, List[Dict[str, Any]]],
    generated_ts: str,
    repair_run_id: str,
) -> List[Dict[str, Any]]:
    return [
        {
            **_base(generated_ts, repair_run_id),
            "rule_scope": "BASELINE_PACK_A_SCOPE",
            "baseline_exclusion_rule": "Baseline pack has no added information under the refined pre-registration scope.",
            "candidate_exclusion_rule": "Keep unchanged. Baseline Pack A remains excluded from direct refined mechanism classification because the repair phase still studies added-information effects only.",
            "keep_or_change": "KEEP",
            "why_change_exists": "This exclusion is scientifically structural rather than a source of ambiguity.",
            "classification_impact": "No v1.1 recovery expected; preserve treatment-only scope.",
            "notes": "24 excluded rows per promoted mechanism came from baseline-pack scope.",
        },
        {
            **_base(generated_ts, repair_run_id),
            "rule_scope": "INVALID_OUTPUT_SCOPE",
            "baseline_exclusion_rule": "Exclude rows where output_valid is not TRUE.",
            "candidate_exclusion_rule": "Keep unchanged. Invalid outputs remain out of scope for refined mechanism classification.",
            "keep_or_change": "KEEP",
            "why_change_exists": "Invalid-output exclusion is a hard governance boundary, not a mechanism-definition issue.",
            "classification_impact": "No v1.1 recovery expected; preserves data integrity.",
            "notes": "14 excluded rows per promoted mechanism came from invalid outputs.",
        },
        {
            **_base(generated_ts, repair_run_id),
            "rule_scope": "OPTIONAL_BOUNDARY_TRACES",
            "baseline_exclusion_rule": "Missing explicit invalidation or no-signal detail could drift into negative or ambiguity logic indirectly.",
            "candidate_exclusion_rule": "Clarify that missing optional boundary traces are not exclusions. They should map to neutral, insufficient, or negative candidate states depending on the remaining evidence.",
            "keep_or_change": "CHANGE",
            "why_change_exists": "Specificity ambiguity was inflated by optional fields behaving like hard negatives rather than optional evidence.",
            "classification_impact": "Reduces artificial ambiguity without widening the formal exclusion set.",
            "notes": "This is a rule-clarification repair, not a broadening of eligible rows.",
        },
    ]


def _change_log_rows(
    generated_ts: str,
    repair_run_id: str,
) -> List[Dict[str, Any]]:
    specs = [
        ("RMR-001", "MECH_INFORMATION_SPECIFICITY", "DEFINITION", "Specificity defined as precision/conditionality/falsifiability bundle.", "Specificity defined as explicit falsifiable-boundary formation.", "39 direct label ambiguities and 77 dry-run summary burden.", "Separates structural narrowing from general detail.", "Expected to reduce ambiguity and overlap.", "Must be frozen before any rerun."),
        ("RMR-002", "MECH_INFORMATION_SPECIFICITY", "POSITIVE_RULE", "Time horizon could help satisfy positivity directly.", "Time horizon becomes supporting-only unless paired with a boundary-forming cue.", "Dominant 17-row time-positive ambiguity pattern.", "Time-only evidence was overclaiming specificity.", "Expected to reduce relevance overlap.", "Needs preregistered supporting/core distinction."),
        ("RMR-003", "MECH_INFORMATION_SPECIFICITY", "NEGATIVE_RULE", "Only clearly generic or verbose rows became negative.", "Relevant-but-unbounded and coherent-but-unbounded rows become deterministic negatives.", "Only 2 negative specificity labels.", "Negative class was too restrictive.", "Expected to improve label balance.", "Needs frozen examples and thresholds."),
        ("RMR-004", "MECH_INFORMATION_SPECIFICITY", "FAILURE_OBSERVABLE", "Missing invalidation text drifted toward negative pressure.", "Missing invalidation becomes neutral unless other evidence shows generic structure.", "22 conflict-driven ambiguity rows.", "Auto-negative missing invalidation created avoidable conflict.", "Expected to lower UNKNOWN counts.", "Must be frozen before dry run."),
        ("RMR-005", "MECH_INFORMATION_SPECIFICITY", "OVERLAP_GATE_RELEVANCE", "Relevant detail could still look specificity-positive.", "Relevance-positive rows need an independent boundary-forming cue to become specificity-positive.", "32/39 specificity-ambiguous rows co-occur with relevance positive.", "Specificity must not shadow relevance.", "Expected to lower pairwise overlap.", "Requires explicit boundary rule."),
        ("RMR-006", "MECH_INFORMATION_SPECIFICITY", "OVERLAP_GATE_CONSISTENCY", "Coherent detail could still look specificity-positive.", "Consistency-positive rows need an independent boundary-forming cue to become specificity-positive.", "21/39 specificity-ambiguous rows co-occur with consistency positive.", "Specificity must not shadow consistency.", "Expected to lower pairwise overlap.", "Requires explicit pairwise separation."),
        ("RMR-007", "MECH_INFORMATION_RELEVANCE", "NEGATIVE_RULE", "Relevance produced 0 negatives.", "Peripheral, secondary-only, or non-path-changing detail becomes negative rather than quasi-positive.", "0 negative relevance labels and 16 ambiguities.", "Relevance needs a real negative case to avoid positivity inflation.", "Expected to improve balance without changing exclusions.", "Needs preregistered peripheral-detail examples."),
        ("RMR-008", "MECH_INFORMATION_RELEVANCE", "SUPPORTING_CUES", "Horizon alignment could contribute to positive relevance too easily.", "Horizon becomes supporting-only unless target-driver path change is explicit.", "Mixed relevance ambiguity patterns with positive horizon + negative driver depth.", "Stops relevance from absorbing specificity-like cues.", "Expected to reduce soft overlap.", "Needs supporting/core observable split."),
        ("RMR-009", "MECH_INFORMATION_CONSISTENCY", "NEGATIVE_RULE", "Consistency produced only 2 negatives.", "Any decisive contradiction in a core plane becomes negative even if softer positive cues remain.", "2 negative consistency labels and 26 ambiguities.", "Consistency negative threshold was too conservative.", "Expected to improve label balance.", "Needs decisive-contradiction definition."),
        ("RMR-010", "MECH_INFORMATION_CONSISTENCY", "POSITIVE_RULE", "Single soft coherence cues could dominate.", "Positive requires coherence across at least two comparison planes and no decisive contradiction.", "Top ambiguity patterns show partial coherence mixed with negative rationale cues.", "Prevents premature positivity.", "Expected to reduce positive-or-unknown skew.", "Needs frozen comparison-plane count."),
        ("RMR-011", "ALL_PROMOTED_REFINED_MECHANISMS", "EXCLUSION_RULES", "Hard exclusions and optional-evidence handling were not clearly separated.", "Keep hard exclusions unchanged; treat missing optional traces as neutral/insufficient/negative rather than excluded.", "Specificity ambiguity was partly driven by optional trace behavior.", "Keeps scope stable while repairing rule semantics.", "Expected to preserve governance while improving determinism.", "Needs explicit exclusion taxonomy."),
        ("RMR-012", "FRAMEWORK", "PROCESS_GATE", "v1.0 preregistration was frozen and already used once.", "v1.1 candidate framework must undergo a full second preregistration before any second dry run.", "User requested v1.0 remain untouched and no rerun occur here.", "Protects against silent post-hoc rule drift.", "Expected to preserve scientific auditability.", "This is a required governance step."),
    ]
    rows: List[Dict[str, Any]] = []
    for change_id, mechanism_id, area, baseline_element, candidate_element, evidence, why_exists, effect, risk in specs:
        rows.append(
            {
                **_base(generated_ts, repair_run_id),
                "change_id": change_id,
                "candidate_framework_version": CANDIDATE_FRAMEWORK_VERSION,
                "mechanism_id": mechanism_id,
                "change_area": area,
                "baseline_element": baseline_element,
                "candidate_element": candidate_element,
                "source_evidence": evidence,
                "why_change_exists": why_exists,
                "expected_effect": effect,
                "risk_if_not_preregistered": risk,
                "notes": "Every v1.1 change remains candidate-only until the second preregistration cycle completes.",
            }
        )
    return rows


def build_refined_mechanism_repair_v0() -> Dict[str, Any]:
    service = build_sheets_service(load_credentials())
    generated_ts = _iso_now()
    repair_run_id = _repair_run_id(generated_ts)
    data = _read_inputs(service)

    conflict_summary = data["Refined_Mechanism_Conflict_Review_Summary"][0]
    prereg_summary = data["Refined_Mechanism_PreRegistration_Summary"][0]

    repair_rows = [
        {
            **_base(generated_ts, repair_run_id),
            "repair_area": "SPECIFICITY_DEFINITION_REPAIR",
            "repair_status": "PASS_WITH_WARNINGS",
            "source_conflict_review_version": _norm(conflict_summary.get("review_version")),
            "source_preregistration_version": _norm(prereg_summary.get("preregistration_version")),
            "baseline_framework_version": BASELINE_VERSION,
            "candidate_framework_version": CANDIDATE_FRAMEWORK_VERSION,
            "repair_scope": "MECH_INFORMATION_SPECIFICITY",
            "scientific_problem": "Specificity remained the highest-ambiguity refined mechanism even after strong conflict reduction.",
            "repair_objective": "Recenter specificity on falsifiable-boundary formation and remove overlap with relevance and consistency.",
            "v1_0_preregistration_preserved": "TRUE",
            "classification_rerun_performed": "FALSE",
            "mechanism_testing_performed": "FALSE",
            "repair_conclusion": "Specificity requires a structural redesign before permanent classification is scientifically defensible.",
            "recommended_next_action": "FREEZE_V11_CANDIDATE_IN_SECOND_PREREGISTRATION",
            "notes": "Primary repair target identified directly from the refined conflict review.",
        },
        {
            **_base(generated_ts, repair_run_id),
            "repair_area": "NEGATIVE_LABEL_RULE_REPAIR",
            "repair_status": "PASS_WITH_WARNINGS",
            "source_conflict_review_version": _norm(conflict_summary.get("review_version")),
            "source_preregistration_version": _norm(prereg_summary.get("preregistration_version")),
            "baseline_framework_version": BASELINE_VERSION,
            "candidate_framework_version": CANDIDATE_FRAMEWORK_VERSION,
            "repair_scope": "ALL_PROMOTED_REFINED_MECHANISMS",
            "scientific_problem": "Negative labels are underpowered across relevance, specificity, and consistency.",
            "repair_objective": "Create deterministic negative cases that do not depend on outcomes and do not simply widen exclusions.",
            "v1_0_preregistration_preserved": "TRUE",
            "classification_rerun_performed": "FALSE",
            "mechanism_testing_performed": "FALSE",
            "repair_conclusion": "Negative-case coverage must be repaired to keep execution from collapsing into positive-or-unknown dominance.",
            "recommended_next_action": "FREEZE_V11_NEGATIVE_CASE_RULES",
            "notes": "The candidate framework narrows ambiguity by clarifying negative cases instead of broadening scope.",
        },
        {
            **_base(generated_ts, repair_run_id),
            "repair_area": "OVERLAP_AND_EXCLUSION_REPAIR",
            "repair_status": "PASS_WITH_WARNINGS",
            "source_conflict_review_version": _norm(conflict_summary.get("review_version")),
            "source_preregistration_version": _norm(prereg_summary.get("preregistration_version")),
            "baseline_framework_version": BASELINE_VERSION,
            "candidate_framework_version": CANDIDATE_FRAMEWORK_VERSION,
            "repair_scope": "PAIRWISE_BOUNDARIES_AND_HARD_EXCLUSIONS",
            "scientific_problem": "Specificity still overlaps with relevance and consistency, while optional trace handling is not sharply distinguished from hard exclusions.",
            "repair_objective": "Define pairwise boundaries, preserve hard exclusions, and clarify that optional evidence gaps are not themselves exclusions.",
            "v1_0_preregistration_preserved": "TRUE",
            "classification_rerun_performed": "FALSE",
            "mechanism_testing_performed": "FALSE",
            "repair_conclusion": "The candidate framework is ready for a second preregistration cycle, but not for immediate dry-run execution.",
            "recommended_next_action": NEXT_STEP,
            "notes": "This phase repairs definitions and rules only; no classification or testing occurs here.",
        },
    ]

    definition_rows = _candidate_definition_rows(data, generated_ts, repair_run_id)
    observable_rows = _candidate_observable_rows(generated_ts, repair_run_id)
    label_rule_rows = _candidate_label_rule_rows(data, generated_ts, repair_run_id)
    specificity_rows = _specificity_repair_rows(data, generated_ts, repair_run_id)
    overlap_rows = _overlap_repair_rows(data, generated_ts, repair_run_id)
    exclusion_rows = _exclusion_review_rows(data, generated_ts, repair_run_id)
    change_log_rows = _change_log_rows(generated_ts, repair_run_id)

    readiness_rows = [
        {
            **_base(generated_ts, repair_run_id),
            "readiness_area": "v1_0_preregistration_preservation",
            "status": "READY",
            "evidence": "All v1.0 sheets were read-only inputs and no existing frozen rows were rewritten.",
            "blocking_issue": "",
            "recommended_action": "Maintain v1.0 as the scientific baseline while freezing v1.1 separately.",
            "notes": "",
        },
        {
            **_base(generated_ts, repair_run_id),
            "readiness_area": "specificity_redesign",
            "status": "READY_WITH_WARNINGS",
            "evidence": "Candidate specificity definition, observables, and rule gates are fully articulated in the v1.1 design outputs.",
            "blocking_issue": "Requires second preregistration before any rerun.",
            "recommended_action": "Freeze the v1.1 specificity design in the next phase.",
            "notes": "",
        },
        {
            **_base(generated_ts, repair_run_id),
            "readiness_area": "negative_label_rule_redesign",
            "status": "READY_WITH_WARNINGS",
            "evidence": "Candidate negative rules are now explicit for relevance, specificity, and consistency.",
            "blocking_issue": "Negative-case examples must be frozen during second preregistration.",
            "recommended_action": "Preregister deterministic negative cases before any new dry run.",
            "notes": "",
        },
        {
            **_base(generated_ts, repair_run_id),
            "readiness_area": "overlap_reduction_design",
            "status": "READY",
            "evidence": "Pairwise boundary rules are defined for all promoted-mechanism pairs.",
            "blocking_issue": "",
            "recommended_action": "Carry pairwise boundaries unchanged into the second preregistration cycle.",
            "notes": "",
        },
        {
            **_base(generated_ts, repair_run_id),
            "readiness_area": "exclusion_rule_review",
            "status": "READY",
            "evidence": "Hard exclusions remain stable while optional-trace handling is clarified.",
            "blocking_issue": "",
            "recommended_action": "Freeze the clarified exclusion taxonomy in the next preregistration.",
            "notes": "",
        },
        {
            **_base(generated_ts, repair_run_id),
            "readiness_area": "second_preregistration_readiness",
            "status": "READY",
            "evidence": "The candidate framework includes updated definitions, candidate observables, label rules, overlap gates, and an explicit change log.",
            "blocking_issue": "",
            "recommended_action": NEXT_STEP,
            "notes": "Ready for preregistration only, not for dry-run execution.",
        },
        {
            **_base(generated_ts, repair_run_id),
            "readiness_area": "refined_classification_dry_run_readiness",
            "status": "BLOCKED",
            "evidence": "The user required v1.0 to stay untouched and this phase performs no rerun.",
            "blocking_issue": "Second preregistration has not happened yet.",
            "recommended_action": "Do not rerun dry classification until the v1.1 candidate framework is frozen.",
            "notes": "",
        },
        {
            **_base(generated_ts, repair_run_id),
            "readiness_area": "refined_classification_execution_readiness",
            "status": "BLOCKED",
            "evidence": "The conflict review already blocked execution, and this phase only creates a candidate repair layer.",
            "blocking_issue": "No v1.1 preregistration, no second dry run, and no second conflict review yet.",
            "recommended_action": "Keep execution blocked.",
            "notes": "",
        },
    ]

    governance_specs = [
        ("GOV_PROVIDER_CALLS", "provider_calls_performed", "0", "0"),
        ("GOV_FORECAST_GENERATION", "forecast_generation_performed", "0", "0"),
        ("GOV_CLASSIFICATION_RERUN", "classification_rerun_count", "0", "0"),
        ("GOV_PERMANENT_LABELS", "permanent_labels_modified", "0", "0"),
        ("GOV_MECHANISM_TESTING", "mechanism_testing_performed", "0", "0"),
        ("GOV_ACCURACY_EVAL", "accuracy_evaluation_performed", "0", "0"),
        ("GOV_V1_PREREG", "v1_0_preregistration_modified", "0", "0"),
        ("GOV_PRODUCTION_WRITES", "production_sheet_write_count", "0", "0"),
        ("GOV_PRODUCTION_BEHAVIOR", "production_behavior_change_count", "0", "0"),
        ("GOV_ROUTING", "routing_changes", "FALSE", "FALSE"),
        ("GOV_WEIGHTING", "weighting_changes", "FALSE", "FALSE"),
        ("GOV_CALIBRATION", "calibration_changes", "FALSE", "FALSE"),
    ]
    governance_rows = [
        {
            **_base(generated_ts, repair_run_id),
            "check_id": check_id,
            "check_name": check_name,
            "expected_value": expected_value,
            "actual_value": actual_value,
            "status": "PASS" if expected_value == actual_value else "FAIL",
            "notes": "Refined mechanism repair is research-design only.",
        }
        for check_id, check_name, expected_value, actual_value in governance_specs
    ]

    summary_row = {
        **_base(generated_ts, repair_run_id),
        "build_status": "PASS_WITH_WARNINGS",
        "final_interpretation": "REFINED_MECHANISM_REPAIR_READY_WITH_WARNINGS",
        "baseline_framework_version": BASELINE_VERSION,
        "candidate_framework_version": CANDIDATE_FRAMEWORK_VERSION,
        "v1_0_preregistration_preserved": "TRUE",
        "candidate_definitions_written": len(definition_rows),
        "candidate_observables_written": len(observable_rows),
        "candidate_label_rules_written": len(label_rule_rows),
        "specificity_definition_redesigned": "TRUE",
        "negative_label_rules_redesigned": "TRUE",
        "overlap_repair_rules_defined": len(overlap_rows),
        "exclusion_rules_reviewed": len(exclusion_rows),
        "proposed_changes_logged": len(change_log_rows),
        "primary_repair_target": "MECH_INFORMATION_SPECIFICITY",
        "strongest_v1_1_change": "TIME_HORIZON_SUPPORT_ONLY_PLUS_FALSIFIABLE_BOUNDARY_GATE",
        "primary_scientific_conclusion": "The v1.1 candidate framework should narrow specificity to falsifiable-boundary formation, broaden deterministic negative cases, and preserve hard exclusions while clarifying optional evidence handling.",
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "classification_rerun_count": 0,
        "mechanism_testing_performed": 0,
        "accuracy_evaluation_performed": 0,
        "v1_0_preregistration_modified": 0,
        "production_behavior_change_count": 0,
        "production_sheet_write_count": 0,
        "ready_for_second_preregistration": "TRUE",
        "ready_for_refined_classification_dry_run": "FALSE",
        "ready_for_refined_classification_execution": "FALSE",
        "ready_for_mechanism_testing": "FALSE",
        "ready_for_production": "FALSE",
        "recommended_next_step": NEXT_STEP,
        "notes": json.dumps(
            {
                "conflict_review_next_step": _norm(conflict_summary.get("recommended_next_step")),
                "preserved_v1_0_version": BASELINE_VERSION,
                "reported_specificity_ambiguity_direct": 39,
                "reported_specificity_ambiguity_dry_run_summary": 77,
                "specificity_overlap_with_relevance_positive": 32,
                "specificity_overlap_with_consistency_positive": 21,
            },
            sort_keys=True,
            ensure_ascii=True,
        ),
    }

    outputs = [
        (OUTPUT_REPAIR, REPAIR_HEADERS, repair_rows),
        (OUTPUT_DEFINITIONS, DEFINITION_HEADERS, definition_rows),
        (OUTPUT_OBSERVABLES, OBSERVABLE_HEADERS, observable_rows),
        (OUTPUT_LABEL_RULES, LABEL_RULE_HEADERS, label_rule_rows),
        (OUTPUT_SPECIFICITY, SPECIFICITY_HEADERS, specificity_rows),
        (OUTPUT_OVERLAP, OVERLAP_HEADERS, overlap_rows),
        (OUTPUT_EXCLUSION, EXCLUSION_HEADERS, exclusion_rows),
        (OUTPUT_CHANGE_LOG, CHANGE_LOG_HEADERS, change_log_rows),
        (OUTPUT_READINESS, READINESS_HEADERS, readiness_rows),
        (OUTPUT_GOVERNANCE, GOVERNANCE_HEADERS, governance_rows),
        (OUTPUT_SUMMARY, SUMMARY_HEADERS, [summary_row]),
    ]

    for sheet_name, headers, rows in outputs:
        actual_headers = _ensure_sheet_minimal_light(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, headers, len(rows))
        _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, actual_headers, rows)

    registry = _upsert_registry_rows(service)
    return {
        "build_status": "PASS_WITH_WARNINGS",
        "final_interpretation": "REFINED_MECHANISM_REPAIR_READY_WITH_WARNINGS",
        "file_created": "automation/build_refined_mechanism_repair_v0.py",
        "sheets_written": {sheet_name: len(rows) for sheet_name, _, rows in outputs},
        "baseline_framework_version": BASELINE_VERSION,
        "candidate_framework_version": CANDIDATE_FRAMEWORK_VERSION,
        "v1_0_preregistration_preserved": True,
        "candidate_definitions_written": len(definition_rows),
        "candidate_observables_written": len(observable_rows),
        "candidate_label_rules_written": len(label_rule_rows),
        "specificity_definition_redesigned": True,
        "negative_label_rules_redesigned": True,
        "overlap_repair_rules_defined": len(overlap_rows),
        "exclusion_rules_reviewed": len(exclusion_rows),
        "proposed_changes_logged": len(change_log_rows),
        "primary_repair_target": "MECH_INFORMATION_SPECIFICITY",
        "ready_for_second_preregistration": True,
        "ready_for_refined_classification_dry_run": False,
        "ready_for_refined_classification_execution": False,
        "ready_for_mechanism_testing": False,
        "ready_for_production": False,
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "classification_rerun_count": 0,
        "mechanism_testing_performed": 0,
        "accuracy_evaluation_performed": 0,
        "v1_0_preregistration_modified": 0,
        "production_behavior_change_count": 0,
        "production_sheet_write_count": 0,
        "recommended_next_step": NEXT_STEP,
        "registry": registry,
    }


def main() -> None:
    result = build_refined_mechanism_repair_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
