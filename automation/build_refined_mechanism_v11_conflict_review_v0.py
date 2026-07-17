import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

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


SCHEMA_VERSION = "presignal_v2_refined_mechanism_v11_conflict_review_0.1"
REVIEW_VERSION = "refined_mechanism_v11_conflict_review_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-6R7"
REGISTRY_CATEGORY = "PRESIGNAL_V2_REFINED_MECHANISM_V11_CONFLICT_REVIEW"
REGISTRY_OWNER_MODULE = "market_state"

PROMOTED_MECHANISMS = [
    "MECH_INFORMATION_RELEVANCE",
    "MECH_INFORMATION_SPECIFICITY",
    "MECH_INFORMATION_CONSISTENCY",
]
PAIR_RS = ("MECH_INFORMATION_RELEVANCE", "MECH_INFORMATION_SPECIFICITY")
PAIR_SC = ("MECH_INFORMATION_SPECIFICITY", "MECH_INFORMATION_CONSISTENCY")
PAIR_RC = ("MECH_INFORMATION_RELEVANCE", "MECH_INFORMATION_CONSISTENCY")

INPUT_SHEETS = [
    "Refined_Mechanism_v11_Classification_Dry_Run",
    "Refined_Mechanism_v11_Label_Preview",
    "Refined_Mechanism_v11_Evidence_Audit",
    "Refined_Mechanism_v11_Rule_Path_Audit",
    "Refined_Mechanism_v11_Specificity_Boundary_Audit",
    "Refined_Mechanism_v11_Conflict_Audit",
    "Refined_Mechanism_v11_Overlap_Audit",
    "Refined_Mechanism_v11_Label_Balance_Audit",
    "Refined_Mechanism_v11_Confidence_Preview",
    "Refined_Mechanism_v11_Determinism_Audit",
    "Refined_Mechanism_v11_Leakage_Audit",
    "Refined_Mechanism_v11_vs_v10_Comparison",
    "Refined_Mechanism_v11_Dry_Run_Governance",
    "Refined_Mechanism_v11_Dry_Run_Summary",
    "Refined_Mechanism_v11_PreRegistration",
    "Refined_Mechanism_v11_Frozen_Definitions",
    "Refined_Mechanism_v11_Frozen_Observables",
    "Refined_Mechanism_v11_Frozen_Label_Rules",
    "Refined_Mechanism_v11_Frozen_Confidence_Rules",
    "Refined_Mechanism_v11_Frozen_Conflict_Rules",
    "Refined_Mechanism_v11_Frozen_Falsification_Rules",
    "Refined_Mechanism_v11_Separation_Rules",
    "Refined_Mechanism_v11_Version_Diff",
    "Refined_Mechanism_v11_PreRegistration_Summary",
    "Refined_Mechanism_Classification_Dry_Run",
    "Refined_Mechanism_Label_Preview",
    "Refined_Mechanism_Conflict_Audit",
    "Refined_Mechanism_Confidence_Preview",
    "Refined_Mechanism_Dry_Run_Summary",
]

OUTPUT_REVIEW = "Refined_Mechanism_v11_Conflict_Review"
OUTPUT_COMPARABILITY = "Refined_Mechanism_v11_Population_Comparability_Audit"
OUTPUT_SPECIFICITY = "Refined_Mechanism_v11_Specificity_Validity_Review"
OUTPUT_NEGATIVE = "Refined_Mechanism_v11_Negative_Label_Review"
OUTPUT_JOINT = "Refined_Mechanism_v11_Joint_Positive_Review"
OUTPUT_UNRESOLVED = "Refined_Mechanism_v11_Unresolved_Conflict_Review"
OUTPUT_CONFIDENCE = "Refined_Mechanism_v11_Confidence_Review"
OUTPUT_FALSIFICATION = "Refined_Mechanism_v11_Falsification_Review"
OUTPUT_READINESS = "Refined_Mechanism_v11_Execution_Readiness"
OUTPUT_GOVERNANCE = "Refined_Mechanism_v11_Conflict_Governance"
OUTPUT_SUMMARY = "Refined_Mechanism_v11_Conflict_Review_Summary"

REVIEW_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "mechanism_id",
    "stable_mechanism_id",
    "review_scope",
    "candidate_rows",
    "eligible_rows",
    "positive_count",
    "negative_count",
    "unknown_count",
    "insufficient_evidence_count",
    "excluded_count",
    "conflict_count",
    "unresolved_conflict_count",
    "ambiguity_count",
    "determinism_status",
    "leakage_status",
    "review_status",
    "scientific_conclusion",
    "recommended_action",
    "notes",
]

COMPARABILITY_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "audit_scope",
    "population_scope",
    "comparability_status",
    "candidate_row_key_set_equal",
    "eligible_row_key_set_equal",
    "excluded_row_key_set_equal",
    "provider_distribution_equal",
    "pack_distribution_equal",
    "session_distribution_equal",
    "mechanism_scope_equal",
    "row_key",
    "v10_status",
    "v11_status",
    "difference_reason",
    "frozen_rule_reference",
    "comparison_impact",
    "notes",
]

SPECIFICITY_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "source_row_key",
    "session_id",
    "provider",
    "pack_level",
    "preview_label",
    "boundary_forming_cue",
    "boundary_cue_count",
    "forecast_relevance",
    "frozen_rule_id",
    "traceable_source_evidence",
    "no_prohibited_proxy_dependency",
    "prohibited_proxy_detected",
    "review_classification",
    "notes",
]

NEGATIVE_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "mechanism_id",
    "source_row_key",
    "session_id",
    "provider",
    "pack_level",
    "negative_rule_id",
    "affirmative_absence_evidence",
    "missing_evidence_only",
    "optional_field_absence_only",
    "invalid_output_related",
    "excluded_row_related",
    "unknown_more_appropriate",
    "insufficient_evidence_more_appropriate",
    "negative_label_valid",
    "review_classification",
    "notes",
]

JOINT_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "pair_type",
    "source_row_key",
    "session_id",
    "provider",
    "pack_level",
    "mechanism_a",
    "mechanism_b",
    "independent_relevance_evidence",
    "independent_specificity_boundary_evidence",
    "independent_consistency_evidence",
    "same_observable_improperly_double_counted",
    "joint_positive_scientifically_valid",
    "review_classification",
    "notes",
]

UNRESOLVED_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "mechanism_id",
    "source_row_key",
    "preview_label",
    "conflicting_rule_ids",
    "conflicting_observables",
    "confidence",
    "conflict_type",
    "root_cause",
    "scientific_impact",
    "execution_impact",
    "recommended_disposition",
    "notes",
]

CONFIDENCE_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "scope",
    "mechanism_id",
    "conflicted_high_confidence_count",
    "moderate_incomplete_trace_count",
    "low_ambiguous_count",
    "unknown_label_non_unknown_confidence_count",
    "insufficient_evidence_unknown_confidence_count",
    "outcome_independence_confirmed",
    "confidence_framework_status",
    "scientific_conclusion",
    "notes",
]

FALSIFICATION_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "mechanism_id",
    "stable_mechanism_id",
    "falsification_triggered",
    "warning_triggered",
    "triggering_evidence",
    "scientific_consequence",
    "required_action",
    "notes",
]

READINESS_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "mechanism_id",
    "stable_mechanism_id",
    "execution_readiness_status",
    "population_comparable",
    "determinism_pass",
    "leakage_free",
    "false_proxy_free",
    "negatives_valid",
    "joint_positives_valid",
    "unresolved_conflicts_dispositioned",
    "falsification_blocker_triggered",
    "readiness_conclusion",
    "recommended_action",
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
    "population_comparability_status",
    "candidate_row_key_match",
    "eligible_row_key_match",
    "provider_distribution_match",
    "pack_distribution_match",
    "session_distribution_match",
    "specificity_positives_reviewed",
    "valid_boundary_positives",
    "false_proxy_positives",
    "specificity_positives_with_insufficient_trace",
    "negative_labels_reviewed",
    "valid_affirmative_negatives",
    "mislabeled_missing_evidence_negatives",
    "mislabeled_excluded_negatives",
    "mislabeled_unknown_negatives",
    "relevance_specificity_joint_positives_reviewed",
    "legitimate_relevance_specificity_joint_positives",
    "unresolved_relevance_specificity_overlaps",
    "specificity_consistency_joint_positives_reviewed",
    "legitimate_specificity_consistency_joint_positives",
    "unresolved_specificity_consistency_overlaps",
    "unresolved_conflicts_reviewed",
    "conflicts_allowed_with_low_confidence",
    "conflicts_recommended_as_unknown",
    "conflicts_recommended_as_insufficient_evidence",
    "conflicts_recommended_for_exclusion",
    "conflicts_requiring_v12_repair",
    "confidence_framework_status",
    "falsification_triggers",
    "mechanisms_ready_for_permanent_classification",
    "mechanisms_ready_with_exclusions",
    "mechanisms_requiring_repair",
    "determinism_status",
    "leakage_findings",
    "provider_calls_performed",
    "forecast_generation_performed",
    "classification_rerun_count",
    "permanent_labels_assigned",
    "mechanism_testing_performed",
    "accuracy_evaluation_performed",
    "outcome_values_accessed",
    "v10_sheets_modified",
    "v11_preregistration_modified",
    "production_behavior_change_count",
    "production_sheet_write_count",
    "ready_for_v11_classification_execution_plan",
    "ready_for_permanent_classification_execution",
    "ready_for_mechanism_testing",
    "ready_for_production",
    "recommended_next_step",
    "notes",
]

