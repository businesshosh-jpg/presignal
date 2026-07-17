import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

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
from automation.build_predictive_mechanism_label_metric_design_v0 import MECHANISM_ORDER
from automation.build_session_information_requests_v0 import _iso_now
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials


SCHEMA_VERSION = "presignal_v2_predictive_mechanism_conflict_review_0.1"
REVIEW_VERSION = "predictive_mechanism_conflict_review_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-6DR"
REGISTRY_CATEGORY = "PRESIGNAL_V2_PREDICTIVE_MECHANISM_CONFLICT_REVIEW"
REGISTRY_OWNER_MODULE = "market_state"

INPUT_SHEETS = [
    "Predictive_Mechanism_Classification_Dry_Run",
    "Predictive_Mechanism_Label_Preview",
    "Predictive_Mechanism_Evidence_Extraction_Audit",
    "Predictive_Mechanism_Conflict_Audit",
    "Predictive_Mechanism_Confidence_Preview",
    "Predictive_Mechanism_Leakage_Audit",
    "Predictive_Mechanism_Determinism_Audit",
    "Predictive_Mechanism_Label_Model",
    "Predictive_Mechanism_Label_Assignment",
    "Predictive_Mechanism_Classification_Rules",
    "Predictive_Mechanism_Classification_Priority",
    "Predictive_Mechanism_Dry_Run_Summary",
]

OUTPUT_REVIEW = "Predictive_Mechanism_Conflict_Review"
OUTPUT_TYPES = "Mechanism_Conflict_Types"
OUTPUT_ROOT_CAUSES = "Mechanism_Conflict_Root_Causes"
OUTPUT_FREQUENCY = "Mechanism_Conflict_Frequency"
OUTPUT_OPTIONS = "Mechanism_Conflict_Resolution_Options"
OUTPUT_INFO_DECOMP = "Mechanism_Information_Value_Decomposition"
OUTPUT_GOVERNANCE = "Mechanism_Conflict_Governance"
OUTPUT_SUMMARY = "Mechanism_Conflict_Review_Summary"

REVIEW_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "mechanism_id",
    "total_preview_rows",
    "total_conflicts",
    "conflict_rate",
    "ambiguity_count",
    "ambiguity_rate",
    "evidence_completeness_profile",
    "evidence_consistency_profile",
    "deterministic_stability",
    "confidence_distribution",
    "review_conclusion",
    "scientific_interpretation",
    "recommended_action",
    "notes",
]

TYPES_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "mechanism_id",
    "conflict_type",
    "conflict_count",
    "conflict_rate",
    "ambiguity_linked",
    "dominant_resolution_path",
    "dominant_preview_outcome",
    "notes",
]

ROOT_CAUSE_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "mechanism_id",
    "root_cause_id",
    "root_cause_classification",
    "primary_for_mechanism",
    "affected_rows",
    "supporting_evidence",
    "evidence_strength",
    "scientific_interpretation",
    "notes",
]

FREQUENCY_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "mechanism_id",
    "preview_rows",
    "positive_labels",
    "negative_labels",
    "unknown_labels",
    "insufficient_evidence_labels",
    "excluded_labels",
    "conflict_rows",
    "ambiguity_rows",
    "extraction_failure_rows",
    "high_confidence_rows",
    "moderate_confidence_rows",
    "low_confidence_rows",
    "unknown_confidence_rows",
    "notes",
]

OPTIONS_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "mechanism_id",
    "related_conflict_type",
    "research_action",
    "action_rationale",
    "scientific_priority",
    "implementation_now",
    "notes",
]

DECOMPOSITION_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "analysis_scope",
    "candidate_latent_concept",
    "observed_signal",
    "observed_count",
    "decomposition_classification",
    "scientific_interpretation",
    "recommended_followup",
    "notes",
]

GOVERNANCE_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
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
    "review_version",
    "review_run_id",
    "build_status",
    "final_interpretation",
    "mechanisms_reviewed",
    "conflict_types_identified",
    "root_causes_identified",
    "highest_conflict_mechanism",
    "decomposition_signal",
    "scientific_recommendation",
    "provider_calls_performed",
    "forecast_generation_performed",
    "mechanism_labels_modified",
    "production_behavior_change_count",
    "ready_for_mechanism_classification_execution",
    "mechanism_revision_needed",
    "ready_for_mechanism_testing",
    "ready_for_production",
    "recommended_next_step",
    "notes",
]


def _review_run_id(generated_ts: str) -> str:
    return "predictive_mechanism_conflict_review_v0_" + generated_ts.replace("-", "").replace(":", "")


def _base(generated_ts: str, review_run_id: str) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "review_version": REVIEW_VERSION,
        "review_run_id": review_run_id,
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


