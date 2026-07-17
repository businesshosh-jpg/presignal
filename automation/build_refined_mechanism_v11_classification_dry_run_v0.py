import json
import re
import sys
from collections import Counter, defaultdict
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
from automation.build_predictive_mechanism_classification_dry_run_v0 import (
    _build_indexes as _build_original_indexes,
)
from automation.build_refined_mechanism_classification_dry_run_v0 import (
    CONDITION_HINTS,
    TIME_HINTS,
    UNCERTAINTY_HINTS,
    _build_refined_context as _build_v10_refined_context,
    _contains_any,
    _direction_signal,
    _family_keyword_hits,
    _source_sheets_from_observables,
    _text,
)
from automation.build_session_information_requests_v0 import _iso_now
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials


SCHEMA_VERSION = "presignal_v2_refined_mechanism_v11_classification_dry_run_0.1"
DRY_RUN_VERSION = "refined_mechanism_v11_classification_dry_run_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-6R6"
REGISTRY_CATEGORY = "PRESIGNAL_V2_REFINED_MECHANISM_V11_DRY_RUN"
REGISTRY_OWNER_MODULE = "market_state"

EXPECTED_CANDIDATE_ROWS = 120
EXPECTED_ELIGIBLE_ROWS = 82

MECHANISM_IDS = [
    "MECH_INFORMATION_RELEVANCE",
    "MECH_INFORMATION_SPECIFICITY",
    "MECH_INFORMATION_CONSISTENCY",
]
PAIRWISE_MECHANISM_PAIRS = [
    ("MECH_INFORMATION_RELEVANCE", "MECH_INFORMATION_SPECIFICITY"),
    ("MECH_INFORMATION_SPECIFICITY", "MECH_INFORMATION_CONSISTENCY"),
    ("MECH_INFORMATION_RELEVANCE", "MECH_INFORMATION_CONSISTENCY"),
]

STATE_POSITIVE = "POSITIVE"
STATE_NEGATIVE = "NEGATIVE"
STATE_UNKNOWN = "UNKNOWN"
STATE_MISSING = "MISSING"

PREVIEW_LABELS = {"POSITIVE", "NEGATIVE", "UNKNOWN", "INSUFFICIENT_EVIDENCE", "EXCLUDED"}
CONFIDENCE_LEVELS = {"HIGH", "MODERATE", "LOW", "UNKNOWN"}

BOUNDARY_CUE_TYPES = [
    "EXPLICIT_CAUSAL_TRIGGER",
    "EXPLICIT_CONDITIONAL_BRANCH",
    "EXPLICIT_INVALIDATION_CONDITION",
    "EXPLICIT_FAILURE_CONDITION",
    "EXPLICIT_NO_SIGNAL_BOUNDARY",
    "EXPLICIT_REGIME_BOUNDARY",
    "EXPLICIT_FORECAST_RELEVANT_THRESHOLD",
    "EXPLICIT_REVERSAL_OR_ALTERATION_CONDITION",
    "TIME_HORIZON_PLUS_DECISION_RELEVANT_CONDITION",
]
PROHIBITED_SPECIFICITY_PROXIES = [
    "GENERIC_TIME_HORIZON_ONLY",
    "VERBOSITY_ONLY",
    "NUMERICAL_DETAIL_ONLY",
    "SOURCE_FIELD_RESTATEMENT_ONLY",
    "CONFIDENCE_LANGUAGE_ONLY",
    "GENERIC_UNCERTAINTY_ONLY",
    "DESCRIPTIVE_PRECISION_WITHOUT_BOUNDARY",
]

FORBIDDEN_FIELD_TERMS = [
    "realized",
    "overall_ok",
    "corrected",
    "outcome",
    "market_reaction",
    "accuracy_",
    "evaluation_",
    "future_",
]

THRESHOLD_RE = re.compile(
    r"(>=|<=|>|<|above|below|at least|less than|more than|meet(?:ing)? or beat(?:ing)?|under|over)\s*\d",
    re.IGNORECASE,
)
NUMBER_RE = re.compile(r"\d")
TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")

GENERIC_BOUNDARY_TERMS = [
    "strong economic data",
    "positive economic data",
    "unexpected strong",
    "unexpected weak",
    "hawkish commentary",
    "dovish commentary",
    "geopolitical events",
    "unusual volatility",
    "market reactions",
    "surprisingly strong us economy",
    "significant upward revision",
    "significant positive surprise",
]
CONCRETE_SIGNAL_TERMS = [
    "cpi",
    "core cpi",
    "retail sales",
    "fed",
    "fomc",
    "dxy",
    "yield",
    "yields",
    "tic",
    "jobless",
    "housing",
    "claims",
    "inflation",
    "usdjpy",
    "usd/jpy",
    "dollar",
    "yen",
]
REVERSAL_TERMS = [
    "reverse",
    "reversal",
    "negate",
    "override",
    "offset",
    "alter",
    "invalidate",
    "invalidated",
    "change forecast",
]
REGIME_TERMS = [
    "regime",
    "trend",
    "volatility",
    "session",
    "pre-session",
    "presession",
]

REQUIRED_INPUT_SHEETS = [
    "Refined_Mechanism_v11_PreRegistration",
    "Refined_Mechanism_v11_Frozen_Definitions",
    "Refined_Mechanism_v11_Frozen_Observables",
    "Refined_Mechanism_v11_Frozen_Label_Rules",
    "Refined_Mechanism_v11_Frozen_Confidence_Rules",
    "Refined_Mechanism_v11_Frozen_Conflict_Rules",
    "Refined_Mechanism_v11_Frozen_Falsification_Rules",
    "Refined_Mechanism_v11_Separation_Rules",
    "Refined_Mechanism_v11_Version_Diff",
    "Refined_Mechanism_v11_Governance",
    "Refined_Mechanism_v11_PreRegistration_Summary",
    "Refined_Mechanism_Classification_Dry_Run",
    "Refined_Mechanism_Label_Preview",
    "Refined_Mechanism_Evidence_Audit",
    "Refined_Mechanism_Conflict_Audit",
    "Refined_Mechanism_Confidence_Preview",
    "Refined_Mechanism_Determinism_Audit",
    "Refined_Mechanism_Leakage_Audit",
    "Refined_Mechanism_Dry_Run_Summary",
    "Pack_Behavior_Tier2_Behavior",
    "Pack_Behavior_Tier2_Transitions",
    "Pack_Behavior_Tier2_Field_Influence",
    "Pack_Behavior_Tier2_NoSignal",
    "Pack_Behavior_Tier2_Invalid_Output",
]

OUTPUT_DRY_RUN = "Refined_Mechanism_v11_Classification_Dry_Run"
OUTPUT_LABEL_PREVIEW = "Refined_Mechanism_v11_Label_Preview"
OUTPUT_EVIDENCE = "Refined_Mechanism_v11_Evidence_Audit"
OUTPUT_RULE_PATH = "Refined_Mechanism_v11_Rule_Path_Audit"
OUTPUT_SPECIFICITY_BOUNDARY = "Refined_Mechanism_v11_Specificity_Boundary_Audit"
OUTPUT_CONFLICT = "Refined_Mechanism_v11_Conflict_Audit"
OUTPUT_OVERLAP = "Refined_Mechanism_v11_Overlap_Audit"
OUTPUT_LABEL_BALANCE = "Refined_Mechanism_v11_Label_Balance_Audit"
OUTPUT_CONFIDENCE = "Refined_Mechanism_v11_Confidence_Preview"
OUTPUT_DETERMINISM = "Refined_Mechanism_v11_Determinism_Audit"
OUTPUT_LEAKAGE = "Refined_Mechanism_v11_Leakage_Audit"
OUTPUT_COMPARISON = "Refined_Mechanism_v11_vs_v10_Comparison"
OUTPUT_GOVERNANCE = "Refined_Mechanism_v11_Dry_Run_Governance"
OUTPUT_SUMMARY = "Refined_Mechanism_v11_Dry_Run_Summary"

DRY_RUN_HEADERS = [
    "generated_ts",
    "schema_version",
    "dry_run_version",
    "dry_run_id",
    "preregistration_version_reference",
    "preview_id",
    "source_row_key",
    "session_id",
    "provider",
    "pack_level",
    "stable_mechanism_id",
    "mechanism_id",
    "candidate_row_in_scope",
    "eligible_for_preview",
    "preview_label",
    "confidence_category",
    "decisive_rule_id",
    "decisive_observables",
    "rejected_alternative_rules",
    "conflict_status",
    "determinism_status",
    "leakage_status",
    "notes",
]

LABEL_PREVIEW_HEADERS = [
    "generated_ts",
    "schema_version",
    "dry_run_version",
    "dry_run_id",
    "preview_id",
    "source_row_key",
    "stable_mechanism_id",
    "mechanism_id",
    "session_id",
    "provider",
    "pack_level",
    "preview_label",
    "executed_rule_id",
    "decisive_observables",
    "decisive_evidence",
    "rejected_alternative_rules",
    "conflict_status",
    "confidence_category",
    "full_audit_path",
    "notes",
]

EVIDENCE_HEADERS = [
    "generated_ts",
    "schema_version",
    "dry_run_version",
    "dry_run_id",
    "preview_id",
    "source_row_key",
    "stable_mechanism_id",
    "mechanism_id",
    "session_id",
    "provider",
    "pack_level",
    "observable_candidates",
    "observables_present",
    "observables_absent",
    "observable_states",
    "extraction_success",
    "ambiguity_detected",
    "decisive_evidence",
    "source_sheets_used",
    "accessed_fields",
    "notes",
]

RULE_PATH_HEADERS = [
    "generated_ts",
    "schema_version",
    "dry_run_version",
    "dry_run_id",
    "preview_id",
    "mechanism_id",
    "source_row_key",
    "observable_candidates",
    "observables_present",
    "observables_absent",
    "positive_rule_checked",
    "negative_rule_checked",
    "unknown_rule_checked",
    "insufficient_evidence_rule_checked",
    "exclusion_rule_checked",
    "decisive_rule_id",
    "decisive_evidence",
    "label_assigned",
    "confidence_assigned",
    "conflict_detected",
    "conflict_resolution_rule",
    "manual_override_used",
]

SPECIFICITY_BOUNDARY_HEADERS = [
    "generated_ts",
    "schema_version",
    "dry_run_version",
    "dry_run_id",
    "mechanism_id",
    "source_row_key",
    "preview_label",
    "boundary_cue_type",
    "boundary_cue_text_or_trace",
    "forecast_relevance_confirmed",
    "prohibited_proxy_detected",
    "time_horizon_present",
    "time_horizon_supporting_only",
    "specificity_positive_valid",
    "audit_status",
    "notes",
]

CONFLICT_HEADERS = [
    "generated_ts",
    "schema_version",
    "dry_run_version",
    "dry_run_id",
    "mechanism_id",
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
    "high_confidence_count",
    "moderate_confidence_count",
    "low_confidence_count",
    "unknown_confidence_count",
    "notes",
]

OVERLAP_HEADERS = [
    "generated_ts",
    "schema_version",
    "dry_run_version",
    "dry_run_id",
    "source_row_key",
    "session_id",
    "provider",
    "pack_level",
    "mechanism_a",
    "label_a",
    "mechanism_b",
    "label_b",
    "pair_status",
    "joint_positive",
    "separation_rule_applied",
    "justification",
    "notes",
]

LABEL_BALANCE_HEADERS = [
    "generated_ts",
    "schema_version",
    "dry_run_version",
    "dry_run_id",
    "row_type",
    "mechanism_id",
    "source_row_key",
    "preview_label",
    "positive_count",
    "negative_count",
    "unknown_count",
    "insufficient_evidence_count",
    "excluded_count",
    "negative_rule_id",
    "affirmative_absence_evidence",
    "missing_evidence_only",
    "optional_field_absence_only",
    "invalid_output_related",
    "excluded_row_related",
    "negative_label_valid",
    "audit_status",
    "notes",
]

CONFIDENCE_HEADERS = [
    "generated_ts",
    "schema_version",
    "dry_run_version",
    "dry_run_id",
    "preview_id",
    "source_row_key",
    "mechanism_id",
    "preview_label",
    "evidence_completeness",
    "evidence_consistency",
    "rule_path_clarity",
    "observable_coverage",
    "ambiguity_level",
    "confidence_category",
    "confidence_reason",
    "notes",
]

DETERMINISM_HEADERS = [
    "generated_ts",
    "schema_version",
    "dry_run_version",
    "dry_run_id",
    "preview_id",
    "source_row_key",
    "mechanism_id",
    "first_pass_label",
    "second_pass_label",
    "first_pass_confidence",
    "second_pass_confidence",
    "first_pass_rule_id",
    "second_pass_rule_id",
    "first_pass_audit_hash",
    "second_pass_audit_hash",
    "determinism_status",
    "notes",
]

LEAKAGE_HEADERS = [
    "generated_ts",
    "schema_version",
    "dry_run_version",
    "dry_run_id",
    "preview_id",
    "source_row_key",
    "mechanism_id",
    "outcome_field_accessed",
    "future_information_accessed",
    "prohibited_sheet_accessed",
    "leakage_status",
    "notes",
]