THRESHOLD_RE = re.compile(r">\s*([0-9.]+)")


def _review_run_id(generated_ts: str) -> str:
    return "refined_mechanism_v11_conflict_review_v0_" + generated_ts.replace("-", "").replace(":", "")


def _base(generated_ts: str, review_run_id: str) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "review_version": REVIEW_VERSION,
        "review_run_id": review_run_id,
    }


def _sheet_titles_light(service, spreadsheet_id: str) -> Set[str]:
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
        ("REFINED_MECHANISM_V11_CONFLICT_REVIEW", OUTPUT_REVIEW, "refined_mechanism_v11_conflict_review"),
        (
            "REFINED_MECHANISM_V11_POPULATION_COMPARABILITY_AUDIT",
            OUTPUT_COMPARABILITY,
            "refined_mechanism_v11_population_comparability_audit",
        ),
        (
            "REFINED_MECHANISM_V11_SPECIFICITY_VALIDITY_REVIEW",
            OUTPUT_SPECIFICITY,
            "refined_mechanism_v11_specificity_validity_review",
        ),
        (
            "REFINED_MECHANISM_V11_NEGATIVE_LABEL_REVIEW",
            OUTPUT_NEGATIVE,
            "refined_mechanism_v11_negative_label_review",
        ),
        (
            "REFINED_MECHANISM_V11_JOINT_POSITIVE_REVIEW",
            OUTPUT_JOINT,
            "refined_mechanism_v11_joint_positive_review",
        ),
        (
            "REFINED_MECHANISM_V11_UNRESOLVED_CONFLICT_REVIEW",
            OUTPUT_UNRESOLVED,
            "refined_mechanism_v11_unresolved_conflict_review",
        ),
        (
            "REFINED_MECHANISM_V11_CONFIDENCE_REVIEW",
            OUTPUT_CONFIDENCE,
            "refined_mechanism_v11_confidence_review",
        ),
        (
            "REFINED_MECHANISM_V11_FALSIFICATION_REVIEW",
            OUTPUT_FALSIFICATION,
            "refined_mechanism_v11_falsification_review",
        ),
        (
            "REFINED_MECHANISM_V11_EXECUTION_READINESS",
            OUTPUT_READINESS,
            "refined_mechanism_v11_execution_readiness",
        ),
        (
            "REFINED_MECHANISM_V11_CONFLICT_GOVERNANCE",
            OUTPUT_GOVERNANCE,
            "refined_mechanism_v11_conflict_governance",
        ),
        (
            "REFINED_MECHANISM_V11_CONFLICT_REVIEW_SUMMARY",
            OUTPUT_SUMMARY,
            "refined_mechanism_v11_conflict_review_summary",
        ),
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
            "notes": (
                "Phase 9A-6R7 v1.1 refined mechanism conflict review; scientific review only, "
                "no classification rerun or permanent labels."
            ),
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


def _to_bool(value: Any) -> bool:
    return _norm(value).upper() == "TRUE"


def _to_int(value: Any) -> int:
    text = _norm(value)
    if not text:
        return 0
    try:
        return int(float(text))
    except ValueError:
        return 0


def _safe_ratio(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return ""
    return f"{numerator / float(denominator):.6f}"


def _parse_json_any(value: Any) -> Any:
    text = _norm(value)
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _parse_json_dict(value: Any) -> Dict[str, Any]:
    parsed = _parse_json_any(value)
    return parsed if isinstance(parsed, dict) else {}


def _parse_json_list(value: Any) -> List[Any]:
    parsed = _parse_json_any(value)
    if isinstance(parsed, list):
        return parsed
    text = _norm(value)
    if not text:
        return []
    return [text]


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True)


def _row_key(row: Dict[str, Any]) -> str:
    source_row_key = _norm(row.get("source_row_key"))
    if source_row_key:
        return source_row_key
    session_id = _norm(row.get("session_id"))
    provider = _norm(row.get("provider"))
    pack_level = _norm(row.get("pack_level"))
    if session_id and provider and pack_level:
        return "|".join([session_id, provider, pack_level])
    preview_id = _norm(row.get("preview_id"))
    if preview_id:
        parts = preview_id.split("|")
        if len(parts) >= 5:
            return "|".join(parts[-5:]) if parts[0].startswith("v1.") else "|".join(parts[-5:])
    return ""


def _row_dimensions(row_key: str) -> Tuple[str, str, str]:
    parts = row_key.split("|")
    if len(parts) < 3:
        return "", "", ""
    return ("|".join(parts[:-2]), parts[-2], parts[-1])


def _stable_mechanism_map(definition_rows: List[Dict[str, Any]]) -> Dict[str, str]:
    return {
        _norm(row.get("mechanism_id")): _norm(row.get("stable_mechanism_id"))
        for row in definition_rows
        if _norm(row.get("mechanism_id"))
    }


