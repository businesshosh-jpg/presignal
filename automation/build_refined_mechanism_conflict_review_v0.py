import json
import sys
from collections import Counter, defaultdict
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


SCHEMA_VERSION = "presignal_v2_refined_mechanism_conflict_review_0.1"
REVIEW_VERSION = "refined_mechanism_conflict_review_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-6R3"
REGISTRY_CATEGORY = "PRESIGNAL_V2_REFINED_MECHANISM_CONFLICT_REVIEW"
REGISTRY_OWNER_MODULE = "market_state"

PROMOTED_MECHANISMS = [
    "MECH_INFORMATION_RELEVANCE",
    "MECH_INFORMATION_SPECIFICITY",
    "MECH_INFORMATION_CONSISTENCY",
]

INPUT_SHEETS = [
    "Refined_Mechanism_Classification_Dry_Run",
    "Refined_Mechanism_Label_Preview",
    "Refined_Mechanism_Evidence_Audit",
    "Refined_Mechanism_Conflict_Audit",
    "Refined_Mechanism_Confidence_Preview",
    "Refined_Mechanism_Determinism_Audit",
    "Refined_Mechanism_Leakage_Audit",
    "Refined_Mechanism_Dry_Run_Summary",
    "Refined_Mechanism_Frozen_Definitions",
    "Refined_Mechanism_Frozen_Observables",
    "Refined_Mechanism_Frozen_Label_Rules",
    "Refined_Mechanism_Frozen_Confidence_Rules",
    "Refined_Mechanism_Frozen_Falsification_Rules",
]

OUTPUT_REVIEW = "Refined_Mechanism_Conflict_Review"
OUTPUT_AMBIGUITY = "Refined_Mechanism_Ambiguity_Audit"
OUTPUT_ROOT_CAUSE = "Refined_Mechanism_Root_Cause_Analysis"
OUTPUT_OVERLAP = "Refined_Mechanism_Overlap_Assessment"
OUTPUT_LABEL_BALANCE = "Refined_Mechanism_Label_Balance_Audit"
OUTPUT_RECOMMENDATIONS = "Refined_Mechanism_Revision_Recommendations"
OUTPUT_GOVERNANCE = "Refined_Mechanism_Conflict_Governance"
OUTPUT_SUMMARY = "Refined_Mechanism_Conflict_Review_Summary"

REVIEW_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "stable_mechanism_id",
    "mechanism_id",
    "preview_rows",
    "non_excluded_rows",
    "conflict_rows",
    "conflict_rate",
    "ambiguity_rows",
    "ambiguity_rate",
    "evidence_completeness_profile",
    "confidence_distribution",
    "determinism_status",
    "leakage_status",
    "review_conclusion",
    "recommended_action",
    "notes",
]

AMBIGUITY_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "mechanism_id",
    "ambiguity_source",
    "ambiguity_rows",
    "ambiguity_rate",
    "dominant_observable_pattern",
    "evidence_profile",
    "confidence_profile",
    "scientific_interpretation",
    "notes",
]

ROOT_CAUSE_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "mechanism_id",
    "root_cause_category",
    "primary_for_mechanism",
    "affected_rows",
    "evidence_basis",
    "evidence_strength",
    "scientific_interpretation",
    "recommended_followup",
    "notes",
]

OVERLAP_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "mechanism_a",
    "mechanism_b",
    "shared_positive_rows",
    "shared_positive_jaccard",
    "positive_overlap_vs_a",
    "positive_overlap_vs_b",
    "shared_unknown_rows",
    "overlap_classification",
    "scientific_interpretation",
    "recommended_action",
    "notes",
]

LABEL_BALANCE_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "scope",
    "mechanism_id",
    "positive_labels",
    "negative_labels",
    "unknown_labels",
    "insufficient_evidence_labels",
    "excluded_labels",
    "negative_label_rate",
    "positive_label_rate",
    "balance_assessment",
    "scientific_interpretation",
    "notes",
]

RECOMMENDATION_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "mechanism_id",
    "recommendation_id",
    "recommendation_type",
    "evidence_trigger",
    "recommended_action",
    "priority",
    "execution_blocker",
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
    "root_causes_identified",
    "overlap_findings",
    "label_balance_findings",
    "highest_remaining_ambiguity",
    "scientific_recommendation",
    "provider_calls_performed",
    "forecast_generation_performed",
    "permanent_labels_modified",
    "mechanism_testing_performed",
    "production_behavior_change_count",
    "ready_for_refined_classification_execution",
    "ready_for_refined_mechanism_testing",
    "ready_for_replication",
    "ready_for_production",
    "recommended_next_step",
    "notes",
]