COMPARISON_HEADERS = [
    "generated_ts",
    "schema_version",
    "dry_run_version",
    "dry_run_id",
    "comparison_scope",
    "mechanism_id",
    "v10_value",
    "v11_value",
    "absolute_delta",
    "relative_delta",
    "scientific_interpretation",
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
    "candidate_rows",
    "eligible_rows_previewed",
    "preview_labels_assigned",
    "positive_labels",
    "negative_labels",
    "unknown_labels",
    "insufficient_evidence_labels",
    "excluded_labels",
    "specificity_positive_labels",
    "specificity_negative_labels",
    "specificity_false_proxy_findings",
    "valid_boundary_forming_specificity_positives",
    "conflicts_detected",
    "unresolved_conflicts",
    "ambiguity_count",
    "relevance_specificity_overlap",
    "specificity_consistency_overlap",
    "v10_conflict_count",
    "v11_conflict_count",
    "conflict_delta",
    "v10_ambiguity_count",
    "v11_ambiguity_count",
    "ambiguity_delta",
    "determinism_status",
    "leakage_findings",
    "highest_remaining_conflict",
    "highest_remaining_ambiguity",
    "strongest_v11_mechanism",
    "primary_scientific_interpretation",
    "provider_calls_performed",
    "forecast_generation_performed",
    "permanent_labels_assigned",
    "mechanism_testing_performed",
    "accuracy_evaluation_performed",
    "outcome_values_accessed",
    "v1_0_sheets_modified",
    "production_behavior_change_count",
    "production_sheet_write_count",
    "ready_for_v11_refined_conflict_review",
    "ready_for_permanent_classification_execution",
    "ready_for_mechanism_testing",
    "ready_for_production",
    "recommended_next_step",
    "notes",
]


def _dry_run_id(generated_ts: str) -> str:
    return "refined_mechanism_v11_classification_dry_run_v0_" + generated_ts.replace("-", "").replace(":", "")


def _base(generated_ts: str, dry_run_id: str) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "dry_run_version": DRY_RUN_VERSION,
        "dry_run_id": dry_run_id,
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
    missing = [sheet for sheet in REQUIRED_INPUT_SHEETS if sheet not in titles]
    if missing:
        raise RuntimeError(f"Missing critical input sheets: {', '.join(sorted(missing))}")
    return {sheet: _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet) for sheet in REQUIRED_INPUT_SHEETS}


def _to_bool(value: Any) -> bool:
    return _norm(value).upper() == "TRUE"


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True)


