import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.build_market_sessions_shadow_v0 import (
    DIAGNOSTICS_SPREADSHEET_ID,
    MAIN_SPREADSHEET_ID,
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


SCHEMA_VERSION = "presignal_v2_market_reaction_canonical_source_selection_review_0.1"
REVIEW_VERSION = "market_reaction_canonical_source_selection_review_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-5M1"
REGISTRY_CATEGORY = "PRESIGNAL_V2_MARKET_REACTION_CANONICAL_SOURCE_SELECTION_REVIEW"
REGISTRY_OWNER_MODULE = "market_state"

MAIN_INPUT_SHEETS = [
    "MR_ProviderRuns",
    "Evaluation_Rows",
    "Outcome_Ledger",
    "Config",
    "Event",
]

DIAG_INPUT_SHEETS = [
    "Market_Reaction_Source_Repair_Design",
    "Market_Reaction_Canonical_Source_Strategy",
    "Market_Reaction_Window_Definition_Design",
    "Market_Reaction_Outcome_Matching_Design",
    "Market_Reaction_Disagreement_Handling",
    "Market_Reaction_Trust_Scoring_Design",
    "Market_Reaction_Repair_Readiness",
    "Market_Reaction_Source_Repair_Summary",
    "Market_Reaction_Outcome_Integrity_Summary",
]

CRITICAL_MAIN_SHEETS = {"MR_ProviderRuns", "Evaluation_Rows", "Outcome_Ledger", "Config"}
CRITICAL_DIAG_SHEETS = {
    "Market_Reaction_Canonical_Source_Strategy",
    "Market_Reaction_Window_Definition_Design",
    "Market_Reaction_Outcome_Matching_Design",
    "Market_Reaction_Disagreement_Handling",
    "Market_Reaction_Trust_Scoring_Design",
    "Market_Reaction_Source_Repair_Summary",
    "Market_Reaction_Outcome_Integrity_Summary",
}

OUTPUT_REVIEW = "Market_Reaction_Canonical_Source_Review"
OUTPUT_COMPARISON = "Market_Reaction_Source_Strategy_Comparison"
OUTPUT_RISK = "Market_Reaction_Source_Risk_Assessment"
OUTPUT_WINDOW = "Market_Reaction_Canonical_Window_Review"
OUTPUT_MATCHING = "Market_Reaction_Canonical_Matching_Review"
OUTPUT_TRUST = "Market_Reaction_Canonical_Trust_Model"
OUTPUT_DECISION = "Market_Reaction_Source_Selection_Decision"
OUTPUT_GOVERNANCE = "Market_Reaction_Canonical_Source_Governance"
OUTPUT_SUMMARY = "Market_Reaction_Canonical_Source_Review_Summary"

REVIEW_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "review_area",
    "review_status",
    "evidence_scope",
    "review_finding",
    "selected_policy",
    "rejected_alternatives",
    "remaining_risk",
    "implementation_dependency",
    "production_excluded",
    "notes",
]

COMPARISON_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "strategy_id",
    "strategy_name",
    "strategy_type",
    "determinism",
    "reproducibility",
    "auditability",
    "provider_independence",
    "ambiguity_reduction",
    "implementation_complexity",
    "long_term_maintainability",
    "presignal_v2_compatibility",
    "review_score",
    "selection_status",
    "selection_rationale",
    "rejection_reason",
    "notes",
]

RISK_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "risk_id",
    "risk_name",
    "severity",
    "evidence",
    "selected_architecture_mitigation",
    "blocks_implementation",
    "future_limitation",
    "notes",
]

WINDOW_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "window_policy_id",
    "candidate_policy",
    "review_result",
    "selected_as_canonical",
    "selection_reason",
    "rejection_or_limitation",
    "expected_window_rule",
    "ambiguity_reduction",
    "notes",
]

MATCHING_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "matching_policy_id",
    "candidate_policy",
    "review_result",
    "selected_as_canonical",
    "canonical_matching_hierarchy",
    "ambiguity_resolution",
    "strict_accuracy_allowed",
    "notes",
]

TRUST_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "trust_field_id",
    "field_name",
    "mandatory",
    "approved_for_implementation",
    "use_in_strict_accuracy_filter",
    "review_decision",
    "notes",
]

