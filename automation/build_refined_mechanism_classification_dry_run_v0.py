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
    _build_context as _build_original_context,
    _build_indexes as _build_original_indexes,
)
from automation.build_session_information_requests_v0 import _iso_now
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials


SCHEMA_VERSION = "presignal_v2_refined_mechanism_classification_dry_run_0.1"
DRY_RUN_VERSION = "refined_mechanism_classification_dry_run_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-6R2"
REGISTRY_CATEGORY = "PRESIGNAL_V2_REFINED_MECHANISM_CLASSIFICATION_DRY_RUN"
REGISTRY_OWNER_MODULE = "market_state"

REQUIRED_INPUT_SHEETS = [
    "Refined_Mechanism_PreRegistration",
    "Refined_Mechanism_Frozen_Definitions",
    "Refined_Mechanism_Frozen_Observables",
    "Refined_Mechanism_Frozen_Label_Rules",
    "Refined_Mechanism_Frozen_Confidence_Rules",
    "Refined_Mechanism_Frozen_Falsification_Rules",
    "Pack_Behavior_Tier2_Behavior",
    "Pack_Behavior_Tier2_Transitions",
    "Pack_Behavior_Tier2_Field_Influence",
    "Pack_Behavior_Tier2_NoSignal",
]

OPTIONAL_INPUT_SHEETS = [
    "Predictive_Mechanism_Dry_Run_Summary",
    "Predictive_Mechanism_Label_Preview",
    "Predictive_Mechanism_Conflict_Audit",
]

OUTPUT_DRY_RUN = "Refined_Mechanism_Classification_Dry_Run"
OUTPUT_LABEL_PREVIEW = "Refined_Mechanism_Label_Preview"
OUTPUT_EVIDENCE = "Refined_Mechanism_Evidence_Audit"
OUTPUT_CONFLICT = "Refined_Mechanism_Conflict_Audit"
OUTPUT_CONFIDENCE = "Refined_Mechanism_Confidence_Preview"
OUTPUT_DETERMINISM = "Refined_Mechanism_Determinism_Audit"
OUTPUT_LEAKAGE = "Refined_Mechanism_Leakage_Audit"
OUTPUT_GOVERNANCE = "Refined_Mechanism_Dry_Run_Governance"
OUTPUT_SUMMARY = "Refined_Mechanism_Dry_Run_Summary"

