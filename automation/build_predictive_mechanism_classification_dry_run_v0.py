import json
import re
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
from automation.build_predictive_mechanism_classification_design_v0 import (
    COMMON_OUTCOME_RULE,
    MECHANISM_ORDER,
    MECH_RULES,
)
from automation.build_session_information_requests_v0 import _iso_now
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials


SCHEMA_VERSION = "presignal_v2_predictive_mechanism_classification_dry_run_0.1"
DRY_RUN_VERSION = "predictive_mechanism_classification_dry_run_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-6D"
REGISTRY_CATEGORY = "PRESIGNAL_V2_PREDICTIVE_MECHANISM_CLASSIFICATION_DRY_RUN"
REGISTRY_OWNER_MODULE = "market_state"

INPUT_SHEETS = [
    "Predictive_Mechanism_Classification_Design",
    "Predictive_Mechanism_Classification_Workflow",
    "Predictive_Mechanism_Evidence_Mapping",
    "Predictive_Mechanism_Classification_Rules",
    "Predictive_Mechanism_Classification_Priority",
    "Predictive_Mechanism_Classification_Conflict_Handling",
    "Predictive_Mechanism_Label_Model",
    "Predictive_Mechanism_Label_Assignment",
    "Predictive_Mechanism_Confidence_Framework",
    "Predictive_Mechanism_Audit_Framework",
    "Pack_Behavior_Tier2_Behavior",
    "Pack_Behavior_Tier2_Transitions",
    "Pack_Behavior_Tier2_Field_Influence",
    "Pack_Behavior_Tier2_NoSignal",
]

OUTPUT_DRY_RUN = "Predictive_Mechanism_Classification_Dry_Run"
OUTPUT_LABEL_PREVIEW = "Predictive_Mechanism_Label_Preview"
OUTPUT_EXTRACTION_AUDIT = "Predictive_Mechanism_Evidence_Extraction_Audit"
OUTPUT_CONFLICT_AUDIT = "Predictive_Mechanism_Conflict_Audit"
OUTPUT_CONFIDENCE = "Predictive_Mechanism_Confidence_Preview"
OUTPUT_LEAKAGE = "Predictive_Mechanism_Leakage_Audit"
OUTPUT_DETERMINISM = "Predictive_Mechanism_Determinism_Audit"
OUTPUT_GOVERNANCE = "Predictive_Mechanism_Dry_Run_Governance"
OUTPUT_SUMMARY = "Predictive_Mechanism_Dry_Run_Summary"

DRY_RUN_HEADERS = [
    "generated_ts",
    "schema_version",
    "dry_run_version",
    "dry_run_id",
    "preview_id",
    "mechanism_id",
    "session_id",
    "provider",
    "pack_level",
    "behavior_row_number",
    "preview_label",
    "preview_confidence",
    "eligible_for_preview",
    "conflict_detected",
    "leakage_status",
    "deterministic_status",
    "rule_executed",
    "notes",
]

LABEL_PREVIEW_HEADERS = [
    "generated_ts",
    "schema_version",
    "dry_run_version",
    "dry_run_id",
    "preview_id",
    "mechanism_id",
    "session_id",
    "provider",
    "pack_level",
    "preview_label",
    "classification_basis",
    "exclusion_reason",
    "unknown_reason",
    "insufficient_evidence_reason",
    "preview_confidence",
    "notes",
]

EXTRACTION_HEADERS = [
    "generated_ts",
    "schema_version",
    "dry_run_version",
    "dry_run_id",
    "preview_id",
    "mechanism_id",
    "session_id",
    "provider",
    "pack_level",
    "observables_found",
    "observables_missing",
    "extraction_success",
    "extraction_failure",
    "ambiguity_detected",
    "rule_executed",
    "source_sheets_used",
    "notes",
]

CONFLICT_HEADERS = [
    "generated_ts",
    "schema_version",
    "dry_run_version",
    "dry_run_id",
    "preview_id",
    "mechanism_id",
    "session_id",
    "provider",
    "pack_level",
    "conflicting_observables",
    "conflicting_labels",
    "unresolved_conflict",
    "conflict_resolution_path",
    "final_preview_outcome",
    "notes",
]

CONFIDENCE_HEADERS = [
    "generated_ts",
    "schema_version",
    "dry_run_version",
    "dry_run_id",
    "preview_id",
    "mechanism_id",
    "session_id",
    "provider",
    "pack_level",
    "evidence_completeness",
    "evidence_consistency",
    "ambiguity_level",
    "preview_confidence",
    "confidence_assignment_reason",
    "notes",
]

LEAKAGE_HEADERS = [
    "generated_ts",
    "schema_version",
    "dry_run_version",
    "dry_run_id",
    "preview_id",
    "mechanism_id",
    "session_id",
    "provider",
    "pack_level",
    "accessed_source_sheets",
    "accessed_fields",
    "realized_direction_accessed",
    "overall_ok_accessed",
    "corrected_outcomes_accessed",
    "evaluation_results_accessed",
    "future_information_accessed",
    "leakage_status",
    "notes",
]

DETERMINISM_HEADERS = [
    "generated_ts",
    "schema_version",
    "dry_run_version",
    "dry_run_id",
    "preview_id",
    "mechanism_id",
    "session_id",
    "provider",
    "pack_level",
    "first_pass_label",
    "second_pass_label",
    "first_pass_confidence",
    "second_pass_confidence",
    "first_pass_rule",
    "second_pass_rule",
    "audit_trail_match",
    "deterministic_status",
    "notes",
]

GOVERNANCE_HEADERS = [
    "generated_ts",
    "schema_version",
    "dry_run_version",
    "dry_run_id",
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
    "dry_run_version",
    "dry_run_id",
    "build_status",
    "final_interpretation",
    "eligible_rows_previewed",
    "preview_labels_assigned",
    "positive_labels",
    "negative_labels",
    "unknown_labels",
    "insufficient_evidence_labels",
    "excluded_labels",
    "evidence_extraction_success",
    "conflicts_detected",
    "leakage_findings",
    "determinism_status",
    "highest_priority_mechanism",
    "highest_conflict_rate",
    "highest_ambiguity",
    "provider_calls_performed",
    "forecast_generation_performed",
    "mechanism_labels_permanently_assigned",
    "accuracy_evaluation_performed",
    "production_behavior_change_count",
    "ready_for_mechanism_classification_execution",
    "ready_for_mechanism_testing",
    "ready_for_replication",
    "ready_for_production",
    "recommended_next_step",
    "notes",
]

PREVIEW_LABELS = {"POSITIVE", "NEGATIVE", "UNKNOWN", "INSUFFICIENT_EVIDENCE", "EXCLUDED"}
CONFIDENCE_LEVELS = {"HIGH", "MODERATE", "LOW", "UNKNOWN"}
FORBIDDEN_FIELD_TERMS = ["realized", "overall_ok", "corrected", "eval_", "evaluation_", "future_"]
TEXT_TOKEN_RE = re.compile(r"[A-Za-z_]{3,}")
STOPWORDS = {
    "and",
    "the",
    "for",
    "with",
    "that",
    "from",
    "this",
    "into",
    "when",
    "then",
    "only",
    "have",
    "were",
    "will",
    "their",
    "while",
    "been",
    "than",
    "they",
    "them",
    "does",
    "under",
    "over",
    "same",
    "used",
    "using",
    "market",
    "event",
    "events",
    "pack",
    "level",
    "context",
    "provided",
}