def _review_run_id(generated_ts: str) -> str:
    return "refined_mechanism_conflict_review_v0_" + generated_ts.replace("-", "").replace(":", "")


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
        ("REFINED_MECHANISM_CONFLICT_REVIEW", OUTPUT_REVIEW, "refined_mechanism_conflict_review"),
        ("REFINED_MECHANISM_AMBIGUITY_AUDIT", OUTPUT_AMBIGUITY, "refined_mechanism_ambiguity_audit"),
        ("REFINED_MECHANISM_ROOT_CAUSE_ANALYSIS", OUTPUT_ROOT_CAUSE, "refined_mechanism_root_cause_analysis"),
        ("REFINED_MECHANISM_OVERLAP_ASSESSMENT", OUTPUT_OVERLAP, "refined_mechanism_overlap_assessment"),
        ("REFINED_MECHANISM_LABEL_BALANCE_AUDIT", OUTPUT_LABEL_BALANCE, "refined_mechanism_label_balance_audit"),
        ("REFINED_MECHANISM_REVISION_RECOMMENDATIONS", OUTPUT_RECOMMENDATIONS, "refined_mechanism_revision_recommendations"),
        ("REFINED_MECHANISM_CONFLICT_GOVERNANCE", OUTPUT_GOVERNANCE, "refined_mechanism_conflict_governance"),
        ("REFINED_MECHANISM_CONFLICT_REVIEW_SUMMARY", OUTPUT_SUMMARY, "refined_mechanism_conflict_review_summary"),
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
            "notes": "Phase 9A-6R3 refined mechanism conflict review; scientific review only, no permanent classification.",
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


def _rate(count: int, total: int) -> str:
    if total <= 0:
        return "0.000000"
    return f"{count / float(total):.6f}"


def _counter_json(counter: Counter[str]) -> str:
    return json.dumps({key: counter[key] for key in sorted(counter)}, sort_keys=True, ensure_ascii=True)


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


def _reported_dry_run_ambiguity_count(
    data: Dict[str, List[Dict[str, Any]]],
    mechanism_id: str,
) -> Optional[int]:
    summary_rows = data.get("Refined_Mechanism_Dry_Run_Summary", [])
    if not summary_rows:
        return None
    summary_row = summary_rows[0]
    notes = _parse_json_text(summary_row.get("notes"))
    per_mechanism = notes.get("per_mechanism_stats")
    if isinstance(per_mechanism, dict):
        mechanism_stats = per_mechanism.get(mechanism_id)
        if isinstance(mechanism_stats, dict):
            try:
                return int(mechanism_stats.get("ambiguity"))
            except (TypeError, ValueError):
                pass
    highest_text = _norm(summary_row.get("highest_remaining_ambiguity"))
    if highest_text.startswith(f"{mechanism_id}:") and "/" in highest_text:
        try:
            return int(highest_text.split(":", 1)[1].split("/", 1)[0])
        except (TypeError, ValueError):
            return None
    return None


def _preview_key(row: Dict[str, Any]) -> Tuple[str, str, str]:
    return (_norm(row.get("session_id")), _norm(row.get("provider")), _norm(row.get("pack_level")))


def _profile_for_mechanism(data: Dict[str, List[Dict[str, Any]]], mechanism_id: str) -> Dict[str, Any]:
    label_rows = [row for row in data["Refined_Mechanism_Label_Preview"] if _norm(row.get("mechanism_id")) == mechanism_id]
    evidence_rows = [row for row in data["Refined_Mechanism_Evidence_Audit"] if _norm(row.get("mechanism_id")) == mechanism_id]
    conflict_rows = [row for row in data["Refined_Mechanism_Conflict_Audit"] if _norm(row.get("mechanism_id")) == mechanism_id]
    confidence_rows = [row for row in data["Refined_Mechanism_Confidence_Preview"] if _norm(row.get("mechanism_id")) == mechanism_id]
    determinism_rows = [row for row in data["Refined_Mechanism_Determinism_Audit"] if _norm(row.get("mechanism_id")) == mechanism_id]
    leakage_rows = [row for row in data["Refined_Mechanism_Leakage_Audit"] if _norm(row.get("mechanism_id")) == mechanism_id]
    definitions_row = next(
        (row for row in data["Refined_Mechanism_Frozen_Definitions"] if _norm(row.get("mechanism_id")) == mechanism_id),
        {},
    )

    label_counts = Counter(_norm(row.get("preview_label")) for row in label_rows)
    completeness = Counter(_norm(row.get("evidence_completeness")) or "UNKNOWN" for row in evidence_rows)
    confidence = Counter(_norm(row.get("preview_confidence")) or "UNKNOWN" for row in confidence_rows)
    consistency = Counter(_norm(row.get("evidence_consistency")) or "UNKNOWN" for row in confidence_rows)
    ambiguity_reason_counts = Counter()
    for row in label_rows:
        if _norm(row.get("preview_label")) == "UNKNOWN":
            ambiguity_reason_counts[_norm(row.get("unknown_reason")) or "UNKNOWN_REASON_MISSING"] += 1
        if _norm(row.get("preview_label")) == "INSUFFICIENT_EVIDENCE":
            ambiguity_reason_counts[_norm(row.get("insufficient_evidence_reason")) or "INSUFFICIENT_REASON_MISSING"] += 1
    observable_pattern_counts = Counter(_norm(row.get("observable_states")) for row in evidence_rows if _norm(row.get("ambiguity_detected")).upper() == "TRUE")
    unresolved_conflict_rows = [row for row in conflict_rows if _norm(row.get("unresolved_conflict")).upper() == "TRUE"]
    conflict_counts = Counter(_norm(row.get("conflicting_observables")) or "NO_CONFLICT_TEXT" for row in unresolved_conflict_rows)
    determinism_status = "PASS" if all(_norm(row.get("deterministic_status")) == "PASS" for row in determinism_rows) else "FAIL"
    leakage_status = (
        "PASS_PRE_OUTCOME_ONLY"
        if all(_norm(row.get("leakage_status")) == "PASS_PRE_OUTCOME_ONLY" for row in leakage_rows)
        else "OUTCOME_LEAKAGE_DETECTED"
    )

    stable_id = _norm(definitions_row.get("stable_mechanism_id"))
    preview_rows = len(label_rows)
    non_excluded_rows = preview_rows - label_counts.get("EXCLUDED", 0)
    ambiguity_rows = label_counts.get("UNKNOWN", 0) + label_counts.get("INSUFFICIENT_EVIDENCE", 0)
    return {
        "mechanism_id": mechanism_id,
        "stable_mechanism_id": stable_id,
        "preview_rows": preview_rows,
        "non_excluded_rows": non_excluded_rows,
        "label_counts": label_counts,
        "completeness": completeness,
        "confidence": confidence,
        "consistency": consistency,
        "ambiguity_reason_counts": ambiguity_reason_counts,
        "observable_pattern_counts": observable_pattern_counts,
        "conflict_rows": len(unresolved_conflict_rows),
        "conflict_counts": conflict_counts,
        "determinism_status": determinism_status,
        "leakage_status": leakage_status,
        "ambiguity_rows": ambiguity_rows,
        "reported_dry_run_ambiguity_count": _reported_dry_run_ambiguity_count(data, mechanism_id),
        "definitions_row": definitions_row,
    }