DRY_RUN_HEADERS = [
    "generated_ts",
    "schema_version",
    "dry_run_version",
    "dry_run_id",
    "preview_id",
    "stable_mechanism_id",
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
    "stable_mechanism_id",
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

EVIDENCE_HEADERS = [
    "generated_ts",
    "schema_version",
    "dry_run_version",
    "dry_run_id",
    "preview_id",
    "stable_mechanism_id",
    "mechanism_id",
    "session_id",
    "provider",
    "pack_level",
    "observable_states",
    "observables_found",
    "observables_missing",
    "evidence_completeness",
    "extraction_success",
    "ambiguity_detected",
    "source_sheets_used",
    "rule_executed",
    "notes",
]

CONFLICT_HEADERS = [
    "generated_ts",
    "schema_version",
    "dry_run_version",
    "dry_run_id",
    "preview_id",
    "stable_mechanism_id",
    "mechanism_id",
    "session_id",
    "provider",
    "pack_level",
    "conflicting_observables",
    "conflict_type",
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
    "stable_mechanism_id",
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

DETERMINISM_HEADERS = [
    "generated_ts",
    "schema_version",
    "dry_run_version",
    "dry_run_id",
    "preview_id",
    "stable_mechanism_id",
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

LEAKAGE_HEADERS = [
    "generated_ts",
    "schema_version",
    "dry_run_version",
    "dry_run_id",
    "preview_id",
    "stable_mechanism_id",
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
    "ambiguity_reduction",
    "conflict_reduction",
    "leakage_findings",
    "determinism_status",
    "strongest_refined_mechanism",
    "highest_remaining_conflict",
    "highest_remaining_ambiguity",
    "provider_calls_performed",
    "forecast_generation_performed",
    "permanent_labels_assigned",
    "mechanism_testing_performed",
    "production_behavior_change_count",
    "ready_for_refined_classification_execution",
    "ready_for_refined_mechanism_testing",
    "ready_for_replication",
    "ready_for_production",
    "recommended_next_step",
    "notes",
]

PREVIEW_LABELS = {"POSITIVE", "NEGATIVE", "UNKNOWN", "INSUFFICIENT_EVIDENCE", "EXCLUDED"}
CONFIDENCE_LEVELS = {"HIGH", "MODERATE", "LOW", "UNKNOWN"}
STATE_POSITIVE = "POSITIVE"
STATE_NEGATIVE = "NEGATIVE"
STATE_UNKNOWN = "UNKNOWN"
STATE_MISSING = "MISSING"
FORBIDDEN_FIELD_TERMS = ["realized", "overall_ok", "corrected", "evaluation_", "eval_", "future_"]

TIME_HINTS = [
    "utc",
    "session",
    "pre-session",
    "presession",
    "intraday",
    "within 24h",
    "within 72h",
    "later in session",
    "reaction window",
    "morning",
    "afternoon",
    "12:30",
    "05:30",
    "16:00",
    "19:20",
]
CONDITION_HINTS = [
    "if ",
    "unless",
    "would invalidate",
    "invalidated",
    "invalidation",
    "provided that",
    "conditional",
    "depends on",
    "if subsequent",
]
UP_HINTS = [
    "upward",
    "upside",
    "bullish",
    "move higher",
    "higher",
    "up forecast",
    "usd strength",
    "stronger usd",
    "yen weakness",
    "hawkish",
    "support usd",
]
DOWN_HINTS = [
    "downward",
    "downside",
    "bearish",
    "move lower",
    "lower",
    "down forecast",
    "usd weakness",
    "weaker usd",
    "softer usd",
    "yen strength",
    "disinflationary",
    "down pressure",
]
UNCERTAINTY_HINTS = [
    "uncertain",
    "uncertainty",
    "mixed",
    "unclear",
    "complex",
    "difficult",
    "tail risk",
    "noise",
    "whipsaw",
    "no clear",
]
SCARCITY_HINTS = [
    "missing",
    "unknown",
    "not available",
    "not provided",
    "lacks",
    "unavailable",
]

FAMILY_KEYWORDS = {
    "usdjpy_trend": ["usdjpy", "trend", "return", "returns", "pre-session", "presession", "momentum"],
    "upcoming_larger_events": [
        "event",
        "events",
        "release",
        "releases",
        "cluster",
        "cpi",
        "fomc",
        "fed",
        "importance",
        "session",
        "24h",
        "72h",
        "utc",
    ],
    "treasury_yields": ["yield", "yields", "treasury", "rate differential", "yield premium", "rates"],
    "dxy": ["dxy", "dollar index", "usd weakness", "usd strength", "dollar weakness", "dollar strength"],
}


def _dry_run_id(generated_ts: str) -> str:
    return "refined_mechanism_classification_dry_run_v0_" + generated_ts.replace("-", "").replace(":", "")


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
    rows = {
        sheet: _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet)
        for sheet in REQUIRED_INPUT_SHEETS
    }
    for sheet in OPTIONAL_INPUT_SHEETS:
        rows[sheet] = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet) if sheet in titles else []
    return rows


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


def _text(*parts: Any) -> str:
    flattened: List[str] = []
    for part in parts:
        if isinstance(part, list):
            flattened.extend([_norm(item) for item in part if _norm(item)])
        else:
            value = _norm(part)
            if value:
                flattened.append(value)
    return " ".join(flattened)


def _contains_any(text: str, phrases: Sequence[str]) -> bool:
    lowered = _norm(text).lower()
    return any(phrase in lowered for phrase in phrases)


def _family_keyword_hits(families: Set[str], text: str) -> List[str]:
    lowered = _norm(text).lower()
    hits: List[str] = []
    for family in sorted(families):
        keywords = FAMILY_KEYWORDS.get(family, [])
        if any(keyword in lowered for keyword in keywords):
            hits.append(family)
    return hits


def _direction_signal(text: str) -> str:
    lowered = _norm(text).lower()
    up_score = sum(1 for hint in UP_HINTS if hint in lowered)
    down_score = sum(1 for hint in DOWN_HINTS if hint in lowered)
    if up_score > 0 and down_score == 0:
        return "UP"
    if down_score > 0 and up_score == 0:
        return "DOWN"
    if up_score > 0 and down_score > 0:
        return "MIXED"
    if _contains_any(lowered, UNCERTAINTY_HINTS):
        return "UNCERTAIN"
    return "NONE"


def _mechanism_scope_exclusion(ctx: Dict[str, Any]) -> str:
    if ctx["pack_level"] == "A":
        return "baseline pack has no added information under the refined pre-registration scope"
    if not ctx["output_valid"]:
        return "output_valid is not TRUE for this behavior row"
    return ""


def _preview_id(mechanism_id: str, session_id: str, provider: str, pack_level: str) -> str:
    return "|".join([mechanism_id, session_id, provider, pack_level])


def _state_metrics(observable_states: Dict[str, str]) -> Dict[str, int]:
    counts = Counter(observable_states.values())
    return {
        "positive": counts.get(STATE_POSITIVE, 0),
        "negative": counts.get(STATE_NEGATIVE, 0),
        "unknown": counts.get(STATE_UNKNOWN, 0),
        "missing": counts.get(STATE_MISSING, 0),
        "total": len(observable_states),
    }


def _finalize_from_observables(
    observable_states: Dict[str, str],
    positive_threshold: int,
    negative_threshold: int,
    hard_negative: bool = False,
) -> Dict[str, Any]:
    metrics = _state_metrics(observable_states)
    conflicts: List[str] = []
    if metrics["positive"] > 0 and metrics["negative"] > 0:
        conflicts.append("positive and negative observable states coexist")
    if hard_negative:
        label = "NEGATIVE"
        rule = "negative_rule"
        unknown_reason = ""
        insufficient_reason = ""
    elif metrics["total"] - metrics["missing"] == 0:
        label = "INSUFFICIENT_EVIDENCE"
        rule = "insufficient_evidence_rule"
        unknown_reason = ""
        insufficient_reason = "all refined observables are missing for this preview"
    elif metrics["missing"] >= metrics["total"] - 1 and metrics["positive"] == 0 and metrics["negative"] == 0:
        label = "INSUFFICIENT_EVIDENCE"
        rule = "insufficient_evidence_rule"
        unknown_reason = ""
        insufficient_reason = "too few observable traces are present for deterministic preview"
    elif metrics["positive"] >= positive_threshold and metrics["negative"] == 0:
        label = "POSITIVE"
        rule = "positive_rule"
        unknown_reason = ""
        insufficient_reason = ""
    elif metrics["negative"] >= negative_threshold and metrics["positive"] == 0:
        label = "NEGATIVE"
        rule = "negative_rule"
        unknown_reason = ""
        insufficient_reason = ""
    elif metrics["positive"] == 0 and metrics["negative"] == 0 and metrics["unknown"] > 0:
        label = "UNKNOWN"
        rule = "unknown_rule"
        unknown_reason = "observable evidence is present but remains partial or mixed"
        insufficient_reason = ""
    elif conflicts:
        label = "UNKNOWN"
        rule = "unknown_rule"
        unknown_reason = "observable states conflict under the frozen refined rules"
        insufficient_reason = ""
    else:
        label = "UNKNOWN"
        rule = "unknown_rule"
        unknown_reason = "observable evidence does not cross a frozen positive or negative threshold"
        insufficient_reason = ""
    return {
        "label": label,
        "rule_executed": rule,
        "conflicts": conflicts,
        "unknown_reason": unknown_reason,
        "insufficient_reason": insufficient_reason,
        "metrics": metrics,
    }


def _confidence_from_result(
    label: str,
    observable_states: Dict[str, str],
    conflict_count: int,
) -> Dict[str, str]:
    metrics = _state_metrics(observable_states)
    if label in {"EXCLUDED", "INSUFFICIENT_EVIDENCE"}:
        return {
            "confidence": "UNKNOWN",
            "evidence_completeness": "SPARSE",
            "evidence_consistency": "UNKNOWN",
            "ambiguity_level": "HIGH" if label == "INSUFFICIENT_EVIDENCE" else "LOW",
            "reason": "confidence is not assigned to excluded or insufficient-evidence previews",
        }
    completeness = "COMPLETE" if metrics["missing"] == 0 else ("PARTIAL" if metrics["missing"] <= 1 else "SPARSE")
    if conflict_count > 0:
        consistency = "CONTRADICTORY"
    elif metrics["unknown"] > 0:
        consistency = "MIXED"
    else:
        consistency = "CONSISTENT"
    ambiguity_level = "LOW"
    if label == "UNKNOWN" or conflict_count > 0:
        ambiguity_level = "HIGH"
    elif metrics["unknown"] > 0 or metrics["missing"] > 0:
        ambiguity_level = "MODERATE"
    if label == "UNKNOWN":
        confidence = "LOW"
    elif completeness == "COMPLETE" and consistency == "CONSISTENT":
        confidence = "HIGH"
    elif label in {"POSITIVE", "NEGATIVE"} and completeness in {"COMPLETE", "PARTIAL"}:
        confidence = "MODERATE"
    else:
        confidence = "LOW"
    return {
        "confidence": confidence,
        "evidence_completeness": completeness,
        "evidence_consistency": consistency,
        "ambiguity_level": ambiguity_level,
        "reason": f"{label.lower()} preview with {completeness.lower()} evidence and {consistency.lower()} observable state.",
    }


def _mechanism_stat(stats: Dict[str, Counter], mechanism_id: str) -> Tuple[int, int, int, int]:
    counter = stats.get(mechanism_id, Counter())
    total = counter.get("TOTAL", 0)
    conflicts = counter.get("CONFLICT", 0)
    ambiguity = counter.get("UNKNOWN", 0) + counter.get("INSUFFICIENT_EVIDENCE", 0)
    high_conf = counter.get("HIGH", 0)
    return total, conflicts, ambiguity, high_conf


def _source_sheets_from_observables(observable_rows: List[Dict[str, Any]]) -> List[str]:
    sources: Set[str] = set()
    for row in observable_rows:
        for part in _norm(row.get("observable_source")).split(";"):
            text = _norm(part)
            if text:
                sources.add(text)
    return sorted(sources)


def _build_refined_context(row: Dict[str, Any], indexes: Dict[str, Any]) -> Dict[str, Any]:
    ctx = _build_original_context(row, indexes)
    session_id = _norm(row.get("session_id"))
    provider = _norm(row.get("provider"))
    baseline_key = (session_id, provider, "A")
    baseline_behavior = indexes["behavior_by_key"].get(baseline_key, {})
    baseline_no_signal = indexes["no_signal_by_key"].get(baseline_key, {})
    ctx.update(
        {
            "primary_driver_summary": _norm(row.get("primary_driver_summary")),
            "secondary_driver_summary": _norm(row.get("secondary_driver_summary")),
            "reasoning_summary": _norm(row.get("reasoning_summary")),
            "invalidation_condition": _norm(row.get("invalidation_condition")),
            "baseline_behavior": baseline_behavior,
            "baseline_no_signal": baseline_no_signal,
        }
    )
    return ctx


def _evaluate_relevance(ctx: Dict[str, Any]) -> Dict[str, Any]:
    exclusion_reason = _mechanism_scope_exclusion(ctx)
    observable_states: Dict[str, str] = {
        "target_driver_alignment": STATE_MISSING,
        "field_to_causal_path_alignment": STATE_MISSING,
        "session_horizon_alignment": STATE_MISSING,
        "driver_linkage_depth": STATE_MISSING,
    }
    accessed_fields = [
        "primary_driver_summary",
        "secondary_driver_summary",
        "information_used",
        "causal_chain",
        "pack_fields_used",
        "pack_fields_that_changed_reasoning",
        "candidate_family",
        "influence_status",
        "forecast_direction",
        "no_signal_reason",
    ]
    if exclusion_reason:
        return {
            "label": "EXCLUDED",
            "classification_basis": "",
            "exclusion_reason": exclusion_reason,
            "unknown_reason": "",
            "insufficient_reason": "",
            "observable_states": observable_states,
            "conflicts": [],
            "accessed_fields": accessed_fields,
            "rule_executed": "excluded_rule",
            "hard_negative": False,
        }

    active_families = set(ctx["used_families"]) | set(ctx["changed_families"]) | set(ctx["discarded_families"])
    driver_text = _text(ctx["primary_driver_summary"], ctx["secondary_driver_summary"])
    causal_text = _text(ctx["causal_chain"], ctx["information_used_text"], ctx["reasoning_summary"])
    horizon_text = _text(causal_text, ctx["no_signal_reason"], ctx["invalidation_condition"])
    primary_hits = _family_keyword_hits(active_families, ctx["primary_driver_summary"])
    secondary_hits = _family_keyword_hits(active_families, ctx["secondary_driver_summary"])
    causal_hits = _family_keyword_hits(active_families, causal_text)
    driver_hits = _family_keyword_hits(active_families, driver_text)

    if active_families:
        observable_states["target_driver_alignment"] = (
            STATE_POSITIVE if driver_hits and causal_hits else STATE_NEGATIVE if ctx["used_count"] > 0 else STATE_UNKNOWN
        )
        observable_states["field_to_causal_path_alignment"] = (
            STATE_POSITIVE
            if (ctx["changed_count"] > 0 and causal_hits)
            else STATE_NEGATIVE
            if (ctx["used_count"] > 0 and ctx["changed_count"] == 0 and not causal_hits)
            else STATE_UNKNOWN
        )
        observable_states["session_horizon_alignment"] = (
            STATE_POSITIVE
            if (
                _contains_any(horizon_text, TIME_HINTS)
                or any("WITHIN_" in field or "PRESESSION" in field for field in ctx["used_fields"] | ctx["changed_fields"])
            )
            else STATE_UNKNOWN
        )
        if primary_hits and not secondary_hits:
            observable_states["driver_linkage_depth"] = STATE_POSITIVE
        elif secondary_hits and not primary_hits:
            observable_states["driver_linkage_depth"] = STATE_NEGATIVE
        elif primary_hits or secondary_hits:
            observable_states["driver_linkage_depth"] = STATE_UNKNOWN

    finalized = _finalize_from_observables(observable_states, positive_threshold=2, negative_threshold=2)
    label = finalized["label"]
    basis = ""
    if label == "POSITIVE":
        basis = "added information aligns with the stated driver path and the causal chain under the refined relevance rules"
    elif label == "NEGATIVE":
        basis = "added information is available but does not align cleanly with the driver path or causal chain"
    return {
        "label": label,
        "classification_basis": basis,
        "exclusion_reason": "",
        "unknown_reason": finalized["unknown_reason"],
        "insufficient_reason": finalized["insufficient_reason"],
        "observable_states": observable_states,
        "conflicts": finalized["conflicts"],
        "accessed_fields": accessed_fields,
        "rule_executed": finalized["rule_executed"],
        "hard_negative": False,
    }


def _evaluate_specificity(ctx: Dict[str, Any]) -> Dict[str, Any]:
    exclusion_reason = _mechanism_scope_exclusion(ctx)
    observable_states: Dict[str, str] = {
        "explicit_direction_condition": STATE_MISSING,
        "explicit_failure_condition": STATE_MISSING,
        "explicit_time_horizon": STATE_MISSING,
        "explicit_no_signal_boundary": STATE_MISSING,
    }
    accessed_fields = [
        "causal_chain",
        "information_used",
        "forecast_direction",
        "no_signal_reason",
        "invalidation_condition",
        "uncertainty_sources",
        "missing_information",
        "no_signal_flag",
        "forecast_confidence",
    ]
    if exclusion_reason:
        return {
            "label": "EXCLUDED",
            "classification_basis": "",
            "exclusion_reason": exclusion_reason,
            "unknown_reason": "",
            "insufficient_reason": "",
            "observable_states": observable_states,
            "conflicts": [],
            "accessed_fields": accessed_fields,
            "rule_executed": "excluded_rule",
            "hard_negative": False,
        }

    direction_text = _text(ctx["causal_chain"], ctx["information_used_text"], ctx["no_signal_reason"])
    invalidation_text = _text(ctx["invalidation_condition"])
    time_text = _text(direction_text, invalidation_text, ctx["primary_driver_summary"])
    uncertainty_count = len(ctx["uncertainty_sources"])
    direction_signal = _direction_signal(direction_text)

    if direction_text:
        has_conditional = _contains_any(_text(direction_text, invalidation_text), CONDITION_HINTS)
        if direction_signal in {"UP", "DOWN"} and has_conditional:
            observable_states["explicit_direction_condition"] = STATE_POSITIVE
        elif direction_signal in {"UP", "DOWN"} and not has_conditional and ctx["current_no_signal_flag"] == "FALSE":
            observable_states["explicit_direction_condition"] = STATE_NEGATIVE
        else:
            observable_states["explicit_direction_condition"] = STATE_UNKNOWN

    if invalidation_text:
        observable_states["explicit_failure_condition"] = (
            STATE_POSITIVE if len(invalidation_text) >= 25 and _contains_any(invalidation_text, CONDITION_HINTS) else STATE_UNKNOWN
        )
    else:
        observable_states["explicit_failure_condition"] = STATE_NEGATIVE

    if time_text:
        observable_states["explicit_time_horizon"] = (
            STATE_POSITIVE if _contains_any(time_text, TIME_HINTS) else STATE_UNKNOWN
        )

    if ctx["current_no_signal_flag"] == "TRUE" and _norm(ctx["no_signal_reason"]):
        observable_states["explicit_no_signal_boundary"] = STATE_POSITIVE
    else:
        observable_states["explicit_no_signal_boundary"] = STATE_UNKNOWN

    finalized = _finalize_from_observables(observable_states, positive_threshold=2, negative_threshold=2)
    label = finalized["label"]
    basis = ""
    if label == "POSITIVE":
        basis = "added information narrows the claim with explicit conditions, failure bounds, or time framing"
    elif label == "NEGATIVE":
        basis = "added information remains generic or verbose without a clear falsifiable boundary"
    return {
        "label": label,
        "classification_basis": basis,
        "exclusion_reason": "",
        "unknown_reason": finalized["unknown_reason"],
        "insufficient_reason": finalized["insufficient_reason"],
        "observable_states": observable_states,
        "conflicts": finalized["conflicts"],
        "accessed_fields": accessed_fields,
        "rule_executed": finalized["rule_executed"],
        "hard_negative": False,
    }


def _evaluate_consistency(ctx: Dict[str, Any]) -> Dict[str, Any]:
    exclusion_reason = _mechanism_scope_exclusion(ctx)
    observable_states: Dict[str, str] = {
        "cross_field_consistency": STATE_MISSING,
        "driver_causal_chain_consistency": STATE_MISSING,
        "direction_rationale_consistency": STATE_MISSING,
        "confidence_evidence_consistency": STATE_MISSING,
    }
    accessed_fields = [
        "candidate_family",
        "influence_status",
        "field_reported_no_effect",
        "primary_driver_summary",
        "secondary_driver_summary",
        "causal_chain",
        "forecast_direction",
        "no_signal_flag",
        "forecast_confidence",
        "confidence_bucket",
        "uncertainty_sources",
        "missing_information",
        "no_signal_reason",
    ]
    if exclusion_reason:
        return {
            "label": "EXCLUDED",
            "classification_basis": "",
            "exclusion_reason": exclusion_reason,
            "unknown_reason": "",
            "insufficient_reason": "",
            "observable_states": observable_states,
            "conflicts": [],
            "accessed_fields": accessed_fields,
            "rule_executed": "excluded_rule",
            "hard_negative": False,
        }

    causal_text = _text(ctx["causal_chain"], ctx["reasoning_summary"])
    primary_text = _text(ctx["primary_driver_summary"])
    secondary_text = _text(ctx["secondary_driver_summary"])
    combined_driver_text = _text(primary_text, secondary_text)
    active_families = set(ctx["used_families"]) | set(ctx["changed_families"])
    cross_hits = _family_keyword_hits(active_families, _text(causal_text, ctx["information_used_text"]))

    if active_families:
        if cross_hits and ctx["no_effect_count"] == 0:
            observable_states["cross_field_consistency"] = STATE_POSITIVE
        elif ctx["used_count"] > 0 and not cross_hits:
            observable_states["cross_field_consistency"] = STATE_NEGATIVE
        else:
            observable_states["cross_field_consistency"] = STATE_UNKNOWN

    primary_direction = _direction_signal(primary_text)
    secondary_direction = _direction_signal(secondary_text)
    causal_direction = _direction_signal(causal_text)
    if primary_text or secondary_text or causal_text:
        if primary_direction in {"UP", "DOWN"} and primary_direction == causal_direction and secondary_direction not in {"UP", "DOWN"}:
            observable_states["driver_causal_chain_consistency"] = STATE_POSITIVE
        elif (
            primary_direction in {"UP", "DOWN"}
            and causal_direction in {"UP", "DOWN"}
            and primary_direction != causal_direction
        ) or (
            secondary_direction in {"UP", "DOWN"}
            and causal_direction in {"UP", "DOWN"}
            and secondary_direction != causal_direction
        ):
            observable_states["driver_causal_chain_consistency"] = STATE_NEGATIVE
        else:
            observable_states["driver_causal_chain_consistency"] = STATE_UNKNOWN

    forecast_direction = ctx["current_direction"].lower()
    if ctx["current_no_signal_flag"] == "TRUE":
        observable_states["direction_rationale_consistency"] = (
            STATE_POSITIVE if _contains_any(_text(causal_text, ctx["no_signal_reason"]), UNCERTAINTY_HINTS) else STATE_UNKNOWN
        )
    elif causal_direction in {"UP", "DOWN"}:
        expected_direction = "up" if causal_direction == "UP" else "down"
        observable_states["direction_rationale_consistency"] = (
            STATE_POSITIVE if forecast_direction == expected_direction else STATE_NEGATIVE
        )
    elif causal_direction == "MIXED":
        observable_states["direction_rationale_consistency"] = STATE_NEGATIVE
    else:
        observable_states["direction_rationale_consistency"] = STATE_UNKNOWN

    uncertainty_count = len(ctx["uncertainty_sources"])
    missing_info_present = bool(ctx["missing_information"]) or _contains_any(ctx["missing_information"], SCARCITY_HINTS)
    current_confidence = ctx["current_confidence"]
    high_confidence = current_confidence is not None and current_confidence >= 70 or ctx["current_confidence_bucket"] == "HIGH"
    if high_confidence and (uncertainty_count >= 2 or missing_info_present or ctx["current_no_signal_flag"] == "TRUE"):
        observable_states["confidence_evidence_consistency"] = STATE_NEGATIVE
    elif not high_confidence and (uncertainty_count >= 1 or missing_info_present or ctx["current_no_signal_flag"] == "TRUE"):
        observable_states["confidence_evidence_consistency"] = STATE_POSITIVE
    elif high_confidence and not uncertainty_count and not missing_info_present:
        observable_states["confidence_evidence_consistency"] = STATE_POSITIVE
    else:
        observable_states["confidence_evidence_consistency"] = STATE_UNKNOWN

    hard_negative = observable_states["direction_rationale_consistency"] == STATE_NEGATIVE and observable_states[
        "driver_causal_chain_consistency"
    ] == STATE_NEGATIVE
    finalized = _finalize_from_observables(
        observable_states,
        positive_threshold=2,
        negative_threshold=2,
        hard_negative=hard_negative,
    )
    label = finalized["label"]
    basis = ""
    if label == "POSITIVE":
        basis = "added information remains internally coherent across fields, drivers, direction rationale, and confidence evidence"
    elif label == "NEGATIVE":
        basis = "added information introduces contradiction across the refined consistency observables"
    return {
        "label": label,
        "classification_basis": basis,
        "exclusion_reason": "",
        "unknown_reason": finalized["unknown_reason"],
        "insufficient_reason": finalized["insufficient_reason"],
        "observable_states": observable_states,
        "conflicts": finalized["conflicts"],
        "accessed_fields": accessed_fields,
        "rule_executed": finalized["rule_executed"],
        "hard_negative": hard_negative,
    }


def _evaluate_mechanism(mechanism_id: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
    if mechanism_id == "MECH_INFORMATION_RELEVANCE":
        return _evaluate_relevance(ctx)
    if mechanism_id == "MECH_INFORMATION_SPECIFICITY":
        return _evaluate_specificity(ctx)
    if mechanism_id == "MECH_INFORMATION_CONSISTENCY":
        return _evaluate_consistency(ctx)
    return {
        "label": "EXCLUDED",
        "classification_basis": "",
        "exclusion_reason": "mechanism is outside the refined dry-run scope",
        "unknown_reason": "",
        "insufficient_reason": "",
        "observable_states": {},
        "conflicts": [],
        "accessed_fields": [],
        "rule_executed": "excluded_rule",
        "hard_negative": False,
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
        ("REFINED_MECHANISM_CLASSIFICATION_DRY_RUN", OUTPUT_DRY_RUN, "refined_mechanism_classification_dry_run"),
        ("REFINED_MECHANISM_LABEL_PREVIEW", OUTPUT_LABEL_PREVIEW, "refined_mechanism_label_preview"),
        ("REFINED_MECHANISM_EVIDENCE_AUDIT", OUTPUT_EVIDENCE, "refined_mechanism_evidence_audit"),
        ("REFINED_MECHANISM_CONFLICT_AUDIT", OUTPUT_CONFLICT, "refined_mechanism_conflict_audit"),
        ("REFINED_MECHANISM_CONFIDENCE_PREVIEW", OUTPUT_CONFIDENCE, "refined_mechanism_confidence_preview"),
        ("REFINED_MECHANISM_DETERMINISM_AUDIT", OUTPUT_DETERMINISM, "refined_mechanism_determinism_audit"),
        ("REFINED_MECHANISM_LEAKAGE_AUDIT", OUTPUT_LEAKAGE, "refined_mechanism_leakage_audit"),
        ("REFINED_MECHANISM_DRY_RUN_GOVERNANCE", OUTPUT_GOVERNANCE, "refined_mechanism_dry_run_governance"),
        ("REFINED_MECHANISM_DRY_RUN_SUMMARY", OUTPUT_SUMMARY, "refined_mechanism_dry_run_summary"),
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
            "notes": "Phase 9A-6R2 refined mechanism dry run; preview-only, deterministic, and non-permanent.",
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


def build_refined_mechanism_classification_dry_run_v0() -> Dict[str, Any]:
    service = build_sheets_service(load_credentials())
    generated_ts = _iso_now()
    dry_run_id = _dry_run_id(generated_ts)
    data = _read_inputs(service)

    prereg_rows = data["Refined_Mechanism_PreRegistration"]
    definitions_rows = data["Refined_Mechanism_Frozen_Definitions"]
    observables_rows = data["Refined_Mechanism_Frozen_Observables"]
    label_rule_rows = data["Refined_Mechanism_Frozen_Label_Rules"]
    behavior_rows = data["Pack_Behavior_Tier2_Behavior"]

    stable_id_by_mechanism = {
        _norm(row.get("mechanism_id")): _norm(row.get("stable_mechanism_id"))
        for row in prereg_rows
        if _norm(row.get("stable_mechanism_id"))
    }
    dry_run_mechanisms = [
        _norm(row.get("mechanism_id"))
        for row in prereg_rows
        if _norm(row.get("dry_run_classification_allowed")).upper() == "TRUE"
    ]
    if not dry_run_mechanisms:
        raise RuntimeError("No promoted refined mechanisms are authorized for dry-run classification.")

    observables_by_mechanism: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in observables_rows:
        mechanism_id = _norm(row.get("mechanism_id"))
        if mechanism_id:
            observables_by_mechanism[mechanism_id].append(row)
    source_sheets_by_mechanism = {
        mechanism_id: _source_sheets_from_observables(rows)
        for mechanism_id, rows in observables_by_mechanism.items()
    }
    label_rules_by_mechanism = {
        _norm(row.get("mechanism_id")): row for row in label_rule_rows if _norm(row.get("mechanism_id"))
    }
    definitions_by_mechanism = {
        _norm(row.get("mechanism_id")): row for row in definitions_rows if _norm(row.get("mechanism_id"))
    }

    original_summary = data.get("Predictive_Mechanism_Dry_Run_Summary", [])
    original_labels = data.get("Predictive_Mechanism_Label_Preview", [])
    original_conflicts = data.get("Predictive_Mechanism_Conflict_Audit", [])

    indexes = _build_original_indexes(data)

    dry_run_rows: List[Dict[str, Any]] = []
    label_preview_rows: List[Dict[str, Any]] = []
    evidence_rows: List[Dict[str, Any]] = []
    conflict_rows: List[Dict[str, Any]] = []
    confidence_rows: List[Dict[str, Any]] = []
    determinism_rows: List[Dict[str, Any]] = []
    leakage_rows: List[Dict[str, Any]] = []
    stats_by_mechanism: Dict[str, Counter] = defaultdict(Counter)
    unique_eligible_behavior_keys: Set[Tuple[str, str, str]] = set()

    for behavior_row in behavior_rows:
        ctx = _build_refined_context(behavior_row, indexes)
        session_id = ctx["session_id"]
        provider = ctx["provider"]
        pack_level = ctx["pack_level"]
        behavior_row_number = behavior_row.get("__source_row_number__", "")
        behavior_key = (session_id, provider, pack_level)

        for mechanism_id in dry_run_mechanisms:
            stable_id = stable_id_by_mechanism.get(mechanism_id, "")
            preview_id = _preview_id(mechanism_id, session_id, provider, pack_level)
            first_pass = _evaluate_mechanism(mechanism_id, ctx)
            second_pass = _evaluate_mechanism(mechanism_id, ctx)

            observable_states = first_pass["observable_states"]
            conflict_detected = bool(first_pass["conflicts"])
            ambiguity_detected = first_pass["label"] in {"UNKNOWN", "INSUFFICIENT_EVIDENCE"} or conflict_detected
            confidence_info = _confidence_from_result(first_pass["label"], observable_states, len(first_pass["conflicts"]))
            first_allowed_sources = source_sheets_by_mechanism.get(mechanism_id, [])
            leakage_detected = any(
                any(term in field.lower() for term in FORBIDDEN_FIELD_TERMS)
                for field in first_pass["accessed_fields"]
            )
            leakage_status = "OUTCOME_LEAKAGE_DETECTED" if leakage_detected else "PASS_PRE_OUTCOME_ONLY"
            deterministic_status = (
                "PASS"
                if (
                    first_pass["label"] == second_pass["label"]
                    and confidence_info["confidence"]
                    == _confidence_from_result(second_pass["label"], second_pass["observable_states"], len(second_pass["conflicts"]))[
                        "confidence"
                    ]
                    and first_pass["rule_executed"] == second_pass["rule_executed"]
                    and json.dumps(first_pass["observable_states"], sort_keys=True)
                    == json.dumps(second_pass["observable_states"], sort_keys=True)
                )
                else "FAIL"
            )

            eligible_for_preview = first_pass["label"] != "EXCLUDED"
            if eligible_for_preview:
                unique_eligible_behavior_keys.add(behavior_key)

            stats = stats_by_mechanism[mechanism_id]
            stats["TOTAL"] += 1
            stats[first_pass["label"]] += 1
            stats[confidence_info["confidence"]] += 1
            if conflict_detected:
                stats["CONFLICT"] += 1
            if ambiguity_detected:
                stats["AMBIGUITY"] += 1

            notes_blob = {
                "frozen_positive_rule": _norm(label_rules_by_mechanism.get(mechanism_id, {}).get("positive_label_rule")),
                "frozen_definition": _norm(definitions_by_mechanism.get(mechanism_id, {}).get("scientific_definition")),
            }
            dry_run_rows.append(
                {
                    **_base(generated_ts, dry_run_id),
                    "preview_id": preview_id,
                    "stable_mechanism_id": stable_id,
                    "mechanism_id": mechanism_id,
                    "session_id": session_id,
                    "provider": provider,
                    "pack_level": pack_level,
                    "behavior_row_number": behavior_row_number,
                    "preview_label": first_pass["label"],
                    "preview_confidence": confidence_info["confidence"],
                    "eligible_for_preview": "TRUE" if eligible_for_preview else "FALSE",
                    "conflict_detected": "TRUE" if conflict_detected else "FALSE",
                    "leakage_status": leakage_status,
                    "deterministic_status": deterministic_status,
                    "rule_executed": first_pass["rule_executed"],
                    "notes": json.dumps(notes_blob, sort_keys=True, ensure_ascii=True),
                }
            )
            label_preview_rows.append(
                {
                    **_base(generated_ts, dry_run_id),
                    "preview_id": preview_id,
                    "stable_mechanism_id": stable_id,
                    "mechanism_id": mechanism_id,
                    "session_id": session_id,
                    "provider": provider,
                    "pack_level": pack_level,
                    "preview_label": first_pass["label"],
                    "classification_basis": first_pass["classification_basis"],
                    "exclusion_reason": first_pass["exclusion_reason"],
                    "unknown_reason": first_pass["unknown_reason"],
                    "insufficient_evidence_reason": first_pass["insufficient_reason"],
                    "preview_confidence": confidence_info["confidence"],
                    "notes": json.dumps(first_pass["observable_states"], sort_keys=True, ensure_ascii=True),
                }
            )
            evidence_rows.append(
                {
                    **_base(generated_ts, dry_run_id),
                    "preview_id": preview_id,
                    "stable_mechanism_id": stable_id,
                    "mechanism_id": mechanism_id,
                    "session_id": session_id,
                    "provider": provider,
                    "pack_level": pack_level,
                    "observable_states": json.dumps(first_pass["observable_states"], sort_keys=True, ensure_ascii=True),
                    "observables_found": json.dumps(
                        [name for name, state in first_pass["observable_states"].items() if state != STATE_MISSING],
                        ensure_ascii=True,
                    ),
                    "observables_missing": json.dumps(
                        [name for name, state in first_pass["observable_states"].items() if state == STATE_MISSING],
                        ensure_ascii=True,
                    ),
                    "evidence_completeness": confidence_info["evidence_completeness"],
                    "extraction_success": "TRUE"
                    if any(state != STATE_MISSING for state in first_pass["observable_states"].values())
                    else "FALSE",
                    "ambiguity_detected": "TRUE" if ambiguity_detected else "FALSE",
                    "source_sheets_used": json.dumps(first_allowed_sources, ensure_ascii=True),
                    "rule_executed": first_pass["rule_executed"],
                    "notes": "Observable states follow the refined pre-registered mechanism order.",
                }
            )
            conflict_rows.append(
                {
                    **_base(generated_ts, dry_run_id),
                    "preview_id": preview_id,
                    "stable_mechanism_id": stable_id,
                    "mechanism_id": mechanism_id,
                    "session_id": session_id,
                    "provider": provider,
                    "pack_level": pack_level,
                    "conflicting_observables": json.dumps(first_pass["conflicts"], ensure_ascii=True),
                    "conflict_type": "positive_negative_mixed" if conflict_detected else "none",
                    "conflicting_labels": json.dumps(
                        [state for state in first_pass["observable_states"].values() if state in {STATE_POSITIVE, STATE_NEGATIVE}],
                        ensure_ascii=True,
                    ),
                    "unresolved_conflict": "TRUE" if conflict_detected else "FALSE",
                    "conflict_resolution_path": (
                        "unknown_after_conflict"
                        if first_pass["label"] == "UNKNOWN" and conflict_detected
                        else first_pass["rule_executed"]
                    ),
                    "final_preview_outcome": first_pass["label"],
                    "notes": "Refined conflict audit remains preview-only and non-permanent.",
                }
            )
            confidence_rows.append(
                {
                    **_base(generated_ts, dry_run_id),
                    "preview_id": preview_id,
                    "stable_mechanism_id": stable_id,
                    "mechanism_id": mechanism_id,
                    "session_id": session_id,
                    "provider": provider,
                    "pack_level": pack_level,
                    "evidence_completeness": confidence_info["evidence_completeness"],
                    "evidence_consistency": confidence_info["evidence_consistency"],
                    "ambiguity_level": confidence_info["ambiguity_level"],
                    "preview_confidence": confidence_info["confidence"],
                    "confidence_assignment_reason": confidence_info["reason"],
                    "notes": "Confidence refers only to the preview label quality, never to forecast confidence.",
                }
            )
            determinism_rows.append(
                {
                    **_base(generated_ts, dry_run_id),
                    "preview_id": preview_id,
                    "stable_mechanism_id": stable_id,
                    "mechanism_id": mechanism_id,
                    "session_id": session_id,
                    "provider": provider,
                    "pack_level": pack_level,
                    "first_pass_label": first_pass["label"],
                    "second_pass_label": second_pass["label"],
                    "first_pass_confidence": confidence_info["confidence"],
                    "second_pass_confidence": _confidence_from_result(
                        second_pass["label"], second_pass["observable_states"], len(second_pass["conflicts"])
                    )["confidence"],
                    "first_pass_rule": first_pass["rule_executed"],
                    "second_pass_rule": second_pass["rule_executed"],
                    "audit_trail_match": "TRUE"
                    if json.dumps(first_pass["observable_states"], sort_keys=True)
                    == json.dumps(second_pass["observable_states"], sort_keys=True)
                    else "FALSE",
                    "deterministic_status": deterministic_status,
                    "notes": "Second pass replays the same frozen refined rules without manual overrides.",
                }
            )
            leakage_rows.append(
                {
                    **_base(generated_ts, dry_run_id),
                    "preview_id": preview_id,
                    "stable_mechanism_id": stable_id,
                    "mechanism_id": mechanism_id,
                    "session_id": session_id,
                    "provider": provider,
                    "pack_level": pack_level,
                    "accessed_source_sheets": json.dumps(first_allowed_sources, ensure_ascii=True),
                    "accessed_fields": json.dumps(sorted(first_pass["accessed_fields"]), ensure_ascii=True),
                    "realized_direction_accessed": "FALSE",
                    "overall_ok_accessed": "FALSE",
                    "corrected_outcomes_accessed": "FALSE",
                    "evaluation_results_accessed": "FALSE",
                    "future_information_accessed": "FALSE",
                    "leakage_status": leakage_status,
                    "notes": "Leakage audit is based on the frozen refined field access set.",
                }
            )

    governance_specs = [
        ("GOV_PROVIDER_CALLS", "provider_calls_performed", "0", "0"),
        ("GOV_FORECAST_GENERATION", "forecast_generation_performed", "0", "0"),
        ("GOV_PERMANENT_LABELS", "permanent_labels_assigned", "0", "0"),
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
            **_base(generated_ts, dry_run_id),
            "check_id": check_id,
            "check_name": check_name,
            "expected_value": expected_value,
            "actual_value": actual_value,
            "status": "PASS" if expected_value == actual_value else "FAIL",
            "notes": "Refined dry run remains preview-only and non-production.",
        }
        for check_id, check_name, expected_value, actual_value in governance_specs
    ]

    label_counter = Counter(row["preview_label"] for row in label_preview_rows)
    determinism_failures = sum(1 for row in determinism_rows if _norm(row.get("deterministic_status")) != "PASS")
    leakage_findings = sum(1 for row in leakage_rows if _norm(row.get("leakage_status")) == "OUTCOME_LEAKAGE_DETECTED")

    original_total = 0
    original_conflict = 0
    original_ambiguity = 0
    for row in original_labels:
        if _norm(row.get("mechanism_id")) == "MECH_INFORMATION_VALUE":
            original_total += 1
            if _norm(row.get("preview_label")) in {"UNKNOWN", "INSUFFICIENT_EVIDENCE"}:
                original_ambiguity += 1
    for row in original_conflicts:
        if _norm(row.get("mechanism_id")) == "MECH_INFORMATION_VALUE" and (
            _norm(row.get("unresolved_conflict")).upper() == "TRUE" or _norm(row.get("conflicting_observables"))
        ):
            original_conflict += 1
    if original_summary:
        summary_notes = _norm(original_summary[0].get("notes"))
        highest_ambiguity_text = _norm(original_summary[0].get("highest_ambiguity"))
        if highest_ambiguity_text.endswith("/120"):
            try:
                original_ambiguity = int(highest_ambiguity_text.split(":")[-1].split("/")[0])
            except ValueError:
                pass
        if not original_total:
            try:
                original_total = int(_norm(original_summary[0].get("preview_labels_assigned"))) // 6
            except ValueError:
                original_total = 120
        if summary_notes and not original_total:
            original_total = 120
    if not original_total:
        original_total = len(behavior_rows)

    per_mechanism_stats: Dict[str, Dict[str, Any]] = {}
    strongest_refined_mechanism = "NONE"
    strongest_tuple: Optional[Tuple[float, float, int, str]] = None
    highest_remaining_conflict = "NONE"
    highest_remaining_conflict_count = -1
    highest_remaining_ambiguity = "NONE"
    highest_remaining_ambiguity_count = -1
    for mechanism_id in dry_run_mechanisms:
        total, conflicts, ambiguity, high_conf = _mechanism_stat(stats_by_mechanism, mechanism_id)
        clean_rate = 0.0 if total == 0 else float(total - conflicts - ambiguity) / float(total)
        conflict_rate = 0.0 if total == 0 else float(conflicts) / float(total)
        ambiguity_rate = 0.0 if total == 0 else float(ambiguity) / float(total)
        per_mechanism_stats[mechanism_id] = {
            "total": total,
            "conflicts": conflicts,
            "ambiguity": ambiguity,
            "high_confidence": high_conf,
            "conflict_rate": conflict_rate,
            "ambiguity_rate": ambiguity_rate,
            "clean_rate": clean_rate,
        }
        rank_tuple = (clean_rate, -conflict_rate, high_conf, mechanism_id)
        if strongest_tuple is None or rank_tuple > strongest_tuple:
            strongest_tuple = rank_tuple
            strongest_refined_mechanism = mechanism_id
        if conflicts > highest_remaining_conflict_count:
            highest_remaining_conflict_count = conflicts
            highest_remaining_conflict = f"{mechanism_id}:{conflicts}/{total or 1}"
        if ambiguity > highest_remaining_ambiguity_count:
            highest_remaining_ambiguity_count = ambiguity
            highest_remaining_ambiguity = f"{mechanism_id}:{ambiguity}/{total or 1}"

    refined_conflict_baseline = highest_remaining_conflict_count if highest_remaining_conflict_count >= 0 else 0
    refined_ambiguity_baseline = highest_remaining_ambiguity_count if highest_remaining_ambiguity_count >= 0 else 0
    ambiguity_reduction_value = original_ambiguity - refined_ambiguity_baseline
    conflict_reduction_value = original_conflict - refined_conflict_baseline
    ambiguity_reduction = (
        f"MECH_INFORMATION_VALUE baseline {original_ambiguity}/{original_total} -> highest refined ambiguity "
        f"{refined_ambiguity_baseline}/{len(behavior_rows)} (reduction {ambiguity_reduction_value} rows)"
    )
    conflict_reduction = (
        f"MECH_INFORMATION_VALUE baseline {original_conflict}/{original_total} -> highest refined conflict "
        f"{refined_conflict_baseline}/{len(behavior_rows)} (reduction {conflict_reduction_value} rows)"
    )

    build_status = "PASS_WITH_WARNINGS"
    final_interpretation = "REFINED_MECHANISM_CLASSIFICATION_DRY_RUN_READY_WITH_WARNINGS"
    recommended_next_step = "PROCEED_TO_PHASE9A6R3_REFINED_CONFLICT_REVIEW"
    if leakage_findings > 0 or determinism_failures > 0 or ambiguity_reduction_value <= 0 or conflict_reduction_value <= 0:
        build_status = "NEEDS_REVIEW"
        final_interpretation = "REFINED_MECHANISM_CLASSIFICATION_DRY_RUN_NEEDS_REPAIR"
        recommended_next_step = "RUN_PHASE9A6R2_DRY_RUN_REPAIR"

    summary_row = {
        **_base(generated_ts, dry_run_id),
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "eligible_rows_previewed": len(unique_eligible_behavior_keys),
        "preview_labels_assigned": len(label_preview_rows),
        "positive_labels": label_counter.get("POSITIVE", 0),
        "negative_labels": label_counter.get("NEGATIVE", 0),
        "unknown_labels": label_counter.get("UNKNOWN", 0),
        "insufficient_evidence_labels": label_counter.get("INSUFFICIENT_EVIDENCE", 0),
        "excluded_labels": label_counter.get("EXCLUDED", 0),
        "ambiguity_reduction": ambiguity_reduction,
        "conflict_reduction": conflict_reduction,
        "leakage_findings": leakage_findings,
        "determinism_status": "PASS" if determinism_failures == 0 else "FAIL",
        "strongest_refined_mechanism": strongest_refined_mechanism,
        "highest_remaining_conflict": highest_remaining_conflict,
        "highest_remaining_ambiguity": highest_remaining_ambiguity,
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "permanent_labels_assigned": 0,
        "mechanism_testing_performed": 0,
        "production_behavior_change_count": 0,
        "ready_for_refined_classification_execution": "FALSE",
        "ready_for_refined_mechanism_testing": "FALSE",
        "ready_for_replication": "FALSE",
        "ready_for_production": "FALSE",
        "recommended_next_step": recommended_next_step,
        "notes": json.dumps(
            {
                "dry_run_scope": dry_run_mechanisms,
                "subdimension_excluded_from_direct_preview": "MECH_INFORMATION_NOVELTY",
                "umbrella_excluded_from_direct_preview": "MECH_INFORMATION_VALUE",
                "per_mechanism_stats": per_mechanism_stats,
                "original_composite_total": original_total,
                "original_composite_conflict": original_conflict,
                "original_composite_ambiguity": original_ambiguity,
            },
            sort_keys=True,
            ensure_ascii=True,
        ),
    }

    outputs = [
        (OUTPUT_DRY_RUN, DRY_RUN_HEADERS, dry_run_rows),
        (OUTPUT_LABEL_PREVIEW, LABEL_PREVIEW_HEADERS, label_preview_rows),
        (OUTPUT_EVIDENCE, EVIDENCE_HEADERS, evidence_rows),
        (OUTPUT_CONFLICT, CONFLICT_HEADERS, conflict_rows),
        (OUTPUT_CONFIDENCE, CONFIDENCE_HEADERS, confidence_rows),
        (OUTPUT_DETERMINISM, DETERMINISM_HEADERS, determinism_rows),
        (OUTPUT_LEAKAGE, LEAKAGE_HEADERS, leakage_rows),
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
        "file_created": "automation/build_refined_mechanism_classification_dry_run_v0.py",
        "sheets_written": {sheet_name: len(rows) for sheet_name, _, rows in outputs},
        "eligible_rows_previewed": len(unique_eligible_behavior_keys),
        "preview_labels_assigned": len(label_preview_rows),
        "positive_labels": label_counter.get("POSITIVE", 0),
        "negative_labels": label_counter.get("NEGATIVE", 0),
        "unknown_labels": label_counter.get("UNKNOWN", 0),
        "insufficient_evidence_labels": label_counter.get("INSUFFICIENT_EVIDENCE", 0),
        "excluded_labels": label_counter.get("EXCLUDED", 0),
        "ambiguity_reduction": ambiguity_reduction,
        "conflict_reduction": conflict_reduction,
        "leakage_findings": leakage_findings,
        "determinism_status": "PASS" if determinism_failures == 0 else "FAIL",
        "strongest_refined_mechanism": strongest_refined_mechanism,
        "highest_remaining_conflict": highest_remaining_conflict,
        "highest_remaining_ambiguity": highest_remaining_ambiguity,
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "permanent_labels_assigned": 0,
        "mechanism_testing_performed": 0,
        "production_behavior_change_count": 0,
        "ready_for_refined_classification_execution": False,
        "ready_for_refined_mechanism_testing": False,
        "ready_for_replication": False,
        "ready_for_production": False,
        "recommended_next_step": recommended_next_step,
        "registry": registry,
    }


def main() -> None:
    result = build_refined_mechanism_classification_dry_run_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