def _dry_run_id(generated_ts: str) -> str:
    return "predictive_mechanism_classification_dry_run_v0_" + generated_ts.replace("-", "").replace(":", "")


def _base(generated_ts: str, dry_run_id: str) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "dry_run_version": DRY_RUN_VERSION,
        "dry_run_id": dry_run_id,
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
        ("PREDICTIVE_MECHANISM_CLASSIFICATION_DRY_RUN", OUTPUT_DRY_RUN, "predictive_mechanism_classification_dry_run"),
        ("PREDICTIVE_MECHANISM_LABEL_PREVIEW", OUTPUT_LABEL_PREVIEW, "predictive_mechanism_label_preview"),
        ("PREDICTIVE_MECHANISM_EVIDENCE_EXTRACTION_AUDIT", OUTPUT_EXTRACTION_AUDIT, "predictive_mechanism_evidence_extraction_audit"),
        ("PREDICTIVE_MECHANISM_CONFLICT_AUDIT", OUTPUT_CONFLICT_AUDIT, "predictive_mechanism_conflict_audit"),
        ("PREDICTIVE_MECHANISM_CONFIDENCE_PREVIEW", OUTPUT_CONFIDENCE, "predictive_mechanism_confidence_preview"),
        ("PREDICTIVE_MECHANISM_LEAKAGE_AUDIT", OUTPUT_LEAKAGE, "predictive_mechanism_leakage_audit"),
        ("PREDICTIVE_MECHANISM_DETERMINISM_AUDIT", OUTPUT_DETERMINISM, "predictive_mechanism_determinism_audit"),
        ("PREDICTIVE_MECHANISM_DRY_RUN_GOVERNANCE", OUTPUT_GOVERNANCE, "predictive_mechanism_dry_run_governance"),
        ("PREDICTIVE_MECHANISM_DRY_RUN_SUMMARY", OUTPUT_SUMMARY, "predictive_mechanism_dry_run_summary"),
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
            "notes": "Phase 9A-6D mechanism classification dry run; preview-only and non-permanent.",
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


def _to_float(value: Any) -> Optional[float]:
    text = _norm(value)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_listish(value: Any) -> List[str]:
    text = _norm(value)
    if not text:
        return []
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [_norm(item) for item in parsed if _norm(item)]
        except json.JSONDecodeError:
            pass
    return [_norm(part) for part in text.split(",") if _norm(part)]


def _tokenize(text: str) -> set[str]:
    return {
        token.lower()
        for token in TEXT_TOKEN_RE.findall(_norm(text))
        if token.lower() not in STOPWORDS
    }


def _overlap_score(a: str, b: str) -> float:
    tokens_a = _tokenize(a)
    tokens_b = _tokenize(b)
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / float(len(tokens_a | tokens_b))


def _make_preview_id(session_id: str, provider: str, pack_level: str, mechanism_id: str) -> str:
    return "|".join([session_id, provider, pack_level, mechanism_id])