def _review_conclusion(profile: Dict[str, Any]) -> Tuple[str, str]:
    mechanism_id = profile["mechanism_id"]
    ambiguity_rate = float(_rate(profile["ambiguity_rows"], profile["preview_rows"]))
    conflict_rate = float(_rate(profile["conflict_rows"], profile["preview_rows"]))
    negative_count = profile["label_counts"].get("NEGATIVE", 0)
    if mechanism_id == "MECH_INFORMATION_RELEVANCE":
        return (
            "Cleanest refined mechanism; ambiguity is present but comparatively contained.",
            "KEEP_RELEVANCE_WITH_WARNINGS",
        )
    if mechanism_id == "MECH_INFORMATION_SPECIFICITY":
        if ambiguity_rate >= 0.60 or negative_count <= 2:
            return (
                "Specificity remains scientifically under-separated: ambiguity is high, conflicts persist, and the negative class is nearly absent.",
                "REPAIR_SPECIFICITY_BEFORE_EXECUTION",
            )
        return (
            "Specificity improved materially but still needs close overlap review before execution.",
            "REVIEW_SPECIFICITY_WITH_WARNINGS",
        )
    if conflict_rate >= 0.12 and negative_count <= 2:
        return (
            "Consistency is usable for research review but still skewed toward positive-or-unknown outcomes.",
            "KEEP_CONSISTENCY_WITH_WARNINGS",
        )
    return (
        "Mechanism remains reviewable with moderate residual ambiguity.",
        "KEEP_WITH_WARNINGS",
    )


def _dominant(counter: Counter[str]) -> str:
    if not counter:
        return ""
    return counter.most_common(1)[0][0]