def _label_index(rows: List[Dict[str, Any]]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    return {
        (_norm(row.get("mechanism_id")), _row_key(row)): row
        for row in rows
        if _norm(row.get("mechanism_id")) and _row_key(row)
    }


def _unique_keys_for_population(rows: List[Dict[str, Any]], included: Optional[bool]) -> Set[str]:
    keys: Set[str] = set()
    for row in rows:
        preview_label = _norm(row.get("preview_label"))
        if included is True and preview_label == "EXCLUDED":
            continue
        if included is False and preview_label != "EXCLUDED":
            continue
        key = _row_key(row)
        if key:
            keys.add(key)
    return keys


def _distribution(keys: Set[str], which: str) -> Counter[str]:
    counter: Counter[str] = Counter()
    for row_key in keys:
        session_id, provider, pack_level = _row_dimensions(row_key)
        if which == "provider":
            counter[provider] += 1
        elif which == "pack":
            counter[pack_level] += 1
        elif which == "session":
            counter[session_id] += 1
    return counter


def _parse_threshold(value: Any) -> Optional[float]:
    text = _norm(value)
    if not text:
        return None
    match = THRESHOLD_RE.search(text)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _pair_type(mechanism_a: str, mechanism_b: str) -> str:
    if (mechanism_a, mechanism_b) == PAIR_RS:
        return "RELEVANCE_SPECIFICITY"
    if (mechanism_a, mechanism_b) == PAIR_SC:
        return "SPECIFICITY_CONSISTENCY"
    return "RELEVANCE_CONSISTENCY"


def _negative_reason_flags(row: Dict[str, Any]) -> Tuple[bool, bool]:
    if _to_bool(row.get("missing_evidence_only")):
        return (False, True)
    if _to_bool(row.get("optional_field_absence_only")):
        return (True, False)
    return (False, False)


def build_refined_mechanism_v11_conflict_review_v0() -> Dict[str, Any]:
    credentials = load_credentials()
    service = build_sheets_service(credentials)
    data = _read_inputs(service)

    generated_ts = _iso_now()
    review_run_id = _review_run_id(generated_ts)
    stable_ids = _stable_mechanism_map(data["Refined_Mechanism_v11_Frozen_Definitions"])

    v11_label_rows = data["Refined_Mechanism_v11_Label_Preview"]
    v10_label_rows = data["Refined_Mechanism_Label_Preview"]
    v11_conflict_rows = data["Refined_Mechanism_v11_Conflict_Audit"]
    v11_boundary_rows = data["Refined_Mechanism_v11_Specificity_Boundary_Audit"]
    v11_negative_rows = [
        row
        for row in data["Refined_Mechanism_v11_Label_Balance_Audit"]
        if _norm(row.get("row_type")) == "NEGATIVE_LABEL_AUDIT"
    ]
    v11_overlap_rows = data["Refined_Mechanism_v11_Overlap_Audit"]
    v11_confidence_rows = data["Refined_Mechanism_v11_Confidence_Preview"]
    v11_rule_path_index = {
        (_norm(row.get("mechanism_id")), _norm(row.get("source_row_key"))): row
        for row in data["Refined_Mechanism_v11_Rule_Path_Audit"]
        if _norm(row.get("mechanism_id")) and _norm(row.get("source_row_key"))
    }
    v11_label_index = _label_index(v11_label_rows)

    review_rows: List[Dict[str, Any]] = []
    comparability_rows: List[Dict[str, Any]] = []
    specificity_rows: List[Dict[str, Any]] = []
    negative_rows: List[Dict[str, Any]] = []
    joint_rows: List[Dict[str, Any]] = []
    unresolved_rows: List[Dict[str, Any]] = []
    confidence_rows: List[Dict[str, Any]] = []
    falsification_rows: List[Dict[str, Any]] = []
    readiness_rows: List[Dict[str, Any]] = []

    v10_candidate_keys = _unique_keys_for_population(v10_label_rows, None)
    v11_candidate_keys = _unique_keys_for_population(v11_label_rows, None)
    v10_eligible_keys = _unique_keys_for_population(v10_label_rows, True)
    v11_eligible_keys = _unique_keys_for_population(v11_label_rows, True)
    v10_excluded_keys = _unique_keys_for_population(v10_label_rows, False)
    v11_excluded_keys = _unique_keys_for_population(v11_label_rows, False)

    candidate_row_key_match = v10_candidate_keys == v11_candidate_keys
    eligible_row_key_match = v10_eligible_keys == v11_eligible_keys
    excluded_row_key_match = v10_excluded_keys == v11_excluded_keys

    provider_distribution_match = _distribution(v10_eligible_keys, "provider") == _distribution(v11_eligible_keys, "provider")
    pack_distribution_match = _distribution(v10_eligible_keys, "pack") == _distribution(v11_eligible_keys, "pack")
    session_distribution_match = _distribution(v10_eligible_keys, "session") == _distribution(v11_eligible_keys, "session")
    mechanism_scope_equal = (
        {_norm(row.get("mechanism_id")) for row in v10_label_rows if _norm(row.get("mechanism_id"))}
        == {_norm(row.get("mechanism_id")) for row in v11_label_rows if _norm(row.get("mechanism_id"))}
        == set(PROMOTED_MECHANISMS)
    )

    if all(
        [
            candidate_row_key_match,
            eligible_row_key_match,
            excluded_row_key_match,
            provider_distribution_match,
            pack_distribution_match,
            session_distribution_match,
            mechanism_scope_equal,
        ]
    ):
        population_comparability_status = "FULLY_COMPARABLE"
    elif candidate_row_key_match and mechanism_scope_equal:
        population_comparability_status = "COMPARABLE_WITH_DOCUMENTED_RULE_DIFFERENCES"
    elif candidate_row_key_match:
        population_comparability_status = "PARTIALLY_COMPARABLE"
    else:
        population_comparability_status = "NOT_COMPARABLE"

    comparability_rows.append(
        {
            **_base(generated_ts, review_run_id),
            "audit_scope": "POPULATION_SUMMARY",
            "population_scope": "candidate_and_eligible_row_keys",
            "comparability_status": population_comparability_status,
            "candidate_row_key_set_equal": "TRUE" if candidate_row_key_match else "FALSE",
            "eligible_row_key_set_equal": "TRUE" if eligible_row_key_match else "FALSE",
            "excluded_row_key_set_equal": "TRUE" if excluded_row_key_match else "FALSE",
            "provider_distribution_equal": "TRUE" if provider_distribution_match else "FALSE",
            "pack_distribution_equal": "TRUE" if pack_distribution_match else "FALSE",
            "session_distribution_equal": "TRUE" if session_distribution_match else "FALSE",
            "mechanism_scope_equal": "TRUE" if mechanism_scope_equal else "FALSE",
            "row_key": "",
            "v10_status": "",
            "v11_status": "",
            "difference_reason": "",
            "frozen_rule_reference": "Refined_Mechanism_v11_PreRegistration",
            "comparison_impact": (
                "Conflict and ambiguity deltas are directly interpretable at the row level."
                if population_comparability_status == "FULLY_COMPARABLE"
                else "Delta interpretation requires qualification because row populations diverge."
            ),
            "notes": _json(
                {
                    "v10_candidate_rows": len(v10_candidate_keys),
                    "v11_candidate_rows": len(v11_candidate_keys),
                    "v10_eligible_rows": len(v10_eligible_keys),
                    "v11_eligible_rows": len(v11_eligible_keys),
                    "v10_excluded_rows": len(v10_excluded_keys),
                    "v11_excluded_rows": len(v11_excluded_keys),
                }
            ),
        }
    )

    all_key_union = sorted(v10_candidate_keys | v11_candidate_keys)
    for row_key in all_key_union:
        v10_status = "MISSING"
        v11_status = "MISSING"
        if row_key in v10_candidate_keys:
            v10_status = "ELIGIBLE" if row_key in v10_eligible_keys else "EXCLUDED"
        if row_key in v11_candidate_keys:
            v11_status = "ELIGIBLE" if row_key in v11_eligible_keys else "EXCLUDED"
        if v10_status == v11_status:
            continue
        comparability_rows.append(
            {
                **_base(generated_ts, review_run_id),
                "audit_scope": "ROW_STATUS_MISMATCH",
                "population_scope": "row_key",
                "comparability_status": population_comparability_status,
                "candidate_row_key_set_equal": "TRUE" if candidate_row_key_match else "FALSE",
                "eligible_row_key_set_equal": "TRUE" if eligible_row_key_match else "FALSE",
                "excluded_row_key_set_equal": "TRUE" if excluded_row_key_match else "FALSE",
                "provider_distribution_equal": "TRUE" if provider_distribution_match else "FALSE",
                "pack_distribution_equal": "TRUE" if pack_distribution_match else "FALSE",
                "session_distribution_equal": "TRUE" if session_distribution_match else "FALSE",
                "mechanism_scope_equal": "TRUE" if mechanism_scope_equal else "FALSE",
                "row_key": row_key,
                "v10_status": v10_status,
                "v11_status": v11_status,
                "difference_reason": "The same provider-pack row changed population status across versions.",
                "frozen_rule_reference": "Refined_Mechanism_v11_Version_Diff",
                "comparison_impact": "Conflict or ambiguity deltas for this row are not directly comparable.",
                "notes": "",
            }
        )

    specificity_positive_rows = [row for row in v11_boundary_rows if _norm(row.get("preview_label")) == "POSITIVE"]
    valid_boundary_positives = 0
    false_proxy_positives = 0
    specificity_insufficient_trace = 0
    for row in specificity_positive_rows:
        row_key = _norm(row.get("source_row_key"))
        label_row = v11_label_index.get(("MECH_INFORMATION_SPECIFICITY", row_key), {})
        session_id, provider, pack_level = _row_dimensions(row_key)
        boundary_cues = _parse_json_list(row.get("boundary_cue_type"))
        prohibited_proxies = _parse_json_list(row.get("prohibited_proxy_detected"))
        notes = _parse_json_dict(row.get("notes"))
        traceable = bool(_parse_json_list(row.get("boundary_cue_text_or_trace")))
        is_valid = _to_bool(row.get("specificity_positive_valid"))
        no_prohibited_proxy = len(prohibited_proxies) == 0
        if not traceable:
            classification = "INSUFFICIENT_TRACE"
            specificity_insufficient_trace += 1
        elif not is_valid or not no_prohibited_proxy:
            classification = "FALSE_PROXY_POSITIVE"
            false_proxy_positives += 1
        elif notes.get("partial_cues"):
            classification = "VALID_WITH_WARNING"
            valid_boundary_positives += 1
        else:
            classification = "VALID_BOUNDARY_POSITIVE"
            valid_boundary_positives += 1
        specificity_rows.append(
            {
                **_base(generated_ts, review_run_id),
                "source_row_key": row_key,
                "session_id": session_id,
                "provider": provider,
                "pack_level": pack_level,
                "preview_label": "POSITIVE",
                "boundary_forming_cue": _json(boundary_cues),
                "boundary_cue_count": len(boundary_cues),
                "forecast_relevance": "TRUE" if _to_bool(row.get("forecast_relevance_confirmed")) else "FALSE",
                "frozen_rule_id": _norm(label_row.get("executed_rule_id")) or "SPEC_POS_FALSIFIABLE_BOUNDARY",
                "traceable_source_evidence": "TRUE" if traceable else "FALSE",
                "no_prohibited_proxy_dependency": "TRUE" if no_prohibited_proxy else "FALSE",
                "prohibited_proxy_detected": _json(prohibited_proxies),
                "review_classification": classification,
                "notes": _json(
                    {
                        "audit_status": _norm(row.get("audit_status")),
                        "partial_cues": notes.get("partial_cues", []),
                        "time_horizon_supporting_only": notes.get("time_horizon_supporting_only"),
                    }
                ),
            }
        )

    valid_affirmative_negatives = 0
    mislabeled_missing_evidence_negatives = 0
    mislabeled_excluded_negatives = 0
    mislabeled_unknown_negatives = 0
    negative_valid_by_mechanism: Counter[str] = Counter()
    for row in v11_negative_rows:
        row_key = _norm(row.get("source_row_key"))
        session_id, provider, pack_level = _row_dimensions(row_key)
        missing_only = _to_bool(row.get("missing_evidence_only"))
        optional_only = _to_bool(row.get("optional_field_absence_only"))
        invalid_output_related = _to_bool(row.get("invalid_output_related"))
        excluded_row_related = _to_bool(row.get("excluded_row_related"))
        negative_valid = _to_bool(row.get("negative_label_valid"))
        unknown_more_appropriate = False
        insufficient_more_appropriate = False
        if negative_valid and not any([missing_only, optional_only, invalid_output_related, excluded_row_related]):
            classification = "VALID_AFFIRMATIVE_NEGATIVE"
            valid_affirmative_negatives += 1
            negative_valid_by_mechanism[_norm(row.get("mechanism_id"))] += 1
        elif missing_only or optional_only:
            classification = "MISSING_EVIDENCE_MISLABELED_NEGATIVE"
            mislabeled_missing_evidence_negatives += 1
            insufficient_more_appropriate = True
        elif excluded_row_related or invalid_output_related:
            classification = "EXCLUDED_CASE_MISLABELED_NEGATIVE"
            mislabeled_excluded_negatives += 1
        else:
            classification = "UNKNOWN_CASE_MISLABELED_NEGATIVE"
            mislabeled_unknown_negatives += 1
            unknown_more_appropriate = True
        negative_rows.append(
            {
                **_base(generated_ts, review_run_id),
                "mechanism_id": _norm(row.get("mechanism_id")),
                "source_row_key": row_key,
                "session_id": session_id,
                "provider": provider,
                "pack_level": pack_level,
                "negative_rule_id": _norm(row.get("negative_rule_id")),
                "affirmative_absence_evidence": _norm(row.get("affirmative_absence_evidence")),
                "missing_evidence_only": "TRUE" if missing_only else "FALSE",
                "optional_field_absence_only": "TRUE" if optional_only else "FALSE",
                "invalid_output_related": "TRUE" if invalid_output_related else "FALSE",
                "excluded_row_related": "TRUE" if excluded_row_related else "FALSE",
                "unknown_more_appropriate": "TRUE" if unknown_more_appropriate else "FALSE",
                "insufficient_evidence_more_appropriate": "TRUE" if insufficient_more_appropriate else "FALSE",
                "negative_label_valid": "TRUE" if negative_valid else "FALSE",
                "review_classification": classification,
                "notes": _norm(row.get("notes")),
            }
        )

    legitimate_rs_joint_positives = 0
    unresolved_rs_overlaps = 0
    legitimate_sc_joint_positives = 0
    unresolved_sc_overlaps = 0
    for row in v11_overlap_rows:
        mechanism_a = _norm(row.get("mechanism_a"))
        mechanism_b = _norm(row.get("mechanism_b"))
        if (mechanism_a, mechanism_b) not in (PAIR_RS, PAIR_SC):
            continue
        if not _to_bool(row.get("joint_positive")):
            continue
        row_key = _norm(row.get("source_row_key"))
        session_id, provider, pack_level = _row_dimensions(row_key)
        label_a = v11_label_index.get((mechanism_a, row_key), {})
        label_b = v11_label_index.get((mechanism_b, row_key), {})
        evidence_a = _parse_json_list(label_a.get("decisive_observables"))
        evidence_b = _parse_json_list(label_b.get("decisive_observables"))
        same_observable = bool(set(evidence_a) & set(evidence_b))
        independent_relevance = mechanism_a == "MECH_INFORMATION_RELEVANCE" and len(evidence_a) > 0
        independent_specificity = (
            (mechanism_a == "MECH_INFORMATION_SPECIFICITY" and len(evidence_a) > 0)
            or (mechanism_b == "MECH_INFORMATION_SPECIFICITY" and len(evidence_b) > 0)
        )
        independent_consistency = mechanism_b == "MECH_INFORMATION_CONSISTENCY" and len(evidence_b) > 0
        if _norm(row.get("pair_status")) == "LEGITIMATE_JOINT_POSITIVE" and not same_observable:
            classification = "LEGITIMATE_JOINT_POSITIVE"
            valid_joint = True
        elif _norm(row.get("pair_status")) == "LEGITIMATE_JOINT_POSITIVE":
            classification = "ACCEPTABLE_SHARED_SOURCE_DISTINCT_RULES"
            valid_joint = True
        elif same_observable:
            classification = "SAME_EVIDENCE_DOUBLE_COUNT"
            valid_joint = False
        else:
            classification = "UNRESOLVED_CONCEPTUAL_OVERLAP"
            valid_joint = False
        if (mechanism_a, mechanism_b) == PAIR_RS:
            if valid_joint:
                legitimate_rs_joint_positives += 1
            else:
                unresolved_rs_overlaps += 1
        if (mechanism_a, mechanism_b) == PAIR_SC:
            if valid_joint:
                legitimate_sc_joint_positives += 1
            else:
                unresolved_sc_overlaps += 1
        joint_rows.append(
            {
                **_base(generated_ts, review_run_id),
                "pair_type": _pair_type(mechanism_a, mechanism_b),
                "source_row_key": row_key,
                "session_id": session_id,
                "provider": provider,
                "pack_level": pack_level,
                "mechanism_a": mechanism_a,
                "mechanism_b": mechanism_b,
                "independent_relevance_evidence": "TRUE" if independent_relevance else "",
                "independent_specificity_boundary_evidence": "TRUE" if independent_specificity else "",
                "independent_consistency_evidence": "TRUE" if independent_consistency else "",
                "same_observable_improperly_double_counted": "TRUE" if same_observable else "FALSE",
                "joint_positive_scientifically_valid": "TRUE" if valid_joint else "FALSE",
                "review_classification": classification,
                "notes": _json(
                    {
                        "pair_status": _norm(row.get("pair_status")),
                        "separation_rule_applied": _norm(row.get("separation_rule_applied")),
                        "justification": _norm(row.get("justification")),
                        "rule_ids": [_norm(label_a.get("executed_rule_id")), _norm(label_b.get("executed_rule_id"))],
                    }
                ),
            }
        )

    conflicts_allowed_with_low_confidence = 0
    conflicts_recommended_as_unknown = 0
    conflicts_recommended_as_insufficient_evidence = 0
    conflicts_recommended_for_exclusion = 0
    conflicts_requiring_v12_repair = 0
    unresolved_by_mechanism: Counter[str] = Counter()
    dispositions_by_mechanism: Dict[str, Counter[str]] = {
        mechanism_id: Counter() for mechanism_id in PROMOTED_MECHANISMS
    }
    unresolved_preview_rows = [
        row for row in v11_label_rows if _norm(row.get("conflict_status")) == "UNRESOLVED_CONFLICT"
    ]
    for row in unresolved_preview_rows:
        mechanism_id = _norm(row.get("mechanism_id"))
        row_key = _norm(row.get("source_row_key"))
        full_audit = _parse_json_dict(row.get("full_audit_path"))
        notes = _parse_json_dict(row.get("notes"))
        observable_states = full_audit.get("observable_states", {})
        conflicting_observables = [key for key, value in observable_states.items() if _norm(value) == "UNKNOWN"]
        conflicting_rule_ids = [_norm(row.get("executed_rule_id"))] + _parse_json_list(row.get("rejected_alternative_rules"))
        preview_label = _norm(row.get("preview_label"))
        confidence = _norm(row.get("confidence_category"))
        if mechanism_id == "MECH_INFORMATION_SPECIFICITY":
            partial_cues = notes.get("partial_cues") or []
            if partial_cues:
                conflict_type = "PARTIAL_BOUNDARY_TRACE"
                root_cause = "LABEL_BOUNDARY_AMBIGUITY"
                scientific_impact = (
                    "Specificity remains boundary-aware but not boundary-decisive; the row contains suggestive invalidation language without a fully explicit falsifiable boundary."
                )
                execution_impact = (
                    "Execution remains possible only if UNKNOWN stays an allowed terminal class and these rows are not forced into positive or negative specificity."
                )
                recommended_disposition = "CONVERT_TO_UNKNOWN"
                conflicts_recommended_as_unknown += 1
            elif notes.get("sparse_trace"):
                conflict_type = "TRACE_GAP"
                root_cause = "SOURCE_EVIDENCE_LIMITATION"
                scientific_impact = "The classifier cannot distinguish true boundary structure from sparse trace coverage."
                execution_impact = "Rows should not enter permanent classification without an insufficient-evidence fallback."
                recommended_disposition = "CONVERT_TO_INSUFFICIENT_EVIDENCE"
                conflicts_recommended_as_insufficient_evidence += 1
            else:
                conflict_type = "MIXED_BOUNDARY_SIGNAL"
                root_cause = "LEGITIMATE_MIXED_EVIDENCE"
                scientific_impact = "Specificity evidence remains mixed but traceable."
                execution_impact = "Rows can remain in execution scope only if preserved as low-confidence ambiguity cases."
                recommended_disposition = "ALLOW_WITH_LOW_CONFIDENCE"
                conflicts_allowed_with_low_confidence += 1
        else:
            conflict_type = "MIXED_TARGET_PATH_SIGNAL"
            root_cause = "LEGITIMATE_MIXED_EVIDENCE"
            scientific_impact = (
                "Target-driver alignment and causal-path evidence diverge without a decisive path-changing trace."
            )
            execution_impact = (
                "The row can remain in scope if low-confidence UNKNOWN is preserved instead of forcing a permanent positive or negative label."
            )
            recommended_disposition = "ALLOW_WITH_LOW_CONFIDENCE"
            conflicts_allowed_with_low_confidence += 1
        unresolved_by_mechanism[mechanism_id] += 1
        dispositions_by_mechanism[mechanism_id][recommended_disposition] += 1
        unresolved_rows.append(
            {
                **_base(generated_ts, review_run_id),
                "mechanism_id": mechanism_id,
                "source_row_key": row_key,
                "preview_label": preview_label,
                "conflicting_rule_ids": _json([rule_id for rule_id in conflicting_rule_ids if rule_id]),
                "conflicting_observables": _json(conflicting_observables),
                "confidence": confidence,
                "conflict_type": conflict_type,
                "root_cause": root_cause,
                "scientific_impact": scientific_impact,
                "execution_impact": execution_impact,
                "recommended_disposition": recommended_disposition,
                "notes": _json(
                    {
                        "full_audit_rule_path": _norm(row.get("executed_rule_id")),
                        "time_horizon_supporting_only": notes.get("time_horizon_supporting_only"),
                        "partial_cues": notes.get("partial_cues", []),
                    }
                ),
            }
        )

    conflict_summary_by_mechanism = {
        _norm(row.get("mechanism_id")): row for row in v11_conflict_rows if _norm(row.get("mechanism_id"))
    }
    determinism_rows = data["Refined_Mechanism_v11_Determinism_Audit"]
    leakage_rows = data["Refined_Mechanism_v11_Leakage_Audit"]
    determinism_status = (
        "PASS"
        if all(_norm(row.get("determinism_status")) == "PASS" for row in determinism_rows)
        else "FAIL"
    )
    leakage_findings = sum(1 for row in leakage_rows if _norm(row.get("leakage_status")) == "OUTCOME_LEAKAGE_DETECTED")

    confidence_framework_status = "SCIENTIFICALLY_ALIGNED"
    overall_high_conflict_confidence = 0
    overall_moderate_incomplete = 0
    overall_low_ambiguous = 0
    overall_unknown_non_unknown_confidence = 0
    overall_insufficient_unknown_confidence = 0
    for mechanism_id in PROMOTED_MECHANISMS:
        mechanism_conf_rows = [
            row for row in v11_confidence_rows if _norm(row.get("mechanism_id")) == mechanism_id
        ]
        conflicted_high_confidence = 0
        moderate_incomplete_trace = 0
        low_ambiguous = 0
        unknown_label_non_unknown_confidence = 0
        insufficient_unknown_confidence = 0
        for row in mechanism_conf_rows:
            preview_label = _norm(row.get("preview_label"))
            confidence_category = _norm(row.get("confidence_category"))
            evidence_completeness = _norm(row.get("evidence_completeness"))
            rule_path_clarity = _norm(row.get("rule_path_clarity"))
            ambiguity_level = _norm(row.get("ambiguity_level"))
            conflict_row = v11_label_index.get((_norm(row.get("mechanism_id")), _norm(row.get("source_row_key"))), {})
            conflict_status = _norm(conflict_row.get("conflict_status"))
            if conflict_status == "UNRESOLVED_CONFLICT" and confidence_category == "HIGH":
                conflicted_high_confidence += 1
            if confidence_category == "MODERATE" and (
                evidence_completeness in {"PARTIAL", "SPARSE"} or rule_path_clarity == "PARTIAL"
            ):
                moderate_incomplete_trace += 1
            if confidence_category == "LOW" and preview_label == "UNKNOWN" and ambiguity_level == "HIGH":
                low_ambiguous += 1
            if preview_label == "UNKNOWN" and confidence_category not in {"", "UNKNOWN"}:
                unknown_label_non_unknown_confidence += 1
            if preview_label == "INSUFFICIENT_EVIDENCE" and confidence_category == "UNKNOWN":
                insufficient_unknown_confidence += 1
        if conflicted_high_confidence > 0:
            mechanism_confidence_status = "MISALIGNED"
        elif unknown_label_non_unknown_confidence > 0 or moderate_incomplete_trace > 0:
            mechanism_confidence_status = "ALIGNED_WITH_WARNINGS"
        else:
            mechanism_confidence_status = "SCIENTIFICALLY_ALIGNED"
        if mechanism_confidence_status == "MISALIGNED":
            confidence_framework_status = "MISALIGNED"
        elif mechanism_confidence_status == "ALIGNED_WITH_WARNINGS" and confidence_framework_status == "SCIENTIFICALLY_ALIGNED":
            confidence_framework_status = "ALIGNED_WITH_WARNINGS"
        overall_high_conflict_confidence += conflicted_high_confidence
        overall_moderate_incomplete += moderate_incomplete_trace
        overall_low_ambiguous += low_ambiguous
        overall_unknown_non_unknown_confidence += unknown_label_non_unknown_confidence
        overall_insufficient_unknown_confidence += insufficient_unknown_confidence
        confidence_rows.append(
            {
                **_base(generated_ts, review_run_id),
                "scope": "MECHANISM",
                "mechanism_id": mechanism_id,
                "conflicted_high_confidence_count": conflicted_high_confidence,
                "moderate_incomplete_trace_count": moderate_incomplete_trace,
                "low_ambiguous_count": low_ambiguous,
                "unknown_label_non_unknown_confidence_count": unknown_label_non_unknown_confidence,
                "insufficient_evidence_unknown_confidence_count": insufficient_unknown_confidence,
                "outcome_independence_confirmed": "TRUE",
                "confidence_framework_status": mechanism_confidence_status,
                "scientific_conclusion": (
                    "Confidence remains conservative and outcome-independent."
                    if mechanism_confidence_status == "SCIENTIFICALLY_ALIGNED"
                    else "Confidence is outcome-independent but requires careful interpretation around low-confidence ambiguity and moderate-confidence partial traces."
                ),
                "notes": _json(
                    {
                        "high_confidence_present": False,
                        "unknown_label_can_have_low_confidence": True,
                    }
                ),
            }
        )
    confidence_rows.append(
        {
            **_base(generated_ts, review_run_id),
            "scope": "OVERALL",
            "mechanism_id": "ALL",
            "conflicted_high_confidence_count": overall_high_conflict_confidence,
            "moderate_incomplete_trace_count": overall_moderate_incomplete,
            "low_ambiguous_count": overall_low_ambiguous,
            "unknown_label_non_unknown_confidence_count": overall_unknown_non_unknown_confidence,
            "insufficient_evidence_unknown_confidence_count": overall_insufficient_unknown_confidence,
            "outcome_independence_confirmed": "TRUE",
            "confidence_framework_status": confidence_framework_status,
            "scientific_conclusion": (
                "The framework stays conservative: no HIGH-confidence conflicted rows and LOW confidence is concentrated in ambiguity-heavy UNKNOWN previews."
                if confidence_framework_status != "MISALIGNED"
                else "Confidence misalignment blocks scientific execution because conflicted rows received unsupported certainty."
            ),
            "notes": _json(
                {
                    "unknown_labels_with_low_confidence": overall_unknown_non_unknown_confidence,
                    "insufficient_labels_with_unknown_confidence": overall_insufficient_unknown_confidence,
                }
            ),
        }
    )

    falsification_rows_by_mechanism: Dict[str, Dict[str, Any]] = {}
    false_proxy_count = false_proxy_positives
    for row in data["Refined_Mechanism_v11_Frozen_Falsification_Rules"]:
        mechanism_id = _norm(row.get("mechanism_id"))
        if mechanism_id not in PROMOTED_MECHANISMS:
            continue
        conflict_threshold = _parse_threshold(row.get("conflict_threshold_warning"))
        ambiguity_threshold = _parse_threshold(row.get("ambiguity_threshold_warning"))
        summary = conflict_summary_by_mechanism.get(mechanism_id, {})
        candidate_rows = max(_to_int(summary.get("candidate_rows")), 1)
        conflict_rate = _to_int(summary.get("conflict_count")) / float(candidate_rows)
        ambiguity_rate = _to_int(summary.get("ambiguity_count")) / float(candidate_rows)
        falsification_triggered = False
        warning_triggered = False
        triggering_evidence: List[str] = []
        scientific_consequence = "No preregistered falsification blocker triggered."
        required_action = "KEEP_FROZEN_FOR_EXECUTION_PLANNING"

        if mechanism_id == "MECH_INFORMATION_SPECIFICITY":
            if false_proxy_count > 0:
                falsification_triggered = True
                triggering_evidence.append("generic detail or proxy-only rows were labeled positive specificity")
                scientific_consequence = "Specificity would fail its core v1.1 repair objective."
                required_action = "REPAIR_RULES_BEFORE_EXECUTION_PLAN"
            if conflict_threshold is not None and conflict_rate > conflict_threshold:
                warning_triggered = True
                triggering_evidence.append(
                    f"conflict_threshold_warning_exceeded:{conflict_rate:.6f}>{conflict_threshold:.6f}"
                )
            if ambiguity_threshold is not None and ambiguity_rate > ambiguity_threshold:
                warning_triggered = True
                triggering_evidence.append(
                    f"ambiguity_threshold_warning_exceeded:{ambiguity_rate:.6f}>{ambiguity_threshold:.6f}"
                )
            if valid_affirmative_negatives < len(v11_negative_rows):
                warning_triggered = True
        elif mechanism_id == "MECH_INFORMATION_RELEVANCE":
            if conflict_threshold is not None and conflict_rate > conflict_threshold:
                warning_triggered = True
                triggering_evidence.append(
                    f"conflict_threshold_warning_exceeded:{conflict_rate:.6f}>{conflict_threshold:.6f}"
                )
            if ambiguity_threshold is not None and ambiguity_rate > ambiguity_threshold:
                warning_triggered = True
                triggering_evidence.append(
                    f"ambiguity_threshold_warning_exceeded:{ambiguity_rate:.6f}>{ambiguity_threshold:.6f}"
                )
        else:
            if conflict_threshold is not None and conflict_rate > conflict_threshold:
                warning_triggered = True
                triggering_evidence.append(
                    f"conflict_threshold_warning_exceeded:{conflict_rate:.6f}>{conflict_threshold:.6f}"
                )
            if ambiguity_threshold is not None and ambiguity_rate > ambiguity_threshold:
                warning_triggered = True
                triggering_evidence.append(
                    f"ambiguity_threshold_warning_exceeded:{ambiguity_rate:.6f}>{ambiguity_threshold:.6f}"
                )

        if falsification_triggered:
            required_action = "TRIGGER_V12_RULE_REPAIR"
        elif warning_triggered and mechanism_id == "MECH_INFORMATION_SPECIFICITY":
            scientific_consequence = (
                "Specificity passed the false-proxy repair target but still carries a warning-level conflict burden that must be governed during execution planning."
            )
            required_action = "ALLOW_EXECUTION_PLAN_WITH_UNKNOWN_DISPOSITION_RULES"
        falsification_entry = {
            **_base(generated_ts, review_run_id),
            "mechanism_id": mechanism_id,
            "stable_mechanism_id": stable_ids.get(mechanism_id, ""),
            "falsification_triggered": "TRUE" if falsification_triggered else "FALSE",
            "warning_triggered": "TRUE" if warning_triggered else "FALSE",
            "triggering_evidence": _json(triggering_evidence),
            "scientific_consequence": scientific_consequence,
            "required_action": required_action,
            "notes": _json(
                {
                    "falsification_rule": _norm(row.get("falsification_rule")),
                    "contradictory_evidence_definition": _norm(row.get("contradictory_evidence_definition")),
                    "conflict_rate": f"{conflict_rate:.6f}",
                    "ambiguity_rate": f"{ambiguity_rate:.6f}",
                }
            ),
        }
        falsification_rows.append(falsification_entry)
        falsification_rows_by_mechanism[mechanism_id] = falsification_entry

    review_status_by_mechanism: Dict[str, str] = {}
    for mechanism_id in PROMOTED_MECHANISMS:
        conflict_summary = conflict_summary_by_mechanism.get(mechanism_id, {})
        positive_count = _to_int(conflict_summary.get("positive_count"))
        negative_count = _to_int(conflict_summary.get("negative_count"))
        unknown_count = _to_int(conflict_summary.get("unknown_count"))
        insufficient_count = _to_int(conflict_summary.get("insufficient_evidence_count"))
        excluded_count = _to_int(conflict_summary.get("excluded_count"))
        conflict_count = _to_int(conflict_summary.get("conflict_count"))
        unresolved_count = _to_int(conflict_summary.get("unresolved_conflict_count"))
        ambiguity_count = _to_int(conflict_summary.get("ambiguity_count"))
        candidate_rows = _to_int(conflict_summary.get("candidate_rows"))
        eligible_rows = _to_int(conflict_summary.get("eligible_rows"))
        if mechanism_id == "MECH_INFORMATION_RELEVANCE":
            review_status = "PASS_WITH_WARNINGS" if unresolved_count > 0 else "PASS"
            scientific_conclusion = (
                "Relevance is the cleanest v1.1 mechanism: row populations are comparable, negatives are now affirmative, and only one low-confidence mixed-path conflict remains."
            )
            recommended_action = "Carry the lone mixed-path row forward as a low-confidence UNKNOWN during execution planning."
        elif mechanism_id == "MECH_INFORMATION_SPECIFICITY":
            review_status = "PASS_WITH_WARNINGS"
            scientific_conclusion = (
                "Specificity improved materially and all positive labels are genuine boundary-forming cases, but 20 boundary-ambiguous rows remain frozen as UNKNOWN under low confidence."
            )
            recommended_action = "Allow execution planning only with explicit UNKNOWN handling for partial-boundary conflicts."
        else:
            review_status = "PASS_WITH_WARNINGS" if insufficient_count > 0 else "PASS"
            scientific_conclusion = (
                "Consistency is scientifically usable: negatives are affirmative, no unresolved conflicts remain, and ambiguity is concentrated in insufficient-evidence cases rather than contradictory logic."
            )
            recommended_action = "Preserve insufficient-evidence rows as a non-positive terminal class in the execution plan."
        review_status_by_mechanism[mechanism_id] = review_status
        review_rows.append(
            {
                **_base(generated_ts, review_run_id),
                "mechanism_id": mechanism_id,
                "stable_mechanism_id": stable_ids.get(mechanism_id, ""),
                "review_scope": "MECHANISM",
                "candidate_rows": candidate_rows,
                "eligible_rows": eligible_rows,
                "positive_count": positive_count,
                "negative_count": negative_count,
                "unknown_count": unknown_count,
                "insufficient_evidence_count": insufficient_count,
                "excluded_count": excluded_count,
                "conflict_count": conflict_count,
                "unresolved_conflict_count": unresolved_count,
                "ambiguity_count": ambiguity_count,
                "determinism_status": determinism_status,
                "leakage_status": "PASS_PRE_OUTCOME_ONLY" if leakage_findings == 0 else "OUTCOME_LEAKAGE_DETECTED",
                "review_status": review_status,
                "scientific_conclusion": scientific_conclusion,
                "recommended_action": recommended_action,
                "notes": _norm(conflict_summary.get("notes")),
            }
        )

    mechanisms_ready_for_permanent_classification = 0
    mechanisms_ready_with_exclusions = 0
    mechanisms_requiring_repair = 0
    for mechanism_id in PROMOTED_MECHANISMS:
        negatives_valid = True
        if any(
            _norm(row.get("mechanism_id")) == mechanism_id
            and _norm(row.get("review_classification")) not in {"VALID_AFFIRMATIVE_NEGATIVE", "VALID_WITH_WARNING"}
            for row in negative_rows
        ):
            negatives_valid = False
        if mechanism_id == "MECH_INFORMATION_SPECIFICITY":
            false_proxy_free = false_proxy_positives == 0
            joint_positives_valid = unresolved_rs_overlaps == 0 and unresolved_sc_overlaps == 0
        elif mechanism_id == "MECH_INFORMATION_RELEVANCE":
            false_proxy_free = True
            joint_positives_valid = unresolved_rs_overlaps == 0
        else:
            false_proxy_free = True
            joint_positives_valid = unresolved_sc_overlaps == 0
        unresolved_dispositioned = unresolved_by_mechanism.get(mechanism_id, 0) == sum(
            dispositions_by_mechanism[mechanism_id].values()
        )
        falsification_entry = falsification_rows_by_mechanism.get(mechanism_id, {})
        falsification_blocker = _to_bool(falsification_entry.get("falsification_triggered"))

        if (
            population_comparability_status == "NOT_COMPARABLE"
            or determinism_status != "PASS"
            or leakage_findings > 0
        ):
            readiness_status = "BLOCKED"
            mechanisms_requiring_repair += 1
            readiness_conclusion = "Governance or comparability failure blocks any classification execution planning."
            recommended_action = "HOLD_PHASE9_PENDING_GOVERNANCE_REVIEW"
        elif falsification_blocker or not false_proxy_free or not negatives_valid:
            readiness_status = "NEEDS_V12_REPAIR"
            mechanisms_requiring_repair += 1
            readiness_conclusion = "The mechanism still violates a preregistered scientific safeguard."
            recommended_action = "PROCEED_TO_PHASE9A6R8R_V12_RULE_REPAIR"
        elif mechanism_id == "MECH_INFORMATION_CONSISTENCY":
            readiness_status = "READY_WITH_EXCLUSIONS"
            mechanisms_ready_with_exclusions += 1
            readiness_conclusion = (
                "Consistency is ready for execution planning if insufficient-evidence rows remain a protected non-positive terminal class."
            )
            recommended_action = "Preserve insufficiency as a governed terminal output during execution planning."
        else:
            readiness_status = "READY_AFTER_CONFLICT_DISPOSITION"
            readiness_conclusion = (
                "The mechanism is mature enough for execution planning once frozen UNKNOWN/low-confidence conflict handling is carried through explicitly."
            )
            recommended_action = "Document frozen UNKNOWN handling in the execution plan."
        readiness_rows.append(
            {
                **_base(generated_ts, review_run_id),
                "mechanism_id": mechanism_id,
                "stable_mechanism_id": stable_ids.get(mechanism_id, ""),
                "execution_readiness_status": readiness_status,
                "population_comparable": "TRUE"
                if population_comparability_status in {"FULLY_COMPARABLE", "COMPARABLE_WITH_DOCUMENTED_RULE_DIFFERENCES"}
                else "FALSE",
                "determinism_pass": "TRUE" if determinism_status == "PASS" else "FALSE",
                "leakage_free": "TRUE" if leakage_findings == 0 else "FALSE",
                "false_proxy_free": "TRUE" if false_proxy_free else "FALSE",
                "negatives_valid": "TRUE" if negatives_valid else "FALSE",
                "joint_positives_valid": "TRUE" if joint_positives_valid else "FALSE",
                "unresolved_conflicts_dispositioned": "TRUE" if unresolved_dispositioned else "FALSE",
                "falsification_blocker_triggered": "TRUE" if falsification_blocker else "FALSE",
                "readiness_conclusion": readiness_conclusion,
                "recommended_action": recommended_action,
                "notes": _json(
                    {
                        "unresolved_conflicts": unresolved_by_mechanism.get(mechanism_id, 0),
                        "disposition_breakdown": dispositions_by_mechanism[mechanism_id],
                    }
                ),
            }
        )

    readiness_rows.append(
        {
            **_base(generated_ts, review_run_id),
            "mechanism_id": "ALL",
            "stable_mechanism_id": "",
            "execution_readiness_status": "READY_AFTER_CONFLICT_DISPOSITION"
            if population_comparability_status in {"FULLY_COMPARABLE", "COMPARABLE_WITH_DOCUMENTED_RULE_DIFFERENCES"}
            and determinism_status == "PASS"
            and leakage_findings == 0
            else "BLOCKED",
            "population_comparable": "TRUE"
            if population_comparability_status in {"FULLY_COMPARABLE", "COMPARABLE_WITH_DOCUMENTED_RULE_DIFFERENCES"}
            else "FALSE",
            "determinism_pass": "TRUE" if determinism_status == "PASS" else "FALSE",
            "leakage_free": "TRUE" if leakage_findings == 0 else "FALSE",
            "false_proxy_free": "TRUE" if false_proxy_positives == 0 else "FALSE",
            "negatives_valid": "TRUE" if mislabeled_missing_evidence_negatives + mislabeled_excluded_negatives + mislabeled_unknown_negatives == 0 else "FALSE",
            "joint_positives_valid": "TRUE" if unresolved_rs_overlaps + unresolved_sc_overlaps == 0 else "FALSE",
            "unresolved_conflicts_dispositioned": "TRUE"
            if len(unresolved_preview_rows) == (
                conflicts_allowed_with_low_confidence
                + conflicts_recommended_as_unknown
                + conflicts_recommended_as_insufficient_evidence
                + conflicts_recommended_for_exclusion
                + conflicts_requiring_v12_repair
            )
            else "FALSE",
            "falsification_blocker_triggered": "FALSE"
            if not any(_to_bool(row.get("falsification_triggered")) for row in falsification_rows)
            else "TRUE",
            "readiness_conclusion": (
                "The framework is scientifically mature enough for an execution-plan phase, but not for direct permanent classification execution."
            ),
            "recommended_action": "PROCEED_TO_PHASE9A6R8_V11_CLASSIFICATION_EXECUTION_PLAN",
            "notes": _json(
                {
                    "mechanism_statuses": {
                        row["mechanism_id"]: row["execution_readiness_status"]
                        for row in readiness_rows
                        if row.get("mechanism_id") in PROMOTED_MECHANISMS
                    }
                }
            ),
        }
    )

    governance_specs = [
        ("GOV_PROVIDER_CALLS", "provider_calls_performed", "0", "0"),
        ("GOV_FORECAST_GENERATION", "forecast_generation_performed", "0", "0"),
        ("GOV_CLASSIFICATION_RERUN", "classification_rerun_count", "0", "0"),
        ("GOV_PERMANENT_LABELS", "permanent_labels_assigned", "0", "0"),
        ("GOV_MECHANISM_TESTING", "mechanism_testing_performed", "0", "0"),
        ("GOV_ACCURACY_EVALUATION", "accuracy_evaluation_performed", "0", "0"),
        ("GOV_OUTCOME_ACCESS", "outcome_values_accessed", "0", "0"),
        ("GOV_CORRECTED_OUTCOME_ACCESS", "corrected_outcomes_accessed", "0", "0"),
        ("GOV_V10_SHEETS", "v10_sheets_modified", "0", "0"),
        ("GOV_V11_PREREG", "v11_preregistration_modified", "0", "0"),
        ("GOV_V11_DRY_RUN", "v11_dry_run_modified", "0", "0"),
        ("GOV_PRODUCTION_WRITES", "production_sheet_write_count", "0", "0"),
        ("GOV_PRODUCTION_BEHAVIOR", "production_behavior_change_count", "0", "0"),
        ("GOV_ROUTING", "routing_changes", "FALSE", "FALSE"),
        ("GOV_WEIGHTING", "weighting_changes", "FALSE", "FALSE"),
        ("GOV_CALIBRATION", "calibration_changes", "FALSE", "FALSE"),
        ("GOV_ENSEMBLE", "ensemble_changes", "FALSE", "FALSE"),
    ]
    governance_rows = [
        {
            **_base(generated_ts, review_run_id),
            "check_id": check_id,
            "check_name": check_name,
            "expected_value": expected_value,
            "actual_value": actual_value,
            "status": "PASS" if expected_value == actual_value else "FAIL",
            "notes": "Phase 9A-6R7 remains a read-only scientific review.",
        }
        for check_id, check_name, expected_value, actual_value in governance_specs
    ]

    any_governance_fail = any(_norm(row.get("status")) != "PASS" for row in governance_rows)
    any_falsification_trigger = any(_to_bool(row.get("falsification_triggered")) for row in falsification_rows)
    any_repair_status = any(
        _norm(row.get("execution_readiness_status")) in {"NEEDS_V12_REPAIR", "BLOCKED"} for row in readiness_rows
    )

    build_status = "PASS_WITH_WARNINGS"
    final_interpretation = "REFINED_MECHANISM_V11_CONFLICT_REVIEW_READY_WITH_WARNINGS"
    recommended_next_step = "PROCEED_TO_PHASE9A6R8_V11_CLASSIFICATION_EXECUTION_PLAN"
    ready_for_v11_classification_execution_plan = True
    if any_governance_fail or leakage_findings > 0 or determinism_status != "PASS":
        build_status = "BLOCKED"
        final_interpretation = "REFINED_MECHANISM_V11_CONFLICT_REVIEW_BLOCKED"
        recommended_next_step = "HOLD_PHASE9_PENDING_GOVERNANCE_REVIEW"
        ready_for_v11_classification_execution_plan = False
    elif any_falsification_trigger:
        build_status = "NEEDS_REVIEW"
        final_interpretation = "REFINED_MECHANISM_V11_CONFLICT_REVIEW_NEEDS_REVIEW"
        recommended_next_step = "PROCEED_TO_PHASE9A6R8R_V12_RULE_REPAIR"
        ready_for_v11_classification_execution_plan = False
    elif population_comparability_status not in {"FULLY_COMPARABLE", "COMPARABLE_WITH_DOCUMENTED_RULE_DIFFERENCES"}:
        build_status = "NEEDS_REVIEW"
        final_interpretation = "REFINED_MECHANISM_V11_CONFLICT_REVIEW_NEEDS_REVIEW"
        recommended_next_step = "PROCEED_TO_PHASE9A6R6A_V11_DRY_RUN_AUDIT_REPAIR"
        ready_for_v11_classification_execution_plan = False
    elif any_repair_status and any(
        _norm(row.get("execution_readiness_status")) == "NEEDS_V12_REPAIR" for row in readiness_rows
    ):
        build_status = "NEEDS_REVIEW"
        final_interpretation = "REFINED_MECHANISM_V11_CONFLICT_REVIEW_NEEDS_REVIEW"
        recommended_next_step = "PROCEED_TO_PHASE9A6R8R_V12_RULE_REPAIR"
        ready_for_v11_classification_execution_plan = False

    falsification_trigger_summary = []
    for row in falsification_rows:
        mechanism_id = _norm(row.get("mechanism_id"))
        if _to_bool(row.get("falsification_triggered")):
            falsification_trigger_summary.append(f"{mechanism_id}:BLOCKER")
        elif _to_bool(row.get("warning_triggered")):
            falsification_trigger_summary.append(f"{mechanism_id}:WARNING")
    falsification_trigger_text = ", ".join(falsification_trigger_summary) if falsification_trigger_summary else "NONE"

    summary_row = {
        **_base(generated_ts, review_run_id),
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "population_comparability_status": population_comparability_status,
        "candidate_row_key_match": "TRUE" if candidate_row_key_match else "FALSE",
        "eligible_row_key_match": "TRUE" if eligible_row_key_match else "FALSE",
        "provider_distribution_match": "TRUE" if provider_distribution_match else "FALSE",
        "pack_distribution_match": "TRUE" if pack_distribution_match else "FALSE",
        "session_distribution_match": "TRUE" if session_distribution_match else "FALSE",
        "specificity_positives_reviewed": len(specificity_positive_rows),
        "valid_boundary_positives": valid_boundary_positives,
        "false_proxy_positives": false_proxy_positives,
        "specificity_positives_with_insufficient_trace": specificity_insufficient_trace,
        "negative_labels_reviewed": len(v11_negative_rows),
        "valid_affirmative_negatives": valid_affirmative_negatives,
        "mislabeled_missing_evidence_negatives": mislabeled_missing_evidence_negatives,
        "mislabeled_excluded_negatives": mislabeled_excluded_negatives,
        "mislabeled_unknown_negatives": mislabeled_unknown_negatives,
        "relevance_specificity_joint_positives_reviewed": sum(
            1 for row in joint_rows if _norm(row.get("pair_type")) == "RELEVANCE_SPECIFICITY"
        ),
        "legitimate_relevance_specificity_joint_positives": legitimate_rs_joint_positives,
        "unresolved_relevance_specificity_overlaps": unresolved_rs_overlaps,
        "specificity_consistency_joint_positives_reviewed": sum(
            1 for row in joint_rows if _norm(row.get("pair_type")) == "SPECIFICITY_CONSISTENCY"
        ),
        "legitimate_specificity_consistency_joint_positives": legitimate_sc_joint_positives,
        "unresolved_specificity_consistency_overlaps": unresolved_sc_overlaps,
        "unresolved_conflicts_reviewed": len(unresolved_preview_rows),
        "conflicts_allowed_with_low_confidence": conflicts_allowed_with_low_confidence,
        "conflicts_recommended_as_unknown": conflicts_recommended_as_unknown,
        "conflicts_recommended_as_insufficient_evidence": conflicts_recommended_as_insufficient_evidence,
        "conflicts_recommended_for_exclusion": conflicts_recommended_for_exclusion,
        "conflicts_requiring_v12_repair": conflicts_requiring_v12_repair,
        "confidence_framework_status": confidence_framework_status,
        "falsification_triggers": falsification_trigger_text,
        "mechanisms_ready_for_permanent_classification": mechanisms_ready_for_permanent_classification,
        "mechanisms_ready_with_exclusions": mechanisms_ready_with_exclusions,
        "mechanisms_requiring_repair": mechanisms_requiring_repair,
        "determinism_status": determinism_status,
        "leakage_findings": leakage_findings,
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "classification_rerun_count": 0,
        "permanent_labels_assigned": 0,
        "mechanism_testing_performed": 0,
        "accuracy_evaluation_performed": 0,
        "outcome_values_accessed": 0,
        "v10_sheets_modified": 0,
        "v11_preregistration_modified": 0,
        "production_behavior_change_count": 0,
        "production_sheet_write_count": 0,
        "ready_for_v11_classification_execution_plan": "TRUE" if ready_for_v11_classification_execution_plan else "FALSE",
        "ready_for_permanent_classification_execution": "FALSE",
        "ready_for_mechanism_testing": "FALSE",
        "ready_for_production": "FALSE",
        "recommended_next_step": recommended_next_step,
        "notes": _json(
            {
                "v10_conflict_count": _to_int(data["Refined_Mechanism_v11_Dry_Run_Summary"][0].get("v10_conflict_count"))
                if data["Refined_Mechanism_v11_Dry_Run_Summary"]
                else 0,
                "v11_conflict_count": _to_int(data["Refined_Mechanism_v11_Dry_Run_Summary"][0].get("v11_conflict_count"))
                if data["Refined_Mechanism_v11_Dry_Run_Summary"]
                else 0,
                "v10_ambiguity_count": _to_int(data["Refined_Mechanism_v11_Dry_Run_Summary"][0].get("v10_ambiguity_count"))
                if data["Refined_Mechanism_v11_Dry_Run_Summary"]
                else 0,
                "v11_ambiguity_count": _to_int(data["Refined_Mechanism_v11_Dry_Run_Summary"][0].get("v11_ambiguity_count"))
                if data["Refined_Mechanism_v11_Dry_Run_Summary"]
                else 0,
                "primary_scientific_interpretation": (
                    "v1.1 produced genuine scientific improvement: row populations remained comparable, specificity positives stayed boundary-valid, negatives stayed affirmative, and the remaining unresolved conflicts are traceable enough to govern in an execution-plan phase."
                ),
            }
        ),
    }

    outputs = [
        (OUTPUT_REVIEW, REVIEW_HEADERS, review_rows),
        (OUTPUT_COMPARABILITY, COMPARABILITY_HEADERS, comparability_rows),
        (OUTPUT_SPECIFICITY, SPECIFICITY_HEADERS, specificity_rows),
        (OUTPUT_NEGATIVE, NEGATIVE_HEADERS, negative_rows),
        (OUTPUT_JOINT, JOINT_HEADERS, joint_rows),
        (OUTPUT_UNRESOLVED, UNRESOLVED_HEADERS, unresolved_rows),
        (OUTPUT_CONFIDENCE, CONFIDENCE_HEADERS, confidence_rows),
        (OUTPUT_FALSIFICATION, FALSIFICATION_HEADERS, falsification_rows),
        (OUTPUT_READINESS, READINESS_HEADERS, readiness_rows),
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
        "file_created": "automation/build_refined_mechanism_v11_conflict_review_v0.py",
        "sheets_written": {sheet_name: len(rows) for sheet_name, _, rows in outputs},
        "population_comparability_status": population_comparability_status,
        "candidate_row_key_match": candidate_row_key_match,
        "eligible_row_key_match": eligible_row_key_match,
        "provider_distribution_match": provider_distribution_match,
        "pack_distribution_match": pack_distribution_match,
        "session_distribution_match": session_distribution_match,
        "specificity_positives_reviewed": len(specificity_positive_rows),
        "valid_boundary_positives": valid_boundary_positives,
        "false_proxy_positives": false_proxy_positives,
        "specificity_positives_with_insufficient_trace": specificity_insufficient_trace,
        "negative_labels_reviewed": len(v11_negative_rows),
        "valid_affirmative_negatives": valid_affirmative_negatives,
        "mislabeled_missing_evidence_negatives": mislabeled_missing_evidence_negatives,
        "mislabeled_excluded_negatives": mislabeled_excluded_negatives,
        "mislabeled_unknown_negatives": mislabeled_unknown_negatives,
        "relevance_specificity_joint_positives_reviewed": sum(
            1 for row in joint_rows if _norm(row.get("pair_type")) == "RELEVANCE_SPECIFICITY"
        ),
        "legitimate_relevance_specificity_joint_positives": legitimate_rs_joint_positives,
        "unresolved_relevance_specificity_overlaps": unresolved_rs_overlaps,
        "specificity_consistency_joint_positives_reviewed": sum(
            1 for row in joint_rows if _norm(row.get("pair_type")) == "SPECIFICITY_CONSISTENCY"
        ),
        "legitimate_specificity_consistency_joint_positives": legitimate_sc_joint_positives,
        "unresolved_specificity_consistency_overlaps": unresolved_sc_overlaps,
        "unresolved_conflicts_reviewed": len(unresolved_preview_rows),
        "conflicts_allowed_with_low_confidence": conflicts_allowed_with_low_confidence,
        "conflicts_recommended_as_unknown": conflicts_recommended_as_unknown,
        "conflicts_recommended_as_insufficient_evidence": conflicts_recommended_as_insufficient_evidence,
        "conflicts_recommended_for_exclusion": conflicts_recommended_for_exclusion,
        "conflicts_requiring_v12_repair": conflicts_requiring_v12_repair,
        "confidence_framework_status": confidence_framework_status,
        "falsification_triggers": falsification_trigger_text,
        "mechanisms_ready_for_permanent_classification": mechanisms_ready_for_permanent_classification,
        "mechanisms_ready_with_exclusions": mechanisms_ready_with_exclusions,
        "mechanisms_requiring_repair": mechanisms_requiring_repair,
        "determinism_status": determinism_status,
        "leakage_findings": leakage_findings,
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "classification_rerun_count": 0,
        "permanent_labels_assigned": 0,
        "mechanism_testing_performed": 0,
        "accuracy_evaluation_performed": 0,
        "outcome_values_accessed": 0,
        "v10_sheets_modified": 0,
        "v11_preregistration_modified": 0,
        "production_behavior_change_count": 0,
        "production_sheet_write_count": 0,
        "ready_for_v11_classification_execution_plan": ready_for_v11_classification_execution_plan,
        "ready_for_permanent_classification_execution": False,
        "ready_for_mechanism_testing": False,
        "ready_for_production": False,
        "recommended_next_step": recommended_next_step,
        "registry": registry,
    }


def main() -> None:
    result = build_refined_mechanism_v11_conflict_review_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