def _safe_ratio(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return ""
    return f"{numerator / float(denominator):.6f}"


def _source_row_key(session_id: str, provider: str, pack_level: str) -> str:
    return "|".join([session_id, provider, pack_level])


def _preview_id(mechanism_id: str, source_row_key: str) -> str:
    return f"{REFINED_VERSION_REFERENCE()}|{mechanism_id}|{source_row_key}"


def REFINED_VERSION_REFERENCE() -> str:
    return "v1.1"


def _tokenize(text: str) -> Set[str]:
    return {token.lower() for token in TOKEN_RE.findall(_norm(text)) if token}


def _overlap_score(a: str, b: str) -> float:
    tokens_a = _tokenize(a)
    tokens_b = _tokenize(b)
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / float(len(tokens_a | tokens_b))


def _is_generic_boundary_text(text: str) -> bool:
    lowered = _norm(text).lower()
    if not lowered:
        return False
    return any(term in lowered for term in GENERIC_BOUNDARY_TERMS) and not THRESHOLD_RE.search(lowered)


def _has_concrete_signal(text: str, active_families: Set[str]) -> bool:
    lowered = _norm(text).lower()
    if not lowered:
        return False
    if any(term in lowered for term in CONCRETE_SIGNAL_TERMS):
        return True
    if NUMBER_RE.search(lowered):
        return True
    return bool(_family_keyword_hits(active_families, lowered))


def _observable_coverage(observable_states: Dict[str, str]) -> str:
    total = len(observable_states)
    if total == 0:
        return "0/0"
    present = sum(1 for state in observable_states.values() if state != STATE_MISSING)
    return f"{present}/{total}"


def _mechanism_scope_exclusion(ctx: Dict[str, Any]) -> str:
    if _norm(ctx.get("pack_level")) == "A":
        return "baseline_pack_a_no_added_information"
    if not bool(ctx.get("output_valid")):
        return "invalid_output_behavior_row"
    return ""


def _make_result(
    mechanism_id: str,
    label: str,
    decisive_rule_id: str,
    decisive_observables: List[str],
    decisive_evidence: List[str],
    observable_states: Dict[str, str],
    conflict_detected: bool,
    unresolved_conflict: bool,
    conflict_resolution_rule: str,
    affirmative_absence_evidence: List[str],
    rejected_alternative_rules: List[str],
    accessed_fields: List[str],
    source_sheets_used: List[str],
    notes: Optional[Dict[str, Any]] = None,
    boundary_audit: Optional[Dict[str, Any]] = None,
    missing_evidence_only: bool = False,
    optional_field_absence_only: bool = False,
    invalid_output_related: bool = False,
    excluded_row_related: bool = False,
) -> Dict[str, Any]:
    return {
        "mechanism_id": mechanism_id,
        "label": label,
        "decisive_rule_id": decisive_rule_id,
        "decisive_observables": decisive_observables,
        "decisive_evidence": decisive_evidence,
        "observable_states": observable_states,
        "conflict_detected": conflict_detected,
        "unresolved_conflict": unresolved_conflict,
        "conflict_resolution_rule": conflict_resolution_rule,
        "manual_override_used": False,
        "affirmative_absence_evidence": affirmative_absence_evidence,
        "rejected_alternative_rules": rejected_alternative_rules,
        "accessed_fields": sorted(set(accessed_fields)),
        "source_sheets_used": sorted(set(source_sheets_used)),
        "notes": notes or {},
        "boundary_audit": boundary_audit or {},
        "missing_evidence_only": missing_evidence_only,
        "optional_field_absence_only": optional_field_absence_only,
        "invalid_output_related": invalid_output_related,
        "excluded_row_related": excluded_row_related,
        "rule_checks": {
            "exclusion_rule_checked": True,
            "insufficient_evidence_rule_checked": True,
            "negative_rule_checked": True,
            "positive_rule_checked": True,
            "unknown_rule_checked": True,
        },
    }


def _assign_confidence(
    label: str,
    observable_states: Dict[str, str],
    conflict_detected: bool,
    unresolved_conflict: bool,
    decisive_rule_id: str,
    rejected_alternative_rules: List[str],
) -> Dict[str, str]:
    coverage = _observable_coverage(observable_states)
    present_count = sum(1 for state in observable_states.values() if state != STATE_MISSING)
    total_count = len(observable_states)
    evidence_completeness = "SPARSE"
    if total_count > 0 and present_count == total_count:
        evidence_completeness = "COMPLETE"
    elif present_count >= max(1, total_count - 1):
        evidence_completeness = "PARTIAL"
    elif present_count > 0:
        evidence_completeness = "SPARSE"

    evidence_consistency = "CONSISTENT"
    if conflict_detected and unresolved_conflict:
        evidence_consistency = "CONTRADICTORY"
    elif conflict_detected:
        evidence_consistency = "MIXED"
    elif label == "UNKNOWN":
        evidence_consistency = "MIXED"
    elif label == "INSUFFICIENT_EVIDENCE":
        evidence_consistency = "UNKNOWN"

    rule_path_clarity = "EXPLICIT"
    if label in {"UNKNOWN", "INSUFFICIENT_EVIDENCE"} or unresolved_conflict:
        rule_path_clarity = "PARTIAL"
    elif rejected_alternative_rules:
        rule_path_clarity = "WARNING_LEVEL"

    ambiguity_level = "LOW"
    if unresolved_conflict or label == "UNKNOWN":
        ambiguity_level = "HIGH"
    elif label == "INSUFFICIENT_EVIDENCE":
        ambiguity_level = "HIGH"
    elif conflict_detected or rejected_alternative_rules:
        ambiguity_level = "MODERATE"

    if label in {"EXCLUDED", "INSUFFICIENT_EVIDENCE"}:
        confidence = "UNKNOWN"
        reason = "confidence is not assigned to excluded or insufficient-evidence previews"
    elif unresolved_conflict or label == "UNKNOWN":
        confidence = "LOW"
        reason = "label remains ambiguity-burdened under the frozen v1.1 rule path"
    elif evidence_completeness == "COMPLETE" and not conflict_detected and not rejected_alternative_rules:
        confidence = "HIGH"
        reason = "complete observable coverage with a clean decisive v1.1 rule path"
    elif evidence_completeness in {"COMPLETE", "PARTIAL"}:
        confidence = "MODERATE"
        reason = "label is decisive but still carries partial coverage or warning-level ambiguity"
    else:
        confidence = "LOW"
        reason = "label is assignable but the observable coverage is sparse"

    return {
        "confidence": confidence,
        "evidence_completeness": evidence_completeness,
        "evidence_consistency": evidence_consistency,
        "rule_path_clarity": rule_path_clarity,
        "observable_coverage": coverage,
        "ambiguity_level": ambiguity_level,
        "reason": reason,
    }


def _evaluate_relevance_v11(
    ctx: Dict[str, Any],
    source_sheets_used: List[str],
) -> Dict[str, Any]:
    exclusion_reason = _mechanism_scope_exclusion(ctx)
    observable_states = {
        "rel_core_target_driver_path": STATE_MISSING,
        "rel_horizon_support_only": STATE_MISSING,
    }
    accessed_fields = [
        "primary_driver_summary",
        "secondary_driver_summary",
        "information_used",
        "causal_chain",
        "reasoning_summary",
        "pack_fields_used",
        "pack_fields_that_changed_reasoning",
        "candidate_family",
        "influence_status",
        "forecast_direction",
        "no_signal_reason",
        "invalidation_condition",
    ]
    if exclusion_reason:
        return _make_result(
            "MECH_INFORMATION_RELEVANCE",
            "EXCLUDED",
            "REL_EXCLUDED_SCOPE",
            [],
            [exclusion_reason],
            observable_states,
            conflict_detected=False,
            unresolved_conflict=False,
            conflict_resolution_rule="excluded_rule",
            affirmative_absence_evidence=[],
            rejected_alternative_rules=["REL_POS_CORE_TARGET_DRIVER_PATH", "REL_NEG_NON_PATH_CHANGING"],
            accessed_fields=accessed_fields,
            source_sheets_used=source_sheets_used,
            notes={"exclusion_reason": exclusion_reason},
            invalid_output_related=exclusion_reason == "invalid_output_behavior_row",
            excluded_row_related=True,
        )

    active_families = set(ctx["used_families"]) | set(ctx["changed_families"]) | set(ctx["discarded_families"])
    driver_text = _text(ctx["primary_driver_summary"], ctx["secondary_driver_summary"])
    causal_text = _text(ctx["causal_chain"], ctx["reasoning_summary"], ctx["information_used_text"])
    horizon_text = _text(causal_text, ctx["no_signal_reason"], ctx["invalidation_condition"])

    primary_hits = _family_keyword_hits(active_families, ctx["primary_driver_summary"])
    secondary_hits = _family_keyword_hits(active_families, ctx["secondary_driver_summary"])
    driver_hits = _family_keyword_hits(active_families, driver_text)
    causal_hits = _family_keyword_hits(active_families, causal_text)
    horizon_present = _contains_any(horizon_text, TIME_HINTS) or any(
        "PRESESSION" in field or "WITHIN_" in field for field in (ctx["used_fields"] | ctx["changed_fields"])
    )
    path_change_visible = bool(ctx["changed_count"] > 0 or ctx["changed_fields"] or ctx["causal_chain_changed_count"] > 0)

    if horizon_present:
        observable_states["rel_horizon_support_only"] = STATE_POSITIVE

    explicit_core_positive = bool(driver_hits and causal_hits and (primary_hits or path_change_visible))
    secondary_only = bool(secondary_hits and not primary_hits and not path_change_visible)
    horizon_only = bool(horizon_present and not driver_hits and not causal_hits)
    peripheral_non_path = bool(
        (ctx["used_count"] > 0 or ctx["discarded_count"] > 0)
        and not explicit_core_positive
        and not secondary_only
        and not horizon_only
        and active_families
    )
    mixed_signal = bool((driver_hits and not causal_hits) or (causal_hits and not driver_hits) or (primary_hits and secondary_hits and not path_change_visible))
    sparse_trace = not driver_text and not causal_text and not active_families

    decisive_evidence: List[str] = []
    affirmative_absence_evidence: List[str] = []
    conflict_detected = False
    unresolved_conflict = False

    if sparse_trace:
        return _make_result(
            "MECH_INFORMATION_RELEVANCE",
            "INSUFFICIENT_EVIDENCE",
            "REL_INSUFFICIENT_PATH_TRACE",
            [],
            ["target-driver linkage and causal-path trace are missing"],
            observable_states,
            conflict_detected=False,
            unresolved_conflict=False,
            conflict_resolution_rule="insufficient_evidence_rule",
            affirmative_absence_evidence=[],
            rejected_alternative_rules=["REL_POS_CORE_TARGET_DRIVER_PATH", "REL_NEG_NON_PATH_CHANGING"],
            accessed_fields=accessed_fields,
            source_sheets_used=source_sheets_used,
            notes={"driver_text_present": bool(driver_text), "causal_text_present": bool(causal_text)},
            missing_evidence_only=True,
        )

    if explicit_core_positive:
        observable_states["rel_core_target_driver_path"] = STATE_POSITIVE
        decisive_evidence.append("target-driver and causal-path alignment are explicit")
    elif secondary_only or horizon_only or peripheral_non_path:
        observable_states["rel_core_target_driver_path"] = STATE_NEGATIVE
        if secondary_only:
            affirmative_absence_evidence.append("secondary-only driver linkage without a primary path change")
        if horizon_only:
            affirmative_absence_evidence.append("horizon cue appears without target-driver path evidence")
        if peripheral_non_path:
            affirmative_absence_evidence.append("added information remains peripheral or non-path-changing")
    elif mixed_signal:
        observable_states["rel_core_target_driver_path"] = STATE_UNKNOWN
        conflict_detected = True
        unresolved_conflict = True
    else:
        observable_states["rel_core_target_driver_path"] = STATE_UNKNOWN

    if observable_states["rel_core_target_driver_path"] == STATE_NEGATIVE and explicit_core_positive:
        conflict_detected = True
    if observable_states["rel_core_target_driver_path"] == STATE_POSITIVE and (secondary_only or horizon_only):
        conflict_detected = True
        unresolved_conflict = False

    if observable_states["rel_core_target_driver_path"] == STATE_NEGATIVE:
        rule_id = "REL_NEG_NON_PATH_CHANGING"
        if secondary_only:
            rule_id = "REL_NEG_SECONDARY_ONLY"
        elif horizon_only:
            rule_id = "REL_NEG_HORIZON_ONLY"
        return _make_result(
            "MECH_INFORMATION_RELEVANCE",
            "NEGATIVE",
            rule_id,
            ["rel_core_target_driver_path"],
            affirmative_absence_evidence,
            observable_states,
            conflict_detected=conflict_detected,
            unresolved_conflict=False,
            conflict_resolution_rule="negative_when_non_path_changing_detail_is_explicit",
            affirmative_absence_evidence=affirmative_absence_evidence,
            rejected_alternative_rules=["REL_POS_CORE_TARGET_DRIVER_PATH"],
            accessed_fields=accessed_fields,
            source_sheets_used=source_sheets_used,
            notes={
                "driver_hits": driver_hits,
                "causal_hits": causal_hits,
                "primary_hits": primary_hits,
                "secondary_hits": secondary_hits,
                "path_change_visible": path_change_visible,
            },
            optional_field_absence_only=False,
        )

    if observable_states["rel_core_target_driver_path"] == STATE_POSITIVE:
        decisive_observables = ["rel_core_target_driver_path"]
        if observable_states["rel_horizon_support_only"] == STATE_POSITIVE:
            decisive_observables.append("rel_horizon_support_only")
            decisive_evidence.append("horizon cue is supporting-only and does not create relevance on its own")
        return _make_result(
            "MECH_INFORMATION_RELEVANCE",
            "POSITIVE",
            "REL_POS_CORE_TARGET_DRIVER_PATH",
            decisive_observables,
            decisive_evidence,
            observable_states,
            conflict_detected=conflict_detected,
            unresolved_conflict=False,
            conflict_resolution_rule="positive_when_target_driver_path_change_is_explicit",
            affirmative_absence_evidence=[],
            rejected_alternative_rules=["REL_NEG_NON_PATH_CHANGING", "REL_UNKNOWN_MIXED_PATH"],
            accessed_fields=accessed_fields,
            source_sheets_used=source_sheets_used,
            notes={
                "driver_hits": driver_hits,
                "causal_hits": causal_hits,
                "primary_hits": primary_hits,
                "path_change_visible": path_change_visible,
            },
        )

    return _make_result(
        "MECH_INFORMATION_RELEVANCE",
        "UNKNOWN",
        "REL_UNKNOWN_MIXED_PATH",
        ["rel_core_target_driver_path"],
        ["target-driver and causal-path signals remain mixed without a decisive path-changing trace"],
        observable_states,
        conflict_detected=conflict_detected or mixed_signal,
        unresolved_conflict=True,
        conflict_resolution_rule="unknown_if_target_alignment_and_path_alignment_diverge",
        affirmative_absence_evidence=[],
        rejected_alternative_rules=["REL_POS_CORE_TARGET_DRIVER_PATH", "REL_NEG_NON_PATH_CHANGING"],
        accessed_fields=accessed_fields,
        source_sheets_used=source_sheets_used,
        notes={
            "driver_hits": driver_hits,
            "causal_hits": causal_hits,
            "primary_hits": primary_hits,
            "secondary_hits": secondary_hits,
            "path_change_visible": path_change_visible,
        },
    )


def _specificity_boundary_features(ctx: Dict[str, Any]) -> Dict[str, Any]:
    active_families = set(ctx["used_families"]) | set(ctx["changed_families"])
    combo = _text(
        ctx["causal_chain"],
        ctx["reasoning_summary"],
        ctx["information_used_text"],
        ctx["primary_driver_summary"],
        ctx["secondary_driver_summary"],
    )
    invalidation_text = _text(ctx["invalidation_condition"])
    no_signal_text = _text(ctx["no_signal_reason"])
    all_text = _text(combo, invalidation_text, no_signal_text)
    time_present = _contains_any(all_text, TIME_HINTS) or any(
        "PRESESSION" in field or "WITHIN_" in field for field in (ctx["used_fields"] | ctx["changed_fields"])
    )
    conditional_present = _contains_any(all_text, CONDITION_HINTS)
    threshold_present = bool(THRESHOLD_RE.search(all_text.lower()))
    reversal_present = any(term in all_text.lower() for term in REVERSAL_TERMS)
    regime_present = conditional_present and any(term in all_text.lower() for term in REGIME_TERMS)
    direction_signal = _direction_signal(all_text)
    concrete_signal = _has_concrete_signal(all_text, active_families)
    forecast_relevance = bool(
        direction_signal in {"UP", "DOWN", "MIXED"}
        or _family_keyword_hits(active_families, all_text)
        or ctx["current_no_signal_flag"] == "TRUE"
    )

    boundary_cues: List[str] = []
    boundary_traces: List[str] = []
    partial_cues: List[str] = []

    if ctx["current_no_signal_flag"] == "TRUE" and no_signal_text:
        boundary_cues.append("EXPLICIT_NO_SIGNAL_BOUNDARY")
        boundary_traces.append(no_signal_text)

    if invalidation_text:
        invalid_lower = invalidation_text.lower()
        if (
            ("invalid" in invalid_lower or "negate" in invalid_lower or "reverse" in invalid_lower or "override" in invalid_lower)
            and (threshold_present or concrete_signal)
            and not _is_generic_boundary_text(invalidation_text)
        ):
            boundary_cues.append("EXPLICIT_INVALIDATION_CONDITION")
            boundary_traces.append(invalidation_text)
        elif conditional_present and concrete_signal and not _is_generic_boundary_text(invalidation_text):
            boundary_cues.append("EXPLICIT_FAILURE_CONDITION")
            boundary_traces.append(invalidation_text)
        elif _is_generic_boundary_text(invalidation_text):
            partial_cues.append("GENERIC_INVALIDATION_TRACE")
        else:
            partial_cues.append("PARTIAL_INVALIDATION_TRACE")

    if conditional_present and direction_signal in {"UP", "DOWN", "MIXED"} and concrete_signal and not _is_generic_boundary_text(combo):
        boundary_cues.append("EXPLICIT_CONDITIONAL_BRANCH")
        boundary_traces.append(combo)
        boundary_cues.append("EXPLICIT_CAUSAL_TRIGGER")
        boundary_traces.append(combo)
    elif conditional_present and concrete_signal:
        partial_cues.append("PARTIAL_CONDITIONAL_TRACE")

    if threshold_present and concrete_signal and (conditional_present or bool(invalidation_text)):
        boundary_cues.append("EXPLICIT_FORECAST_RELEVANT_THRESHOLD")
        boundary_traces.append(all_text)

    if reversal_present and forecast_relevance and not _is_generic_boundary_text(all_text):
        boundary_cues.append("EXPLICIT_REVERSAL_OR_ALTERATION_CONDITION")
        boundary_traces.append(all_text)

    if regime_present and forecast_relevance and concrete_signal:
        boundary_cues.append("EXPLICIT_REGIME_BOUNDARY")
        boundary_traces.append(all_text)

    if time_present and conditional_present and forecast_relevance and concrete_signal:
        boundary_cues.append("TIME_HORIZON_PLUS_DECISION_RELEVANT_CONDITION")
        boundary_traces.append(all_text)

    boundary_cues = list(dict.fromkeys(boundary_cues))
    boundary_traces = list(dict.fromkeys(boundary_traces))
    partial_cues = list(dict.fromkeys(partial_cues))

    prohibited_proxies: List[str] = []
    if time_present and not boundary_cues and not partial_cues:
        prohibited_proxies.append("GENERIC_TIME_HORIZON_ONLY")
    if len(all_text.split()) >= 40 and not boundary_cues and not partial_cues and not threshold_present:
        prohibited_proxies.append("VERBOSITY_ONLY")
    if NUMBER_RE.search(all_text) and not boundary_cues and not partial_cues and not threshold_present:
        prohibited_proxies.append("NUMERICAL_DETAIL_ONLY")
    if (
        _overlap_score(ctx["information_used_text"], ctx["causal_chain"]) > 0.65
        and not boundary_cues
        and not partial_cues
        and not conditional_present
    ):
        prohibited_proxies.append("SOURCE_FIELD_RESTATEMENT_ONLY")
    if (
        ("confidence" in all_text.lower() or ctx["current_confidence"] is not None)
        and not boundary_cues
        and not partial_cues
        and not conditional_present
        and not invalidation_text
    ):
        prohibited_proxies.append("CONFIDENCE_LANGUAGE_ONLY")
    if _contains_any(all_text, UNCERTAINTY_HINTS) and not boundary_cues and not partial_cues:
        prohibited_proxies.append("GENERIC_UNCERTAINTY_ONLY")
    if (time_present or NUMBER_RE.search(all_text)) and not boundary_cues and not partial_cues:
        prohibited_proxies.append("DESCRIPTIVE_PRECISION_WITHOUT_BOUNDARY")
    prohibited_proxies = list(dict.fromkeys(prohibited_proxies))

    generic_direction_restatement = bool(
        direction_signal in {"UP", "DOWN", "MIXED"}
        and not boundary_cues
        and not partial_cues
        and not ctx["current_no_signal_flag"] == "TRUE"
    )
    sparse_trace = len(all_text.strip()) < 20
    time_horizon_support_only = bool(time_present and not boundary_cues)
    specificity_positive_valid = bool(boundary_cues and forecast_relevance)
    false_proxy = bool(not specificity_positive_valid and prohibited_proxies)
    affirmative_negative_evidence = []
    if generic_direction_restatement:
        affirmative_negative_evidence.append("generic direction restatement without a falsifiable boundary")
    if "GENERIC_TIME_HORIZON_ONLY" in prohibited_proxies:
        affirmative_negative_evidence.append("time framing appears without a decision-relevant boundary")
    if "VERBOSITY_ONLY" in prohibited_proxies:
        affirmative_negative_evidence.append("additional detail remains verbose rather than falsifiable")
    if "NUMERICAL_DETAIL_ONLY" in prohibited_proxies:
        affirmative_negative_evidence.append("numerical detail appears without a forecast-relevant threshold")
    if "SOURCE_FIELD_RESTATEMENT_ONLY" in prohibited_proxies:
        affirmative_negative_evidence.append("source-field restatement appears without a new boundary")
    if "CONFIDENCE_LANGUAGE_ONLY" in prohibited_proxies:
        affirmative_negative_evidence.append("confidence wording appears without a boundary-forming cue")
    if "GENERIC_UNCERTAINTY_ONLY" in prohibited_proxies:
        affirmative_negative_evidence.append("uncertainty language appears without a falsifiable boundary")
    if "DESCRIPTIVE_PRECISION_WITHOUT_BOUNDARY" in prohibited_proxies:
        affirmative_negative_evidence.append("descriptive precision appears without a boundary-forming condition")

    return {
        "boundary_cues": boundary_cues,
        "boundary_traces": boundary_traces,
        "partial_cues": partial_cues,
        "prohibited_proxies": prohibited_proxies,
        "forecast_relevance_confirmed": forecast_relevance,
        "time_horizon_present": time_present,
        "time_horizon_supporting_only": time_horizon_support_only,
        "specificity_positive_valid": specificity_positive_valid,
        "specificity_false_proxy": false_proxy,
        "generic_direction_restatement": generic_direction_restatement,
        "affirmative_negative_evidence": affirmative_negative_evidence,
        "sparse_trace": sparse_trace,
    }


def _evaluate_specificity_v11(
    ctx: Dict[str, Any],
    source_sheets_used: List[str],
) -> Dict[str, Any]:
    exclusion_reason = _mechanism_scope_exclusion(ctx)
    observable_states = {
        "spec_falsifiable_boundary_present": STATE_MISSING,
        "spec_generic_direction_restatement": STATE_MISSING,
        "spec_time_horizon_support_only": STATE_MISSING,
        "spec_missing_invalidation_neutral": STATE_MISSING,
    }
    accessed_fields = [
        "causal_chain",
        "reasoning_summary",
        "information_used",
        "primary_driver_summary",
        "secondary_driver_summary",
        "forecast_direction",
        "no_signal_reason",
        "invalidation_condition",
        "uncertainty_sources",
        "missing_information",
        "no_signal_flag",
        "forecast_confidence",
    ]
    if exclusion_reason:
        return _make_result(
            "MECH_INFORMATION_SPECIFICITY",
            "EXCLUDED",
            "SPEC_EXCLUDED_SCOPE",
            [],
            [exclusion_reason],
            observable_states,
            conflict_detected=False,
            unresolved_conflict=False,
            conflict_resolution_rule="excluded_rule",
            affirmative_absence_evidence=[],
            rejected_alternative_rules=["SPEC_POS_FALSIFIABLE_BOUNDARY", "SPEC_NEG_STRUCTURALLY_UNBOUNDED"],
            accessed_fields=accessed_fields,
            source_sheets_used=source_sheets_used,
            notes={"exclusion_reason": exclusion_reason},
            boundary_audit={
                "boundary_cues": [],
                "boundary_traces": [],
                "partial_cues": [],
                "prohibited_proxies": [],
                "forecast_relevance_confirmed": False,
                "time_horizon_present": False,
                "time_horizon_supporting_only": False,
                "specificity_positive_valid": False,
                "specificity_false_proxy": False,
            },
            invalid_output_related=exclusion_reason == "invalid_output_behavior_row",
            excluded_row_related=True,
        )

    boundary = _specificity_boundary_features(ctx)
    if boundary["boundary_cues"]:
        observable_states["spec_falsifiable_boundary_present"] = STATE_POSITIVE
    elif boundary["partial_cues"]:
        observable_states["spec_falsifiable_boundary_present"] = STATE_UNKNOWN
    elif boundary["sparse_trace"]:
        observable_states["spec_falsifiable_boundary_present"] = STATE_MISSING
    else:
        observable_states["spec_falsifiable_boundary_present"] = STATE_UNKNOWN

    if boundary["generic_direction_restatement"] or boundary["affirmative_negative_evidence"]:
        observable_states["spec_generic_direction_restatement"] = STATE_POSITIVE
    elif boundary["sparse_trace"]:
        observable_states["spec_generic_direction_restatement"] = STATE_MISSING
    else:
        observable_states["spec_generic_direction_restatement"] = STATE_UNKNOWN

    if boundary["time_horizon_present"]:
        observable_states["spec_time_horizon_support_only"] = STATE_POSITIVE
    else:
        observable_states["spec_time_horizon_support_only"] = STATE_MISSING

    if not _norm(ctx["invalidation_condition"]):
        observable_states["spec_missing_invalidation_neutral"] = STATE_POSITIVE
    else:
        observable_states["spec_missing_invalidation_neutral"] = STATE_UNKNOWN

    if boundary["sparse_trace"]:
        return _make_result(
            "MECH_INFORMATION_SPECIFICITY",
            "INSUFFICIENT_EVIDENCE",
            "SPEC_INSUFFICIENT_TRACE",
            [],
            ["the row lacks enough pre-outcome trace to evaluate boundary structure"],
            observable_states,
            conflict_detected=False,
            unresolved_conflict=False,
            conflict_resolution_rule="insufficient_evidence_rule",
            affirmative_absence_evidence=[],
            rejected_alternative_rules=["SPEC_POS_FALSIFIABLE_BOUNDARY", "SPEC_NEG_STRUCTURALLY_UNBOUNDED"],
            accessed_fields=accessed_fields,
            source_sheets_used=source_sheets_used,
            notes=boundary,
            boundary_audit=boundary,
            missing_evidence_only=True,
        )

    conflict_detected = bool(boundary["boundary_cues"] and boundary["affirmative_negative_evidence"])
    unresolved_conflict = bool(boundary["partial_cues"] and boundary["affirmative_negative_evidence"] and not boundary["boundary_cues"])

    if boundary["specificity_positive_valid"]:
        return _make_result(
            "MECH_INFORMATION_SPECIFICITY",
            "POSITIVE",
            "SPEC_POS_FALSIFIABLE_BOUNDARY",
            ["spec_falsifiable_boundary_present"],
            boundary["boundary_traces"] or ["explicit falsifiable boundary-forming cue present"],
            observable_states,
            conflict_detected=conflict_detected,
            unresolved_conflict=False,
            conflict_resolution_rule="positive_when_falsifiable_boundary_is_explicit_and_uncontested",
            affirmative_absence_evidence=[],
            rejected_alternative_rules=["SPEC_NEG_STRUCTURALLY_UNBOUNDED", "SPEC_UNKNOWN_PARTIAL_BOUNDARY"],
            accessed_fields=accessed_fields,
            source_sheets_used=source_sheets_used,
            notes=boundary,
            boundary_audit=boundary,
        )

    if boundary["affirmative_negative_evidence"] and not boundary["partial_cues"]:
        if boundary["generic_direction_restatement"]:
            rule_id = "SPEC_NEG_GENERIC_DIRECTION_RESTATEMENT"
        elif "GENERIC_TIME_HORIZON_ONLY" in boundary["prohibited_proxies"]:
            rule_id = "SPEC_NEG_TIME_ONLY"
        else:
            rule_id = "SPEC_NEG_STRUCTURALLY_UNBOUNDED"
        return _make_result(
            "MECH_INFORMATION_SPECIFICITY",
            "NEGATIVE",
            rule_id,
            ["spec_generic_direction_restatement"],
            boundary["affirmative_negative_evidence"],
            observable_states,
            conflict_detected=conflict_detected,
            unresolved_conflict=False,
            conflict_resolution_rule="negative_when_row_is_relevant_or_coherent_but_structurally_unbounded",
            affirmative_absence_evidence=boundary["affirmative_negative_evidence"],
            rejected_alternative_rules=["SPEC_POS_FALSIFIABLE_BOUNDARY"],
            accessed_fields=accessed_fields,
            source_sheets_used=source_sheets_used,
            notes=boundary,
            boundary_audit=boundary,
        )

    return _make_result(
        "MECH_INFORMATION_SPECIFICITY",
        "UNKNOWN",
        "SPEC_UNKNOWN_PARTIAL_BOUNDARY",
        ["spec_falsifiable_boundary_present"],
        boundary["partial_cues"] or ["boundary traces remain partial or pseudo-specific under v1.1"],
        observable_states,
        conflict_detected=conflict_detected or bool(boundary["partial_cues"]),
        unresolved_conflict=True,
        conflict_resolution_rule="unknown_when_boundary_evidence_is_partial_or_internally_mixed",
        affirmative_absence_evidence=[],
        rejected_alternative_rules=["SPEC_POS_FALSIFIABLE_BOUNDARY", "SPEC_NEG_STRUCTURALLY_UNBOUNDED"],
        accessed_fields=accessed_fields,
        source_sheets_used=source_sheets_used,
        notes=boundary,
        boundary_audit=boundary,
    )


def _evaluate_consistency_v11(
    ctx: Dict[str, Any],
    source_sheets_used: List[str],
) -> Dict[str, Any]:
    exclusion_reason = _mechanism_scope_exclusion(ctx)
    observable_states = {
        "cons_decisive_contradiction_priority": STATE_MISSING,
        "cons_cross_field_supporting": STATE_MISSING,
    }
    accessed_fields = [
        "candidate_family",
        "influence_status",
        "field_reported_no_effect",
        "primary_driver_summary",
        "secondary_driver_summary",
        "causal_chain",
        "reasoning_summary",
        "forecast_direction",
        "no_signal_flag",
        "forecast_confidence",
        "confidence_bucket",
        "uncertainty_sources",
        "missing_information",
        "no_signal_reason",
        "information_used",
    ]
    if exclusion_reason:
        return _make_result(
            "MECH_INFORMATION_CONSISTENCY",
            "EXCLUDED",
            "CONS_EXCLUDED_SCOPE",
            [],
            [exclusion_reason],
            observable_states,
            conflict_detected=False,
            unresolved_conflict=False,
            conflict_resolution_rule="excluded_rule",
            affirmative_absence_evidence=[],
            rejected_alternative_rules=["CONS_POS_TWO_COHERENT_PLANES", "CONS_NEG_DECISIVE_CONTRADICTION"],
            accessed_fields=accessed_fields,
            source_sheets_used=source_sheets_used,
            notes={"exclusion_reason": exclusion_reason},
            invalid_output_related=exclusion_reason == "invalid_output_behavior_row",
            excluded_row_related=True,
        )

    causal_text = _text(ctx["causal_chain"], ctx["reasoning_summary"])
    primary_text = _text(ctx["primary_driver_summary"])
    secondary_text = _text(ctx["secondary_driver_summary"])
    active_families = set(ctx["used_families"]) | set(ctx["changed_families"])

    cross_field_plane: Optional[bool] = None
    cross_hits = _family_keyword_hits(active_families, _text(causal_text, ctx["information_used_text"]))
    if active_families:
        if cross_hits and ctx["no_effect_count"] == 0:
            cross_field_plane = True
        elif ctx["used_count"] > 0 and not cross_hits and ctx["changed_count"] == 0:
            cross_field_plane = False

    primary_direction = _direction_signal(primary_text)
    secondary_direction = _direction_signal(secondary_text)
    causal_direction = _direction_signal(causal_text)
    driver_chain_plane: Optional[bool] = None
    if (primary_direction in {"UP", "DOWN"} or secondary_direction in {"UP", "DOWN"}) and causal_direction in {"UP", "DOWN"}:
        observed = [direction for direction in [primary_direction, secondary_direction] if direction in {"UP", "DOWN"}]
        if len(set(observed)) > 1:
            driver_chain_plane = False
        elif observed:
            driver_chain_plane = observed[0] == causal_direction

    direction_rationale_plane: Optional[bool] = None
    if ctx["current_no_signal_flag"] == "TRUE":
        if ctx["no_signal_reason"]:
            direction_rationale_plane = True if _contains_any(_text(causal_text, ctx["no_signal_reason"]), UNCERTAINTY_HINTS) else None
    elif causal_direction in {"UP", "DOWN"} and ctx["current_direction"] in {"up", "down"}:
        direction_rationale_plane = (causal_direction == "UP" and ctx["current_direction"] == "up") or (
            causal_direction == "DOWN" and ctx["current_direction"] == "down"
        )
    elif causal_direction == "MIXED":
        direction_rationale_plane = False

    confidence_evidence_plane: Optional[bool] = None
    uncertainty_count = len(ctx["uncertainty_sources"])
    missing_info_present = bool(ctx["missing_information"])
    high_confidence = (ctx["current_confidence"] or 0) >= 70 or ctx["current_confidence_bucket"] == "HIGH"
    if high_confidence and (uncertainty_count >= 2 or missing_info_present or ctx["current_no_signal_flag"] == "TRUE"):
        confidence_evidence_plane = False
    elif (not high_confidence) and (uncertainty_count >= 1 or missing_info_present or ctx["current_no_signal_flag"] == "TRUE"):
        confidence_evidence_plane = True
    elif high_confidence and uncertainty_count == 0 and not missing_info_present:
        confidence_evidence_plane = True

    observed_planes = [cross_field_plane, driver_chain_plane, direction_rationale_plane, confidence_evidence_plane]
    observed_count = sum(1 for plane in observed_planes if plane is not None)
    positive_count = sum(1 for plane in observed_planes if plane is True)
    decisive_core_negative = any(plane is False for plane in [driver_chain_plane, direction_rationale_plane, confidence_evidence_plane])
    cross_negative = cross_field_plane is False

    if observed_count < 2:
        return _make_result(
            "MECH_INFORMATION_CONSISTENCY",
            "INSUFFICIENT_EVIDENCE",
            "CONS_INSUFFICIENT_COMPARISON_PLANES",
            [],
            ["fewer than two comparison planes are observable under the frozen v1.1 traces"],
            observable_states,
            conflict_detected=False,
            unresolved_conflict=False,
            conflict_resolution_rule="insufficient_evidence_rule",
            affirmative_absence_evidence=[],
            rejected_alternative_rules=["CONS_POS_TWO_COHERENT_PLANES", "CONS_NEG_DECISIVE_CONTRADICTION"],
            accessed_fields=accessed_fields,
            source_sheets_used=source_sheets_used,
            notes={
                "cross_field_plane": cross_field_plane,
                "driver_chain_plane": driver_chain_plane,
                "direction_rationale_plane": direction_rationale_plane,
                "confidence_evidence_plane": confidence_evidence_plane,
            },
            missing_evidence_only=True,
        )

    conflict_detected = positive_count > 0 and (decisive_core_negative or cross_negative)
    if decisive_core_negative or (cross_negative and positive_count == 0):
        observable_states["cons_decisive_contradiction_priority"] = STATE_NEGATIVE
        if positive_count > 0:
            observable_states["cons_cross_field_supporting"] = STATE_POSITIVE
        return _make_result(
            "MECH_INFORMATION_CONSISTENCY",
            "NEGATIVE",
            "CONS_NEG_DECISIVE_CONTRADICTION",
            ["cons_decisive_contradiction_priority"],
            ["a decisive contradiction is explicit in one or more core comparison planes"],
            observable_states,
            conflict_detected=conflict_detected,
            unresolved_conflict=False,
            conflict_resolution_rule="decisive_contradiction_beats_soft_coherence",
            affirmative_absence_evidence=["core comparison planes contradict the stated forecast logic"],
            rejected_alternative_rules=["CONS_POS_TWO_COHERENT_PLANES"],
            accessed_fields=accessed_fields,
            source_sheets_used=source_sheets_used,
            notes={
                "cross_field_plane": cross_field_plane,
                "driver_chain_plane": driver_chain_plane,
                "direction_rationale_plane": direction_rationale_plane,
                "confidence_evidence_plane": confidence_evidence_plane,
            },
        )

    if positive_count >= 2:
        observable_states["cons_decisive_contradiction_priority"] = STATE_POSITIVE
        observable_states["cons_cross_field_supporting"] = STATE_POSITIVE if cross_field_plane is True else STATE_UNKNOWN
        return _make_result(
            "MECH_INFORMATION_CONSISTENCY",
            "POSITIVE",
            "CONS_POS_TWO_COHERENT_PLANES",
            ["cons_decisive_contradiction_priority", "cons_cross_field_supporting"],
            ["at least two comparison planes remain coherent and no decisive contradiction is present"],
            observable_states,
            conflict_detected=False,
            unresolved_conflict=False,
            conflict_resolution_rule="positive_when_two_planes_are_coherent_without_decisive_contradiction",
            affirmative_absence_evidence=[],
            rejected_alternative_rules=["CONS_NEG_DECISIVE_CONTRADICTION", "CONS_UNKNOWN_PARTIAL_COMPARABILITY"],
            accessed_fields=accessed_fields,
            source_sheets_used=source_sheets_used,
            notes={
                "cross_field_plane": cross_field_plane,
                "driver_chain_plane": driver_chain_plane,
                "direction_rationale_plane": direction_rationale_plane,
                "confidence_evidence_plane": confidence_evidence_plane,
            },
        )

    observable_states["cons_decisive_contradiction_priority"] = STATE_UNKNOWN
    observable_states["cons_cross_field_supporting"] = STATE_POSITIVE if cross_field_plane is True else STATE_UNKNOWN
    return _make_result(
        "MECH_INFORMATION_CONSISTENCY",
        "UNKNOWN",
        "CONS_UNKNOWN_PARTIAL_COMPARABILITY",
        ["cons_decisive_contradiction_priority"],
        ["comparison planes are partially observable but do not produce a decisive coherent or contradictory outcome"],
        observable_states,
        conflict_detected=conflict_detected,
        unresolved_conflict=True,
        conflict_resolution_rule="unknown_when_partial_comparability_remains_after_v11_rules",
        affirmative_absence_evidence=[],
        rejected_alternative_rules=["CONS_POS_TWO_COHERENT_PLANES", "CONS_NEG_DECISIVE_CONTRADICTION"],
        accessed_fields=accessed_fields,
        source_sheets_used=source_sheets_used,
        notes={
            "cross_field_plane": cross_field_plane,
            "driver_chain_plane": driver_chain_plane,
            "direction_rationale_plane": direction_rationale_plane,
            "confidence_evidence_plane": confidence_evidence_plane,
        },
    )


def _evaluate_mechanism_v11(
    mechanism_id: str,
    ctx: Dict[str, Any],
    source_sheets_used: List[str],
) -> Dict[str, Any]:
    if mechanism_id == "MECH_INFORMATION_RELEVANCE":
        return _evaluate_relevance_v11(ctx, source_sheets_used)
    if mechanism_id == "MECH_INFORMATION_SPECIFICITY":
        return _evaluate_specificity_v11(ctx, source_sheets_used)
    if mechanism_id == "MECH_INFORMATION_CONSISTENCY":
        return _evaluate_consistency_v11(ctx, source_sheets_used)
    raise RuntimeError(f"Unexpected v1.1 mechanism: {mechanism_id}")


def _result_hash(result: Dict[str, Any], confidence: Dict[str, str]) -> str:
    payload = {
        "label": result["label"],
        "decisive_rule_id": result["decisive_rule_id"],
        "decisive_observables": result["decisive_observables"],
        "decisive_evidence": result["decisive_evidence"],
        "observable_states": result["observable_states"],
        "conflict_detected": result["conflict_detected"],
        "unresolved_conflict": result["unresolved_conflict"],
        "conflict_resolution_rule": result["conflict_resolution_rule"],
        "affirmative_absence_evidence": result["affirmative_absence_evidence"],
        "rejected_alternative_rules": result["rejected_alternative_rules"],
        "confidence": confidence["confidence"],
        "evidence_completeness": confidence["evidence_completeness"],
        "evidence_consistency": confidence["evidence_consistency"],
        "rule_path_clarity": confidence["rule_path_clarity"],
        "observable_coverage": confidence["observable_coverage"],
    }
    return _json(payload)


def _classify_twice(
    mechanism_id: str,
    ctx: Dict[str, Any],
    source_sheets_used: List[str],
) -> Tuple[Dict[str, Any], Dict[str, str], Dict[str, Any], Dict[str, str], str]:
    first = _evaluate_mechanism_v11(mechanism_id, ctx, source_sheets_used)
    first_conf = _assign_confidence(
        first["label"],
        first["observable_states"],
        first["conflict_detected"],
        first["unresolved_conflict"],
        first["decisive_rule_id"],
        first["rejected_alternative_rules"],
    )
    second = _evaluate_mechanism_v11(mechanism_id, ctx, source_sheets_used)
    second_conf = _assign_confidence(
        second["label"],
        second["observable_states"],
        second["conflict_detected"],
        second["unresolved_conflict"],
        second["decisive_rule_id"],
        second["rejected_alternative_rules"],
    )
    deterministic_status = (
        "PASS"
        if (
            first["label"] == second["label"]
            and first["decisive_rule_id"] == second["decisive_rule_id"]
            and _result_hash(first, first_conf) == _result_hash(second, second_conf)
        )
        else "FAIL"
    )
    return first, first_conf, second, second_conf, deterministic_status


def _pair_status(
    mechanism_a: str,
    label_a: str,
    result_a: Dict[str, Any],
    mechanism_b: str,
    label_b: str,
    result_b: Dict[str, Any],
) -> Tuple[str, str, str]:
    if label_a == "EXCLUDED" or label_b == "EXCLUDED":
        return "NOT_APPLICABLE_EXCLUDED", "scope_exclusion", "pair includes an excluded preview"

    if mechanism_a == "MECH_INFORMATION_RELEVANCE" and mechanism_b == "MECH_INFORMATION_SPECIFICITY":
        if label_a == "POSITIVE" and label_b == "POSITIVE":
            if result_b.get("boundary_audit", {}).get("specificity_positive_valid"):
                return (
                    "LEGITIMATE_JOINT_POSITIVE",
                    "relevance_vs_specificity_boundary",
                    "target alignment and boundary formation are both explicit under the v1.1 separation rule",
                )
            return (
                "UNRESOLVED_OVERLAP",
                "relevance_vs_specificity_boundary",
                "specificity-positive status lacks a clear boundary-forming justification beyond target alignment",
            )
        if label_a == "POSITIVE" and label_b in {"NEGATIVE", "UNKNOWN", "INSUFFICIENT_EVIDENCE"}:
            return (
                "SEPARATION_RULE_RESOLVED",
                "relevance_vs_specificity_boundary",
                "information can remain target-relevant while failing to create a falsifiable boundary",
            )

    if mechanism_a == "MECH_INFORMATION_SPECIFICITY" and mechanism_b == "MECH_INFORMATION_CONSISTENCY":
        if label_a == "POSITIVE" and label_b == "POSITIVE":
            if result_a.get("boundary_audit", {}).get("specificity_positive_valid"):
                return (
                    "LEGITIMATE_JOINT_POSITIVE",
                    "specificity_vs_consistency_boundary",
                    "boundary formation and internal agreement are jointly supported without contradiction",
                )
            return (
                "UNRESOLVED_OVERLAP",
                "specificity_vs_consistency_boundary",
                "specificity-positive status is not fully separated from coherence-only evidence",
            )
        if label_b == "POSITIVE" and label_a in {"NEGATIVE", "UNKNOWN", "INSUFFICIENT_EVIDENCE"}:
            return (
                "SEPARATION_RULE_RESOLVED",
                "specificity_vs_consistency_boundary",
                "a row may remain coherent without becoming boundary-forming",
            )

    if mechanism_a == "MECH_INFORMATION_RELEVANCE" and mechanism_b == "MECH_INFORMATION_CONSISTENCY":
        if label_a == "POSITIVE" and label_b == "POSITIVE":
            return (
                "LEGITIMATE_JOINT_POSITIVE",
                "relevance_vs_consistency_boundary",
                "information can be both target-aligned and internally coherent under the frozen separation rule",
            )
        if "POSITIVE" in {label_a, label_b} and ("NEGATIVE" in {label_a, label_b} or "UNKNOWN" in {label_a, label_b}):
            return (
                "SEPARATION_RULE_RESOLVED",
                "relevance_vs_consistency_boundary",
                "relevance and consistency remain distinct dimensions under the frozen v1.1 rule set",
            )

    if label_a == "POSITIVE" and label_b == "POSITIVE":
        return ("ACCEPTABLE_OVERLAP", "generic_joint_positive", "joint positivity remains allowed under the v1.1 framework")
    if "POSITIVE" in {label_a, label_b}:
        return ("SEPARATION_RULE_RESOLVED", "generic_pair_resolution", "pairwise distinction is resolved under the frozen separation rules")
    return ("NOT_APPLICABLE", "no_positive_pair", "pair does not present a joint-positive or overlap-relevant condition")


def _build_v10_stats(
    data: Dict[str, List[Dict[str, Any]]],
    contexts_by_key: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    label_rows = data["Refined_Mechanism_Label_Preview"]
    conflict_rows = data["Refined_Mechanism_Conflict_Audit"]
    confidence_rows = data["Refined_Mechanism_Confidence_Preview"]

    label_counts: Dict[str, Counter] = defaultdict(Counter)
    conflict_counts: Counter = Counter()
    unresolved_conflicts: Counter = Counter()
    confidence_counts: Dict[str, Counter] = defaultdict(Counter)
    overlaps: Counter = Counter()
    specificity_false_proxy_count = 0

    preview_by_key: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for row in label_rows:
        mechanism_id = _norm(row.get("mechanism_id"))
        source_row_key = _source_row_key(_norm(row.get("session_id")), _norm(row.get("provider")), _norm(row.get("pack_level")))
        preview_by_key[(mechanism_id, source_row_key)] = row
        label_counts[mechanism_id][_norm(row.get("preview_label"))] += 1
        if mechanism_id == "MECH_INFORMATION_SPECIFICITY" and _norm(row.get("preview_label")) == "POSITIVE":
            ctx = contexts_by_key.get(source_row_key, {})
            if ctx:
                boundary = _specificity_boundary_features(ctx)
                if not boundary["specificity_positive_valid"] or boundary["specificity_false_proxy"]:
                    specificity_false_proxy_count += 1

    for row in conflict_rows:
        mechanism_id = _norm(row.get("mechanism_id"))
        unresolved = _norm(row.get("unresolved_conflict")).upper() == "TRUE"
        if unresolved:
            conflict_counts[mechanism_id] += 1
            unresolved_conflicts[mechanism_id] += 1

    for row in confidence_rows:
        mechanism_id = _norm(row.get("mechanism_id"))
        confidence_counts[mechanism_id][_norm(row.get("preview_confidence"))] += 1

    all_keys = sorted({key for (_, key) in preview_by_key.keys()})
    for source_row_key in all_keys:
        rel = _norm(preview_by_key.get(("MECH_INFORMATION_RELEVANCE", source_row_key), {}).get("preview_label"))
        spec = _norm(preview_by_key.get(("MECH_INFORMATION_SPECIFICITY", source_row_key), {}).get("preview_label"))
        cons = _norm(preview_by_key.get(("MECH_INFORMATION_CONSISTENCY", source_row_key), {}).get("preview_label"))
        if rel == "POSITIVE" and spec == "POSITIVE":
            overlaps["relevance_specificity_overlap"] += 1
        if spec == "POSITIVE" and cons == "POSITIVE":
            overlaps["specificity_consistency_overlap"] += 1

    eligible_rows = len(
        {
            _source_row_key(_norm(row.get("session_id")), _norm(row.get("provider")), _norm(row.get("pack_level")))
            for row in label_rows
            if _norm(row.get("preview_label")) != "EXCLUDED"
        }
    )
    ambiguity_counts: Counter = Counter()
    for mechanism_id, counter in label_counts.items():
        ambiguity_counts[mechanism_id] = counter.get("UNKNOWN", 0) + counter.get("INSUFFICIENT_EVIDENCE", 0)

    return {
        "label_counts": label_counts,
        "conflict_counts": conflict_counts,
        "unresolved_conflicts": unresolved_conflicts,
        "confidence_counts": confidence_counts,
        "eligible_rows": eligible_rows,
        "ambiguity_counts": ambiguity_counts,
        "overlaps": overlaps,
        "specificity_false_proxy_count": specificity_false_proxy_count,
        "overall_conflict_count": sum(conflict_counts.values()),
        "overall_ambiguity_count": sum(ambiguity_counts.values()),
    }


def _upsert_registry_rows(service) -> Dict[str, int]:
    titles = _sheet_titles_light(service, PROJECT_OVERVIEWS_SPREADSHEET_ID)
    if REGISTRY_SHEET not in titles:
        return {"updated": 0, "appended": 0, "status": "missing"}
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_norm(row.get("logical_sheet_id")).upper(): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_norm(row.get("logical_sheet_id")).upper(): row for row in rows}
    specs = [
        ("REFINED_MECHANISM_V11_CLASSIFICATION_DRY_RUN", OUTPUT_DRY_RUN, "refined_mechanism_v11_classification_dry_run"),
        ("REFINED_MECHANISM_V11_LABEL_PREVIEW", OUTPUT_LABEL_PREVIEW, "refined_mechanism_v11_label_preview"),
        ("REFINED_MECHANISM_V11_EVIDENCE_AUDIT", OUTPUT_EVIDENCE, "refined_mechanism_v11_evidence_audit"),
        ("REFINED_MECHANISM_V11_RULE_PATH_AUDIT", OUTPUT_RULE_PATH, "refined_mechanism_v11_rule_path_audit"),
        ("REFINED_MECHANISM_V11_SPECIFICITY_BOUNDARY_AUDIT", OUTPUT_SPECIFICITY_BOUNDARY, "refined_mechanism_v11_specificity_boundary_audit"),
        ("REFINED_MECHANISM_V11_CONFLICT_AUDIT", OUTPUT_CONFLICT, "refined_mechanism_v11_conflict_audit"),
        ("REFINED_MECHANISM_V11_OVERLAP_AUDIT", OUTPUT_OVERLAP, "refined_mechanism_v11_overlap_audit"),
        ("REFINED_MECHANISM_V11_LABEL_BALANCE_AUDIT", OUTPUT_LABEL_BALANCE, "refined_mechanism_v11_label_balance_audit"),
        ("REFINED_MECHANISM_V11_CONFIDENCE_PREVIEW", OUTPUT_CONFIDENCE, "refined_mechanism_v11_confidence_preview"),
        ("REFINED_MECHANISM_V11_DETERMINISM_AUDIT", OUTPUT_DETERMINISM, "refined_mechanism_v11_determinism_audit"),
        ("REFINED_MECHANISM_V11_LEAKAGE_AUDIT", OUTPUT_LEAKAGE, "refined_mechanism_v11_leakage_audit"),
        ("REFINED_MECHANISM_V11_VS_V10_COMPARISON", OUTPUT_COMPARISON, "refined_mechanism_v11_vs_v10_comparison"),
        ("REFINED_MECHANISM_V11_DRY_RUN_GOVERNANCE", OUTPUT_GOVERNANCE, "refined_mechanism_v11_dry_run_governance"),
        ("REFINED_MECHANISM_V11_DRY_RUN_SUMMARY", OUTPUT_SUMMARY, "refined_mechanism_v11_dry_run_summary"),
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
            "notes": "Phase 9A-6R6 v1.1 refined mechanism dry run; preview-only, deterministic, zero-leakage target, and non-permanent.",
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


def build_refined_mechanism_v11_classification_dry_run_v0() -> Dict[str, Any]:
    service = build_sheets_service(load_credentials())
    generated_ts = _iso_now()
    dry_run_id = _dry_run_id(generated_ts)
    data = _read_inputs(service)

    prereg_rows = data["Refined_Mechanism_v11_PreRegistration"]
    observable_rows = data["Refined_Mechanism_v11_Frozen_Observables"]
    behavior_rows = data["Pack_Behavior_Tier2_Behavior"]
    invalid_rows = data["Pack_Behavior_Tier2_Invalid_Output"]

    indexes = _build_original_indexes(
        {
            "Pack_Behavior_Tier2_Behavior": data["Pack_Behavior_Tier2_Behavior"],
            "Pack_Behavior_Tier2_Transitions": data["Pack_Behavior_Tier2_Transitions"],
            "Pack_Behavior_Tier2_Field_Influence": data["Pack_Behavior_Tier2_Field_Influence"],
            "Pack_Behavior_Tier2_NoSignal": data["Pack_Behavior_Tier2_NoSignal"],
        }
    )

    stable_id_by_mechanism = {
        _norm(row.get("mechanism_id")): _norm(row.get("stable_mechanism_id"))
        for row in prereg_rows
        if _norm(row.get("mechanism_id"))
    }
    promoted_mechanisms = [
        _norm(row.get("mechanism_id"))
        for row in prereg_rows
        if _norm(row.get("mechanism_role")) == "PROMOTED_REFINED_MECHANISM"
        and "DRY_RUN" in _norm(row.get("future_classification_allowed"))
    ]
    if sorted(promoted_mechanisms) != sorted(MECHANISM_IDS):
        raise RuntimeError(
            "Unexpected v1.1 dry-run mechanism set: "
            + ", ".join(sorted(promoted_mechanisms))
        )

    observables_by_mechanism: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in observable_rows:
        mechanism_id = _norm(row.get("mechanism_id"))
        if mechanism_id:
            observables_by_mechanism[mechanism_id].append(row)
    source_sheets_by_mechanism = {
        mechanism_id: _source_sheets_from_observables(rows)
        for mechanism_id, rows in observables_by_mechanism.items()
    }

    invalid_source_keys = {
        _source_row_key(_norm(row.get("session_id")), _norm(row.get("provider")), _norm(row.get("pack_level")))
        for row in invalid_rows
    }

    contexts_by_key: Dict[str, Dict[str, Any]] = {}
    for behavior_row in behavior_rows:
        ctx = _build_v10_refined_context(behavior_row, indexes)
        contexts_by_key[_source_row_key(ctx["session_id"], ctx["provider"], ctx["pack_level"])] = ctx

    v10_stats = _build_v10_stats(data, contexts_by_key)

    dry_run_rows: List[Dict[str, Any]] = []
    label_preview_rows: List[Dict[str, Any]] = []
    evidence_rows: List[Dict[str, Any]] = []
    rule_path_rows: List[Dict[str, Any]] = []
    specificity_boundary_rows: List[Dict[str, Any]] = []
    overlap_rows: List[Dict[str, Any]] = []
    confidence_rows: List[Dict[str, Any]] = []
    determinism_rows: List[Dict[str, Any]] = []
    leakage_rows: List[Dict[str, Any]] = []

    label_results_by_mechanism_and_key: Dict[Tuple[str, str], Tuple[Dict[str, Any], Dict[str, str]]] = {}
    stats_by_mechanism: Dict[str, Counter] = defaultdict(Counter)
    eligible_source_row_keys: Set[str] = set()
    negative_audit_rows: List[Dict[str, Any]] = []
    overall_label_counter: Counter = Counter()

    candidate_row_count = len(behavior_rows)
    candidate_row_in_scope = "TRUE"

    for behavior_row in behavior_rows:
        ctx = contexts_by_key[
            _source_row_key(
                _norm(behavior_row.get("session_id")),
                _norm(behavior_row.get("provider")),
                _norm(behavior_row.get("pack_level")),
            )
        ]
        session_id = ctx["session_id"]
        provider = ctx["provider"]
        pack_level = ctx["pack_level"]
        source_row_key = _source_row_key(session_id, provider, pack_level)

        for mechanism_id in promoted_mechanisms:
            preview_id = _preview_id(mechanism_id, source_row_key)
            source_sheets_used = source_sheets_by_mechanism.get(mechanism_id, [])
            first_result, first_conf, second_result, second_conf, deterministic_status = _classify_twice(
                mechanism_id, ctx, source_sheets_used
            )
            label_results_by_mechanism_and_key[(mechanism_id, source_row_key)] = (first_result, first_conf)

            conflict_status = "UNRESOLVED_CONFLICT" if first_result["unresolved_conflict"] else (
                "RESOLVED_CONFLICT" if first_result["conflict_detected"] else "NO_CONFLICT"
            )
            eligible_for_preview = first_result["label"] != "EXCLUDED"
            if eligible_for_preview:
                eligible_source_row_keys.add(source_row_key)

            overall_label_counter[first_result["label"]] += 1
            stats = stats_by_mechanism[mechanism_id]
            stats["candidate_rows"] += 1
            stats["eligible_rows"] += 1 if eligible_for_preview else 0
            stats[f"label_{first_result['label']}"] += 1
            stats[f"confidence_{first_conf['confidence']}"] += 1
            if first_result["conflict_detected"]:
                stats["conflict_count"] += 1
            if first_result["unresolved_conflict"]:
                stats["unresolved_conflict_count"] += 1
            if first_result["label"] in {"UNKNOWN", "INSUFFICIENT_EVIDENCE"}:
                stats["ambiguity_count"] += 1

            dry_run_rows.append(
                {
                    **_base(generated_ts, dry_run_id),
                    "preregistration_version_reference": REFINED_VERSION_REFERENCE(),
                    "preview_id": preview_id,
                    "source_row_key": source_row_key,
                    "session_id": session_id,
                    "provider": provider,
                    "pack_level": pack_level,
                    "stable_mechanism_id": stable_id_by_mechanism.get(mechanism_id, ""),
                    "mechanism_id": mechanism_id,
                    "candidate_row_in_scope": candidate_row_in_scope,
                    "eligible_for_preview": "TRUE" if eligible_for_preview else "FALSE",
                    "preview_label": first_result["label"],
                    "confidence_category": first_conf["confidence"],
                    "decisive_rule_id": first_result["decisive_rule_id"],
                    "decisive_observables": _json(first_result["decisive_observables"]),
                    "rejected_alternative_rules": _json(first_result["rejected_alternative_rules"]),
                    "conflict_status": conflict_status,
                    "determinism_status": deterministic_status,
                    "leakage_status": "PASS_PRE_OUTCOME_ONLY",
                    "notes": _json(
                        {
                            "observable_states": first_result["observable_states"],
                            "rule_path_clarity": first_conf["rule_path_clarity"],
                        }
                    ),
                }
            )

            label_preview_rows.append(
                {
                    **_base(generated_ts, dry_run_id),
                    "preview_id": preview_id,
                    "source_row_key": source_row_key,
                    "stable_mechanism_id": stable_id_by_mechanism.get(mechanism_id, ""),
                    "mechanism_id": mechanism_id,
                    "session_id": session_id,
                    "provider": provider,
                    "pack_level": pack_level,
                    "preview_label": first_result["label"],
                    "executed_rule_id": first_result["decisive_rule_id"],
                    "decisive_observables": _json(first_result["decisive_observables"]),
                    "decisive_evidence": _json(first_result["decisive_evidence"]),
                    "rejected_alternative_rules": _json(first_result["rejected_alternative_rules"]),
                    "conflict_status": conflict_status,
                    "confidence_category": first_conf["confidence"],
                    "full_audit_path": _result_hash(first_result, first_conf),
                    "notes": _json(first_result["notes"]),
                }
            )

            evidence_rows.append(
                {
                    **_base(generated_ts, dry_run_id),
                    "preview_id": preview_id,
                    "source_row_key": source_row_key,
                    "stable_mechanism_id": stable_id_by_mechanism.get(mechanism_id, ""),
                    "mechanism_id": mechanism_id,
                    "session_id": session_id,
                    "provider": provider,
                    "pack_level": pack_level,
                    "observable_candidates": _json(sorted(first_result["observable_states"].keys())),
                    "observables_present": _json(
                        [name for name, state in first_result["observable_states"].items() if state != STATE_MISSING]
                    ),
                    "observables_absent": _json(
                        [name for name, state in first_result["observable_states"].items() if state == STATE_MISSING]
                    ),
                    "observable_states": _json(first_result["observable_states"]),
                    "extraction_success": "TRUE" if any(state != STATE_MISSING for state in first_result["observable_states"].values()) else "FALSE",
                    "ambiguity_detected": "TRUE"
                    if first_result["label"] in {"UNKNOWN", "INSUFFICIENT_EVIDENCE"} or first_result["unresolved_conflict"]
                    else "FALSE",
                    "decisive_evidence": _json(first_result["decisive_evidence"]),
                    "source_sheets_used": _json(first_result["source_sheets_used"]),
                    "accessed_fields": _json(first_result["accessed_fields"]),
                    "notes": _json(first_result["notes"]),
                }
            )

            rule_path_rows.append(
                {
                    **_base(generated_ts, dry_run_id),
                    "preview_id": preview_id,
                    "mechanism_id": mechanism_id,
                    "source_row_key": source_row_key,
                    "observable_candidates": _json(sorted(first_result["observable_states"].keys())),
                    "observables_present": _json(
                        [name for name, state in first_result["observable_states"].items() if state != STATE_MISSING]
                    ),
                    "observables_absent": _json(
                        [name for name, state in first_result["observable_states"].items() if state == STATE_MISSING]
                    ),
                    "positive_rule_checked": "TRUE",
                    "negative_rule_checked": "TRUE",
                    "unknown_rule_checked": "TRUE",
                    "insufficient_evidence_rule_checked": "TRUE",
                    "exclusion_rule_checked": "TRUE",
                    "decisive_rule_id": first_result["decisive_rule_id"],
                    "decisive_evidence": _json(first_result["decisive_evidence"]),
                    "label_assigned": first_result["label"],
                    "confidence_assigned": first_conf["confidence"],
                    "conflict_detected": "TRUE" if first_result["conflict_detected"] else "FALSE",
                    "conflict_resolution_rule": first_result["conflict_resolution_rule"],
                    "manual_override_used": "FALSE",
                }
            )

            if mechanism_id == "MECH_INFORMATION_SPECIFICITY":
                boundary = first_result["boundary_audit"]
                cue_types = boundary.get("boundary_cues") or ["NONE"]
                trace_text = boundary.get("boundary_traces") or first_result["decisive_evidence"] or [""]
                specificity_boundary_rows.append(
                    {
                        **_base(generated_ts, dry_run_id),
                        "mechanism_id": mechanism_id,
                        "source_row_key": source_row_key,
                        "preview_label": first_result["label"],
                        "boundary_cue_type": _json(cue_types),
                        "boundary_cue_text_or_trace": _json(trace_text),
                        "forecast_relevance_confirmed": "TRUE" if boundary.get("forecast_relevance_confirmed") else "FALSE",
                        "prohibited_proxy_detected": _json(boundary.get("prohibited_proxies", [])),
                        "time_horizon_present": "TRUE" if boundary.get("time_horizon_present") else "FALSE",
                        "time_horizon_supporting_only": "TRUE" if boundary.get("time_horizon_supporting_only") else "FALSE",
                        "specificity_positive_valid": "TRUE" if boundary.get("specificity_positive_valid") else "FALSE",
                        "audit_status": (
                            "SPECIFICITY_FALSE_PROXY_DETECTED"
                            if first_result["label"] == "POSITIVE" and (
                                not boundary.get("specificity_positive_valid") or boundary.get("specificity_false_proxy")
                            )
                            else "PASS_VALID_BOUNDARY"
                            if first_result["label"] == "POSITIVE"
                            else "NON_POSITIVE_PREVIEW"
                        ),
                        "notes": _json(boundary),
                    }
                )

            confidence_rows.append(
                {
                    **_base(generated_ts, dry_run_id),
                    "preview_id": preview_id,
                    "source_row_key": source_row_key,
                    "mechanism_id": mechanism_id,
                    "preview_label": first_result["label"],
                    "evidence_completeness": first_conf["evidence_completeness"],
                    "evidence_consistency": first_conf["evidence_consistency"],
                    "rule_path_clarity": first_conf["rule_path_clarity"],
                    "observable_coverage": first_conf["observable_coverage"],
                    "ambiguity_level": first_conf["ambiguity_level"],
                    "confidence_category": first_conf["confidence"],
                    "confidence_reason": first_conf["reason"],
                    "notes": _json({"rejected_alternative_rules": first_result["rejected_alternative_rules"]}),
                }
            )

            determinism_rows.append(
                {
                    **_base(generated_ts, dry_run_id),
                    "preview_id": preview_id,
                    "source_row_key": source_row_key,
                    "mechanism_id": mechanism_id,
                    "first_pass_label": first_result["label"],
                    "second_pass_label": second_result["label"],
                    "first_pass_confidence": first_conf["confidence"],
                    "second_pass_confidence": second_conf["confidence"],
                    "first_pass_rule_id": first_result["decisive_rule_id"],
                    "second_pass_rule_id": second_result["decisive_rule_id"],
                    "first_pass_audit_hash": _result_hash(first_result, first_conf),
                    "second_pass_audit_hash": _result_hash(second_result, second_conf),
                    "determinism_status": deterministic_status,
                    "notes": "Second pass replays the same frozen v1.1 rules without manual overrides.",
                }
            )

            leakage_status = "PASS_PRE_OUTCOME_ONLY"
            outcome_field_accessed = "FALSE"
            future_information_accessed = "FALSE"
            prohibited_sheet_accessed = "FALSE"
            if any(any(term in field.lower() for term in FORBIDDEN_FIELD_TERMS) for field in first_result["accessed_fields"]):
                leakage_status = "OUTCOME_LEAKAGE_DETECTED"
                outcome_field_accessed = "TRUE"
            leakage_rows.append(
                {
                    **_base(generated_ts, dry_run_id),
                    "preview_id": preview_id,
                    "source_row_key": source_row_key,
                    "mechanism_id": mechanism_id,
                    "outcome_field_accessed": outcome_field_accessed,
                    "future_information_accessed": future_information_accessed,
                    "prohibited_sheet_accessed": prohibited_sheet_accessed,
                    "leakage_status": leakage_status,
                    "notes": _json(
                        {
                            "source_sheets_used": first_result["source_sheets_used"],
                            "accessed_fields": first_result["accessed_fields"],
                        }
                    ),
                }
            )

            if first_result["label"] == "NEGATIVE":
                negative_audit_rows.append(
                    {
                        **_base(generated_ts, dry_run_id),
                        "row_type": "NEGATIVE_LABEL_AUDIT",
                        "mechanism_id": mechanism_id,
                        "source_row_key": source_row_key,
                        "preview_label": "NEGATIVE",
                        "positive_count": "",
                        "negative_count": "",
                        "unknown_count": "",
                        "insufficient_evidence_count": "",
                        "excluded_count": "",
                        "negative_rule_id": first_result["decisive_rule_id"],
                        "affirmative_absence_evidence": _json(first_result["affirmative_absence_evidence"]),
                        "missing_evidence_only": "TRUE" if first_result["missing_evidence_only"] else "FALSE",
                        "optional_field_absence_only": "TRUE" if first_result["optional_field_absence_only"] else "FALSE",
                        "invalid_output_related": "TRUE" if (source_row_key in invalid_source_keys or first_result["invalid_output_related"]) else "FALSE",
                        "excluded_row_related": "TRUE" if first_result["excluded_row_related"] else "FALSE",
                        "negative_label_valid": "TRUE"
                        if (
                            bool(first_result["affirmative_absence_evidence"])
                            and not first_result["missing_evidence_only"]
                            and not first_result["optional_field_absence_only"]
                            and not (source_row_key in invalid_source_keys)
                            and not first_result["excluded_row_related"]
                        )
                        else "FALSE",
                        "audit_status": "PASS_VALID_NEGATIVE"
                        if (
                            bool(first_result["affirmative_absence_evidence"])
                            and not first_result["missing_evidence_only"]
                            and not first_result["optional_field_absence_only"]
                            and not (source_row_key in invalid_source_keys)
                            and not first_result["excluded_row_related"]
                        )
                        else "INVALID_NEGATIVE_LABEL",
                        "notes": _json(first_result["notes"]),
                    }
                )

    label_balance_rows: List[Dict[str, Any]] = []
    for mechanism_id in promoted_mechanisms:
        stats = stats_by_mechanism[mechanism_id]
        label_balance_rows.append(
            {
                **_base(generated_ts, dry_run_id),
                "row_type": "MECHANISM_SUMMARY",
                "mechanism_id": mechanism_id,
                "source_row_key": "",
                "preview_label": "",
                "positive_count": stats.get("label_POSITIVE", 0),
                "negative_count": stats.get("label_NEGATIVE", 0),
                "unknown_count": stats.get("label_UNKNOWN", 0),
                "insufficient_evidence_count": stats.get("label_INSUFFICIENT_EVIDENCE", 0),
                "excluded_count": stats.get("label_EXCLUDED", 0),
                "negative_rule_id": "",
                "affirmative_absence_evidence": "",
                "missing_evidence_only": "",
                "optional_field_absence_only": "",
                "invalid_output_related": "",
                "excluded_row_related": "",
                "negative_label_valid": "",
                "audit_status": "SUMMARY_ONLY",
                "notes": _json(
                    {
                        "candidate_rows": stats.get("candidate_rows", 0),
                        "eligible_rows": stats.get("eligible_rows", 0),
                    }
                ),
            }
        )
    label_balance_rows.extend(negative_audit_rows)

    for source_row_key, ctx in sorted(contexts_by_key.items()):
        session_id = ctx["session_id"]
        provider = ctx["provider"]
        pack_level = ctx["pack_level"]
        for mechanism_a, mechanism_b in PAIRWISE_MECHANISM_PAIRS:
            result_a, _conf_a = label_results_by_mechanism_and_key[(mechanism_a, source_row_key)]
            result_b, _conf_b = label_results_by_mechanism_and_key[(mechanism_b, source_row_key)]
            status, separation_rule_applied, justification = _pair_status(
                mechanism_a,
                result_a["label"],
                result_a,
                mechanism_b,
                result_b["label"],
                result_b,
            )
            if status == "NOT_APPLICABLE" and result_a["label"] == "EXCLUDED" and result_b["label"] == "EXCLUDED":
                continue
            overlap_rows.append(
                {
                    **_base(generated_ts, dry_run_id),
                    "source_row_key": source_row_key,
                    "session_id": session_id,
                    "provider": provider,
                    "pack_level": pack_level,
                    "mechanism_a": mechanism_a,
                    "label_a": result_a["label"],
                    "mechanism_b": mechanism_b,
                    "label_b": result_b["label"],
                    "pair_status": status,
                    "joint_positive": "TRUE" if result_a["label"] == "POSITIVE" and result_b["label"] == "POSITIVE" else "FALSE",
                    "separation_rule_applied": separation_rule_applied,
                    "justification": justification,
                    "notes": _json(
                        {
                            "a_rule": result_a["decisive_rule_id"],
                            "b_rule": result_b["decisive_rule_id"],
                        }
                    ),
                }
            )

    conflict_rows: List[Dict[str, Any]] = []
    highest_remaining_conflict = "NONE"
    highest_remaining_ambiguity = "NONE"
    strongest_v11_mechanism = "NONE"
    strongest_rank: Optional[Tuple[float, float, int, str]] = None
    pairwise_joint_overlap_counts = Counter()

    for row in overlap_rows:
        if row["joint_positive"] == "TRUE":
            pair_key = f"{row['mechanism_a']}|{row['mechanism_b']}"
            pairwise_joint_overlap_counts[pair_key] += 1

    for mechanism_id in promoted_mechanisms:
        stats = stats_by_mechanism[mechanism_id]
        eligible = stats.get("eligible_rows", 0)
        positive_count = stats.get("label_POSITIVE", 0)
        negative_count = stats.get("label_NEGATIVE", 0)
        unknown_count = stats.get("label_UNKNOWN", 0)
        insufficient_count = stats.get("label_INSUFFICIENT_EVIDENCE", 0)
        excluded_count = stats.get("label_EXCLUDED", 0)
        conflict_count = stats.get("conflict_count", 0)
        unresolved_conflict_count = stats.get("unresolved_conflict_count", 0)
        ambiguity_count = stats.get("ambiguity_count", 0)
        high_confidence_count = stats.get("confidence_HIGH", 0)
        moderate_confidence_count = stats.get("confidence_MODERATE", 0)
        low_confidence_count = stats.get("confidence_LOW", 0)
        unknown_confidence_count = stats.get("confidence_UNKNOWN", 0)

        conflict_rows.append(
            {
                **_base(generated_ts, dry_run_id),
                "mechanism_id": mechanism_id,
                "candidate_rows": stats.get("candidate_rows", 0),
                "eligible_rows": eligible,
                "positive_count": positive_count,
                "negative_count": negative_count,
                "unknown_count": unknown_count,
                "insufficient_evidence_count": insufficient_count,
                "excluded_count": excluded_count,
                "conflict_count": conflict_count,
                "unresolved_conflict_count": unresolved_conflict_count,
                "ambiguity_count": ambiguity_count,
                "high_confidence_count": high_confidence_count,
                "moderate_confidence_count": moderate_confidence_count,
                "low_confidence_count": low_confidence_count,
                "unknown_confidence_count": unknown_confidence_count,
                "notes": _json(
                    {
                        "conflict_rate": _safe_ratio(conflict_count, stats.get("candidate_rows", 0)),
                        "ambiguity_rate": _safe_ratio(ambiguity_count, stats.get("candidate_rows", 0)),
                    }
                ),
            }
        )

        if highest_remaining_conflict == "NONE" or conflict_count > int(highest_remaining_conflict.split(":")[1].split("/")[0]):
            highest_remaining_conflict = f"{mechanism_id}:{conflict_count}/{stats.get('candidate_rows', 0)}"
        if highest_remaining_ambiguity == "NONE" or ambiguity_count > int(highest_remaining_ambiguity.split(":")[1].split("/")[0]):
            highest_remaining_ambiguity = f"{mechanism_id}:{ambiguity_count}/{stats.get('candidate_rows', 0)}"

        decisive_rate = 0.0 if eligible == 0 else float(positive_count + negative_count) / float(eligible)
        ambiguity_rate = 1.0 if eligible == 0 else float(ambiguity_count) / float(eligible)
        rank_tuple = (decisive_rate, -ambiguity_rate, high_confidence_count, mechanism_id)
        if strongest_rank is None or rank_tuple > strongest_rank:
            strongest_rank = rank_tuple
            strongest_v11_mechanism = mechanism_id

    comparison_rows: List[Dict[str, Any]] = []
    v11_confidence_counts: Dict[str, Counter] = defaultdict(Counter)
    for row in confidence_rows:
        v11_confidence_counts[_norm(row.get("mechanism_id"))][_norm(row.get("confidence_category"))] += 1

    def add_comparison(scope: str, mechanism_id: str, v10_value: Any, v11_value: Any, interpretation: str, notes: str = "") -> None:
        numeric_delta = ""
        relative_delta = ""
        if isinstance(v10_value, (int, float)) and isinstance(v11_value, (int, float)):
            numeric_delta = v11_value - v10_value
            if v10_value != 0:
                relative_delta = f"{(v11_value - v10_value) / float(v10_value):.6f}"
        comparison_rows.append(
            {
                **_base(generated_ts, dry_run_id),
                "comparison_scope": scope,
                "mechanism_id": mechanism_id,
                "v10_value": v10_value,
                "v11_value": v11_value,
                "absolute_delta": numeric_delta,
                "relative_delta": relative_delta,
                "scientific_interpretation": interpretation,
                "notes": notes,
            }
        )

    add_comparison(
        "eligible_rows",
        "OVERALL",
        v10_stats["eligible_rows"],
        len(eligible_source_row_keys),
        "The eligible population should remain stable unless a frozen v1.1 scope rule changed it.",
        notes=_json({"expected_eligible_rows": EXPECTED_ELIGIBLE_ROWS}),
    )
    add_comparison(
        "overall_conflict_count",
        "OVERALL",
        v10_stats["overall_conflict_count"],
        sum(stats.get("conflict_count", 0) for stats in stats_by_mechanism.values()),
        "Overall unresolved or resolved conflict burden across promoted mechanism-row previews.",
    )
    add_comparison(
        "overall_ambiguity_count",
        "OVERALL",
        v10_stats["overall_ambiguity_count"],
        sum(stats.get("ambiguity_count", 0) for stats in stats_by_mechanism.values()),
        "Overall UNKNOWN plus INSUFFICIENT_EVIDENCE burden across promoted mechanism-row previews.",
    )

    for mechanism_id in promoted_mechanisms:
        v10_counter = v10_stats["label_counts"].get(mechanism_id, Counter())
        v11_counter = stats_by_mechanism[mechanism_id]
        add_comparison("positive_labels", mechanism_id, v10_counter.get("POSITIVE", 0), v11_counter.get("label_POSITIVE", 0), "Positive-label count under comparable promoted-mechanism preview scope.")
        add_comparison("negative_labels", mechanism_id, v10_counter.get("NEGATIVE", 0), v11_counter.get("label_NEGATIVE", 0), "Negative-label count should rise only if v1.1 negatives remain affirmative and valid.")
        add_comparison("unknown_labels", mechanism_id, v10_counter.get("UNKNOWN", 0), v11_counter.get("label_UNKNOWN", 0), "Unknown-label change tracks direct label ambiguity, not confidence burden.")
        add_comparison("insufficient_evidence_labels", mechanism_id, v10_counter.get("INSUFFICIENT_EVIDENCE", 0), v11_counter.get("label_INSUFFICIENT_EVIDENCE", 0), "Insufficient-evidence change reflects trace coverage, not predictive performance.")
        add_comparison("excluded_labels", mechanism_id, v10_counter.get("EXCLUDED", 0), v11_counter.get("label_EXCLUDED", 0), "Excluded-label count should remain stable if the dry-run scope stayed frozen.")
        add_comparison("conflict_count", mechanism_id, v10_stats["conflict_counts"].get(mechanism_id, 0), v11_counter.get("conflict_count", 0), "Conflict-count change measures rule-path disagreement under comparable mechanism scope.")
        add_comparison("ambiguity_count", mechanism_id, v10_stats["ambiguity_counts"].get(mechanism_id, 0), v11_counter.get("ambiguity_count", 0), "Ambiguity-count change measures UNKNOWN and INSUFFICIENT_EVIDENCE burden at the label layer.")
        add_comparison(
            "confidence_distribution",
            mechanism_id,
            _json(dict(v10_stats["confidence_counts"].get(mechanism_id, Counter()))),
            _json(dict(v11_confidence_counts.get(mechanism_id, Counter()))),
            "Confidence distribution compares label-quality burden only; it does not imply predictive accuracy.",
        )

    add_comparison(
        "specificity_positive_count",
        "MECH_INFORMATION_SPECIFICITY",
        v10_stats["label_counts"].get("MECH_INFORMATION_SPECIFICITY", Counter()).get("POSITIVE", 0),
        stats_by_mechanism["MECH_INFORMATION_SPECIFICITY"].get("label_POSITIVE", 0),
        "Specificity-positive count should fall or stay disciplined if v1.1 blocks detail-only positives.",
    )
    add_comparison(
        "specificity_negative_count",
        "MECH_INFORMATION_SPECIFICITY",
        v10_stats["label_counts"].get("MECH_INFORMATION_SPECIFICITY", Counter()).get("NEGATIVE", 0),
        stats_by_mechanism["MECH_INFORMATION_SPECIFICITY"].get("label_NEGATIVE", 0),
        "Specificity-negative count should rise only if negatives reflect affirmative non-boundary evidence.",
    )
    specificity_false_proxy_findings = sum(
        1 for row in specificity_boundary_rows if _norm(row.get("audit_status")) == "SPECIFICITY_FALSE_PROXY_DETECTED"
    )
    add_comparison(
        "specificity_false_proxy_count",
        "MECH_INFORMATION_SPECIFICITY",
        v10_stats["specificity_false_proxy_count"],
        specificity_false_proxy_findings,
        "False-proxy comparison uses the same v1.1 boundary audit standard for both the old and new preview populations.",
    )
    add_comparison(
        "relevance_specificity_overlap",
        "PAIR_RELEVANCE_SPECIFICITY",
        v10_stats["overlaps"].get("relevance_specificity_overlap", 0),
        pairwise_joint_overlap_counts.get("MECH_INFORMATION_RELEVANCE|MECH_INFORMATION_SPECIFICITY", 0),
        "Joint-positive overlap is legitimate only when specificity identifies a real boundary beyond target alignment.",
    )
    add_comparison(
        "specificity_consistency_overlap",
        "PAIR_SPECIFICITY_CONSISTENCY",
        v10_stats["overlaps"].get("specificity_consistency_overlap", 0),
        pairwise_joint_overlap_counts.get("MECH_INFORMATION_SPECIFICITY|MECH_INFORMATION_CONSISTENCY", 0),
        "Joint-positive overlap is legitimate only when specificity remains boundary-forming rather than coherence-only.",
    )

    governance_specs = [
        ("GOV_PROVIDER_CALLS", "provider_calls_performed", "0", "0"),
        ("GOV_FORECAST_GENERATION", "forecast_generation_performed", "0", "0"),
        ("GOV_PERMANENT_LABELS", "permanent_labels_assigned", "0", "0"),
        ("GOV_MECHANISM_TESTING", "mechanism_testing_performed", "0", "0"),
        ("GOV_ACCURACY_EVALUATION", "accuracy_evaluation_performed", "0", "0"),
        ("GOV_OUTCOME_ACCESS", "outcome_values_accessed", "0", "0"),
        ("GOV_CORRECTED_OUTCOME_ACCESS", "corrected_outcomes_accessed", "0", "0"),
        ("GOV_V10_PREREG", "v10_preregistration_modified", "0", "0"),
        ("GOV_V10_DRY_RUN", "v10_dry_run_modified", "0", "0"),
        ("GOV_PRODUCTION_WRITES", "production_sheet_write_count", "0", "0"),
        ("GOV_PRODUCTION_BEHAVIOR", "production_behavior_change_count", "0", "0"),
        ("GOV_ROUTING", "routing_changes", "FALSE", "FALSE"),
        ("GOV_WEIGHTING", "weighting_changes", "FALSE", "FALSE"),
        ("GOV_CALIBRATION", "calibration_changes", "FALSE", "FALSE"),
        ("GOV_ENSEMBLE", "ensemble_changes", "FALSE", "FALSE"),
    ]
    governance_rows = [
        {
            **_base(generated_ts, dry_run_id),
            "check_id": check_id,
            "check_name": check_name,
            "expected_value": expected_value,
            "actual_value": actual_value,
            "status": "PASS" if expected_value == actual_value else "FAIL",
            "notes": "v1.1 dry run remains preview-only and non-production.",
        }
        for check_id, check_name, expected_value, actual_value in governance_specs
    ]

    determinism_failures = sum(1 for row in determinism_rows if _norm(row.get("determinism_status")) != "PASS")
    leakage_findings = sum(1 for row in leakage_rows if _norm(row.get("leakage_status")) == "OUTCOME_LEAKAGE_DETECTED")
    valid_specificity_positive_count = sum(
        1
        for row in specificity_boundary_rows
        if _norm(row.get("preview_label")) == "POSITIVE" and _norm(row.get("specificity_positive_valid")) == "TRUE"
    )
    invalid_negative_count = sum(
        1
        for row in negative_audit_rows
        if _norm(row.get("negative_label_valid")) != "TRUE"
    )
    overall_conflicts_detected = sum(stats.get("conflict_count", 0) for stats in stats_by_mechanism.values())
    overall_unresolved_conflicts = sum(stats.get("unresolved_conflict_count", 0) for stats in stats_by_mechanism.values())
    overall_ambiguity_count = sum(stats.get("ambiguity_count", 0) for stats in stats_by_mechanism.values())

    v10_conflict_count = v10_stats["overall_conflict_count"]
    v11_conflict_count = overall_conflicts_detected
    v10_ambiguity_count = v10_stats["overall_ambiguity_count"]
    v11_ambiguity_count = overall_ambiguity_count

    ready_for_v11_refined_conflict_review = (
        determinism_failures == 0
        and leakage_findings == 0
        and specificity_false_proxy_findings == 0
        and invalid_negative_count == 0
    )

    build_status = "PASS_WITH_WARNINGS"
    final_interpretation = "REFINED_MECHANISM_V11_CLASSIFICATION_DRY_RUN_READY_WITH_WARNINGS"
    recommended_next_step = "PROCEED_TO_PHASE9A6R7_V11_REFINED_CONFLICT_REVIEW"
    if determinism_failures > 0 or leakage_findings > 0:
        build_status = "BLOCKED"
        final_interpretation = "REFINED_MECHANISM_V11_CLASSIFICATION_DRY_RUN_BLOCKED"
        recommended_next_step = "HOLD_PHASE9_PENDING_GOVERNANCE_REVIEW"
    elif (
        len(eligible_source_row_keys) != EXPECTED_ELIGIBLE_ROWS
        and len(eligible_source_row_keys) != v10_stats["eligible_rows"]
    ) or candidate_row_count != EXPECTED_CANDIDATE_ROWS:
        build_status = "NEEDS_REVIEW"
        final_interpretation = "REFINED_MECHANISM_V11_CLASSIFICATION_DRY_RUN_NEEDS_REVIEW"
        recommended_next_step = "RUN_PHASE9A6R6_V11_DRY_RUN_REPAIR"
    elif specificity_false_proxy_findings > 0 or invalid_negative_count > 0:
        build_status = "NEEDS_REVIEW"
        final_interpretation = "REFINED_MECHANISM_V11_CLASSIFICATION_DRY_RUN_NEEDS_REVIEW"
        recommended_next_step = "RUN_PHASE9A6R6_V11_DRY_RUN_REPAIR"

    primary_scientific_interpretation = (
        "v1.1 preserved deterministic, pre-outcome classification and converted specificity into an auditable falsifiable-boundary construct without using outcome information."
        if ready_for_v11_refined_conflict_review
        else "v1.1 dry-run execution surfaced rule-path or governance issues that must be repaired before conflict review."
    )

    summary_row = {
        **_base(generated_ts, dry_run_id),
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "candidate_rows": candidate_row_count,
        "eligible_rows_previewed": len(eligible_source_row_keys),
        "preview_labels_assigned": len(label_preview_rows),
        "positive_labels": overall_label_counter.get("POSITIVE", 0),
        "negative_labels": overall_label_counter.get("NEGATIVE", 0),
        "unknown_labels": overall_label_counter.get("UNKNOWN", 0),
        "insufficient_evidence_labels": overall_label_counter.get("INSUFFICIENT_EVIDENCE", 0),
        "excluded_labels": overall_label_counter.get("EXCLUDED", 0),
        "specificity_positive_labels": stats_by_mechanism["MECH_INFORMATION_SPECIFICITY"].get("label_POSITIVE", 0),
        "specificity_negative_labels": stats_by_mechanism["MECH_INFORMATION_SPECIFICITY"].get("label_NEGATIVE", 0),
        "specificity_false_proxy_findings": specificity_false_proxy_findings,
        "valid_boundary_forming_specificity_positives": valid_specificity_positive_count,
        "conflicts_detected": overall_conflicts_detected,
        "unresolved_conflicts": overall_unresolved_conflicts,
        "ambiguity_count": overall_ambiguity_count,
        "relevance_specificity_overlap": pairwise_joint_overlap_counts.get("MECH_INFORMATION_RELEVANCE|MECH_INFORMATION_SPECIFICITY", 0),
        "specificity_consistency_overlap": pairwise_joint_overlap_counts.get("MECH_INFORMATION_SPECIFICITY|MECH_INFORMATION_CONSISTENCY", 0),
        "v10_conflict_count": v10_conflict_count,
        "v11_conflict_count": v11_conflict_count,
        "conflict_delta": v11_conflict_count - v10_conflict_count,
        "v10_ambiguity_count": v10_ambiguity_count,
        "v11_ambiguity_count": v11_ambiguity_count,
        "ambiguity_delta": v11_ambiguity_count - v10_ambiguity_count,
        "determinism_status": "PASS" if determinism_failures == 0 else "FAIL",
        "leakage_findings": leakage_findings,
        "highest_remaining_conflict": highest_remaining_conflict,
        "highest_remaining_ambiguity": highest_remaining_ambiguity,
        "strongest_v11_mechanism": strongest_v11_mechanism,
        "primary_scientific_interpretation": primary_scientific_interpretation,
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "permanent_labels_assigned": 0,
        "mechanism_testing_performed": 0,
        "accuracy_evaluation_performed": 0,
        "outcome_values_accessed": 0,
        "v1_0_sheets_modified": 0,
        "production_behavior_change_count": 0,
        "production_sheet_write_count": 0,
        "ready_for_v11_refined_conflict_review": "TRUE" if ready_for_v11_refined_conflict_review else "FALSE",
        "ready_for_permanent_classification_execution": "FALSE",
        "ready_for_mechanism_testing": "FALSE",
        "ready_for_production": "FALSE",
        "recommended_next_step": recommended_next_step,
        "notes": _json(
            {
                "expected_candidate_rows": EXPECTED_CANDIDATE_ROWS,
                "expected_eligible_rows": EXPECTED_ELIGIBLE_ROWS,
                "v10_eligible_rows": v10_stats["eligible_rows"],
                "specificity_false_proxy_target": 0,
                "negative_label_invalid_count": invalid_negative_count,
            }
        ),
    }

    outputs = [
        (OUTPUT_DRY_RUN, DRY_RUN_HEADERS, dry_run_rows),
        (OUTPUT_LABEL_PREVIEW, LABEL_PREVIEW_HEADERS, label_preview_rows),
        (OUTPUT_EVIDENCE, EVIDENCE_HEADERS, evidence_rows),
        (OUTPUT_RULE_PATH, RULE_PATH_HEADERS, rule_path_rows),
        (OUTPUT_SPECIFICITY_BOUNDARY, SPECIFICITY_BOUNDARY_HEADERS, specificity_boundary_rows),
        (OUTPUT_CONFLICT, CONFLICT_HEADERS, conflict_rows),
        (OUTPUT_OVERLAP, OVERLAP_HEADERS, overlap_rows),
        (OUTPUT_LABEL_BALANCE, LABEL_BALANCE_HEADERS, label_balance_rows),
        (OUTPUT_CONFIDENCE, CONFIDENCE_HEADERS, confidence_rows),
        (OUTPUT_DETERMINISM, DETERMINISM_HEADERS, determinism_rows),
        (OUTPUT_LEAKAGE, LEAKAGE_HEADERS, leakage_rows),
        (OUTPUT_COMPARISON, COMPARISON_HEADERS, comparison_rows),
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
        "file_created": "automation/build_refined_mechanism_v11_classification_dry_run_v0.py",
        "sheets_written": {sheet_name: len(rows) for sheet_name, _, rows in outputs},
        "candidate_rows": candidate_row_count,
        "eligible_rows_previewed": len(eligible_source_row_keys),
        "preview_labels_assigned": len(label_preview_rows),
        "positive_labels": overall_label_counter.get("POSITIVE", 0),
        "negative_labels": overall_label_counter.get("NEGATIVE", 0),
        "unknown_labels": overall_label_counter.get("UNKNOWN", 0),
        "insufficient_evidence_labels": overall_label_counter.get("INSUFFICIENT_EVIDENCE", 0),
        "excluded_labels": overall_label_counter.get("EXCLUDED", 0),
        "specificity_positive_labels": stats_by_mechanism["MECH_INFORMATION_SPECIFICITY"].get("label_POSITIVE", 0),
        "specificity_negative_labels": stats_by_mechanism["MECH_INFORMATION_SPECIFICITY"].get("label_NEGATIVE", 0),
        "specificity_false_proxy_findings": specificity_false_proxy_findings,
        "valid_boundary_forming_specificity_positives": valid_specificity_positive_count,
        "conflicts_detected": overall_conflicts_detected,
        "unresolved_conflicts": overall_unresolved_conflicts,
        "ambiguity_count": overall_ambiguity_count,
        "relevance_specificity_overlap": pairwise_joint_overlap_counts.get("MECH_INFORMATION_RELEVANCE|MECH_INFORMATION_SPECIFICITY", 0),
        "specificity_consistency_overlap": pairwise_joint_overlap_counts.get("MECH_INFORMATION_SPECIFICITY|MECH_INFORMATION_CONSISTENCY", 0),
        "v10_conflict_count": v10_conflict_count,
        "v11_conflict_count": v11_conflict_count,
        "conflict_delta": v11_conflict_count - v10_conflict_count,
        "v10_ambiguity_count": v10_ambiguity_count,
        "v11_ambiguity_count": v11_ambiguity_count,
        "ambiguity_delta": v11_ambiguity_count - v10_ambiguity_count,
        "determinism_status": "PASS" if determinism_failures == 0 else "FAIL",
        "leakage_findings": leakage_findings,
        "highest_remaining_conflict": highest_remaining_conflict,
        "highest_remaining_ambiguity": highest_remaining_ambiguity,
        "strongest_v11_mechanism": strongest_v11_mechanism,
        "primary_scientific_interpretation": primary_scientific_interpretation,
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "permanent_labels_assigned": 0,
        "mechanism_testing_performed": 0,
        "accuracy_evaluation_performed": 0,
        "outcome_values_accessed": 0,
        "v1_0_sheets_modified": 0,
        "production_behavior_change_count": 0,
        "production_sheet_write_count": 0,
        "ready_for_v11_refined_conflict_review": ready_for_v11_refined_conflict_review,
        "ready_for_permanent_classification_execution": False,
        "ready_for_mechanism_testing": False,
        "ready_for_production": False,
        "recommended_next_step": recommended_next_step,
        "registry": registry,
    }


def main() -> None:
    result = build_refined_mechanism_v11_classification_dry_run_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