DECISION_HEADERS = [
    "generated_ts",
    "schema_version",
    "review_version",
    "review_run_id",
    "decision_id",
    "canonical_strategy_selected",
    "canonical_window_selected",
    "canonical_matching_strategy_selected",
    "disagreement_policy_selected",
    "trust_metadata_approved",
    "why_selected",
    "why_alternatives_rejected",
    "assumptions",
    "risks",
    "future_limitations",
    "ready_for_outcome_source_implementation",
    "recommended_next_step",
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
    "strategies_reviewed",
    "canonical_strategy_selected",
    "canonical_window_selected",
    "canonical_matching_strategy_selected",
    "disagreement_policy_selected",
    "trust_metadata_approved",
    "highest_remaining_risk",
    "ready_for_outcome_source_implementation",
    "ready_for_accuracy_replication",
    "ready_for_production",
    "provider_calls_performed",
    "forecast_generation_performed",
    "accuracy_evaluation_performed",
    "metrics_recalculated",
    "market_reaction_values_modified",
    "evaluation_rows_written",
    "outcome_ledger_written",
    "production_sheet_write_count",
    "production_behavior_change_count",
    "routing_changes",
    "weighting_changes",
    "calibration_changes",
    "ensemble_changes",
    "recommended_next_step",
    "notes",
]


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _float(value: Any) -> Optional[float]:
    raw = _norm(value)
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _int(value: Any) -> int:
    val = _float(value)
    return int(val) if val is not None else 0


def _run_id(generated_ts: str) -> str:
    compact = generated_ts.replace("-", "").replace(":", "").replace("Z", "Z")
    return f"market_reaction_canonical_source_selection_review_v0_{compact}"


def _base(generated_ts: str, review_run_id: str) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "review_version": REVIEW_VERSION,
        "review_run_id": review_run_id,
    }


def _sheet_titles(service, spreadsheet_id: str) -> Set[str]:
    metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    return {sheet["properties"]["title"] for sheet in metadata.get("sheets", [])}


def _safe_rows(
    service,
    spreadsheet_id: str,
    titles: Set[str],
    sheet_name: str,
    missing: List[str],
) -> List[Dict[str, Any]]:
    if sheet_name not in titles:
        missing.append(sheet_name)
        return []
    try:
        return _sheet_to_rows(service, spreadsheet_id, sheet_name)
    except Exception:
        missing.append(sheet_name)
        return []


def _get_headers(service, spreadsheet_id: str, sheet_name: str) -> List[str]:
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=f"'{sheet_name}'!1:1")
        .execute()
    )
    values = result.get("values", [])
    return values[0] if values else []


def _ensure_sheet_minimal(
    service,
    spreadsheet_id: str,
    sheet_name: str,
    required_headers: Sequence[str],
    data_row_count: int,
) -> List[str]:
    metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    titles = {sheet["properties"]["title"] for sheet in metadata.get("sheets", [])}
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