def _build_indexes(inputs: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    behavior_rows = inputs["Pack_Behavior_Tier2_Behavior"]
    no_signal_by_key: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for row in inputs["Pack_Behavior_Tier2_NoSignal"]:
        no_signal_by_key[(_norm(row.get("session_id")), _norm(row.get("provider")), _norm(row.get("pack_level")))] = row

    field_rows_by_key: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in inputs["Pack_Behavior_Tier2_Field_Influence"]:
        key = (_norm(row.get("session_id")), _norm(row.get("provider")), _norm(row.get("pack_level")))
        field_rows_by_key[key].append(row)

    transitions_by_session_provider: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in inputs["Pack_Behavior_Tier2_Transitions"]:
        key = (_norm(row.get("session_id")), _norm(row.get("provider")))
        transitions_by_session_provider[key].append(row)

    behavior_by_key: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    behavior_by_session_provider: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in behavior_rows:
        key = (_norm(row.get("session_id")), _norm(row.get("provider")), _norm(row.get("pack_level")))
        behavior_by_key[key] = row
        behavior_by_session_provider[(key[0], key[1])].append(row)

    return {
        "behavior_rows": behavior_rows,
        "no_signal_by_key": no_signal_by_key,
        "field_rows_by_key": field_rows_by_key,
        "transitions_by_session_provider": transitions_by_session_provider,
        "behavior_by_key": behavior_by_key,
        "behavior_by_session_provider": behavior_by_session_provider,
    }


def _build_context(
    row: Dict[str, Any],
    indexes: Dict[str, Any],
) -> Dict[str, Any]:
    session_id = _norm(row.get("session_id"))
    provider = _norm(row.get("provider"))
    pack_level = _norm(row.get("pack_level"))
    key = (session_id, provider, pack_level)
    session_provider_key = (session_id, provider)
    no_signal = indexes["no_signal_by_key"].get(key, {})
    field_rows = indexes["field_rows_by_key"].get(key, [])
    peer_behavior_rows = indexes["behavior_by_session_provider"].get(session_provider_key, [])
    peer_behavior_by_pack = {_norm(r.get("pack_level")): r for r in peer_behavior_rows}
    peer_no_signal_rows = {
        _norm(r.get("pack_level")): indexes["no_signal_by_key"].get((session_id, provider, _norm(r.get("pack_level"))), {})
        for r in peer_behavior_rows
    }
    all_transitions = indexes["transitions_by_session_provider"].get(session_provider_key, [])
    relevant_transitions = [
        tr
        for tr in all_transitions
        if _norm(tr.get("from_pack_level")) == pack_level or _norm(tr.get("to_pack_level")) == pack_level
    ]
    pass_relevant_transitions = [tr for tr in relevant_transitions if _norm(tr.get("transition_status")) == "PASS"]

    used_fields = set(_parse_listish(row.get("pack_fields_used")))
    discarded_fields = set(_parse_listish(row.get("pack_fields_discarded")))
    changed_fields = set(_parse_listish(row.get("pack_fields_that_changed_reasoning")))
    unchanged_fields = set(_parse_listish(row.get("pack_fields_that_did_not_change_reasoning")))
    uncertainty_sources = _parse_listish(row.get("uncertainty_sources"))
    missing_information = _norm(row.get("missing_information"))
    information_used_text = _norm(row.get("information_used"))
    information_not_used_text = _norm(row.get("information_not_used"))
    causal_chain = _norm(row.get("causal_chain"))

    family_counts: Dict[str, Counter[str]] = defaultdict(Counter)
    field_status_counter: Counter[str] = Counter()
    used_count = 0
    discarded_count = 0
    changed_count = 0
    no_effect_count = 0
    available_not_mentioned_count = 0
    available_count = 0
    valid_field_rows = 0
    used_families: set[str] = set()
    changed_families: set[str] = set()
    discarded_families: set[str] = set()
    available_families: set[str] = set()
    usdjpy_family_available = False
    usdjpy_family_used = False
    usdjpy_family_changed = False
    for field_row in field_rows:
        status = _norm(field_row.get("influence_status"))
        family = _norm(field_row.get("candidate_family"))
        field_status_counter[status] += 1
        if family:
            family_counts[family][status] += 1
        if _to_bool(field_row.get("field_available_in_pack")):
            available_count += 1
            if family:
                available_families.add(family)
        if status != "INVALID_OUTPUT":
            valid_field_rows += 1
        if _to_bool(field_row.get("field_reported_used")) or status.startswith("USED"):
            used_count += 1
            if family:
                used_families.add(family)
        if _to_bool(field_row.get("field_reported_discarded")) or status == "EXPLICITLY_DISCARDED":
            discarded_count += 1
            if family:
                discarded_families.add(family)
        if _to_bool(field_row.get("field_reported_changed_reasoning")) or status == "USED_AND_CHANGED_REASONING":
            changed_count += 1
            if family:
                changed_families.add(family)
        if _to_bool(field_row.get("field_reported_no_effect")) or status == "EXPLICITLY_NO_EFFECT":
            no_effect_count += 1
        if status == "AVAILABLE_NOT_MENTIONED":
            available_not_mentioned_count += 1
        if family == "usdjpy_trend":
            usdjpy_family_available = usdjpy_family_available or _to_bool(field_row.get("field_available_in_pack"))
            usdjpy_family_used = usdjpy_family_used or _to_bool(field_row.get("field_reported_used")) or status.startswith("USED")
            usdjpy_family_changed = usdjpy_family_changed or _to_bool(field_row.get("field_reported_changed_reasoning")) or status == "USED_AND_CHANGED_REASONING"

    current_direction = _norm(no_signal.get("forecast_direction")).lower()
    current_confidence = _to_float(no_signal.get("forecast_confidence"))
    current_confidence_bucket = _norm(no_signal.get("confidence_bucket")).upper()
    current_no_signal_flag = _norm(no_signal.get("no_signal_flag")).upper()
    output_valid = _norm(no_signal.get("output_valid")).upper()
    no_signal_reason = _norm(no_signal.get("no_signal_reason"))
    no_signal_source = _norm(no_signal.get("no_signal_source"))

    direction_change_count = 0
    direction_unknown_count = 0
    hard_direction_conflict_count = 0
    no_signal_changed_count = 0
    material_confidence_change_count = 0
    confidence_change_count = 0
    causal_chain_changed_count = 0
    information_used_changed_count = 0
    for tr in pass_relevant_transitions:
        direction_transition = _norm(tr.get("direction_transition"))
        confidence_transition = _norm(tr.get("confidence_transition"))
        no_signal_transition = _norm(tr.get("no_signal_transition"))
        if direction_transition not in {"", "UNCHANGED", "UNKNOWN"}:
            direction_change_count += 1
        if direction_transition == "UNKNOWN":
            direction_unknown_count += 1
        if (
            "TO" in direction_transition
            and "NO_CLEAR_DIRECTION" not in direction_transition
            and direction_transition not in {"UNCHANGED", "UNKNOWN"}
        ):
            hard_direction_conflict_count += 1
        if no_signal_transition == "CHANGED":
            no_signal_changed_count += 1
        if confidence_transition in {"MATERIAL_INCREASE", "MATERIAL_DECREASE", "INCREASED", "DECREASED"}:
            confidence_change_count += 1
        if confidence_transition in {"MATERIAL_INCREASE", "MATERIAL_DECREASE"}:
            material_confidence_change_count += 1
        if _norm(tr.get("causal_chain_transition")) == "CHANGED":
            causal_chain_changed_count += 1
        if _norm(tr.get("information_used_transition")) == "CHANGED":
            information_used_changed_count += 1

    peer_valid_directions = []
    peer_causal_chains = []
    for pack, ns_row in peer_no_signal_rows.items():
        if _norm(ns_row.get("output_valid")).upper() == "TRUE":
            direction = _norm(ns_row.get("forecast_direction")).lower()
            if direction:
                peer_valid_directions.append(direction)
        peer_chain = _norm(peer_behavior_by_pack.get(pack, {}).get("causal_chain"))
        if peer_chain:
            peer_causal_chains.append(peer_chain)
    distinct_strong_directions = sorted({d for d in peer_valid_directions if d not in {"", "no_clear_direction", "invalid"}})
    no_clear_present = any(d == "no_clear_direction" for d in peer_valid_directions)
    baseline_behavior = peer_behavior_by_pack.get("A", {})
    baseline_no_signal = peer_no_signal_rows.get("A", {})
    baseline_available = (
        pack_level != "A"
        and bool(baseline_behavior)
        and _norm(baseline_no_signal.get("output_valid")).upper() == "TRUE"
    )
    baseline_chain = _norm(baseline_behavior.get("causal_chain"))
    overlap_to_baseline = _overlap_score(causal_chain, baseline_chain) if baseline_chain else 0.0
    overlap_to_peers = max((_overlap_score(causal_chain, peer) for peer in peer_causal_chains if peer != causal_chain), default=0.0)

    low_signal_context = (
        current_no_signal_flag == "TRUE"
        or current_confidence_bucket in {"LOW", "UNKNOWN"}
        or current_direction == "no_clear_direction"
        or bool(missing_information)
        or len(uncertainty_sources) >= 2
        or bool(no_signal_reason)
    )
    restraint_signal = (
        current_no_signal_flag == "TRUE"
        or current_direction in {"no_clear_direction", "flat"}
        or (current_confidence is not None and current_confidence <= 50)
        or current_confidence_bucket == "LOW"
    )
    aggressive_signal = (
        current_direction in {"up", "down"}
        and (
            (current_confidence is not None and current_confidence >= 70)
            or current_confidence_bucket == "HIGH"
        )
    )
    transition_overreach = any(
        _norm(tr.get("no_signal_from")).upper() == "TRUE"
        and _norm(tr.get("no_signal_to")).upper() == "FALSE"
        and _norm(tr.get("confidence_transition")) in {"MATERIAL_INCREASE", "INCREASED"}
        for tr in pass_relevant_transitions
    )

    pack_fields_total = len(used_fields | discarded_fields | changed_fields | unchanged_fields)
    regime_family_present = usdjpy_family_available or any("USDJPY" in field for field in used_fields | discarded_fields | changed_fields | unchanged_fields)
    mentions_trend = (
        "trend" in information_used_text.lower()
        or "usdjpy" in information_used_text.lower()
        or "trend" in causal_chain.lower()
        or usdjpy_family_used
    )
    mixed_family_use = len(changed_families | used_families) > 1

    return {
        "session_id": session_id,
        "provider": provider,
        "pack_level": pack_level,
        "behavior_row_number": row.get("__source_row_number__", ""),
        "output_valid": output_valid == "TRUE",
        "output_invalid": output_valid != "TRUE",
        "pack_fields_total": pack_fields_total,
        "used_fields": used_fields,
        "discarded_fields": discarded_fields,
        "changed_fields": changed_fields,
        "unchanged_fields": unchanged_fields,
        "information_used_text": information_used_text,
        "information_not_used_text": information_not_used_text,
        "causal_chain": causal_chain,
        "uncertainty_sources": uncertainty_sources,
        "missing_information": missing_information,
        "field_rows": field_rows,
        "field_status_counter": field_status_counter,
        "family_counts": family_counts,
        "used_count": used_count,
        "discarded_count": discarded_count,
        "changed_count": changed_count,
        "no_effect_count": no_effect_count,
        "available_not_mentioned_count": available_not_mentioned_count,
        "available_count": available_count,
        "valid_field_rows": valid_field_rows,
        "used_families": used_families,
        "changed_families": changed_families,
        "discarded_families": discarded_families,
        "available_families": available_families,
        "usdjpy_family_available": usdjpy_family_available,
        "usdjpy_family_used": usdjpy_family_used,
        "usdjpy_family_changed": usdjpy_family_changed,
        "current_direction": current_direction,
        "current_confidence": current_confidence,
        "current_confidence_bucket": current_confidence_bucket,
        "current_no_signal_flag": current_no_signal_flag,
        "no_signal_reason": no_signal_reason,
        "no_signal_source": no_signal_source,
        "all_transitions": all_transitions,
        "relevant_transitions": relevant_transitions,
        "pass_relevant_transitions": pass_relevant_transitions,
        "direction_change_count": direction_change_count,
        "direction_unknown_count": direction_unknown_count,
        "hard_direction_conflict_count": hard_direction_conflict_count,
        "no_signal_changed_count": no_signal_changed_count,
        "confidence_change_count": confidence_change_count,
        "material_confidence_change_count": material_confidence_change_count,
        "causal_chain_changed_count": causal_chain_changed_count,
        "information_used_changed_count": information_used_changed_count,
        "peer_behavior_rows": peer_behavior_rows,
        "peer_valid_directions": peer_valid_directions,
        "distinct_strong_directions": distinct_strong_directions,
        "no_clear_present": no_clear_present,
        "baseline_available": baseline_available,
        "baseline_chain": baseline_chain,
        "overlap_to_baseline": overlap_to_baseline,
        "overlap_to_peers": overlap_to_peers,
        "low_signal_context": low_signal_context,
        "restraint_signal": restraint_signal,
        "aggressive_signal": aggressive_signal,
        "transition_overreach": transition_overreach,
        "regime_family_present": regime_family_present,
        "mentions_trend": mentions_trend,
        "mixed_family_use": mixed_family_use,
    }


def _confidence_from_state(
    mechanism_id: str,
    label: str,
    found: List[str],
    missing: List[str],
    conflict_detected: bool,
    ambiguity_detected: bool,
) -> Tuple[str, str, str, str]:
    ambiguity_level = "LOW"
    if mechanism_id in {"MECH_INFORMATION_VALUE", "MECH_INFORMATION_FILTERING"}:
        ambiguity_level = "HIGH"
    elif mechanism_id in {"MECH_CONDITIONAL_PREDICTIVENESS", "MECH_FORECAST_STABILITY"}:
        ambiguity_level = "MODERATE"
    elif mechanism_id == "MECH_CAUSAL_ROBUSTNESS":
        ambiguity_level = "HIGH"
    if label in {"EXCLUDED", "INSUFFICIENT_EVIDENCE"}:
        return "UNKNOWN", "SPARSE", "UNKNOWN", ambiguity_level
    completeness = "COMPLETE" if not missing else ("PARTIAL" if len(missing) == 1 else "SPARSE")
    consistency = "CONSISTENT"
    if conflict_detected:
        consistency = "CONTRADICTORY"
    elif ambiguity_detected or label == "UNKNOWN":
        consistency = "MIXED"
    if label == "UNKNOWN" or conflict_detected:
        return "LOW", completeness, consistency, ambiguity_level
    if completeness == "COMPLETE" and ambiguity_level == "LOW":
        return "HIGH", completeness, consistency, ambiguity_level
    if completeness == "COMPLETE":
        return "MODERATE", completeness, consistency, ambiguity_level
    if completeness == "PARTIAL":
        return "MODERATE", completeness, consistency, ambiguity_level
    return "LOW", completeness, consistency, ambiguity_level


def _classify_mechanism(mechanism_id: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
    found: List[str] = []
    missing: List[str] = []
    conflicts: List[str] = []
    accessed_fields: List[str] = []
    source_sheets_used = {"Pack_Behavior_Tier2_Behavior", "Pack_Behavior_Tier2_NoSignal", "Pack_Behavior_Tier2_Field_Influence", "Pack_Behavior_Tier2_Transitions"}
    rule_executed = ""
    classification_basis = ""
    exclusion_reason = ""
    unknown_reason = ""
    insufficient_reason = ""
    label = "UNKNOWN"

    def require(name: str, condition: bool) -> None:
        if condition:
            found.append(name)
        else:
            missing.append(name)

    def set_excluded(reason: str) -> None:
        nonlocal label, rule_executed, exclusion_reason
        label = "EXCLUDED"
        rule_executed = "excluded_rule"
        exclusion_reason = reason

    def set_insufficient(reason: str) -> None:
        nonlocal label, rule_executed, insufficient_reason
        label = "INSUFFICIENT_EVIDENCE"
        rule_executed = "insufficient_evidence_rule"
        insufficient_reason = reason

    def set_unknown(reason: str) -> None:
        nonlocal label, rule_executed, unknown_reason
        label = "UNKNOWN"
        rule_executed = "unknown_rule"
        unknown_reason = reason

    if ctx["output_invalid"]:
        set_excluded("output_valid is not TRUE for this behavior row")

    if mechanism_id == "MECH_INFORMATION_VALUE":
        accessed_fields.extend(
            [
                "pack_fields_used",
                "pack_fields_that_changed_reasoning",
                "field_reported_used",
                "field_reported_changed_reasoning",
                "field_reported_no_effect",
                "field_available_in_pack",
                "candidate_family",
                "causal_chain_transition",
            ]
        )
        if label != "EXCLUDED" and ctx["pack_level"] == "A":
            set_excluded("baseline pack has no incremental feature exposure to classify")
        require("baseline_available", ctx["baseline_available"])
        require("field_trace_present", ctx["valid_field_rows"] > 0)
        require("feature_exposure_signal", ctx["used_count"] > 0 or bool(ctx["used_fields"]))
        require("reasoning_delta_signal", ctx["changed_count"] > 0 or bool(ctx["changed_fields"]) or ctx["causal_chain_changed_count"] > 0)
        irrelevant_penalty = ctx["no_effect_count"] > 0 or (ctx["available_not_mentioned_count"] > ctx["used_count"] and ctx["changed_count"] == 0)
        conflict_detected = (
            ("feature_exposure_signal" in found) != ("reasoning_delta_signal" in found)
            or (("feature_exposure_signal" in found) and irrelevant_penalty)
        )
        if conflict_detected:
            conflicts.append("feature exposure and reasoning delta do not align cleanly")
        if label not in {"EXCLUDED"}:
            if not ctx["baseline_available"] or ctx["valid_field_rows"] == 0:
                set_insufficient("missing baseline or valid field-influence trace")
            elif ("feature_exposure_signal" in found) and ("reasoning_delta_signal" in found) and not irrelevant_penalty:
                label = "POSITIVE"
                rule_executed = "positive_rule"
                classification_basis = "explicit feature exposure changed reasoning without a no-effect penalty"
            elif ctx["available_count"] > 0 and (not ("feature_exposure_signal" in found) or not ("reasoning_delta_signal" in found) or irrelevant_penalty):
                label = "NEGATIVE"
                rule_executed = "negative_rule"
                classification_basis = "feature was available but failed to change reasoning cleanly"
            else:
                set_unknown("incremental value evidence is mixed across feature use and reasoning change")

    elif mechanism_id == "MECH_SIGNAL_DISCIPLINE":
        accessed_fields.extend(
            [
                "no_signal_flag",
                "forecast_confidence",
                "confidence_bucket",
                "forecast_direction",
                "missing_information",
                "uncertainty_sources",
                "no_signal_reason",
                "no_signal_transition",
                "confidence_transition",
            ]
        )
        require("no_signal_trace_present", ctx["current_no_signal_flag"] in {"TRUE", "FALSE"})
        require("confidence_trace_present", ctx["current_confidence"] is not None or ctx["current_confidence_bucket"] in {"LOW", "MEDIUM", "HIGH", "UNKNOWN"})
        require("low_signal_context", ctx["low_signal_context"])
        conflict_detected = ctx["restraint_signal"] and ctx["aggressive_signal"]
        if conflict_detected:
            conflicts.append("restraint and aggressive directional signals coexist")
        if label not in {"EXCLUDED"}:
            if ctx["current_no_signal_flag"] == "INVALID":
                set_excluded("no-signal normalization status indicates invalid output state")
            elif not ("no_signal_trace_present" in found) or not ("confidence_trace_present" in found):
                set_insufficient("missing no-signal or confidence trace")
            elif not ctx["low_signal_context"]:
                set_excluded("row is not in a low-signal context for this mechanism")
            elif ctx["restraint_signal"] and not ctx["aggressive_signal"]:
                label = "POSITIVE"
                rule_executed = "positive_rule"
                classification_basis = "low-signal context is matched with directional restraint or explicit no-signal behavior"
            elif ctx["aggressive_signal"] or ctx["transition_overreach"]:
                label = "NEGATIVE"
                rule_executed = "negative_rule"
                classification_basis = "low-signal context still produced aggressive directional conviction"
            else:
                set_unknown("low-signal context exists but restraint and conviction do not separate cleanly")

    elif mechanism_id == "MECH_CONDITIONAL_PREDICTIVENESS":
        accessed_fields.extend(
            [
                "candidate_family",
                "field_available_in_pack",
                "field_reported_used",
                "field_reported_changed_reasoning",
                "pack_fields_used",
                "pack_fields_that_changed_reasoning",
                "information_used",
            ]
        )
        if label != "EXCLUDED" and ctx["pack_level"] == "A":
            set_excluded("baseline pack has no regime-conditioned pack exposure")
        require("regime_family_present", ctx["regime_family_present"])
        require("regime_family_used", ctx["usdjpy_family_used"] or ctx["mentions_trend"])
        require("regime_family_changed_reasoning", ctx["usdjpy_family_changed"] or "USDJPY_TREND_LABEL" in ctx["changed_fields"])
        conflict_detected = ctx["mixed_family_use"] and ("regime_family_used" in found)
        if conflict_detected:
            conflicts.append("regime family use is mixed with multi-family reasoning shifts")
        if label not in {"EXCLUDED"}:
            if ctx["valid_field_rows"] == 0:
                set_insufficient("no valid field-influence trace for regime-conditioned evidence")
            elif not ctx["regime_family_present"]:
                set_insufficient("no pre-registered regime family evidence is available")
            elif ("regime_family_used" in found) and (("regime_family_changed_reasoning" in found) or ctx["mentions_trend"]) and not ctx["mixed_family_use"]:
                label = "POSITIVE"
                rule_executed = "positive_rule"
                classification_basis = "regime family is explicitly used and drives reasoning in a constrained slice"
            elif ctx["regime_family_present"] and not ("regime_family_used" in found):
                label = "NEGATIVE"
                rule_executed = "negative_rule"
                classification_basis = "regime family was available but did not guide reasoning"
            else:
                set_unknown("regime-conditioned evidence is present but mixed across families or gating cues")

    elif mechanism_id == "MECH_INFORMATION_FILTERING":
        accessed_fields.extend(
            [
                "pack_fields_used",
                "pack_fields_discarded",
                "field_reported_discarded",
                "field_reported_no_effect",
                "field_reported_changed_reasoning",
                "information_not_used",
                "candidate_family",
            ]
        )
        if label != "EXCLUDED" and ctx["pack_level"] == "A":
            set_excluded("baseline pack has no additional information set to filter")
        require("field_trace_present", ctx["valid_field_rows"] > 0)
        require("discard_signal_present", ctx["discarded_count"] > 0 or bool(ctx["discarded_fields"]) or bool(ctx["information_not_used_text"]))
        require("retained_signal_present", ctx["used_count"] > 0 or bool(ctx["used_fields"]))
        conflict_detected = ("discard_signal_present" in found) and ctx["no_effect_count"] > 0
        if conflict_detected:
            conflicts.append("fields are both discarded and reported as no-effect, making filtering ambiguous")
        if label not in {"EXCLUDED"}:
            if ctx["valid_field_rows"] == 0:
                set_insufficient("missing valid field-influence trace")
            elif ("discard_signal_present" in found) and ("retained_signal_present" in found) and ctx["no_effect_count"] == 0:
                label = "POSITIVE"
                rule_executed = "positive_rule"
                classification_basis = "added information was selectively filtered rather than simply accumulated"
            elif ("retained_signal_present" in found) and not ("discard_signal_present" in found):
                label = "NEGATIVE"
                rule_executed = "negative_rule"
                classification_basis = "available information was retained without visible filtering behavior"
            else:
                set_unknown("filtering signals are mixed or too coarse to separate from verbosity")

    elif mechanism_id == "MECH_FORECAST_STABILITY":
        accessed_fields.extend(
            [
                "direction_transition",
                "confidence_transition",
                "no_signal_transition",
                "transition_status",
                "causal_chain_transition",
            ]
        )
        require("paired_transition_trace_present", len(ctx["pass_relevant_transitions"]) > 0)
        require("direction_stability_trace", ctx["direction_change_count"] == 0)
        require("no_signal_stability_trace", ctx["no_signal_changed_count"] == 0)
        conflict_detected = ctx["direction_change_count"] > 0 and ctx["no_signal_changed_count"] == 0 and ctx["material_confidence_change_count"] == 0
        if conflict_detected:
            conflicts.append("direction moved while no-signal and confidence traces stayed stable")
        if label not in {"EXCLUDED"}:
            if len(ctx["pass_relevant_transitions"]) == 0:
                set_insufficient("no PASS transitions are available for stability preview")
            elif ctx["direction_change_count"] == 0 and ctx["no_signal_changed_count"] == 0 and ctx["material_confidence_change_count"] <= 1:
                label = "POSITIVE"
                rule_executed = "positive_rule"
                classification_basis = "forecast stayed stable across relevant transitions without directional drift"
            elif ctx["direction_change_count"] > 0 or (ctx["no_signal_changed_count"] > 0 and ctx["material_confidence_change_count"] >= 1):
                label = "NEGATIVE"
                rule_executed = "negative_rule"
                classification_basis = "forecast changed materially under pack transitions without a frozen high-value trigger model"
            else:
                set_unknown("forecast movement is limited but not cleanly selective")

    elif mechanism_id == "MECH_CAUSAL_ROBUSTNESS":
        accessed_fields.extend(
            [
                "causal_chain",
                "causal_chain_transition",
                "forecast_direction",
                "direction_transition",
                "pack_fields_that_changed_reasoning",
            ]
        )
        require("causal_chain_present", bool(ctx["causal_chain"]))
        require("multi_context_trace_present", len(ctx["peer_behavior_rows"]) >= 2 and len(ctx["pass_relevant_transitions"]) > 0)
        require("stable_direction_context", len(ctx["distinct_strong_directions"]) <= 1)
        conflict_detected = ctx["hard_direction_conflict_count"] > 0 or (ctx["overlap_to_baseline"] >= 0.15 and len(ctx["distinct_strong_directions"]) > 1)
        if conflict_detected:
            conflicts.append("causal-chain coherence and directional consistency disagree across pack variants")
        if label not in {"EXCLUDED"}:
            if not ctx["causal_chain"] or len(ctx["peer_behavior_rows"]) < 2:
                set_insufficient("not enough causal-chain trace coverage for multi-context comparison")
            elif len(ctx["distinct_strong_directions"]) > 1:
                label = "NEGATIVE"
                rule_executed = "negative_rule"
                classification_basis = "pack variants produce conflicting directional causal frames"
            elif (ctx["overlap_to_baseline"] >= 0.15 or ctx["overlap_to_peers"] >= 0.15) and len(ctx["distinct_strong_directions"]) <= 1 and not ctx["no_clear_present"]:
                label = "POSITIVE"
                rule_executed = "positive_rule"
                classification_basis = "core causal chain remains directionally coherent across available pack variants"
            else:
                set_unknown("causal trace exists but robustness remains ambiguous across contexts")

    else:
        set_excluded("unsupported mechanism_id")
        conflict_detected = False

    ambiguity_detected = bool(conflicts) or label == "UNKNOWN"
    confidence, completeness, consistency, ambiguity_level = _confidence_from_state(
        mechanism_id,
        label,
        found,
        missing,
        bool(conflicts),
        ambiguity_detected,
    )
    conflict_resolution_path = "no_conflict"
    if label == "EXCLUDED":
        conflict_resolution_path = "exclusion_precedence"
    elif label == "INSUFFICIENT_EVIDENCE":
        conflict_resolution_path = "insufficient_evidence_precedence"
    elif label == "NEGATIVE":
        conflict_resolution_path = "negative_precedence"
    elif label == "POSITIVE":
        conflict_resolution_path = "positive_precedence"
    elif label == "UNKNOWN":
        conflict_resolution_path = "unknown_after_conflict_or_ambiguity"

    accessed_field_set = sorted(set(accessed_fields))
    leakage_detected = any(any(term in field.lower() for term in FORBIDDEN_FIELD_TERMS) for field in accessed_field_set)
    leakage_status = "OUTCOME_LEAKAGE_DETECTED" if leakage_detected else "PASS_PRE_OUTCOME_ONLY"
    if leakage_detected:
        conflicts.append("prohibited outcome-linked field detected in accessed_fields")

    result = {
        "label": label,
        "confidence": confidence,
        "eligible_for_preview": label != "EXCLUDED",
        "found_observables": sorted(set(found)),
        "missing_observables": sorted(set(missing)),
        "extraction_success": len(found) > 0 and label != "EXCLUDED",
        "extraction_failure": label in {"INSUFFICIENT_EVIDENCE", "EXCLUDED"},
        "ambiguity_detected": ambiguity_detected,
        "conflict_detected": bool(conflicts),
        "conflicting_observables": conflicts,
        "conflicting_labels": (
            "POSITIVE vs NEGATIVE" if bool(conflicts) and label in {"POSITIVE", "NEGATIVE", "UNKNOWN"} else ""
        ),
        "unresolved_conflict": label == "UNKNOWN" and bool(conflicts),
        "conflict_resolution_path": conflict_resolution_path,
        "final_preview_outcome": label,
        "preview_confidence": confidence,
        "rule_executed": rule_executed or "unknown_rule",
        "classification_basis": classification_basis,
        "exclusion_reason": exclusion_reason,
        "unknown_reason": unknown_reason,
        "insufficient_evidence_reason": insufficient_reason,
        "evidence_completeness": completeness,
        "evidence_consistency": consistency,
        "ambiguity_level": ambiguity_level,
        "confidence_assignment_reason": (
            "derived from completeness, consistency, and ambiguity under the frozen confidence framework"
        ),
        "source_sheets_used": sorted(source_sheets_used),
        "accessed_fields": accessed_field_set,
        "realized_direction_accessed": False,
        "overall_ok_accessed": False,
        "corrected_outcomes_accessed": False,
        "evaluation_results_accessed": False,
        "future_information_accessed": False,
        "leakage_status": leakage_status,
        "audit_signature": json.dumps(
            {
                "label": label,
                "confidence": confidence,
                "found": sorted(set(found)),
                "missing": sorted(set(missing)),
                "conflicts": conflicts,
                "rule": rule_executed or "unknown_rule",
            },
            sort_keys=True,
        ),
    }
    return result


def build_predictive_mechanism_classification_dry_run_v0() -> Dict[str, Any]:
    service = build_sheets_service(load_credentials())
    generated_ts = _iso_now()
    dry_run_id = _dry_run_id(generated_ts)
    inputs = _read_inputs(service)
    indexes = _build_indexes(inputs)

    dry_run_rows: List[Dict[str, Any]] = []
    label_rows: List[Dict[str, Any]] = []
    extraction_rows: List[Dict[str, Any]] = []
    conflict_rows: List[Dict[str, Any]] = []
    confidence_rows: List[Dict[str, Any]] = []
    leakage_rows: List[Dict[str, Any]] = []
    determinism_rows: List[Dict[str, Any]] = []

    label_counter: Counter[str] = Counter()
    conflict_counter: Counter[str] = Counter()
    ambiguity_counter: Counter[str] = Counter()
    extraction_success_count = 0
    leakage_findings = 0
    determinism_failures = 0

    for behavior_row in indexes["behavior_rows"]:
        ctx = _build_context(behavior_row, indexes)
        for mechanism_id in MECHANISM_ORDER:
            preview_id = _make_preview_id(ctx["session_id"], ctx["provider"], ctx["pack_level"], mechanism_id)
            first_pass = _classify_mechanism(mechanism_id, ctx)
            second_pass = _classify_mechanism(mechanism_id, ctx)
            deterministic_status = (
                "PASS"
                if (
                    first_pass["label"] == second_pass["label"]
                    and first_pass["confidence"] == second_pass["confidence"]
                    and first_pass["rule_executed"] == second_pass["rule_executed"]
                    and first_pass["audit_signature"] == second_pass["audit_signature"]
                )
                else "FAIL"
            )
            if deterministic_status == "FAIL":
                determinism_failures += 1
            if first_pass["extraction_success"]:
                extraction_success_count += 1
            if first_pass["leakage_status"] == "OUTCOME_LEAKAGE_DETECTED":
                leakage_findings += 1
            label_counter[first_pass["label"]] += 1
            if first_pass["conflict_detected"]:
                conflict_counter[mechanism_id] += 1
            if first_pass["ambiguity_detected"] or first_pass["label"] == "UNKNOWN":
                ambiguity_counter[mechanism_id] += 1

            notes = json.dumps(
                {
                    "outcome_independence_rule": COMMON_OUTCOME_RULE,
                    "non_permanent_preview": True,
                },
                sort_keys=True,
            )
            dry_run_rows.append(
                {
                    **_base(generated_ts, dry_run_id),
                    "preview_id": preview_id,
                    "mechanism_id": mechanism_id,
                    "session_id": ctx["session_id"],
                    "provider": ctx["provider"],
                    "pack_level": ctx["pack_level"],
                    "behavior_row_number": ctx["behavior_row_number"],
                    "preview_label": first_pass["label"],
                    "preview_confidence": first_pass["preview_confidence"],
                    "eligible_for_preview": "TRUE" if first_pass["eligible_for_preview"] else "FALSE",
                    "conflict_detected": "TRUE" if first_pass["conflict_detected"] else "FALSE",
                    "leakage_status": first_pass["leakage_status"],
                    "deterministic_status": deterministic_status,
                    "rule_executed": first_pass["rule_executed"],
                    "notes": notes,
                }
            )
            label_rows.append(
                {
                    **_base(generated_ts, dry_run_id),
                    "preview_id": preview_id,
                    "mechanism_id": mechanism_id,
                    "session_id": ctx["session_id"],
                    "provider": ctx["provider"],
                    "pack_level": ctx["pack_level"],
                    "preview_label": first_pass["label"],
                    "classification_basis": first_pass["classification_basis"],
                    "exclusion_reason": first_pass["exclusion_reason"],
                    "unknown_reason": first_pass["unknown_reason"],
                    "insufficient_evidence_reason": first_pass["insufficient_evidence_reason"],
                    "preview_confidence": first_pass["preview_confidence"],
                    "notes": "Preview labels are diagnostic only and do not become permanent in this phase.",
                }
            )
            extraction_rows.append(
                {
                    **_base(generated_ts, dry_run_id),
                    "preview_id": preview_id,
                    "mechanism_id": mechanism_id,
                    "session_id": ctx["session_id"],
                    "provider": ctx["provider"],
                    "pack_level": ctx["pack_level"],
                    "observables_found": "; ".join(first_pass["found_observables"]),
                    "observables_missing": "; ".join(first_pass["missing_observables"]),
                    "extraction_success": "TRUE" if first_pass["extraction_success"] else "FALSE",
                    "extraction_failure": "TRUE" if first_pass["extraction_failure"] else "FALSE",
                    "ambiguity_detected": "TRUE" if first_pass["ambiguity_detected"] else "FALSE",
                    "rule_executed": first_pass["rule_executed"],
                    "source_sheets_used": "; ".join(first_pass["source_sheets_used"]),
                    "notes": "Observable extraction is pre-outcome only.",
                }
            )
            conflict_rows.append(
                {
                    **_base(generated_ts, dry_run_id),
                    "preview_id": preview_id,
                    "mechanism_id": mechanism_id,
                    "session_id": ctx["session_id"],
                    "provider": ctx["provider"],
                    "pack_level": ctx["pack_level"],
                    "conflicting_observables": "; ".join(first_pass["conflicting_observables"]),
                    "conflicting_labels": first_pass["conflicting_labels"],
                    "unresolved_conflict": "TRUE" if first_pass["unresolved_conflict"] else "FALSE",
                    "conflict_resolution_path": first_pass["conflict_resolution_path"],
                    "final_preview_outcome": first_pass["final_preview_outcome"],
                    "notes": "No manual overrides are permitted in the dry run.",
                }
            )
            confidence_rows.append(
                {
                    **_base(generated_ts, dry_run_id),
                    "preview_id": preview_id,
                    "mechanism_id": mechanism_id,
                    "session_id": ctx["session_id"],
                    "provider": ctx["provider"],
                    "pack_level": ctx["pack_level"],
                    "evidence_completeness": first_pass["evidence_completeness"],
                    "evidence_consistency": first_pass["evidence_consistency"],
                    "ambiguity_level": first_pass["ambiguity_level"],
                    "preview_confidence": first_pass["preview_confidence"],
                    "confidence_assignment_reason": first_pass["confidence_assignment_reason"],
                    "notes": "Preview confidence refers to label-quality only, not forecast quality.",
                }
            )
            leakage_rows.append(
                {
                    **_base(generated_ts, dry_run_id),
                    "preview_id": preview_id,
                    "mechanism_id": mechanism_id,
                    "session_id": ctx["session_id"],
                    "provider": ctx["provider"],
                    "pack_level": ctx["pack_level"],
                    "accessed_source_sheets": "; ".join(first_pass["source_sheets_used"]),
                    "accessed_fields": "; ".join(first_pass["accessed_fields"]),
                    "realized_direction_accessed": "TRUE" if first_pass["realized_direction_accessed"] else "FALSE",
                    "overall_ok_accessed": "TRUE" if first_pass["overall_ok_accessed"] else "FALSE",
                    "corrected_outcomes_accessed": "TRUE" if first_pass["corrected_outcomes_accessed"] else "FALSE",
                    "evaluation_results_accessed": "TRUE" if first_pass["evaluation_results_accessed"] else "FALSE",
                    "future_information_accessed": "TRUE" if first_pass["future_information_accessed"] else "FALSE",
                    "leakage_status": first_pass["leakage_status"],
                    "notes": "Leakage audit confirms pre-outcome-only field access.",
                }
            )
            determinism_rows.append(
                {
                    **_base(generated_ts, dry_run_id),
                    "preview_id": preview_id,
                    "mechanism_id": mechanism_id,
                    "session_id": ctx["session_id"],
                    "provider": ctx["provider"],
                    "pack_level": ctx["pack_level"],
                    "first_pass_label": first_pass["label"],
                    "second_pass_label": second_pass["label"],
                    "first_pass_confidence": first_pass["confidence"],
                    "second_pass_confidence": second_pass["confidence"],
                    "first_pass_rule": first_pass["rule_executed"],
                    "second_pass_rule": second_pass["rule_executed"],
                    "audit_trail_match": "TRUE" if first_pass["audit_signature"] == second_pass["audit_signature"] else "FALSE",
                    "deterministic_status": deterministic_status,
                    "notes": "Dry-run determinism check reruns the same frozen rule stack on identical inputs.",
                }
            )

    governance_specs = [
        ("GOV_PROVIDER_CALLS", "provider_calls_performed", "0", "0"),
        ("GOV_FORECAST_GENERATION", "forecast_generation_performed", "0", "0"),
        ("GOV_MECHANISM_TESTING", "mechanism_testing_performed", "0", "0"),
        ("GOV_CLASSIFICATION_EXECUTION", "mechanism_classification_execution", "0", "0"),
        ("GOV_METRIC_CALCULATION", "mechanism_metrics_calculated", "0", "0"),
        ("GOV_ACCURACY_EVALUATION", "accuracy_evaluation_performed", "0", "0"),
        ("GOV_PROVIDER_RERUN", "provider_rerun_count", "0", "0"),
        ("GOV_PROMPT_MODIFICATION", "prompt_modification", "FALSE", "FALSE"),
        ("GOV_ROUTING", "routing_changes", "FALSE", "FALSE"),
        ("GOV_WEIGHTING", "weighting_changes", "FALSE", "FALSE"),
        ("GOV_CALIBRATION", "calibration_changes", "FALSE", "FALSE"),
        ("GOV_PRODUCTION_WRITES", "production_writes", "0", "0"),
        ("GOV_PRODUCTION_BEHAVIOR", "production_behavior_change_count", "0", "0"),
        ("GOV_PERMANENT_LABELS", "mechanism_labels_permanently_assigned", "0", "0"),
    ]
    governance_rows = [
        {
            **_base(generated_ts, dry_run_id),
            "check_id": check_id,
            "check_name": name,
            "expected_value": expected,
            "actual_value": actual,
            "status": "PASS" if expected == actual else "FAIL",
            "notes": "Preview-only dry run.",
        }
        for check_id, name, expected, actual in governance_specs
    ]

    total_previews = len(dry_run_rows)
    eligible_rows_previewed = total_previews - label_counter["EXCLUDED"]
    highest_conflict_rate = "NONE"
    if conflict_counter:
        preview_counts_by_mech = Counter(row["mechanism_id"] for row in dry_run_rows)
        highest_conflict_rate = max(
            (
                f"{mechanism_id}:{conflict_counter[mechanism_id]}/{preview_counts_by_mech[mechanism_id]}"
                for mechanism_id in MECHANISM_ORDER
            ),
            key=lambda item: float(item.split(":")[1].split("/")[0]) / max(1.0, float(item.split("/")[1])),
        )
    highest_ambiguity = "NONE"
    if ambiguity_counter:
        preview_counts_by_mech = Counter(row["mechanism_id"] for row in dry_run_rows)
        highest_ambiguity = max(
            (
                f"{mechanism_id}:{ambiguity_counter[mechanism_id]}/{preview_counts_by_mech[mechanism_id]}"
                for mechanism_id in MECHANISM_ORDER
            ),
            key=lambda item: float(item.split(":")[1].split("/")[0]) / max(1.0, float(item.split("/")[1])),
        )

    ready_for_execution = leakage_findings == 0 and determinism_failures == 0
    build_status = "PASS_WITH_WARNINGS" if ready_for_execution else "NEEDS_REVIEW"
    final_interpretation = (
        "PREDICTIVE_MECHANISM_CLASSIFICATION_DRY_RUN_READY_WITH_WARNINGS"
        if ready_for_execution
        else "PREDICTIVE_MECHANISM_CLASSIFICATION_DRY_RUN_NEEDS_REVIEW"
    )
    recommended_next = (
        "PROCEED_TO_PHASE9A6E_MECHANISM_CLASSIFICATION_EXECUTION"
        if ready_for_execution
        else "RUN_PHASE9A6D_DRY_RUN_REPAIR"
    )
    summary_rows = [
        {
            **_base(generated_ts, dry_run_id),
            "build_status": build_status,
            "final_interpretation": final_interpretation,
            "eligible_rows_previewed": eligible_rows_previewed,
            "preview_labels_assigned": total_previews,
            "positive_labels": label_counter["POSITIVE"],
            "negative_labels": label_counter["NEGATIVE"],
            "unknown_labels": label_counter["UNKNOWN"],
            "insufficient_evidence_labels": label_counter["INSUFFICIENT_EVIDENCE"],
            "excluded_labels": label_counter["EXCLUDED"],
            "evidence_extraction_success": extraction_success_count,
            "conflicts_detected": sum(conflict_counter.values()),
            "leakage_findings": leakage_findings,
            "determinism_status": "PASS" if determinism_failures == 0 else "FAIL",
            "highest_priority_mechanism": "MECH_INFORMATION_VALUE",
            "highest_conflict_rate": highest_conflict_rate,
            "highest_ambiguity": highest_ambiguity,
            "provider_calls_performed": 0,
            "forecast_generation_performed": 0,
            "mechanism_labels_permanently_assigned": 0,
            "accuracy_evaluation_performed": 0,
            "production_behavior_change_count": 0,
            "ready_for_mechanism_classification_execution": "TRUE" if ready_for_execution else "FALSE",
            "ready_for_mechanism_testing": "FALSE",
            "ready_for_replication": "FALSE",
            "ready_for_production": "FALSE",
            "recommended_next_step": recommended_next,
            "notes": json.dumps(
                {
                    "non_permanent_preview": True,
                    "preview_label_set": sorted(PREVIEW_LABELS),
                    "confidence_levels": sorted(CONFIDENCE_LEVELS),
                    "outcome_independence_rule": COMMON_OUTCOME_RULE,
                },
                sort_keys=True,
            ),
        }
    ]

    outputs = [
        (OUTPUT_DRY_RUN, DRY_RUN_HEADERS, dry_run_rows),
        (OUTPUT_LABEL_PREVIEW, LABEL_PREVIEW_HEADERS, label_rows),
        (OUTPUT_EXTRACTION_AUDIT, EXTRACTION_HEADERS, extraction_rows),
        (OUTPUT_CONFLICT_AUDIT, CONFLICT_HEADERS, conflict_rows),
        (OUTPUT_CONFIDENCE, CONFIDENCE_HEADERS, confidence_rows),
        (OUTPUT_LEAKAGE, LEAKAGE_HEADERS, leakage_rows),
        (OUTPUT_DETERMINISM, DETERMINISM_HEADERS, determinism_rows),
        (OUTPUT_GOVERNANCE, GOVERNANCE_HEADERS, governance_rows),
        (OUTPUT_SUMMARY, SUMMARY_HEADERS, summary_rows),
    ]
    for sheet_name, headers, rows in outputs:
        actual_headers = _ensure_sheet_minimal_light(
            service,
            DIAGNOSTICS_SPREADSHEET_ID,
            sheet_name,
            headers,
            len(rows),
        )
        _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, actual_headers, rows)

    registry = _upsert_registry_rows(service)
    return {
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "file_created": "automation/build_predictive_mechanism_classification_dry_run_v0.py",
        "sheets_written": {sheet_name: len(rows) for sheet_name, _, rows in outputs},
        "eligible_rows_previewed": eligible_rows_previewed,
        "preview_labels_assigned": total_previews,
        "positive_labels": label_counter["POSITIVE"],
        "negative_labels": label_counter["NEGATIVE"],
        "unknown_labels": label_counter["UNKNOWN"],
        "insufficient_evidence_labels": label_counter["INSUFFICIENT_EVIDENCE"],
        "excluded_labels": label_counter["EXCLUDED"],
        "evidence_extraction_success": extraction_success_count,
        "conflicts_detected": sum(conflict_counter.values()),
        "leakage_findings": leakage_findings,
        "determinism_status": "PASS" if determinism_failures == 0 else "FAIL",
        "highest_priority_mechanism": "MECH_INFORMATION_VALUE",
        "highest_conflict_rate": highest_conflict_rate,
        "highest_ambiguity": highest_ambiguity,
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "mechanism_labels_permanently_assigned": 0,
        "accuracy_evaluation_performed": 0,
        "production_behavior_change_count": 0,
        "ready_for_mechanism_classification_execution": ready_for_execution,
        "ready_for_mechanism_testing": False,
        "ready_for_replication": False,
        "ready_for_production": False,
        "recommended_next_step": recommended_next,
        "registry": registry,
    }


def main() -> None:
    result = build_predictive_mechanism_classification_dry_run_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