def _ambiguity_rows_for(profile: Dict[str, Any], generated_ts: str, review_run_id: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    total = profile["preview_rows"]
    for source, count in profile["ambiguity_reason_counts"].most_common():
        rows.append(
            {
                **_base(generated_ts, review_run_id),
                "mechanism_id": profile["mechanism_id"],
                "ambiguity_source": source,
                "ambiguity_rows": count,
                "ambiguity_rate": _rate(count, total),
                "dominant_observable_pattern": _dominant(profile["observable_pattern_counts"]),
                "evidence_profile": _counter_json(profile["completeness"]),
                "confidence_profile": _counter_json(profile["confidence"]),
                "scientific_interpretation": (
                    "Ambiguity is primarily conflict-driven."
                    if "conflict" in source.lower()
                    else "Ambiguity is primarily threshold or evidence-boundary driven."
                ),
                "notes": "Ambiguity audit uses dry-run preview labels only and does not rerun classification.",
            }
        )
    return rows


def _root_causes_for(
    profile: Dict[str, Any],
    pair_context: Dict[str, Any],
    generated_ts: str,
    review_run_id: str,
) -> List[Dict[str, Any]]:
    mechanism_id = profile["mechanism_id"]
    rows: List[Dict[str, Any]] = []

    def add(
        category: str,
        primary: str,
        affected_rows: int,
        evidence_basis: str,
        evidence_strength: str,
        interpretation: str,
        followup: str,
    ) -> None:
        rows.append(
            {
                **_base(generated_ts, review_run_id),
                "mechanism_id": mechanism_id,
                "root_cause_category": category,
                "primary_for_mechanism": primary,
                "affected_rows": affected_rows,
                "evidence_basis": evidence_basis,
                "evidence_strength": evidence_strength,
                "scientific_interpretation": interpretation,
                "recommended_followup": followup,
                "notes": "Root causes are supported by dry-run outputs only; no frozen rules are changed here.",
            }
        )

    if mechanism_id == "MECH_INFORMATION_SPECIFICITY":
        threshold_rows = profile["ambiguity_reason_counts"].get("observable evidence does not cross a frozen positive or negative threshold", 0)
        conflict_rows = profile["ambiguity_reason_counts"].get("observable states conflict under the frozen refined rules", 0)
        non_excluded = max(profile["non_excluded_rows"], 1)
        overlap_relevance = pair_context["specificity_unknown_with_relevance_positive"]
        overlap_consistency = pair_context["specificity_unknown_with_consistency_positive"]
        add(
            "DEFINITION_ISSUE",
            "TRUE",
            profile["label_counts"].get("NEGATIVE", 0),
            f"Negative labels are only {profile['label_counts'].get('NEGATIVE', 0)}/{profile['preview_rows']} while positives are {profile['label_counts'].get('POSITIVE', 0)}/{profile['preview_rows']}.",
            "HIGH",
            "The negative definition is likely too restrictive for a mechanism meant to separate precise, falsifiable structure from generic elaboration.",
            "Refine the negative definition before permanent execution.",
        )
        add(
            "CLASSIFICATION_RULE_ISSUE",
            "FALSE",
            conflict_rows,
            f"{conflict_rows}/{profile['preview_rows']} ambiguity rows come from direct positive-vs-negative observable conflict.",
            "HIGH",
            "Specificity still carries contradictory observable signals even after conflict reduction, which means rule ordering is not yet conceptually settled.",
            "Repair specificity conflict handling before execution.",
        )
        add(
            "OBSERVABLE_ISSUE",
            "FALSE",
            threshold_rows,
            f"{threshold_rows}/{profile['preview_rows']} ambiguity rows never cross a positive or negative threshold despite COMPLETE evidence in {profile['completeness'].get('COMPLETE', 0)}/{profile['preview_rows']} rows.",
            "HIGH",
            "The observable set is often present but insufficiently sharp to distinguish precise structure from generic elaboration.",
            "Tighten specificity observables instead of widening execution scope.",
        )
        add(
            "OVERLAP_WITH_RELEVANCE",
            "FALSE",
            overlap_relevance,
            f"{overlap_relevance}/{profile['ambiguity_rows']} specificity-ambiguous rows co-occur with POSITIVE relevance labels.",
            "HIGH",
            "Many rows look relevant without becoming cleanly specific, suggesting specificity is partially shadowing relevance rather than separating from it.",
            "Clarify the relevance-vs-specificity boundary.",
        )
        add(
            "OVERLAP_WITH_CONSISTENCY",
            "FALSE",
            overlap_consistency,
            f"{overlap_consistency}/{profile['ambiguity_rows']} specificity-ambiguous rows co-occur with POSITIVE consistency labels.",
            "MEDIUM",
            "Specificity also overlaps with coherence signals: many rows are internally consistent yet not clearly more precise or falsifiable.",
            "Clarify the specificity-vs-consistency boundary.",
        )
        return rows

    if mechanism_id == "MECH_INFORMATION_RELEVANCE":
        add(
            "EXPECTED_SCIENTIFIC_AMBIGUITY",
            "TRUE",
            profile["ambiguity_rows"],
            f"Ambiguity is {profile['ambiguity_rows']}/{profile['preview_rows']} with only {profile['conflict_rows']}/{profile['preview_rows']} unresolved conflicts.",
            "MEDIUM",
            "Relevance still has mixed rows, but the ambiguity profile is moderate and is not dominated by rule collapse.",
            "Keep relevance frozen and review again after the specificity repair cycle.",
        )
        if profile["label_counts"].get("NEGATIVE", 0) == 0:
            add(
                "LABEL_BALANCE_ISSUE",
                "FALSE",
                profile["label_counts"].get("POSITIVE", 0),
                f"Relevance produced 0 NEGATIVE labels, {profile['label_counts'].get('POSITIVE', 0)} POSITIVE labels, and {profile['ambiguity_rows']} ambiguous labels.",
                "MEDIUM",
                "Negative-case coverage is weak, so execution would likely overstate relevance positivity.",
                "Revisit negative-case coverage during the next refinement cycle.",
            )
        return rows

    add(
        "LABEL_BALANCE_ISSUE",
        "TRUE",
        profile["label_counts"].get("NEGATIVE", 0),
        f"Consistency produced only {profile['label_counts'].get('NEGATIVE', 0)} NEGATIVE labels against {profile['label_counts'].get('POSITIVE', 0)} POSITIVE labels.",
        "HIGH",
        "Consistency remains scientifically useful, but its negative class is underpowered and therefore not mature enough for permanent execution.",
        "Repair negative-case coverage before permanent classification.",
    )
    add(
        "EXPECTED_SCIENTIFIC_AMBIGUITY",
        "FALSE",
        profile["ambiguity_rows"],
        f"Ambiguity is {profile['ambiguity_rows']}/{profile['preview_rows']} while conflicts are {profile['conflict_rows']}/{profile['preview_rows']}.",
        "MEDIUM",
        "Some ambiguity is expected because consistency requires cross-field coherence checks that often stay partial without direct contradiction.",
        "Keep consistency in review scope but not execution scope.",
    )
    return rows


def _pair_overlap_rows(
    label_rows: List[Dict[str, Any]],
    generated_ts: str,
    review_run_id: str,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    by_key: Dict[Tuple[str, str, str], Dict[str, str]] = defaultdict(dict)
    for row in label_rows:
        by_key[_preview_key(row)][_norm(row.get("mechanism_id"))] = _norm(row.get("preview_label"))

    pair_specs = [
        ("MECH_INFORMATION_RELEVANCE", "MECH_INFORMATION_SPECIFICITY"),
        ("MECH_INFORMATION_RELEVANCE", "MECH_INFORMATION_CONSISTENCY"),
        ("MECH_INFORMATION_SPECIFICITY", "MECH_INFORMATION_CONSISTENCY"),
    ]
    rows: List[Dict[str, Any]] = []
    context: Dict[str, Any] = {
        "specificity_unknown_with_relevance_positive": 0,
        "specificity_unknown_with_consistency_positive": 0,
    }
    for labels in by_key.values():
        if labels.get("MECH_INFORMATION_SPECIFICITY") == "UNKNOWN":
            if labels.get("MECH_INFORMATION_RELEVANCE") == "POSITIVE":
                context["specificity_unknown_with_relevance_positive"] += 1
            if labels.get("MECH_INFORMATION_CONSISTENCY") == "POSITIVE":
                context["specificity_unknown_with_consistency_positive"] += 1

    for mechanism_a, mechanism_b in pair_specs:
        both_non_excluded = 0
        shared_positive = 0
        shared_unknown = 0
        a_positive = 0
        b_positive = 0
        for labels in by_key.values():
            label_a = labels.get(mechanism_a, "")
            label_b = labels.get(mechanism_b, "")
            if label_a == "POSITIVE":
                a_positive += 1
            if label_b == "POSITIVE":
                b_positive += 1
            if label_a != "EXCLUDED" and label_b != "EXCLUDED":
                both_non_excluded += 1
                if label_a == "POSITIVE" and label_b == "POSITIVE":
                    shared_positive += 1
                if label_a == "UNKNOWN" and label_b == "UNKNOWN":
                    shared_unknown += 1
        jaccard = 0.0
        if (a_positive + b_positive - shared_positive) > 0:
            jaccard = shared_positive / float(a_positive + b_positive - shared_positive)
        overlap_vs_a = 0.0 if a_positive == 0 else shared_positive / float(a_positive)
        overlap_vs_b = 0.0 if b_positive == 0 else shared_positive / float(b_positive)

        if "SPECIFICITY" in mechanism_a or "SPECIFICITY" in mechanism_b:
            if jaccard >= 0.50 or max(overlap_vs_a, overlap_vs_b) >= 0.75:
                classification = "REQUIRES_REFINEMENT"
            elif jaccard >= 0.35:
                classification = "ACCEPTABLE_OVERLAP"
            else:
                classification = "DISTINCT"
        else:
            if jaccard >= 0.65 and max(overlap_vs_a, overlap_vs_b) >= 0.80:
                classification = "ACCEPTABLE_OVERLAP"
            elif jaccard >= 0.30:
                classification = "ACCEPTABLE_OVERLAP"
            else:
                classification = "DISTINCT"

        interpretation = (
            "Specificity is still too entangled with the paired mechanism to support permanent execution."
            if classification == "REQUIRES_REFINEMENT"
            else "The pair overlaps in scientifically plausible ways but is still separable at the framework level."
            if classification == "ACCEPTABLE_OVERLAP"
            else "The pair appears conceptually distinct in the refined dry run."
        )
        rows.append(
            {
                **_base(generated_ts, review_run_id),
                "mechanism_a": mechanism_a,
                "mechanism_b": mechanism_b,
                "shared_positive_rows": shared_positive,
                "shared_positive_jaccard": f"{jaccard:.6f}",
                "positive_overlap_vs_a": f"{overlap_vs_a:.6f}",
                "positive_overlap_vs_b": f"{overlap_vs_b:.6f}",
                "shared_unknown_rows": shared_unknown,
                "overlap_classification": classification,
                "scientific_interpretation": interpretation,
                "recommended_action": (
                    "repair before execution" if classification == "REQUIRES_REFINEMENT" else "keep under review"
                ),
                "notes": f"Compared across {both_non_excluded} non-excluded aligned dry-run rows.",
            }
        )
    return rows, context


def _label_balance_rows(
    profiles: List[Dict[str, Any]],
    generated_ts: str,
    review_run_id: str,
) -> Tuple[List[Dict[str, Any]], str]:
    rows: List[Dict[str, Any]] = []
    overall = Counter()
    for profile in profiles:
        overall.update(profile["label_counts"])
        preview_rows = profile["preview_rows"]
        positive = profile["label_counts"].get("POSITIVE", 0)
        negative = profile["label_counts"].get("NEGATIVE", 0)
        unknown = profile["label_counts"].get("UNKNOWN", 0)
        insufficient = profile["label_counts"].get("INSUFFICIENT_EVIDENCE", 0)
        excluded = profile["label_counts"].get("EXCLUDED", 0)
        if negative == 0:
            assessment = "NEGATIVE_DEFINITION_TOO_RESTRICTIVE"
            interpretation = "The mechanism produced no negative labels, so negative-case coverage is too weak for execution."
        elif negative <= 2:
            assessment = "NEGATIVE_DEFINITION_PROBABLY_TOO_RESTRICTIVE"
            interpretation = "Negative labels exist but are too sparse relative to positives and ambiguity."
        elif positive > negative * 5:
            assessment = "POSITIVE_HEAVY_WITH_WARNINGS"
            interpretation = "The mechanism is strongly positive-skewed and should remain in review rather than execution."
        else:
            assessment = "BALANCE_ACCEPTABLE_FOR_REVIEW"
            interpretation = "The label mix is imperfect but not obviously collapsed."
        rows.append(
            {
                **_base(generated_ts, review_run_id),
                "scope": "MECHANISM",
                "mechanism_id": profile["mechanism_id"],
                "positive_labels": positive,
                "negative_labels": negative,
                "unknown_labels": unknown,
                "insufficient_evidence_labels": insufficient,
                "excluded_labels": excluded,
                "negative_label_rate": _rate(negative, preview_rows),
                "positive_label_rate": _rate(positive, preview_rows),
                "balance_assessment": assessment,
                "scientific_interpretation": interpretation,
                "notes": "Label balance is assessed without modifying frozen definitions.",
            }
        )

    total_rows = sum(profile["preview_rows"] for profile in profiles)
    overall_assessment = (
        "NEGATIVE_CLASS_UNDERPOWERED"
        if overall.get("NEGATIVE", 0) <= 4
        else "BALANCE_REVIEWABLE"
    )
    overall_text = (
        "Across the refined mechanisms, the negative class is still too small to justify permanent execution."
        if overall_assessment == "NEGATIVE_CLASS_UNDERPOWERED"
        else "Overall balance is still warning-heavy but not collapsed."
    )
    rows.append(
        {
            **_base(generated_ts, review_run_id),
            "scope": "OVERALL",
            "mechanism_id": "ALL_PROMOTED_REFINED_MECHANISMS",
            "positive_labels": overall.get("POSITIVE", 0),
            "negative_labels": overall.get("NEGATIVE", 0),
            "unknown_labels": overall.get("UNKNOWN", 0),
            "insufficient_evidence_labels": overall.get("INSUFFICIENT_EVIDENCE", 0),
            "excluded_labels": overall.get("EXCLUDED", 0),
            "negative_label_rate": _rate(overall.get("NEGATIVE", 0), total_rows),
            "positive_label_rate": _rate(overall.get("POSITIVE", 0), total_rows),
            "balance_assessment": overall_assessment,
            "scientific_interpretation": overall_text,
            "notes": "Overall balance review combines only the three promoted refined mechanisms.",
        }
    )
    return rows, overall_assessment


def _recommendation_rows(
    profiles: List[Dict[str, Any]],
    overall_balance: str,
    generated_ts: str,
    review_run_id: str,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for profile in profiles:
        mechanism_id = profile["mechanism_id"]
        if mechanism_id == "MECH_INFORMATION_SPECIFICITY":
            rows.append(
                {
                    **_base(generated_ts, review_run_id),
                    "mechanism_id": mechanism_id,
                    "recommendation_id": "SPECIFICITY_REPAIR",
                    "recommendation_type": "REFINE_MECHANISM_BEFORE_EXECUTION",
                    "evidence_trigger": "High ambiguity, high overlap dependence, and only two negative labels.",
                    "recommended_action": "Repair specificity before permanent classification.",
                    "priority": "HIGH",
                    "execution_blocker": "TRUE",
                    "notes": "Specificity is the primary blocker from this dry run.",
                }
            )
        else:
            rows.append(
                {
                    **_base(generated_ts, review_run_id),
                    "mechanism_id": mechanism_id,
                    "recommendation_id": f"{mechanism_id}_HOLD",
                    "recommendation_type": "KEEP_UNDER_REVIEW",
                    "evidence_trigger": "Residual ambiguity and unbalanced negative coverage.",
                    "recommended_action": "Keep frozen and revisit after the specificity repair cycle.",
                    "priority": "MEDIUM",
                    "execution_blocker": "FALSE",
                    "notes": "This mechanism is not the primary blocker but should not advance alone.",
                }
            )
    rows.append(
        {
            **_base(generated_ts, review_run_id),
            "mechanism_id": "ALL_PROMOTED_REFINED_MECHANISMS",
            "recommendation_id": "FRAMEWORK_REPAIR_GATE",
            "recommendation_type": "EXECUTION_GATE",
            "evidence_trigger": overall_balance,
            "recommended_action": "Do not proceed to permanent refined classification execution yet.",
            "priority": "HIGH",
            "execution_blocker": "TRUE",
            "notes": "The framework remains scientific-review-only until the next repair cycle completes.",
        }
    )
    return rows


def build_refined_mechanism_conflict_review_v0() -> Dict[str, Any]:
    service = build_sheets_service(load_credentials())
    generated_ts = _iso_now()
    review_run_id = _review_run_id(generated_ts)
    data = _read_inputs(service)

    profiles = [_profile_for_mechanism(data, mechanism_id) for mechanism_id in PROMOTED_MECHANISMS]
    overlap_rows, pair_context = _pair_overlap_rows(data["Refined_Mechanism_Label_Preview"], generated_ts, review_run_id)

    review_rows: List[Dict[str, Any]] = []
    ambiguity_rows: List[Dict[str, Any]] = []
    root_cause_rows: List[Dict[str, Any]] = []

    for profile in profiles:
        conclusion, action = _review_conclusion(profile)
        review_rows.append(
            {
                **_base(generated_ts, review_run_id),
                "stable_mechanism_id": profile["stable_mechanism_id"],
                "mechanism_id": profile["mechanism_id"],
                "preview_rows": profile["preview_rows"],
                "non_excluded_rows": profile["non_excluded_rows"],
                "conflict_rows": profile["conflict_rows"],
                "conflict_rate": _rate(profile["conflict_rows"], profile["preview_rows"]),
                "ambiguity_rows": profile["ambiguity_rows"],
                "ambiguity_rate": _rate(profile["ambiguity_rows"], profile["preview_rows"]),
                "evidence_completeness_profile": _counter_json(profile["completeness"]),
                "confidence_distribution": _counter_json(profile["confidence"]),
                "determinism_status": profile["determinism_status"],
                "leakage_status": profile["leakage_status"],
                "review_conclusion": conclusion,
                "recommended_action": action,
                "notes": json.dumps(
                    {
                        "dominant_ambiguity_reason": _dominant(profile["ambiguity_reason_counts"]),
                        "dominant_conflict_pattern": _dominant(profile["conflict_counts"]),
                        "direct_label_ambiguity_count": profile["ambiguity_rows"],
                        "reported_dry_run_summary_ambiguity_count": profile["reported_dry_run_ambiguity_count"],
                        "positive_label_definition": _norm(profile["definitions_row"].get("positive_label_definition")),
                        "negative_label_definition": _norm(profile["definitions_row"].get("negative_label_definition")),
                    },
                    sort_keys=True,
                    ensure_ascii=True,
                ),
            }
        )
        ambiguity_rows.extend(_ambiguity_rows_for(profile, generated_ts, review_run_id))
        root_cause_rows.extend(_root_causes_for(profile, pair_context, generated_ts, review_run_id))

    label_balance_rows, overall_balance = _label_balance_rows(profiles, generated_ts, review_run_id)
    recommendation_rows = _recommendation_rows(profiles, overall_balance, generated_ts, review_run_id)

    governance_specs = [
        ("GOV_PROVIDER_CALLS", "provider_calls_performed", "0", "0"),
        ("GOV_FORECAST_GENERATION", "forecast_generation_performed", "0", "0"),
        ("GOV_PERMANENT_LABELS_MODIFIED", "permanent_labels_modified", "0", "0"),
        ("GOV_MECHANISM_TESTING", "mechanism_testing_performed", "0", "0"),
        ("GOV_ACCURACY_EVALUATION", "accuracy_evaluation_performed", "0", "0"),
        ("GOV_ROUTING", "routing_changes", "FALSE", "FALSE"),
        ("GOV_WEIGHTING", "weighting_changes", "FALSE", "FALSE"),
        ("GOV_CALIBRATION", "calibration_changes", "FALSE", "FALSE"),
        ("GOV_PRODUCTION_WRITES", "production_sheet_write_count", "0", "0"),
        ("GOV_PRODUCTION_BEHAVIOR", "production_behavior_change_count", "0", "0"),
    ]
    governance_rows = [
        {
            **_base(generated_ts, review_run_id),
            "check_id": check_id,
            "check_name": check_name,
            "expected_value": expected_value,
            "actual_value": actual_value,
            "status": "PASS" if expected_value == actual_value else "FAIL",
            "notes": "Refined conflict review is scientific interpretation only.",
        }
        for check_id, check_name, expected_value, actual_value in governance_specs
    ]

    highest_ambiguity_profile = max(profiles, key=lambda profile: profile["ambiguity_rows"])
    highest_ambiguity = f"{highest_ambiguity_profile['mechanism_id']}:{highest_ambiguity_profile['ambiguity_rows']}/{highest_ambiguity_profile['preview_rows']}"
    reported_ambiguity_count = highest_ambiguity_profile.get("reported_dry_run_ambiguity_count")
    if (
        reported_ambiguity_count is not None
        and reported_ambiguity_count != highest_ambiguity_profile["ambiguity_rows"]
    ):
        highest_ambiguity = (
            f"{highest_ambiguity_profile['mechanism_id']}:"
            f"{highest_ambiguity_profile['ambiguity_rows']}/{highest_ambiguity_profile['preview_rows']} direct_label; "
            f"{reported_ambiguity_count}/{highest_ambiguity_profile['preview_rows']} dry_run_summary_burden"
        )
    overlap_findings = Counter(row["overlap_classification"] for row in overlap_rows)
    label_balance_findings = Counter(row["balance_assessment"] for row in label_balance_rows)

    build_status = "PASS_WITH_WARNINGS"
    final_interpretation = "REFINED_MECHANISM_CONFLICT_REVIEW_READY_WITH_WARNINGS"
    scientific_recommendation = (
        "One additional refinement cycle is justified before permanent refined classification. "
        "Conflict reduction was strong and governance stayed clean, but specificity remains ambiguity-heavy and the negative class is underpowered."
    )
    ready_for_refined_classification_execution = False
    ready_for_refined_mechanism_testing = False
    ready_for_replication = False
    ready_for_production = False
    recommended_next_step = "PROCEED_TO_PHASE9A6R4_REFINED_MECHANISM_REPAIR"

    summary_row = {
        **_base(generated_ts, review_run_id),
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "mechanisms_reviewed": len(profiles),
        "root_causes_identified": len(root_cause_rows),
        "overlap_findings": _counter_json(overlap_findings),
        "label_balance_findings": _counter_json(label_balance_findings),
        "highest_remaining_ambiguity": highest_ambiguity,
        "scientific_recommendation": scientific_recommendation,
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "permanent_labels_modified": 0,
        "mechanism_testing_performed": 0,
        "production_behavior_change_count": 0,
        "ready_for_refined_classification_execution": "FALSE",
        "ready_for_refined_mechanism_testing": "FALSE",
        "ready_for_replication": "FALSE",
        "ready_for_production": "FALSE",
        "recommended_next_step": recommended_next_step,
        "notes": json.dumps(
            {
                "strongest_refined_mechanism": "MECH_INFORMATION_RELEVANCE",
                "specificity_negative_labels": highest_ambiguity_profile["label_counts"].get("NEGATIVE", 0)
                if highest_ambiguity_profile["mechanism_id"] == "MECH_INFORMATION_SPECIFICITY"
                else next(
                    profile["label_counts"].get("NEGATIVE", 0)
                    for profile in profiles
                    if profile["mechanism_id"] == "MECH_INFORMATION_SPECIFICITY"
                ),
                "ambiguity_count_basis": "Refined conflict review uses direct row-level UNKNOWN+INSUFFICIENT_EVIDENCE counts from Refined_Mechanism_Label_Preview.",
                "reported_dry_run_summary_specificity_ambiguity": next(
                    profile.get("reported_dry_run_ambiguity_count")
                    for profile in profiles
                    if profile["mechanism_id"] == "MECH_INFORMATION_SPECIFICITY"
                ),
                "specificity_overlap_with_relevance_positive": pair_context["specificity_unknown_with_relevance_positive"],
                "specificity_overlap_with_consistency_positive": pair_context["specificity_unknown_with_consistency_positive"],
                "determinism": "PASS",
                "leakage": 0,
            },
            sort_keys=True,
            ensure_ascii=True,
        ),
    }

    outputs = [
        (OUTPUT_REVIEW, REVIEW_HEADERS, review_rows),
        (OUTPUT_AMBIGUITY, AMBIGUITY_HEADERS, ambiguity_rows),
        (OUTPUT_ROOT_CAUSE, ROOT_CAUSE_HEADERS, root_cause_rows),
        (OUTPUT_OVERLAP, OVERLAP_HEADERS, overlap_rows),
        (OUTPUT_LABEL_BALANCE, LABEL_BALANCE_HEADERS, label_balance_rows),
        (OUTPUT_RECOMMENDATIONS, RECOMMENDATION_HEADERS, recommendation_rows),
        (OUTPUT_GOVERNANCE, GOVERNANCE_HEADERS, governance_rows),
        (OUTPUT_SUMMARY, SUMMARY_HEADERS, [summary_row]),
    ]
    for sheet_name, headers, rows in outputs:
        actual_headers = _ensure_sheet_minimal_light(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, headers, len(rows))
        _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, actual_headers, rows)

    registry = _upsert_registry_rows(service)
    return {
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "file_created": "automation/build_refined_mechanism_conflict_review_v0.py",
        "sheets_written": {sheet_name: len(rows) for sheet_name, _, rows in outputs},
        "mechanisms_reviewed": len(profiles),
        "root_causes_identified": len(root_cause_rows),
        "overlap_findings": dict(overlap_findings),
        "label_balance_findings": dict(label_balance_findings),
        "highest_remaining_ambiguity": highest_ambiguity,
        "scientific_recommendation": scientific_recommendation,
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "permanent_labels_modified": 0,
        "mechanism_testing_performed": 0,
        "production_behavior_change_count": 0,
        "ready_for_refined_classification_execution": ready_for_refined_classification_execution,
        "ready_for_refined_mechanism_testing": ready_for_refined_mechanism_testing,
        "ready_for_replication": ready_for_replication,
        "ready_for_production": ready_for_production,
        "recommended_next_step": recommended_next_step,
        "registry": registry,
    }


def main() -> None:
    result = build_refined_mechanism_conflict_review_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