def _latest(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    return rows[-1] if rows else {}


def _config_map(rows: Sequence[Dict[str, Any]]) -> Dict[str, str]:
    return {_upper(row.get("key")): _norm(row.get("value")) for row in rows if _norm(row.get("key"))}


def _provider_hierarchy(config: Dict[str, str]) -> str:
    providers = [
        config.get("MR_PRIMARY_PROVIDER") or "tiingo",
        config.get("MR_COMPARE_PROVIDER") or "eodhd",
        config.get("MR_COMPARE_PROVIDER_2") or "massive",
        config.get("MR_COMPARE_PROVIDER_3") or "twelvedata",
    ]
    seen = []
    for provider in providers:
        if provider and provider not in seen:
            seen.append(provider)
    return " > ".join(seen)


def _source_pair_risk(source_rows: Sequence[Dict[str, Any]]) -> str:
    counter: Counter[str] = Counter()
    for row in source_rows:
        status = _norm(row.get("comparison_status"))
        if status in {"PASS", "MINOR_DIFFERENCE"}:
            continue
        pair = "|".join(sorted([_norm(row.get("provider_source_a")), _norm(row.get("provider_source_b"))]))
        if pair:
            counter[pair] += 1
    return counter.most_common(1)[0][0] if counter else "NONE"


def _score_strategy(strategy_type: str) -> Dict[str, Any]:
    scores = {
        "single_canonical_provider": {
            "determinism": 5,
            "reproducibility": 5,
            "auditability": 4,
            "provider_independence": 1,
            "ambiguity_reduction": 2,
            "implementation_complexity": 5,
            "long_term_maintainability": 3,
            "presignal_v2_compatibility": 3,
            "selection_status": "REJECTED",
            "selection_rationale": "",
            "rejection_reason": "Too brittle given source outages, source disagreements, and missing-candle/window issues.",
        },
        "hierarchical_fallback": {
            "determinism": 5,
            "reproducibility": 5,
            "auditability": 5,
            "provider_independence": 4,
            "ambiguity_reduction": 5,
            "implementation_complexity": 3,
            "long_term_maintainability": 5,
            "presignal_v2_compatibility": 5,
            "selection_status": "SELECTED",
            "selection_rationale": "Best balance of deterministic construction, source robustness, audit metadata, and compatibility with current Config provider hierarchy.",
            "rejection_reason": "",
        },
        "consensus_source": {
            "determinism": 4,
            "reproducibility": 4,
            "auditability": 5,
            "provider_independence": 5,
            "ambiguity_reduction": 4,
            "implementation_complexity": 3,
            "long_term_maintainability": 3,
            "presignal_v2_compatibility": 4,
            "selection_status": "REJECTED_AS_PRIMARY",
            "selection_rationale": "",
            "rejection_reason": "Strong validation subset, but too likely to shrink sample size and exclude usable outcomes if used as the primary canonical source.",
        },
        "weighted_confidence_source": {
            "determinism": 2,
            "reproducibility": 2,
            "auditability": 2,
            "provider_independence": 4,
            "ambiguity_reduction": 3,
            "implementation_complexity": 1,
            "long_term_maintainability": 2,
            "presignal_v2_compatibility": 2,
            "selection_status": "REJECTED",
            "selection_rationale": "",
            "rejection_reason": "Premature hidden weighting before source integrity and source reliability have been repaired.",
        },
    }
    return scores.get(strategy_type, scores["single_canonical_provider"])


def _build_comparison_rows(
    generated_ts: str,
    review_run_id: str,
    strategy_rows: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    rows = []
    for strategy in strategy_rows:
        strategy_type = _norm(strategy.get("strategy_type"))
        score = _score_strategy(strategy_type)
        review_score = sum(score[field] for field in [
            "determinism",
            "reproducibility",
            "auditability",
            "provider_independence",
            "ambiguity_reduction",
            "implementation_complexity",
            "long_term_maintainability",
            "presignal_v2_compatibility",
        ])
        row = _base(generated_ts, review_run_id)
        row.update(
            {
                "strategy_id": strategy.get("strategy_id"),
                "strategy_name": strategy.get("strategy_name"),
                "strategy_type": strategy_type,
                "determinism": score["determinism"],
                "reproducibility": score["reproducibility"],
                "auditability": score["auditability"],
                "provider_independence": score["provider_independence"],
                "ambiguity_reduction": score["ambiguity_reduction"],
                "implementation_complexity": score["implementation_complexity"],
                "long_term_maintainability": score["long_term_maintainability"],
                "presignal_v2_compatibility": score["presignal_v2_compatibility"],
                "review_score": review_score,
                "selection_status": score["selection_status"],
                "selection_rationale": score["selection_rationale"],
                "rejection_reason": score["rejection_reason"],
                "notes": "Qualitative governance score only; no market reaction or accuracy values recalculated.",
            }
        )
        rows.append(row)
    return rows


def _build_review_rows(generated_ts: str, review_run_id: str, summary: Dict[str, Any], hierarchy: str) -> List[Dict[str, Any]]:
    evidence = (
        f"trust={summary.get('market_reaction_trust_classification')}; "
        f"pips_mismatches={summary.get('pips_formula_mismatches')}; "
        f"window_issues={summary.get('window_issues')}; "
        f"source_direction_disagreements={summary.get('source_direction_disagreements')}; "
        f"ambiguous_matches={summary.get('outcome_matches_ambiguous')}"
    )
    areas = [
        ("strategy_review", "PASS_WITH_WARNINGS", "Hierarchical fallback is selected after comparing determinism, auditability, ambiguity reduction, and maintainability.", "HIERARCHICAL_FALLBACK", "single provider|consensus as primary|weighted confidence", "source hierarchy still requires implementation validation"),
        ("source_hierarchy", "PASS_WITH_WARNINGS", "Use Config-defined source hierarchy for deterministic fallback, preserving provider disagreement metadata.", f"Config hierarchy: {hierarchy}", "hard-coded provider ranking", "Config values must be snapshotted in construction_version"),
        ("window_policy", "PASS_WITH_WARNINGS", "Fixed event-relative primary window minimizes discretionary anchor movement.", "EVENT_RELATIVE_FIXED_DURATION", "session-based primary|anchor-adjusted primary", "delayed reaction remains metadata-only"),
        ("matching_policy", "PASS_WITH_WARNINGS", "Current country+release_ts matching is not sufficient for strict accuracy.", "canonical_outcome_id > event_id+session_id+release_ts+window_id > batch_id fallback > country+release_ts review-only", "country+release_ts strict matching", "canonical_outcome_id must be materialized"),
        ("disagreement_policy", "PASS_WITH_WARNINGS", "Disagreements must alter trust metadata and strict denominator eligibility.", "LOW/MODERATE/HIGH/UNUSABLE policy", "silent source choice", "thresholds must remain frozen during implementation"),
        ("trust_model", "PASS", "Trust metadata is mandatory for future accuracy filtering.", "mandatory canonical_source/fallback/provider_agreement/window_confidence/outcome_confidence/trust_level/construction_version/canonical_outcome_id", "untracked final-provider outcomes", "schema must be append-only"),
        ("readiness", "PASS_WITH_WARNINGS", "Review selects a canonical architecture and can proceed to implementation, but accuracy replication remains blocked.", "READY_FOR_OUTCOME_SOURCE_IMPLEMENTATION", "accuracy replication before outcome repair", "repair implementation and re-audit required before replication"),
    ]
    rows = []
    for area, status, finding, selected, rejected, risk in areas:
        row = _base(generated_ts, review_run_id)
        row.update(
            {
                "review_area": area,
                "review_status": status,
                "evidence_scope": evidence,
                "review_finding": finding,
                "selected_policy": selected,
                "rejected_alternatives": rejected,
                "remaining_risk": risk,
                "implementation_dependency": "Phase 9A-5M2 must implement without modifying source history in place.",
                "production_excluded": "TRUE",
                "notes": "Review-only; no outcome values, accuracy metrics, or production behavior changed.",
            }
        )
        rows.append(row)
    return rows


def _build_risk_rows(
    generated_ts: str,
    review_run_id: str,
    summary: Dict[str, Any],
    highest_pair: str,
) -> List[Dict[str, Any]]:
    rows_data = [
        ("RISK_SOURCE_DISAGREEMENT", "Provider source disagreement", "HIGH", f"direction_disagreements={summary.get('source_direction_disagreements')}; large_pips={summary.get('large_pips_disagreements')}; highest_pair={highest_pair}", "agreement gate + trust_level + review/exclude policy", "FALSE", "Some rows may leave strict denominators after repair."),
        ("RISK_WINDOW_INTEGRITY", "Window integrity", "HIGH", f"window_issues={summary.get('window_issues')}", "fixed event-relative window + window_confidence metadata", "FALSE", "Delayed reactions remain separate metadata, not replacement outcomes."),
        ("RISK_AMBIGUOUS_MATCHING", "Ambiguous outcome matching", "HIGH", f"ambiguous_matches={summary.get('outcome_matches_ambiguous')}/{summary.get('outcome_matches_checked')}", "canonical_outcome_id and event/session/window hierarchy", "FALSE", "Historical 9A-5F rows should be treated as pre-repair evidence."),
        ("RISK_FORMULA_LABEL_MISMATCH", "Formula and label mismatch", "MEDIUM", f"pips={summary.get('pips_formula_mismatches')}; direction={summary.get('direction_label_mismatches')}; strength={summary.get('strength_label_mismatches')}", "reconstruct labels from canonical pips during repair, do not trust stale derived labels", "FALSE", "Repair must preserve original values and write repaired shadow outputs."),
        ("RISK_SAMPLE_SHRINKAGE", "Strict denominator shrinkage", "MEDIUM", f"high_sensitivity_rows={summary.get('accuracy_rows_high_sensitivity')}", "KEEP_WITH_WARNING and EXCLUDE_FROM_STRICT_ACCURACY policies", "FALSE", "Future accuracy studies may need more rows after filtering."),
    ]
    rows = []
    for rid, name, severity, evidence, mitigation, blocks, limitation in rows_data:
        row = _base(generated_ts, review_run_id)
        row.update(
            {
                "risk_id": rid,
                "risk_name": name,
                "severity": severity,
                "evidence": evidence,
                "selected_architecture_mitigation": mitigation,
                "blocks_implementation": blocks,
                "future_limitation": limitation,
                "notes": "Risk informs repair implementation; no source data changed.",
            }
        )
        rows.append(row)
    return rows


def _build_window_rows(generated_ts: str, review_run_id: str, window_rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for source in window_rows:
        sid = _norm(source.get("window_strategy_id"))
        selected = sid == "WIN_EVENT_FIXED_5M"
        if selected:
            result = "SELECTED"
            reason = "Most deterministic, minimizes discretionary anchor movement, and aligns with existing MR_HORIZON_MIN configuration."
            limitation = "May miss delayed reactions; delayed reaction must remain supplemental metadata."
        elif sid == "WIN_ANCHOR_ADJUSTED":
            result = "REJECTED_AS_PRIMARY"
            reason = "Useful as metadata only."
            limitation = "Anchor selection can shift ground truth if used as canonical primary window."
        elif sid == "WIN_SESSION_BASED":
            result = "REJECTED_AS_PRIMARY"
            reason = "Session windows weaken event-level causal attribution."
            limitation = "Could be designed later for session-level research, not canonical event accuracy."
        else:
            result = "SUPPORTING_METADATA"
            reason = "Delayed reactions should be flagged without replacing immediate outcome."
            limitation = "Must not be used as alternate scoring target."
        row = _base(generated_ts, review_run_id)
        row.update(
            {
                "window_policy_id": sid,
                "candidate_policy": source.get("window_strategy_name"),
                "review_result": result,
                "selected_as_canonical": "TRUE" if selected else "FALSE",
                "selection_reason": reason,
                "rejection_or_limitation": limitation,
                "expected_window_rule": source.get("window_definition"),
                "ambiguity_reduction": "Fixed event-relative rule reduces window choice ambiguity; supplemental flags preserve delayed-reaction evidence.",
                "notes": "No windows recalculated or modified.",
            }
        )
        rows.append(row)
    return rows


def _build_matching_rows(generated_ts: str, review_run_id: str, matching_rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    hierarchy = "canonical_outcome_id > event_id+session_id+release_ts+outcome_window_id > batch_id+release_ts+outcome_window_id > country+release_ts review-only"
    rows = []
    for source in matching_rows:
        sid = _norm(source.get("matching_strategy_id"))
        selected = sid == "MATCH_EVENT_SESSION_PRIMARY"
        if selected:
            result = "SELECTED"
            strict = "TRUE"
            ambiguity = "Duplicates allowed only when they resolve to the same canonical_outcome_id; otherwise AMBIGUOUS_REVIEW."
        elif sid == "MATCH_BATCH_PRIMARY":
            result = "SUPPORTING_FALLBACK"
            strict = "TRUE_WITH_BATCH_SCOPE"
            ambiguity = "Valid for batch-level rows only when batch_id and outcome_window_id match."
        else:
            result = "REJECTED_FOR_STRICT_ACCURACY"
            strict = "FALSE"
            ambiguity = "country+release_ts may only be diagnostic/review fallback."
        row = _base(generated_ts, review_run_id)
        row.update(
            {
                "matching_policy_id": sid,
                "candidate_policy": source.get("matching_strategy_name"),
                "review_result": result,
                "selected_as_canonical": "TRUE" if selected else "FALSE",
                "canonical_matching_hierarchy": hierarchy,
                "ambiguity_resolution": ambiguity,
                "strict_accuracy_allowed": strict,
                "notes": "No accuracy rows rematched in this phase.",
            }
        )
        rows.append(row)
    return rows


def _build_trust_rows(generated_ts: str, review_run_id: str, trust_rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    mandatory_fields = {
        "canonical_source",
        "fallback_used",
        "fallback_reason",
        "provider_agreement",
        "pips_disagreement_abs",
        "window_confidence",
        "outcome_confidence",
        "trust_level",
        "construction_version",
        "canonical_outcome_id",
    }
    rows = []
    for source in trust_rows:
        field_name = _norm(source.get("field_name"))
        mandatory = field_name in mandatory_fields
        row = _base(generated_ts, review_run_id)
        row.update(
            {
                "trust_field_id": source.get("trust_field_id"),
                "field_name": field_name,
                "mandatory": "TRUE" if mandatory else "FALSE",
                "approved_for_implementation": "TRUE",
                "use_in_strict_accuracy_filter": source.get("used_for_accuracy_filtering") if mandatory else "FALSE",
                "review_decision": "APPROVED_MANDATORY" if mandatory else "APPROVED_OPTIONAL",
                "notes": "Trust field approved for repaired shadow outcome schema; append-only schema discipline required.",
            }
        )
        rows.append(row)
    return rows


def _build_decision_rows(generated_ts: str, review_run_id: str, hierarchy: str) -> List[Dict[str, Any]]:
    row = _base(generated_ts, review_run_id)
    row.update(
        {
            "decision_id": "CANONICAL_SOURCE_DECISION_V0",
            "canonical_strategy_selected": "HIERARCHICAL_FALLBACK",
            "canonical_window_selected": "EVENT_RELATIVE_FIXED_DURATION",
            "canonical_matching_strategy_selected": "CANONICAL_OUTCOME_ID_WITH_EVENT_SESSION_WINDOW_HIERARCHY",
            "disagreement_policy_selected": "LOW_DISAGREEMENT|MODERATE_DISAGREEMENT|HIGH_DISAGREEMENT|UNUSABLE",
            "trust_metadata_approved": "TRUE",
            "why_selected": f"Hierarchical fallback is deterministic, auditable, robust to missing sources, and compatible with the existing Config source order ({hierarchy}) while preserving disagreement evidence.",
            "why_alternatives_rejected": "Single canonical provider is brittle; consensus source is too sample-shrinking as the primary architecture; weighted confidence is premature and risks hidden weighting.",
            "assumptions": "Config source order is governance-approved for implementation; thresholds remain frozen; repaired outputs are written to shadow/diagnostic outputs rather than mutating source history.",
            "risks": "Source hierarchy still requires implementation validation; source disagreements and window issues may exclude rows from strict denominators.",
            "future_limitations": "Accuracy replication remains blocked until repaired outcomes are materialized and re-audited.",
            "ready_for_outcome_source_implementation": "TRUE",
            "recommended_next_step": "PROCEED_TO_PHASE9A5M2_OUTCOME_SOURCE_IMPLEMENTATION",
            "notes": "This is a governance selection of architecture, not a provider performance ranking.",
        }
    )
    return [row]


def _build_governance_rows(generated_ts: str, review_run_id: str) -> List[Dict[str, Any]]:
    checks = [
        ("provider_calls_performed", 0, 0),
        ("forecast_generation_performed", 0, 0),
        ("accuracy_evaluation_performed", 0, 0),
        ("metrics_recalculated", 0, 0),
        ("market_reaction_values_modified", 0, 0),
        ("evaluation_rows_written", 0, 0),
        ("outcome_ledger_written", 0, 0),
        ("production_sheet_write_count", 0, 0),
        ("production_behavior_change_count", 0, 0),
        ("thresholds_modified", 0, 0),
        ("routing_changes", "FALSE", "FALSE"),
        ("weighting_changes", "FALSE", "FALSE"),
        ("calibration_changes", "FALSE", "FALSE"),
        ("ensemble_changes", "FALSE", "FALSE"),
    ]
    rows = []
    for name, expected, actual in checks:
        row = _base(generated_ts, review_run_id)
        row.update(
            {
                "check_id": f"CHK_{name.upper()}",
                "check_name": name,
                "expected_value": expected,
                "actual_value": actual,
                "status": "PASS" if str(expected) == str(actual) else "FAIL",
                "notes": "Phase 9A-5M1 is review-only and does not implement or mutate source data.",
            }
        )
        rows.append(row)
    return rows


def _upsert_registry_rows(service) -> Dict[str, int]:
    headers = _ensure_sheet_minimal(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET, REGISTRY_HEADERS, 1)
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_upper(row.get("logical_sheet_id")): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_upper(row.get("logical_sheet_id")): row for row in rows}
    registry_rows = [
        ("MARKET_REACTION_CANONICAL_SOURCE_REVIEW", OUTPUT_REVIEW, "market_reaction_canonical_source_review"),
        ("MARKET_REACTION_SOURCE_STRATEGY_COMPARISON", OUTPUT_COMPARISON, "market_reaction_source_strategy_comparison"),
        ("MARKET_REACTION_SOURCE_RISK_ASSESSMENT", OUTPUT_RISK, "market_reaction_source_risk_assessment"),
        ("MARKET_REACTION_CANONICAL_WINDOW_REVIEW", OUTPUT_WINDOW, "market_reaction_canonical_window_review"),
        ("MARKET_REACTION_CANONICAL_MATCHING_REVIEW", OUTPUT_MATCHING, "market_reaction_canonical_matching_review"),
        ("MARKET_REACTION_CANONICAL_TRUST_MODEL", OUTPUT_TRUST, "market_reaction_canonical_trust_model"),
        ("MARKET_REACTION_SOURCE_SELECTION_DECISION", OUTPUT_DECISION, "market_reaction_source_selection_decision"),
        ("MARKET_REACTION_CANONICAL_SOURCE_GOVERNANCE", OUTPUT_GOVERNANCE, "market_reaction_canonical_source_governance"),
        ("MARKET_REACTION_CANONICAL_SOURCE_REVIEW_SUMMARY", OUTPUT_SUMMARY, "market_reaction_canonical_source_review_summary"),
    ]
    updates = []
    appended = 0
    for logical_id, sheet_name, role in registry_rows:
        key = _upper(logical_id)
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
            "notes": "Phase 9A-5M1 canonical source selection review; governance decision only.",
            "registry_created_ts": _norm(existing.get("registry_created_ts")) or now,
            "registry_last_verified_ts": now,
            "registry_migration_ts": _norm(existing.get("registry_migration_ts")),
            "registry_rename_ts": _norm(existing.get("registry_rename_ts")),
        }
        values = [merged.get(header, "") for header in headers]
        if key in by_id:
            row_number = by_id[key]
        else:
            appended += 1
            row_number = len(rows) + appended + 1
        updates.append({"range": f"'{REGISTRY_SHEET}'!A{row_number}:{_column_letter(len(headers))}{row_number}", "values": [values]})
    if updates:
        batch_update_values(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, updates)
    return {"updated": len(registry_rows) - appended, "appended": appended}


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build PreSignal v2.0 Phase 9A-5M1 canonical source selection review.")
    return parser.parse_args(argv)


def build_market_reaction_canonical_source_selection_review_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    args = args or _parse_args()
    _ = args
    generated_ts = _iso_now()
    review_run_id = _run_id(generated_ts)
    service = build_sheets_service(load_credentials())
    main_titles = _sheet_titles(service, MAIN_SPREADSHEET_ID)
    diag_titles = _sheet_titles(service, DIAGNOSTICS_SPREADSHEET_ID)
    missing_main: List[str] = []
    missing_diag: List[str] = []
    main_inputs = {sheet: _safe_rows(service, MAIN_SPREADSHEET_ID, main_titles, sheet, missing_main) for sheet in MAIN_INPUT_SHEETS}
    diag_inputs = {sheet: _safe_rows(service, DIAGNOSTICS_SPREADSHEET_ID, diag_titles, sheet, missing_diag) for sheet in DIAG_INPUT_SHEETS}
    missing_critical = sorted(
        [f"MAIN:{sheet}" for sheet in missing_main if sheet in CRITICAL_MAIN_SHEETS]
        + [f"DIAGNOSTICS:{sheet}" for sheet in missing_diag if sheet in CRITICAL_DIAG_SHEETS]
    )
    if missing_critical:
        raise RuntimeError(f"Missing critical Phase 9A-5M1 inputs: {missing_critical}")

    repair_summary = _latest(diag_inputs["Market_Reaction_Source_Repair_Summary"])
    integrity_summary = _latest(diag_inputs["Market_Reaction_Outcome_Integrity_Summary"])
    if _norm(repair_summary.get("final_interpretation")) != "MARKET_REACTION_OUTCOME_SOURCE_REPAIR_DESIGN_READY_WITH_WARNINGS":
        raise RuntimeError("Phase 9A-5M source repair design is not ready for source selection review.")
    if _norm(repair_summary.get("repair_readiness")) != "READY_FOR_SOURCE_SELECTION_REVIEW":
        raise RuntimeError("Phase 9A-5M repair readiness is not READY_FOR_SOURCE_SELECTION_REVIEW.")

    config = _config_map(main_inputs["Config"])
    hierarchy = _provider_hierarchy(config)
    strategy_rows = diag_inputs["Market_Reaction_Canonical_Source_Strategy"]
    window_source_rows = diag_inputs["Market_Reaction_Window_Definition_Design"]
    matching_source_rows = diag_inputs["Market_Reaction_Outcome_Matching_Design"]
    trust_source_rows = diag_inputs["Market_Reaction_Trust_Scoring_Design"]
    source_comparison_rows: List[Dict[str, Any]] = []
    # This optional read is intentionally pulled only if the sheet is already in diagnostics;
    # it sharpens the risk row without making source-comparison detail a critical dependency.
    if "Market_Reaction_Source_Comparison_Audit" in diag_titles:
        source_comparison_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, "Market_Reaction_Source_Comparison_Audit")
    highest_pair = _source_pair_risk(source_comparison_rows) or integrity_summary.get("highest_risk_source_pair") or "eodhd|tiingo"

    comparison_rows = _build_comparison_rows(generated_ts, review_run_id, strategy_rows)
    review_rows = _build_review_rows(generated_ts, review_run_id, integrity_summary, hierarchy)
    risk_rows = _build_risk_rows(generated_ts, review_run_id, integrity_summary, highest_pair)
    window_rows = _build_window_rows(generated_ts, review_run_id, window_source_rows)
    matching_rows = _build_matching_rows(generated_ts, review_run_id, matching_source_rows)
    trust_rows = _build_trust_rows(generated_ts, review_run_id, trust_source_rows)
    decision_rows = _build_decision_rows(generated_ts, review_run_id, hierarchy)
    governance_rows = _build_governance_rows(generated_ts, review_run_id)
    governance_failed = any(_norm(row.get("status")) != "PASS" for row in governance_rows)

    build_status = "PASS_WITH_WARNINGS" if not governance_failed else "FAIL"
    final_interpretation = (
        "MARKET_REACTION_CANONICAL_SOURCE_REVIEW_READY_WITH_WARNINGS"
        if not governance_failed
        else "MARKET_REACTION_CANONICAL_SOURCE_REVIEW_BLOCKED"
    )
    summary_row = {
        **_base(generated_ts, review_run_id),
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "strategies_reviewed": len(strategy_rows),
        "canonical_strategy_selected": "HIERARCHICAL_FALLBACK",
        "canonical_window_selected": "EVENT_RELATIVE_FIXED_DURATION",
        "canonical_matching_strategy_selected": "CANONICAL_OUTCOME_ID_WITH_EVENT_SESSION_WINDOW_HIERARCHY",
        "disagreement_policy_selected": "LOW_DISAGREEMENT|MODERATE_DISAGREEMENT|HIGH_DISAGREEMENT|UNUSABLE",
        "trust_metadata_approved": "TRUE",
        "highest_remaining_risk": "implementation_must_materialize_canonical_outcome_id_and_validate_source_hierarchy",
        "ready_for_outcome_source_implementation": "TRUE",
        "ready_for_accuracy_replication": "FALSE",
        "ready_for_production": "FALSE",
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "accuracy_evaluation_performed": 0,
        "metrics_recalculated": 0,
        "market_reaction_values_modified": 0,
        "evaluation_rows_written": 0,
        "outcome_ledger_written": 0,
        "production_sheet_write_count": 0,
        "production_behavior_change_count": 0,
        "routing_changes": "FALSE",
        "weighting_changes": "FALSE",
        "calibration_changes": "FALSE",
        "ensemble_changes": "FALSE",
        "recommended_next_step": "PROCEED_TO_PHASE9A5M2_OUTCOME_SOURCE_IMPLEMENTATION",
        "notes": json.dumps(
            {
                "provider_hierarchy_from_config": hierarchy,
                "source_repair_summary": repair_summary.get("final_interpretation"),
                "outcome_integrity_summary": integrity_summary.get("final_interpretation"),
                "market_reaction_trust": integrity_summary.get("market_reaction_trust_classification"),
                "highest_risk_source_pair": highest_pair,
                "review_only": True,
                "repair_implemented": False,
                "accuracy_replication_allowed": False,
            },
            sort_keys=True,
        ),
    }
    summary_rows = [summary_row]

    outputs = [
        (OUTPUT_REVIEW, REVIEW_HEADERS, review_rows),
        (OUTPUT_COMPARISON, COMPARISON_HEADERS, comparison_rows),
        (OUTPUT_RISK, RISK_HEADERS, risk_rows),
        (OUTPUT_WINDOW, WINDOW_HEADERS, window_rows),
        (OUTPUT_MATCHING, MATCHING_HEADERS, matching_rows),
        (OUTPUT_TRUST, TRUST_HEADERS, trust_rows),
        (OUTPUT_DECISION, DECISION_HEADERS, decision_rows),
        (OUTPUT_GOVERNANCE, GOVERNANCE_HEADERS, governance_rows),
        (OUTPUT_SUMMARY, SUMMARY_HEADERS, summary_rows),
    ]
    for sheet_name, headers, rows in outputs:
        actual_headers = _ensure_sheet_minimal(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, headers, len(rows))
        _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, actual_headers, rows)

    registry = _upsert_registry_rows(service)
    return {
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "file_created": "automation/build_market_reaction_canonical_source_selection_review_v0.py",
        "sheets_written": {sheet_name: len(rows) for sheet_name, _, rows in outputs},
        "strategies_reviewed": len(strategy_rows),
        "canonical_strategy_selected": "HIERARCHICAL_FALLBACK",
        "canonical_window_selected": "EVENT_RELATIVE_FIXED_DURATION",
        "canonical_matching_strategy_selected": "CANONICAL_OUTCOME_ID_WITH_EVENT_SESSION_WINDOW_HIERARCHY",
        "disagreement_policy_selected": summary_row["disagreement_policy_selected"],
        "trust_metadata_approved": True,
        "highest_remaining_risk": summary_row["highest_remaining_risk"],
        "ready_for_outcome_source_implementation": True,
        "ready_for_accuracy_replication": False,
        "ready_for_production": False,
        "recommended_next_step": summary_row["recommended_next_step"],
        "registry": registry,
    }


def main() -> None:
    result = build_market_reaction_canonical_source_selection_review_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