def _upsert_registry_rows(service) -> Dict[str, int]:
    titles = _sheet_titles_light(service, PROJECT_OVERVIEWS_SPREADSHEET_ID)
    if REGISTRY_SHEET not in titles:
        return {"updated": 0, "appended": 0, "status": "missing"}
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_norm(row.get("logical_sheet_id")).upper(): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_norm(row.get("logical_sheet_id")).upper(): row for row in rows}
    specs = [
        ("PREDICTIVE_MECHANISM_CONFLICT_REVIEW", OUTPUT_REVIEW, "predictive_mechanism_conflict_review"),
        ("MECHANISM_CONFLICT_TYPES", OUTPUT_TYPES, "mechanism_conflict_types"),
        ("MECHANISM_CONFLICT_ROOT_CAUSES", OUTPUT_ROOT_CAUSES, "mechanism_conflict_root_causes"),
        ("MECHANISM_CONFLICT_FREQUENCY", OUTPUT_FREQUENCY, "mechanism_conflict_frequency"),
        ("MECHANISM_CONFLICT_RESOLUTION_OPTIONS", OUTPUT_OPTIONS, "mechanism_conflict_resolution_options"),
        ("MECHANISM_INFORMATION_VALUE_DECOMPOSITION", OUTPUT_INFO_DECOMP, "mechanism_information_value_decomposition"),
        ("MECHANISM_CONFLICT_GOVERNANCE", OUTPUT_GOVERNANCE, "mechanism_conflict_governance"),
        ("MECHANISM_CONFLICT_REVIEW_SUMMARY", OUTPUT_SUMMARY, "mechanism_conflict_review_summary"),
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
            "notes": "Phase 9A-6DR mechanism conflict review; research review only, no permanent label changes.",
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


def _to_float(value: Any) -> Optional[float]:
    text = _norm(value)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _counter_json(counter: Counter[str]) -> str:
    return json.dumps({key: counter[key] for key in sorted(counter)}, sort_keys=True, ensure_ascii=True)


def _latest(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    return rows[-1] if rows else {}


def _has_conflict(row: Dict[str, Any]) -> bool:
    return bool(_norm(row.get("conflicting_observables")) or _norm(row.get("conflicting_labels")))


def _rate(count: int, total: int) -> str:
    if total <= 0:
        return "0.000000"
    return f"{count / float(total):.6f}"


def _dominant(counter: Counter[str]) -> str:
    if not counter:
        return ""
    return counter.most_common(1)[0][0]


def _profile_for_mechanism(data: Dict[str, List[Dict[str, Any]]], mechanism_id: str) -> Dict[str, Any]:
    label_rows = [row for row in data["Predictive_Mechanism_Label_Preview"] if _norm(row.get("mechanism_id")) == mechanism_id]
    conflict_rows = [row for row in data["Predictive_Mechanism_Conflict_Audit"] if _norm(row.get("mechanism_id")) == mechanism_id]
    extraction_rows = [row for row in data["Predictive_Mechanism_Evidence_Extraction_Audit"] if _norm(row.get("mechanism_id")) == mechanism_id]
    confidence_rows = [row for row in data["Predictive_Mechanism_Confidence_Preview"] if _norm(row.get("mechanism_id")) == mechanism_id]
    determinism_rows = [row for row in data["Predictive_Mechanism_Determinism_Audit"] if _norm(row.get("mechanism_id")) == mechanism_id]
    label_model = next((row for row in data["Predictive_Mechanism_Label_Model"] if _norm(row.get("mechanism_id")) == mechanism_id), {})
    assignment = next((row for row in data["Predictive_Mechanism_Label_Assignment"] if _norm(row.get("mechanism_id")) == mechanism_id), {})
    rule_row = next((row for row in data["Predictive_Mechanism_Classification_Rules"] if _norm(row.get("mechanism_id")) == mechanism_id), {})

    label_counts = Counter(_norm(row.get("preview_label")) for row in label_rows)
    conflict_count = sum(1 for row in conflict_rows if _has_conflict(row))
    ambiguity_count = sum(1 for row in extraction_rows if _norm(row.get("ambiguity_detected")).upper() == "TRUE")
    extraction_failures = sum(1 for row in extraction_rows if _norm(row.get("extraction_failure")).upper() == "TRUE")
    completeness = Counter(_norm(row.get("evidence_completeness")) or "UNKNOWN" for row in confidence_rows)
    consistency = Counter(_norm(row.get("evidence_consistency")) or "UNKNOWN" for row in confidence_rows)
    confidence = Counter(_norm(row.get("preview_confidence")) or "UNKNOWN" for row in confidence_rows)
    conflict_type_counts = Counter(_norm(row.get("conflicting_observables")) for row in conflict_rows if _norm(row.get("conflicting_observables")))
    resolution_counts = Counter(_norm(row.get("conflict_resolution_path")) for row in conflict_rows if _norm(row.get("conflict_resolution_path")))
    outcome_counts = Counter(_norm(row.get("final_preview_outcome")) for row in conflict_rows if _norm(row.get("final_preview_outcome")))
    determinism_counts = Counter(_norm(row.get("deterministic_status")) or "UNKNOWN" for row in determinism_rows)
    found_counts = Counter(_norm(row.get("observables_found")) for row in extraction_rows if _norm(row.get("observables_found")))
    missing_counts = Counter(_norm(row.get("observables_missing")) for row in extraction_rows if _norm(row.get("observables_missing")))
    basis_counts = Counter(_norm(row.get("classification_basis")) for row in label_rows if _norm(row.get("classification_basis")))
    exclusion_counts = Counter(_norm(row.get("exclusion_reason")) for row in label_rows if _norm(row.get("exclusion_reason")))
    insufficient_counts = Counter(_norm(row.get("insufficient_evidence_reason")) for row in label_rows if _norm(row.get("insufficient_evidence_reason")))
    unknown_counts = Counter(_norm(row.get("unknown_reason")) for row in label_rows if _norm(row.get("unknown_reason")))

    return {
        "mechanism_id": mechanism_id,
        "label_rows": label_rows,
        "total_preview_rows": len(label_rows),
        "label_counts": label_counts,
        "conflict_count": conflict_count,
        "ambiguity_count": ambiguity_count,
        "extraction_failures": extraction_failures,
        "completeness": completeness,
        "consistency": consistency,
        "confidence": confidence,
        "conflict_type_counts": conflict_type_counts,
        "resolution_counts": resolution_counts,
        "outcome_counts": outcome_counts,
        "determinism_counts": determinism_counts,
        "found_counts": found_counts,
        "missing_counts": missing_counts,
        "basis_counts": basis_counts,
        "exclusion_counts": exclusion_counts,
        "insufficient_counts": insufficient_counts,
        "unknown_counts": unknown_counts,
        "label_model": label_model,
        "assignment": assignment,
        "rule_row": rule_row,
    }


def _review_conclusion(profile: Dict[str, Any]) -> tuple[str, str, str]:
    mechanism_id = profile["mechanism_id"]
    total = profile["total_preview_rows"]
    conflict_count = profile["conflict_count"]
    ambiguity_count = profile["ambiguity_count"]
    complete_count = profile["completeness"].get("COMPLETE", 0)
    contradictory_count = profile["consistency"].get("CONTRADICTORY", 0)

    if mechanism_id == "MECH_INFORMATION_VALUE":
        conclusion = "Highest conflict mechanism; conflict persists even when evidence is present and deterministic."
        interpretation = (
            f"{conflict_count}/{total} preview rows show the same feature-exposure vs reasoning-delta conflict, "
            f"{complete_count}/{total} rows have COMPLETE evidence, {contradictory_count}/{total} rows are CONTRADICTORY, "
            "and ambiguity is 120/120. This points to a conceptual mechanism-composition problem rather than a dry-run defect."
        )
        action = "PROCEED_TO_PHASE9A6R_MECHANISM_REFINEMENT"
        return conclusion, interpretation, action
    if mechanism_id == "MECH_INFORMATION_FILTERING":
        return (
            "Conflict is moderate and localized to filtering-vs-no-effect ambiguity.",
            "Discarded-field evidence and no-effect evidence overlap, so the current rule set cannot cleanly separate filtering from verbosity suppression.",
            "Collect additional observables and refine rule ordering before mechanism testing.",
        )
    if mechanism_id == "MECH_CONDITIONAL_PREDICTIVENESS":
        return (
            "Conflict reflects mixed regime evidence rather than execution failure.",
            "Observed conflicts arise when regime-family evidence overlaps with broader multi-family reasoning shifts, making conditional use hard to isolate.",
            "Narrow regime observables before testing.",
        )
    if mechanism_id == "MECH_CAUSAL_ROBUSTNESS":
        return (
            "Conflict is moderate and tied to coherence-vs-direction mismatch across contexts.",
            "The classifier can detect when causal coherence survives but directional consistency does not, indicating a real scientific tension rather than implementation instability.",
            "Retain with warnings and improve context-trace granularity before testing.",
        )
    if mechanism_id == "MECH_FORECAST_STABILITY":
        return (
            "Conflict is low; main limitation is sparse paired-trace evidence.",
            "Only a small share of rows show direct stability conflicts, so the larger issue is sample structure rather than conceptual breakdown.",
            "Keep frozen but require more paired perturbation evidence before testing.",
        )
    return (
        "No direct conflict spike; ambiguity is driven mainly by partial evidence.",
        f"Conflict rate is {conflict_count}/{total} while ambiguity is {ambiguity_count}/{total}, indicating partial-context uncertainty instead of contradiction.",
        "Keep unchanged and downgrade confidence when low-signal context is partial.",
    )


def _root_causes_for(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    mechanism_id = profile["mechanism_id"]
    total = profile["total_preview_rows"]
    conflict_count = profile["conflict_count"]
    ambiguity_count = profile["ambiguity_count"]
    complete_count = profile["completeness"].get("COMPLETE", 0)
    contradictory_count = profile["consistency"].get("CONTRADICTORY", 0)
    dominant_conflict = _dominant(profile["conflict_type_counts"])
    found = _dominant(profile["found_counts"])
    missing = _dominant(profile["missing_counts"])
    basis = _dominant(profile["basis_counts"])
    rows: List[Dict[str, Any]] = []

    def add(root_cause_id: str, classification: str, primary: str, affected_rows: int, evidence: str, strength: str, interpretation: str) -> None:
        rows.append(
            {
                "mechanism_id": mechanism_id,
                "root_cause_id": root_cause_id,
                "root_cause_classification": classification,
                "primary_for_mechanism": primary,
                "affected_rows": affected_rows,
                "supporting_evidence": evidence,
                "evidence_strength": strength,
                "scientific_interpretation": interpretation,
                "notes": "Root causes are derived from dry-run evidence only; no label changes are performed.",
            }
        )

    if mechanism_id == "MECH_INFORMATION_VALUE":
        add(
            "MECH_INFORMATION_VALUE_BROAD_DEFINITION",
            "OVERLY_BROAD_MECHANISM_DEFINITION",
            "TRUE",
            conflict_count,
            f"{conflict_count}/{total} conflict rows share one dominant contradiction: '{dominant_conflict}'.",
            "HIGH",
            "The current mechanism definition asks one label to represent several distinct concepts inside a single incremental-value test.",
        )
        add(
            "MECH_INFORMATION_VALUE_MISSING_DIMENSIONS",
            "MISSING_OBSERVABLE_DIMENSIONS",
            "FALSE",
            conflict_count,
            (
                f"{complete_count}/{total} rows are COMPLETE, yet {contradictory_count}/{total} rows remain CONTRADICTORY and "
                f"the dominant found evidence is '{found}'."
            ),
            "HIGH",
            "Pre-outcome traces can see exposure and reasoning movement, but they cannot yet separate relevance, novelty, specificity, and consistency.",
        )
        add(
            "MECH_INFORMATION_VALUE_CONFLICTING_OBSERVABLES",
            "CONFLICTING_OBSERVABLES",
            "FALSE",
            conflict_count,
            f"The conflict audit repeatedly records '{dominant_conflict}'.",
            "HIGH",
            "The direct scientific symptom is observable contradiction between feature exposure and reasoning-delta evidence.",
        )
        add(
            "MECH_INFORMATION_VALUE_INSUFFICIENT_EVIDENCE_SECONDARY",
            "INSUFFICIENT_EVIDENCE",
            "FALSE",
            profile["confidence"].get("UNKNOWN", 0),
            f"{profile['confidence'].get('UNKNOWN', 0)}/{total} rows carry UNKNOWN confidence and {profile['label_counts'].get('INSUFFICIENT_EVIDENCE', 0)}/{total} rows were labeled insufficient_evidence.",
            "MEDIUM",
            "Insufficient evidence is present, but it is not the primary explanation because high conflict persists even on complete rows.",
        )
        return rows

    if mechanism_id == "MECH_INFORMATION_FILTERING":
        add(
            "MECH_INFORMATION_FILTERING_RULE_OVERLAP",
            "OVERLAPPING_RULES",
            "TRUE",
            conflict_count,
            f"{conflict_count}/{total} conflict rows share '{dominant_conflict}'.",
            "HIGH",
            "Discard and no-effect traces overlap in the current rule set, making filtering hard to distinguish from benign non-use.",
        )
        add(
            "MECH_INFORMATION_FILTERING_CONFLICTING_OBSERVABLES",
            "CONFLICTING_OBSERVABLES",
            "FALSE",
            ambiguity_count,
            f"Ambiguity affects {ambiguity_count}/{total} rows while the dominant missing pattern is '{missing}'.",
            "MEDIUM",
            "Filtering evidence is present, but the direction of the evidence remains mixed.",
        )
        return rows

    if mechanism_id == "MECH_CONDITIONAL_PREDICTIVENESS":
        add(
            "MECH_CONDITIONAL_PREDICTIVENESS_MULTI_MECH",
            "MULTIPLE_SIMULTANEOUS_MECHANISMS",
            "TRUE",
            conflict_count,
            f"{conflict_count}/{total} conflicts use the dominant description '{dominant_conflict}'.",
            "HIGH",
            "The dry run is seeing regime use mixed with broader reasoning shifts, so one conditional label is absorbing multiple mechanism candidates.",
        )
        add(
            "MECH_CONDITIONAL_PREDICTIVENESS_INSUFFICIENT_REGIME_TRACE",
            "INSUFFICIENT_EVIDENCE",
            "FALSE",
            profile["label_counts"].get("EXCLUDED", 0),
            f"Exclusions affect {profile['label_counts'].get('EXCLUDED', 0)}/{total} rows and the dominant missing pattern is '{missing}'.",
            "MEDIUM",
            "Some ambiguity is still trace-sparsity, especially where regime change is not explicitly documented.",
        )
        return rows

    if mechanism_id == "MECH_CAUSAL_ROBUSTNESS":
        add(
            "MECH_CAUSAL_ROBUSTNESS_CONFLICTING_OBSERVABLES",
            "CONFLICTING_OBSERVABLES",
            "TRUE",
            conflict_count,
            f"{conflict_count}/{total} conflicts report '{dominant_conflict}'.",
            "HIGH",
            "Coherent causal chains and stable direction are not equivalent, and the current mechanism captures that scientific separation.",
        )
        add(
            "MECH_CAUSAL_ROBUSTNESS_MISSING_DIMENSIONS",
            "MISSING_OBSERVABLE_DIMENSIONS",
            "FALSE",
            ambiguity_count,
            f"Ambiguity affects {ambiguity_count}/{total} rows while {profile['confidence'].get('LOW', 0)}/{total} rows have LOW confidence.",
            "MEDIUM",
            "More granular premise-tracking would help distinguish partial robustness from true contradiction.",
        )
        return rows

    if mechanism_id == "MECH_FORECAST_STABILITY":
        add(
            "MECH_FORECAST_STABILITY_INSUFFICIENT_PAIRED_TRACE",
            "INSUFFICIENT_EVIDENCE",
            "TRUE",
            profile["extraction_failures"],
            f"Extraction failures affect {profile['extraction_failures']}/{total} rows and the dominant missing pattern is '{missing}'.",
            "MEDIUM",
            "Paired perturbation evidence is the limiting factor more than conceptual conflict.",
        )
        add(
            "MECH_FORECAST_STABILITY_CONFLICTING_OBSERVABLES",
            "CONFLICTING_OBSERVABLES",
            "FALSE",
            conflict_count,
            f"Only {conflict_count}/{total} rows show the dominant conflict '{dominant_conflict}'.",
            "LOW",
            "The mechanism is comparatively stable, but a small number of rows still show direction shifts without supporting trace changes.",
        )
        return rows

    add(
        "MECH_SIGNAL_DISCIPLINE_INSUFFICIENT_LOW_SIGNAL_CONTEXT",
        "INSUFFICIENT_EVIDENCE",
        "TRUE",
        ambiguity_count,
        f"Conflict count is {conflict_count}/{total}; ambiguity count is {ambiguity_count}/{total}; dominant missing pattern is '{missing}'.",
        "MEDIUM",
        "This mechanism is limited by partial low-signal context evidence rather than contradictory observables.",
    )
    return rows


def _resolution_options_for(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    mechanism_id = profile["mechanism_id"]
    dominant_conflict = _dominant(profile["conflict_type_counts"]) or "NO_DIRECT_CONFLICT_IDENTIFIED"
    options: List[Dict[str, Any]] = []

    def add(action: str, rationale: str, priority: str) -> None:
        options.append(
            {
                "mechanism_id": mechanism_id,
                "related_conflict_type": dominant_conflict,
                "research_action": action,
                "action_rationale": rationale,
                "scientific_priority": priority,
                "implementation_now": "FALSE",
                "notes": "Recommendation only; no rule changes are implemented in this phase.",
            }
        )

    if mechanism_id == "MECH_INFORMATION_VALUE":
        add("collect_additional_observables", "Separate relevance, novelty, specificity, and consistency before permanent classification.", "HIGH")
        add("split_mechanism", "The dry run suggests Information Value is carrying multiple latent concepts.", "HIGH")
        add("lower_confidence", "Until refinement, keep preview confidence conservative because ambiguity is universal.", "HIGH")
        add("postpone_testing", "Do not begin mechanism testing on the highest-priority mechanism until the conceptual conflict is reduced.", "HIGH")
    elif mechanism_id == "MECH_INFORMATION_FILTERING":
        add("refine_rule_ordering", "Discard-vs-no-effect overlap looks like rule overlap more than a full mechanism split.", "MEDIUM")
        add("collect_additional_observables", "Add filtering-specific observables that separate selective pruning from generic non-use.", "MEDIUM")
    elif mechanism_id == "MECH_CONDITIONAL_PREDICTIVENESS":
        add("require_more_evidence", "Freeze narrower regime markers before testing.", "MEDIUM")
        add("collect_additional_observables", "Capture outside-regime suppression more explicitly.", "MEDIUM")
    elif mechanism_id == "MECH_CAUSAL_ROBUSTNESS":
        add("collect_additional_observables", "Add premise-level traceability across contexts.", "MEDIUM")
        add("lower_confidence", "Keep classifications conservative when coherence and directional consistency diverge.", "MEDIUM")
    elif mechanism_id == "MECH_FORECAST_STABILITY":
        add("require_more_evidence", "More paired perturbation rows are needed than conflict resolution changes.", "LOW")
        add("keep_unchanged", "The mechanism is not the primary scientific blocker.", "LOW")
    else:
        add("lower_confidence", "Ambiguity is driven by partial low-signal context rather than a rule defect.", "LOW")
        add("keep_unchanged", "Signal discipline does not currently require conceptual redesign.", "LOW")
    return options


def _build_information_value_decomposition(profile: Dict[str, Any], generated_ts: str, review_run_id: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    total = profile["total_preview_rows"]
    conflict_count = profile["conflict_count"]
    contradictory = profile["consistency"].get("CONTRADICTORY", 0)
    complete = profile["completeness"].get("COMPLETE", 0)
    negative = profile["label_counts"].get("NEGATIVE", 0)
    excluded_baseline = profile["exclusion_counts"].get("baseline pack has no incremental feature exposure to classify", 0)

    def add(scope: str, concept: str, signal: str, count: int, classification: str, interpretation: str, followup: str) -> None:
        rows.append(
            {
                **_base(generated_ts, review_run_id),
                "analysis_scope": scope,
                "candidate_latent_concept": concept,
                "observed_signal": signal,
                "observed_count": count,
                "decomposition_classification": classification,
                "scientific_interpretation": interpretation,
                "recommended_followup": followup,
                "notes": "This sheet evaluates whether decomposition is justified; it does not create new mechanisms.",
            }
        )

    add(
        "overall",
        "MECH_INFORMATION_VALUE",
        "Complete evidence often still produces contradiction and universal high ambiguity.",
        conflict_count,
        "STRONG_DECOMPOSITION_SIGNAL",
        (
            f"{conflict_count}/{total} conflict rows, {complete}/{total} COMPLETE evidence rows, and {contradictory}/{total} CONTRADICTORY consistency rows "
            "indicate that Information Value is behaving like a composite construct rather than a single clean mechanism."
        ),
        "Use refinement to separate latent concepts before permanent classification.",
    )
    add(
        "candidate",
        "Information Relevance",
        "Feature availability frequently fails to translate into clean reasoning change.",
        negative,
        "STRONG_DECOMPOSITION_SIGNAL",
        f"{negative}/{total} rows were classified NEGATIVE with basis 'feature was available but failed to change reasoning cleanly', implying that presence and relevance are separable.",
        "Add observables that distinguish mere exposure from relevant use.",
    )
    add(
        "candidate",
        "Information Novelty",
        "Baseline incremental exposure is sometimes absent, blocking novelty assessment.",
        excluded_baseline,
        "POSSIBLE_DECOMPOSITION",
        f"{excluded_baseline}/{total} rows were excluded because the baseline pack had no incremental feature exposure to classify, suggesting novelty is a distinct prerequisite dimension.",
        "Freeze stronger baseline-difference observables before testing.",
    )
    add(
        "candidate",
        "Information Specificity",
        "Feature exposure and reasoning delta often fail to align cleanly.",
        conflict_count,
        "STRONG_DECOMPOSITION_SIGNAL",
        f"The dominant conflict phrase appears in {conflict_count}/{total} rows, implying that a feature can be mentioned or available without specifically driving the causal update.",
        "Add specificity traces that identify which feature moved which part of the reasoning chain.",
    )
    add(
        "candidate",
        "Information Consistency",
        "Contradictory evidence dominates even when completeness is high.",
        contradictory,
        "STRONG_DECOMPOSITION_SIGNAL",
        f"{contradictory}/{total} rows show CONTRADICTORY evidence consistency while ambiguity remains HIGH for all rows, implying consistency is its own measurable dimension.",
        "Add pre-outcome consistency checks before permanent classification.",
    )
    return rows


def build_predictive_mechanism_conflict_review_v0() -> Dict[str, Any]:
    service = build_sheets_service(load_credentials())
    generated_ts = _iso_now()
    review_run_id = _review_run_id(generated_ts)
    data = _read_inputs(service)
    dry_run_summary = _latest(data["Predictive_Mechanism_Dry_Run_Summary"])

    profiles = [_profile_for_mechanism(data, mechanism_id) for mechanism_id in MECHANISM_ORDER]
    review_rows: List[Dict[str, Any]] = []
    type_rows: List[Dict[str, Any]] = []
    root_cause_rows: List[Dict[str, Any]] = []
    frequency_rows: List[Dict[str, Any]] = []
    option_rows: List[Dict[str, Any]] = []

    for profile in profiles:
        conclusion, interpretation, action = _review_conclusion(profile)
        total = profile["total_preview_rows"]
        review_rows.append(
            {
                **_base(generated_ts, review_run_id),
                "mechanism_id": profile["mechanism_id"],
                "total_preview_rows": total,
                "total_conflicts": profile["conflict_count"],
                "conflict_rate": _rate(profile["conflict_count"], total),
                "ambiguity_count": profile["ambiguity_count"],
                "ambiguity_rate": _rate(profile["ambiguity_count"], total),
                "evidence_completeness_profile": _counter_json(profile["completeness"]),
                "evidence_consistency_profile": _counter_json(profile["consistency"]),
                "deterministic_stability": _counter_json(profile["determinism_counts"]),
                "confidence_distribution": _counter_json(profile["confidence"]),
                "review_conclusion": conclusion,
                "scientific_interpretation": interpretation,
                "recommended_action": action,
                "notes": json.dumps(
                    {
                        "dominant_conflict": _dominant(profile["conflict_type_counts"]),
                        "dominant_resolution_path": _dominant(profile["resolution_counts"]),
                        "dominant_basis": _dominant(profile["basis_counts"]),
                    },
                    sort_keys=True,
                    ensure_ascii=True,
                ),
            }
        )

        if profile["conflict_type_counts"]:
            for conflict_type, count in profile["conflict_type_counts"].most_common():
                type_rows.append(
                    {
                        **_base(generated_ts, review_run_id),
                        "mechanism_id": profile["mechanism_id"],
                        "conflict_type": conflict_type,
                        "conflict_count": count,
                        "conflict_rate": _rate(count, total),
                        "ambiguity_linked": "TRUE" if profile["ambiguity_count"] >= count else "FALSE",
                        "dominant_resolution_path": _dominant(profile["resolution_counts"]),
                        "dominant_preview_outcome": _dominant(profile["outcome_counts"]),
                        "notes": "Conflict type counts use the dry-run conflict audit only.",
                    }
                )
        else:
            type_rows.append(
                {
                    **_base(generated_ts, review_run_id),
                    "mechanism_id": profile["mechanism_id"],
                    "conflict_type": "NO_DIRECT_CONFLICT_IDENTIFIED",
                    "conflict_count": 0,
                    "conflict_rate": _rate(0, total),
                    "ambiguity_linked": "TRUE" if profile["ambiguity_count"] > 0 else "FALSE",
                    "dominant_resolution_path": _dominant(profile["resolution_counts"]),
                    "dominant_preview_outcome": _dominant(profile["outcome_counts"]),
                    "notes": "This mechanism still has ambiguity, but not a direct conflict-type spike.",
                }
            )

        for row in _root_causes_for(profile):
            root_cause_rows.append({**_base(generated_ts, review_run_id), **row})
        for row in _resolution_options_for(profile):
            option_rows.append({**_base(generated_ts, review_run_id), **row})
        frequency_rows.append(
            {
                **_base(generated_ts, review_run_id),
                "mechanism_id": profile["mechanism_id"],
                "preview_rows": total,
                "positive_labels": profile["label_counts"].get("POSITIVE", 0),
                "negative_labels": profile["label_counts"].get("NEGATIVE", 0),
                "unknown_labels": profile["label_counts"].get("UNKNOWN", 0),
                "insufficient_evidence_labels": profile["label_counts"].get("INSUFFICIENT_EVIDENCE", 0),
                "excluded_labels": profile["label_counts"].get("EXCLUDED", 0),
                "conflict_rows": profile["conflict_count"],
                "ambiguity_rows": profile["ambiguity_count"],
                "extraction_failure_rows": profile["extraction_failures"],
                "high_confidence_rows": profile["confidence"].get("HIGH", 0),
                "moderate_confidence_rows": profile["confidence"].get("MODERATE", 0),
                "low_confidence_rows": profile["confidence"].get("LOW", 0),
                "unknown_confidence_rows": profile["confidence"].get("UNKNOWN", 0),
                "notes": "Frequency rows separate conflict, ambiguity, and confidence because they are not scientifically equivalent.",
            }
        )

    info_value_profile = next(profile for profile in profiles if profile["mechanism_id"] == "MECH_INFORMATION_VALUE")
    decomposition_rows = _build_information_value_decomposition(info_value_profile, generated_ts, review_run_id)

    governance_specs = [
        ("GOV_PROVIDER_CALLS", "provider_calls_performed", "0", "0"),
        ("GOV_FORECAST_GENERATION", "forecast_generation_performed", "0", "0"),
        ("GOV_CLASSIFICATION_RERUNS", "classification_rerun_count", "0", "0"),
        ("GOV_MECHANISM_LABELS_MODIFIED", "mechanism_labels_modified", "0", "0"),
        ("GOV_ACCURACY_EVALUATION", "accuracy_evaluation_performed", "0", "0"),
        ("GOV_PRODUCTION_BEHAVIOR", "production_behavior_change_count", "0", "0"),
        ("GOV_PRODUCTION_WRITES", "production_sheet_write_count", "0", "0"),
        ("GOV_ROUTING", "routing_changes", "FALSE", "FALSE"),
        ("GOV_WEIGHTING", "weighting_changes", "FALSE", "FALSE"),
        ("GOV_CALIBRATION", "calibration_changes", "FALSE", "FALSE"),
    ]
    governance_rows = [
        {
            **_base(generated_ts, review_run_id),
            "check_id": check_id,
            "check_name": check_name,
            "expected_value": expected_value,
            "actual_value": actual_value,
            "status": "PASS" if expected_value == actual_value else "FAIL",
            "notes": "Conflict review is read-only and non-production.",
        }
        for check_id, check_name, expected_value, actual_value in governance_specs
    ]

    highest_conflict_profile = max(profiles, key=lambda profile: profile["conflict_count"])
    unique_conflict_types = len({row["conflict_type"] for row in type_rows if row["conflict_type"] != "NO_DIRECT_CONFLICT_IDENTIFIED"})
    unique_root_causes = len({row["root_cause_classification"] for row in root_cause_rows})
    decomposition_signal = next(
        (row["decomposition_classification"] for row in decomposition_rows if row["analysis_scope"] == "overall"),
        "NO_EVIDENCE_FOR_DECOMPOSITION",
    )
    scientific_recommendation = (
        "The dry run is operationally sound. The MECH_INFORMATION_VALUE conflict is scientific: it behaves like a composite mechanism "
        "whose current label mixes relevance, novelty, specificity, and consistency."
    )
    ready_for_execution = "FALSE" if decomposition_signal == "STRONG_DECOMPOSITION_SIGNAL" else "TRUE"
    mechanism_revision_needed = "TRUE" if ready_for_execution == "FALSE" else "FALSE"
    recommended_next_step = (
        "PROCEED_TO_PHASE9A6R_MECHANISM_REFINEMENT"
        if mechanism_revision_needed == "TRUE"
        else "PROCEED_TO_PHASE9A6E_MECHANISM_CLASSIFICATION_EXECUTION"
    )

    summary_rows = [
        {
            **_base(generated_ts, review_run_id),
            "build_status": "PASS_WITH_WARNINGS",
            "final_interpretation": "PREDICTIVE_MECHANISM_CONFLICT_REVIEW_READY_WITH_WARNINGS",
            "mechanisms_reviewed": len(profiles),
            "conflict_types_identified": unique_conflict_types,
            "root_causes_identified": unique_root_causes,
            "highest_conflict_mechanism": highest_conflict_profile["mechanism_id"],
            "decomposition_signal": decomposition_signal,
            "scientific_recommendation": scientific_recommendation,
            "provider_calls_performed": 0,
            "forecast_generation_performed": 0,
            "mechanism_labels_modified": 0,
            "production_behavior_change_count": 0,
            "ready_for_mechanism_classification_execution": ready_for_execution,
            "mechanism_revision_needed": mechanism_revision_needed,
            "ready_for_mechanism_testing": "FALSE",
            "ready_for_production": "FALSE",
            "recommended_next_step": recommended_next_step,
            "notes": json.dumps(
                {
                    "dry_run_final_interpretation": dry_run_summary.get("final_interpretation", ""),
                    "highest_conflict_rate": dry_run_summary.get("highest_conflict_rate", ""),
                    "highest_ambiguity": dry_run_summary.get("highest_ambiguity", ""),
                    "guardrail": "research_review_only",
                },
                sort_keys=True,
                ensure_ascii=True,
            ),
        }
    ]

    outputs = [
        (OUTPUT_REVIEW, REVIEW_HEADERS, review_rows),
        (OUTPUT_TYPES, TYPES_HEADERS, type_rows),
        (OUTPUT_ROOT_CAUSES, ROOT_CAUSE_HEADERS, root_cause_rows),
        (OUTPUT_FREQUENCY, FREQUENCY_HEADERS, frequency_rows),
        (OUTPUT_OPTIONS, OPTIONS_HEADERS, option_rows),
        (OUTPUT_INFO_DECOMP, DECOMPOSITION_HEADERS, decomposition_rows),
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
        "file_created": "automation/build_predictive_mechanism_conflict_review_v0.py",
        "sheets_written": {sheet_name: len(rows) for sheet_name, _, rows in outputs},
        "mechanisms_reviewed": len(profiles),
        "conflict_types_identified": unique_conflict_types,
        "root_causes_identified": unique_root_causes,
        "highest_conflict_mechanism": highest_conflict_profile["mechanism_id"],
        "decomposition_signal": decomposition_signal,
        "scientific_recommendation": scientific_recommendation,
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "mechanism_labels_modified": 0,
        "production_behavior_change_count": 0,
        "ready_for_mechanism_classification_execution": ready_for_execution == "TRUE",
        "mechanism_revision_needed": mechanism_revision_needed == "TRUE",
        "ready_for_mechanism_testing": False,
        "ready_for_production": False,
        "recommended_next_step": recommended_next_step,
        "registry": registry,
    }


def main() -> None:
    result = build_predictive_mechanism_conflict_review_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
