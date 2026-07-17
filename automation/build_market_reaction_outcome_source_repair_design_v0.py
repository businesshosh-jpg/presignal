import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

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
    _ensure_sheet,
    _norm,
    _sheet_to_rows,
    _write_rows,
)
from automation.build_session_information_requests_v0 import _iso_now, _truncate_text
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials


SCHEMA_VERSION = "presignal_v2_market_reaction_outcome_source_repair_design_0.1"
DESIGN_VERSION = "market_reaction_outcome_source_repair_design_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-5M"
REGISTRY_CATEGORY = "PRESIGNAL_V2_MARKET_REACTION_OUTCOME_SOURCE_REPAIR_DESIGN"
REGISTRY_OWNER_MODULE = "market_state"

MAIN_INPUT_SHEETS = [
    "MR_ProviderRuns",
    "Evaluation_Rows",
    "Outcome_Ledger",
    "Evaluation_Summary",
    "Evaluation_BatchCompare",
    "Evaluation_Scenario",
    "Config",
    "Event",
]

DIAG_INPUT_SHEETS = [
    "Market_Reaction_Outcome_Integrity_Audit",
    "Market_Reaction_Pips_Formula_Audit",
    "Market_Reaction_Direction_Label_Audit",
    "Market_Reaction_Strength_Label_Audit",
    "Market_Reaction_Window_Audit",
    "Market_Reaction_Source_Comparison_Audit",
    "Market_Reaction_Outcome_Match_Audit",
    "Market_Reaction_Accuracy_Impact_Audit",
    "Market_Reaction_Outcome_Integrity_Summary",
]

CRITICAL_MAIN_SHEETS = {"MR_ProviderRuns", "Evaluation_Rows", "Outcome_Ledger", "Config"}
CRITICAL_DIAG_SHEETS = {
    "Market_Reaction_Outcome_Integrity_Audit",
    "Market_Reaction_Source_Comparison_Audit",
    "Market_Reaction_Outcome_Match_Audit",
    "Market_Reaction_Accuracy_Impact_Audit",
    "Market_Reaction_Outcome_Integrity_Summary",
}

OUTPUT_DESIGN = "Market_Reaction_Source_Repair_Design"
OUTPUT_SOURCE = "Market_Reaction_Canonical_Source_Strategy"
OUTPUT_WINDOW = "Market_Reaction_Window_Definition_Design"
OUTPUT_MATCHING = "Market_Reaction_Outcome_Matching_Design"
OUTPUT_DISAGREEMENT = "Market_Reaction_Disagreement_Handling"
OUTPUT_TRUST = "Market_Reaction_Trust_Scoring_Design"
OUTPUT_READINESS = "Market_Reaction_Repair_Readiness"
OUTPUT_GOVERNANCE = "Market_Reaction_Source_Repair_Governance"
OUTPUT_SUMMARY = "Market_Reaction_Source_Repair_Summary"

DESIGN_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "design_area",
    "design_status",
    "source_evidence",
    "problem_statement",
    "design_objective",
    "proposed_design",
    "decision_status",
    "blocking_dependency",
    "recommended_next_action",
    "production_excluded",
    "notes",
]

SOURCE_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "strategy_id",
    "strategy_name",
    "strategy_type",
    "candidate_source_hierarchy",
    "advantages",
    "disadvantages",
    "handles_source_disagreement",
    "handles_missing_source",
    "handles_large_pips_difference",
    "trust_metadata_required",
    "evidence_support",
    "design_status",
    "recommended_for_review",
    "final_provider_decided",
    "notes",
]

WINDOW_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "window_strategy_id",
    "window_strategy_name",
    "window_type",
    "window_definition",
    "expected_horizon_minutes",
    "overlap_handling",
    "missing_candle_handling",
    "delayed_reaction_handling",
    "confidence_metadata",
    "advantages",
    "risks",
    "recommended_status",
    "notes",
]

MATCHING_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "matching_strategy_id",
    "matching_strategy_name",
    "key_hierarchy",
    "required_keys",
    "fallback_keys",
    "duplicate_handling",
    "batch_handling",
    "session_handling",
    "ambiguity_resolution",
    "evidence_support",
    "recommended_status",
    "notes",
]

DISAGREEMENT_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "disagreement_rule_id",
    "disagreement_class",
    "trigger_condition",
    "future_accuracy_handling",
    "canonical_outcome_allowed",
    "manual_review_required",
    "trust_level_effect",
    "affected_metrics",
    "notes",
]

TRUST_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "trust_field_id",
    "field_name",
    "field_purpose",
    "allowed_values_or_type",
    "required",
    "derivation_rule",
    "used_for_accuracy_filtering",
    "notes",
]

READINESS_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "readiness_check_id",
    "readiness_area",
    "check_description",
    "check_status",
    "blocking",
    "evidence_value",
    "required_before_implementation",
    "notes",
]

GOVERNANCE_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
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
    "design_version",
    "design_run_id",
    "build_status",
    "final_interpretation",
    "canonical_source_strategies_designed",
    "window_strategies_designed",
    "outcome_matching_strategies_designed",
    "disagreement_strategies_designed",
    "trust_metadata_fields_designed",
    "repair_readiness",
    "highest_remaining_risk",
    "recommended_canonical_architecture",
    "provider_calls_performed",
    "forecast_generation_performed",
    "accuracy_evaluation_performed",
    "accuracy_results_modified",
    "market_reaction_values_modified",
    "evaluation_rows_written",
    "outcome_ledger_written",
    "production_sheet_write_count",
    "production_behavior_change_count",
    "routing_changes",
    "weighting_changes",
    "calibration_changes",
    "ensemble_changes",
    "ready_for_outcome_source_repair_implementation",
    "ready_for_canonical_source_selection_review",
    "ready_for_accuracy_replication",
    "ready_for_production",
    "recommended_next_step",
    "notes",
]


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _bool(value: Any) -> bool:
    return _upper(value) in {"TRUE", "YES", "1", "Y"}


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
    return f"market_reaction_outcome_source_repair_design_v0_{compact}"


def _base(generated_ts: str, design_run_id: str) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "design_version": DESIGN_VERSION,
        "design_run_id": design_run_id,
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


def _issue_value(summary: Dict[str, Any], key: str) -> int:
    return _int(summary.get(key))


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


def _build_design_rows(generated_ts: str, design_run_id: str, summary: Dict[str, Any]) -> List[Dict[str, Any]]:
    evidence = (
        f"pips_mismatch={summary.get('pips_formula_mismatches')}; "
        f"window_issues={summary.get('window_issues')}; "
        f"source_direction_disagreements={summary.get('source_direction_disagreements')}; "
        f"ambiguous_matches={summary.get('outcome_matches_ambiguous')}; "
        f"high_sensitivity={summary.get('accuracy_rows_high_sensitivity')}"
    )
    rows_data = [
        (
            "canonical_source_architecture",
            "PASS_WITH_WARNINGS",
            "Market Reaction source disagreement means current final-provider output cannot be treated as definitive.",
            "Define a deterministic source hierarchy with explicit disagreement metadata.",
            "Candidate architecture: hierarchical canonical source with agreement gate and trust scoring; final provider not chosen in this phase.",
            "DESIGNED_PENDING_SOURCE_SELECTION",
            "canonical provider order must be reviewed before implementation",
            "PROCEED_TO_PHASE9A5M1_CANONICAL_SOURCE_SELECTION_REVIEW",
        ),
        (
            "window_definition",
            "PASS_WITH_WARNINGS",
            "Window issues indicate some outcomes may not use the intended reaction horizon.",
            "Freeze event-relative window construction and missing-candle handling.",
            "Use event-relative fixed horizon from Config with explicit start/end, candle count, and window_confidence metadata.",
            "DESIGNED_PENDING_IMPLEMENTATION",
            "window repair implementation must preserve existing source rows read-only",
            "PROCEED_TO_PHASE9A5M1_CANONICAL_SOURCE_SELECTION_REVIEW",
        ),
        (
            "outcome_matching",
            "PASS_WITH_WARNINGS",
            "145/145 controlled accuracy rows matched ambiguously by country + release_ts.",
            "Require deterministic keys that distinguish event/session/batch and prevent duplicate provider/prediction matches.",
            "Preferred hierarchy: event_id + session_id + release_ts, then batch_id, then country/release_ts only as review fallback.",
            "DESIGNED_PENDING_IMPLEMENTATION",
            "future repaired outcome ledger must materialize canonical outcome keys",
            "PROCEED_TO_PHASE9A5M1_CANONICAL_SOURCE_SELECTION_REVIEW",
        ),
        (
            "provider_disagreement",
            "PASS_WITH_WARNINGS",
            "Source direction, strength, and pips disagreements can flip future accuracy labels.",
            "Classify disagreement rather than silently choosing a source.",
            "Define agreement, minor disagreement, major disagreement, and unusable classes with accuracy handling rules.",
            "DESIGNED_PENDING_IMPLEMENTATION",
            "canonical source selection review should decide tolerance thresholds",
            "PROCEED_TO_PHASE9A5M1_CANONICAL_SOURCE_SELECTION_REVIEW",
        ),
        (
            "trust_metadata",
            "PASS",
            "Future accuracy evaluation needs ground-truth trust metadata on each outcome row.",
            "Make trust/audit metadata first-class fields in repaired outcome construction.",
            "Add canonical_source, fallback_used, provider_agreement, window_confidence, outcome_confidence, trust_level, construction_version.",
            "DESIGNED_PENDING_IMPLEMENTATION",
            "repaired ledger schema required",
            "PROCEED_TO_PHASE9A5M1_CANONICAL_SOURCE_SELECTION_REVIEW",
        ),
        (
            "accuracy_impact_policy",
            "PASS_WITH_WARNINGS",
            "56/145 evaluated rows were high sensitivity to outcome construction uncertainty.",
            "Prevent unstable outcomes from silently entering strict accuracy denominators.",
            "Future evaluation handling: keep, keep_with_warning, exclude_from_strict_accuracy, review_outcome_source, review_window.",
            "DESIGNED_PENDING_IMPLEMENTATION",
            "metric repair must consume outcome trust metadata",
            "PROCEED_TO_PHASE9A5M1_CANONICAL_SOURCE_SELECTION_REVIEW",
        ),
    ]
    rows = []
    for area, status, problem, objective, design, decision, blocker, action in rows_data:
        row = _base(generated_ts, design_run_id)
        row.update(
            {
                "design_area": area,
                "design_status": status,
                "source_evidence": evidence,
                "problem_statement": problem,
                "design_objective": objective,
                "proposed_design": design,
                "decision_status": decision,
                "blocking_dependency": blocker,
                "recommended_next_action": action,
                "production_excluded": "TRUE",
                "notes": "Design-only; no Market Reaction, Evaluation_Rows, Outcome_Ledger, or accuracy results modified.",
            }
        )
        rows.append(row)
    return rows


def _build_source_strategy_rows(generated_ts: str, design_run_id: str, summary: Dict[str, Any]) -> List[Dict[str, Any]]:
    evidence = (
        f"source_pairs={summary.get('source_comparison_pairs')}; "
        f"direction_disagreements={summary.get('source_direction_disagreements')}; "
        f"strength_disagreements={summary.get('source_strength_disagreements')}; "
        f"large_pips_disagreements={summary.get('large_pips_disagreements')}"
    )
    strategies = [
        (
            "SRC_STRAT_SINGLE_CANONICAL",
            "Single Canonical Provider",
            "single_canonical_provider",
            "Tier1=<selected provider only>",
            "Simple, reproducible, easy to audit.",
            "Brittle when selected source has outage, missing candles, or provider-specific data artifacts.",
            "FALSE",
            "FALSE",
            "FALSE",
            "canonical_source|construction_version|window_confidence|outcome_confidence",
            "Use only if source-selection review proves one provider dominates integrity checks.",
            "NEEDS_REVIEW",
            "FALSE",
        ),
        (
            "SRC_STRAT_HIERARCHICAL_FALLBACK",
            "Hierarchical Fallback With Agreement Gate",
            "hierarchical_fallback",
            "Tier1=<primary>; Tier2=<secondary>; Tier3=<fallback>; disagreement metadata always retained",
            "Deterministic, robust to missing source rows, compatible with explicit fallback metadata.",
            "Requires governance-approved provider order and tolerance rules.",
            "TRUE",
            "TRUE",
            "TRUE",
            "canonical_source|fallback_used|fallback_reason|provider_agreement|pips_disagreement_abs|trust_level|construction_version",
            "Best architecture candidate given source disagreement and missing/unstable outcomes.",
            "RECOMMENDED_FOR_REVIEW",
            "TRUE",
        ),
        (
            "SRC_STRAT_CONSENSUS_SOURCE",
            "Consensus Source",
            "consensus_source",
            "Use outcome only when at least two providers agree within pips/direction tolerance",
            "Strong protection against provider-specific artifacts.",
            "Can discard many rows and reduce accuracy sample size.",
            "TRUE",
            "FALSE",
            "TRUE",
            "provider_agreement|agreement_provider_count|consensus_method|trust_level|construction_version",
            "Useful as a strict subset or validation view, not necessarily complete canonical source.",
            "SUPPORTING_STRATEGY",
            "FALSE",
        ),
        (
            "SRC_STRAT_WEIGHTED_CONFIDENCE",
            "Weighted Confidence Source",
            "weighted_confidence_source",
            "Blend providers based on historical source trust scores",
            "Can model provider reliability continuously.",
            "Adds complexity and risks hidden weighting before source integrity is repaired.",
            "TRUE",
            "TRUE",
            "TRUE",
            "source_weight|weight_version|provider_agreement|trust_level|construction_version",
            "Not recommended until a source-selection review defines source reliability evidence.",
            "HOLD",
            "FALSE",
        ),
    ]
    rows = []
    for (
        sid,
        name,
        strategy_type,
        hierarchy,
        advantages,
        disadvantages,
        handles_disagreement,
        handles_missing,
        handles_large,
        metadata,
        support,
        status,
        recommended,
    ) in strategies:
        row = _base(generated_ts, design_run_id)
        row.update(
            {
                "strategy_id": sid,
                "strategy_name": name,
                "strategy_type": strategy_type,
                "candidate_source_hierarchy": hierarchy,
                "advantages": advantages,
                "disadvantages": disadvantages,
                "handles_source_disagreement": handles_disagreement,
                "handles_missing_source": handles_missing,
                "handles_large_pips_difference": handles_large,
                "trust_metadata_required": metadata,
                "evidence_support": f"{support} Evidence: {evidence}",
                "design_status": status,
                "recommended_for_review": recommended,
                "final_provider_decided": "FALSE",
                "notes": "Final canonical provider/order is intentionally not selected in Phase 9A-5M.",
            }
        )
        rows.append(row)
    return rows


def _build_window_rows(generated_ts: str, design_run_id: str) -> List[Dict[str, Any]]:
    windows = [
        (
            "WIN_EVENT_FIXED_5M",
            "Event-relative fixed horizon",
            "event_relative",
            "start_ts = release_ts or deterministic anchor_ts; end_ts = start_ts + MR_HORIZON_MIN",
            "Config.MR_HORIZON_MIN",
            "If overlapping releases share release_ts, attach window to canonical outcome_key and batch/member metadata.",
            "If no candles, mark outcome_status=MISSING_CANDLES and exclude from strict accuracy.",
            "Do not extend window silently; record delayed_reaction_candidate separately.",
            "window_confidence|window_start_rule|window_end_rule|candle_count|missing_candle_flag",
            "Most reproducible and closest to existing design.",
            "Can miss delayed reactions or anchor-adjusted spikes.",
            "PRIMARY_RECOMMENDED",
        ),
        (
            "WIN_ANCHOR_ADJUSTED",
            "Anchor-adjusted reaction window",
            "anchor_adjusted",
            "start_ts = detected anchor_ts; end_ts = anchor_ts + horizon",
            "Config.MR_HORIZON_MIN",
            "Allowed only when anchor detection is deterministic and recorded.",
            "If anchor unavailable, fallback to event-relative with fallback_used=TRUE.",
            "Record anchor_delta_min and do not silently change event-relative truth.",
            "anchor_ts|anchor_delta_min|anchor_confidence|fallback_used",
            "May reflect actual market move onset better.",
            "Can introduce outcome-moving discretion if anchor detection is unstable.",
            "SECONDARY_REVIEW",
        ),
        (
            "WIN_SESSION_BASED",
            "Session-based outcome window",
            "session_based",
            "window spans configured session boundary rather than immediate event horizon",
            "custom_session_window",
            "Overlapping events resolved by session_id and event membership.",
            "Missing candles require session exclusion or manual review.",
            "Delayed reaction is captured but attribution is weaker.",
            "session_id|session_window|event_membership|attribution_confidence",
            "May fit multi-event sessions.",
            "Weakens event-level causal attribution.",
            "HOLD_FOR_SEPARATE_DESIGN",
        ),
        (
            "WIN_DELAYED_REACTION_FLAG",
            "Delayed reaction supplement",
            "supplemental_flag",
            "Keep fixed primary window; add delayed_reaction_flag based on separate deterministic criteria",
            "primary + supplemental",
            "Does not replace canonical immediate outcome.",
            "If delayed reaction cannot be evaluated, keep primary outcome and flag unknown.",
            "Used as metadata, not a replacement truth label.",
            "delayed_reaction_flag|delayed_window_pips|delayed_confidence",
            "Preserves canonical immediate outcome while surfacing ambiguity.",
            "Could be misused if treated as alternate scoring target.",
            "SUPPORTING_METADATA",
        ),
    ]
    rows = []
    for item in windows:
        (
            sid,
            name,
            wtype,
            definition,
            horizon,
            overlap,
            missing,
            delayed,
            metadata,
            advantages,
            risks,
            status,
        ) = item
        row = _base(generated_ts, design_run_id)
        row.update(
            {
                "window_strategy_id": sid,
                "window_strategy_name": name,
                "window_type": wtype,
                "window_definition": definition,
                "expected_horizon_minutes": horizon,
                "overlap_handling": overlap,
                "missing_candle_handling": missing,
                "delayed_reaction_handling": delayed,
                "confidence_metadata": metadata,
                "advantages": advantages,
                "risks": risks,
                "recommended_status": status,
                "notes": "Window design only; no windows or market reaction values modified.",
            }
        )
        rows.append(row)
    return rows


def _build_matching_rows(generated_ts: str, design_run_id: str, summary: Dict[str, Any]) -> List[Dict[str, Any]]:
    evidence = f"ambiguous_accuracy_matches={summary.get('outcome_matches_ambiguous')}/{summary.get('outcome_matches_checked')}"
    rows_data = [
        (
            "MATCH_EVENT_SESSION_PRIMARY",
            "Event/session canonical key",
            "event_id + session_id + release_ts + outcome_window_id",
            "event_id|session_id|release_ts|outcome_window_id",
            "batch_id|country+release_ts as review-only fallback",
            "Do not pick among duplicates silently; duplicates must share same canonical_outcome_id or be flagged ambiguous.",
            "Batch-level forecasts map to canonical batch_outcome_id; member rows retain member_event_id.",
            "session_id binds controlled pack outputs to intended replay/session cohort.",
            "Resolves current country+release_ts ambiguity by requiring canonical identity.",
            evidence,
            "PRIMARY_RECOMMENDED",
        ),
        (
            "MATCH_BATCH_PRIMARY",
            "Batch-aware outcome key",
            "batch_id + release_ts + outcome_window_id, with event members attached",
            "batch_id|release_ts|outcome_window_id",
            "event_id when no batch_id; country+release_ts only for diagnostics",
            "Multiple member events may share one batch outcome only if batch_id matches.",
            "Batch rows use batch_outcome_id; member rows may use member_outcome_id.",
            "session_id still required for controlled pack sessions.",
            "Handles same-minute multi-event batches better than country+release_ts.",
            evidence,
            "SUPPORTING_STRATEGY",
        ),
        (
            "MATCH_RELEASE_TS_ONLY",
            "Country + release_ts fallback",
            "country + release_ts only",
            "country|release_ts",
            "none",
            "Always mark ambiguous if more than one event/prediction/batch row matches.",
            "Cannot distinguish same-timestamp batch members.",
            "Not sufficient for controlled accuracy denominators.",
            "Existing method produced 145/145 ambiguous matches.",
            evidence,
            "DISALLOW_FOR_STRICT_ACCURACY",
        ),
    ]
    rows = []
    for (
        sid,
        name,
        hierarchy,
        required,
        fallback,
        duplicate,
        batch,
        session,
        ambiguity,
        support,
        status,
    ) in rows_data:
        row = _base(generated_ts, design_run_id)
        row.update(
            {
                "matching_strategy_id": sid,
                "matching_strategy_name": name,
                "key_hierarchy": hierarchy,
                "required_keys": required,
                "fallback_keys": fallback,
                "duplicate_handling": duplicate,
                "batch_handling": batch,
                "session_handling": session,
                "ambiguity_resolution": ambiguity,
                "evidence_support": support,
                "recommended_status": status,
                "notes": "Design-only matching strategy; no accuracy rows rematched.",
            }
        )
        rows.append(row)
    return rows


def _build_disagreement_rows(generated_ts: str, design_run_id: str) -> List[Dict[str, Any]]:
    rows_data = [
        (
            "DISAGREE_AGREEMENT",
            "agreement",
            "same direction and pips difference <= 1 pip and same strength",
            "KEEP",
            "TRUE",
            "FALSE",
            "trust_level=HIGH",
            "all",
            "Outcome can enter strict accuracy denominator if window and formula checks pass.",
        ),
        (
            "DISAGREE_MINOR",
            "minor_disagreement",
            "same direction but pips difference > 1 and < 5 pips, or strength differs near boundary",
            "KEEP_WITH_WARNING",
            "TRUE",
            "FALSE",
            "trust_level=MEDIUM",
            "overall_ok|strength-sensitive metrics",
            "Allowed for direction metrics; strict overall metrics should carry warning.",
        ),
        (
            "DISAGREE_MAJOR",
            "major_disagreement",
            "direction disagreement or pips difference >= 5 pips",
            "REVIEW_OUTCOME_SOURCE",
            "FALSE",
            "TRUE",
            "trust_level=LOW",
            "direction_match_rate|overall_ok|false_signal_rate",
            "Do not silently choose a source for strict accuracy.",
        ),
        (
            "DISAGREE_UNUSABLE",
            "unusable",
            "missing canonical source, missing prices, missing window, or pips difference >= 15 pips",
            "EXCLUDE_FROM_STRICT_ACCURACY",
            "FALSE",
            "TRUE",
            "trust_level=UNUSABLE",
            "all",
            "Future evaluation may count in outcome-availability audit but not strict accuracy denominator.",
        ),
    ]
    rows = []
    for rule_id, cls, trigger, handling, allowed, manual, effect, metrics, notes in rows_data:
        row = _base(generated_ts, design_run_id)
        row.update(
            {
                "disagreement_rule_id": rule_id,
                "disagreement_class": cls,
                "trigger_condition": trigger,
                "future_accuracy_handling": handling,
                "canonical_outcome_allowed": allowed,
                "manual_review_required": manual,
                "trust_level_effect": effect,
                "affected_metrics": metrics,
                "notes": notes,
            }
        )
        rows.append(row)
    return rows


def _build_trust_rows(generated_ts: str, design_run_id: str) -> List[Dict[str, Any]]:
    fields = [
        ("TRUST_CANONICAL_SOURCE", "canonical_source", "Which market-data source supplied canonical pips/direction/strength.", "provider_source_id", "TRUE", "selected by approved source hierarchy", "TRUE"),
        ("TRUST_FALLBACK_USED", "fallback_used", "Whether primary source was unavailable or disqualified.", "TRUE|FALSE", "TRUE", "TRUE if non-primary tier used", "TRUE"),
        ("TRUST_FALLBACK_REASON", "fallback_reason", "Why fallback was used.", "missing_source|window_issue|formula_issue|source_disagreement|none", "TRUE", "derived during canonical construction", "TRUE"),
        ("TRUST_PROVIDER_AGREEMENT", "provider_agreement", "Provider-source agreement class.", "agreement|minor_disagreement|major_disagreement|unusable", "TRUE", "derived from provider-source comparisons", "TRUE"),
        ("TRUST_PIPS_DISAGREEMENT_ABS", "pips_disagreement_abs", "Largest absolute pips difference across available sources.", "number", "TRUE", "max provider-source pips delta", "TRUE"),
        ("TRUST_WINDOW_CONFIDENCE", "window_confidence", "Confidence in reaction window integrity.", "HIGH|MEDIUM|LOW|UNUSABLE", "TRUE", "derived from start/end/candle/window checks", "TRUE"),
        ("TRUST_OUTCOME_CONFIDENCE", "outcome_confidence", "Combined source and window trust.", "HIGH|MEDIUM|LOW|UNUSABLE", "TRUE", "minimum of source agreement and window confidence", "TRUE"),
        ("TRUST_LEVEL", "trust_level", "Future accuracy denominator handling level.", "STRICT_OK|WARNING|REVIEW|EXCLUDE", "TRUE", "mapped from outcome_confidence and disagreement class", "TRUE"),
        ("TRUST_CONSTRUCTION_VERSION", "construction_version", "Version of deterministic outcome construction.", "string", "TRUE", "set by repair implementation", "FALSE"),
        ("TRUST_OUTCOME_KEY", "canonical_outcome_id", "Stable key for matching forecasts to market outcome.", "string", "TRUE", "event/session/window identity hash or deterministic key", "TRUE"),
        ("TRUST_AUDIT_NOTES", "outcome_audit_notes", "Human-readable notes for warnings.", "string", "FALSE", "derived warning summaries", "FALSE"),
    ]
    rows = []
    for fid, name, purpose, allowed, required, rule, filtering in fields:
        row = _base(generated_ts, design_run_id)
        row.update(
            {
                "trust_field_id": fid,
                "field_name": name,
                "field_purpose": purpose,
                "allowed_values_or_type": allowed,
                "required": required,
                "derivation_rule": rule,
                "used_for_accuracy_filtering": filtering,
                "notes": "Metadata design only; fields are not materialized in source sheets in this phase.",
            }
        )
        rows.append(row)
    return rows


def _build_readiness_rows(
    generated_ts: str,
    design_run_id: str,
    summary: Dict[str, Any],
    missing_critical: Sequence[str],
) -> List[Dict[str, Any]]:
    rows_data = [
        ("READ_AUDIT_AVAILABLE", "audit_inputs", "Phase 9A-5M-0 audit sheets available.", "PASS" if not missing_critical else "BLOCKED", bool(missing_critical), "|".join(missing_critical) or "all critical inputs present", "Restore missing critical audit inputs."),
        ("READ_SOURCE_STRATEGIES", "canonical_source", "Candidate canonical source strategies defined.", "PASS", False, "4 strategies", "Select canonical source/order before implementation."),
        ("READ_WINDOW_STRATEGIES", "window_definition", "Deterministic window strategies defined.", "PASS", False, "4 strategies", "Implement fixed event-relative primary window and warning metadata."),
        ("READ_MATCHING_STRATEGIES", "outcome_matching", "Deterministic matching hierarchy defined.", "PASS", False, "3 strategies", "Materialize canonical_outcome_id before strict replication."),
        ("READ_DISAGREEMENT_RULES", "provider_disagreement", "Disagreement classes and evaluation handling defined.", "PASS", False, "4 rules", "Approve thresholds in source selection review."),
        ("READ_TRUST_METADATA", "trust_metadata", "Trust metadata fields defined.", "PASS", False, "11 fields", "Add fields in repair implementation."),
        ("READ_FINAL_PROVIDER", "canonical_provider_selection", "Final canonical provider/order selected.", "NEEDS_REVIEW", True, "not selected by design phase", "Conduct canonical source selection review."),
        ("READ_IMPLEMENTATION", "repair_implementation", "Repair can be implemented immediately.", "NEEDS_REVIEW", True, "architecture designed but source order pending", "Proceed to Phase 9A-5M1 source selection review first."),
        ("READ_ACCURACY_REPLICATION", "accuracy_replication", "Ready for accuracy replication.", "BLOCKED", True, "outcome layer still questionable", "Repair and re-audit market reaction outcomes first."),
    ]
    rows = []
    for cid, area, desc, status, blocking, evidence, required in rows_data:
        row = _base(generated_ts, design_run_id)
        row.update(
            {
                "readiness_check_id": cid,
                "readiness_area": area,
                "check_description": desc,
                "check_status": status,
                "blocking": "TRUE" if blocking else "FALSE",
                "evidence_value": evidence,
                "required_before_implementation": required,
                "notes": "Readiness for design/selection only; no implementation performed.",
            }
        )
        rows.append(row)
    return rows


def _build_governance_rows(generated_ts: str, design_run_id: str) -> List[Dict[str, Any]]:
    checks = [
        ("provider_calls_performed", 0, 0),
        ("forecast_generation_performed", 0, 0),
        ("accuracy_evaluation_performed", 0, 0),
        ("accuracy_results_modified", 0, 0),
        ("market_reaction_values_modified", 0, 0),
        ("evaluation_rows_written", 0, 0),
        ("outcome_ledger_written", 0, 0),
        ("production_sheet_write_count", 0, 0),
        ("production_behavior_change_count", 0, 0),
        ("thresholds_modified", 0, 0),
        ("experiments_rerun", 0, 0),
        ("routing_changes", "FALSE", "FALSE"),
        ("weighting_changes", "FALSE", "FALSE"),
        ("calibration_changes", "FALSE", "FALSE"),
        ("ensemble_changes", "FALSE", "FALSE"),
    ]
    rows = []
    for name, expected, actual in checks:
        row = _base(generated_ts, design_run_id)
        row.update(
            {
                "check_id": f"CHK_{name.upper()}",
                "check_name": name,
                "expected_value": expected,
                "actual_value": actual,
                "status": "PASS" if str(expected) == str(actual) else "FAIL",
                "notes": "Phase 9A-5M is design-only and does not modify outcome/evaluation/production sources.",
            }
        )
        rows.append(row)
    return rows


def _upsert_registry_rows(service) -> Dict[str, int]:
    headers = _ensure_sheet(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET, REGISTRY_HEADERS)
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_upper(row.get("logical_sheet_id")): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_upper(row.get("logical_sheet_id")): row for row in rows}
    registry_rows = [
        ("MARKET_REACTION_SOURCE_REPAIR_DESIGN", OUTPUT_DESIGN, "market_reaction_source_repair_design"),
        ("MARKET_REACTION_CANONICAL_SOURCE_STRATEGY", OUTPUT_SOURCE, "market_reaction_canonical_source_strategy"),
        ("MARKET_REACTION_WINDOW_DEFINITION_DESIGN", OUTPUT_WINDOW, "market_reaction_window_definition_design"),
        ("MARKET_REACTION_OUTCOME_MATCHING_DESIGN", OUTPUT_MATCHING, "market_reaction_outcome_matching_design"),
        ("MARKET_REACTION_DISAGREEMENT_HANDLING", OUTPUT_DISAGREEMENT, "market_reaction_disagreement_handling"),
        ("MARKET_REACTION_TRUST_SCORING_DESIGN", OUTPUT_TRUST, "market_reaction_trust_scoring_design"),
        ("MARKET_REACTION_REPAIR_READINESS", OUTPUT_READINESS, "market_reaction_repair_readiness"),
        ("MARKET_REACTION_SOURCE_REPAIR_GOVERNANCE", OUTPUT_GOVERNANCE, "market_reaction_source_repair_governance"),
        ("MARKET_REACTION_SOURCE_REPAIR_SUMMARY", OUTPUT_SUMMARY, "market_reaction_source_repair_summary"),
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
            "notes": "Phase 9A-5M outcome source repair design; design-only diagnostics.",
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
    parser = argparse.ArgumentParser(description="Build PreSignal v2.0 Phase 9A-5M outcome source repair design.")
    return parser.parse_args(argv)


def build_market_reaction_outcome_source_repair_design_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    args = args or _parse_args()
    _ = args
    generated_ts = _iso_now()
    design_run_id = _run_id(generated_ts)
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
    _ = main_inputs

    audit_summary = _latest(diag_inputs["Market_Reaction_Outcome_Integrity_Summary"])
    if not missing_critical and _norm(audit_summary.get("final_interpretation")) != "MARKET_REACTION_OUTCOME_INTEGRITY_NEEDS_REPAIR":
        raise RuntimeError("Phase 9A-5M-0 did not conclude MARKET_REACTION_OUTCOME_INTEGRITY_NEEDS_REPAIR; repair design blocked.")

    source_rows = diag_inputs["Market_Reaction_Source_Comparison_Audit"]
    design_rows = _build_design_rows(generated_ts, design_run_id, audit_summary)
    source_strategy_rows = _build_source_strategy_rows(generated_ts, design_run_id, audit_summary)
    window_rows = _build_window_rows(generated_ts, design_run_id)
    matching_rows = _build_matching_rows(generated_ts, design_run_id, audit_summary)
    disagreement_rows = _build_disagreement_rows(generated_ts, design_run_id)
    trust_rows = _build_trust_rows(generated_ts, design_run_id)
    readiness_rows = _build_readiness_rows(generated_ts, design_run_id, audit_summary, missing_critical)
    governance_rows = _build_governance_rows(generated_ts, design_run_id)

    governance_failed = any(_norm(row.get("status")) != "PASS" for row in governance_rows)
    build_status = "PASS_WITH_WARNINGS" if not governance_failed and not missing_critical else "FAIL"
    final_interpretation = (
        "MARKET_REACTION_OUTCOME_SOURCE_REPAIR_DESIGN_READY_WITH_WARNINGS"
        if not governance_failed and not missing_critical
        else "MARKET_REACTION_OUTCOME_SOURCE_REPAIR_DESIGN_BLOCKED"
    )
    highest_pair = _source_pair_risk(source_rows) or audit_summary.get("highest_risk_source_pair") or "eodhd|tiingo"
    highest_risk = (
        "canonical_source_not_selected_and_current_matching_ambiguous"
        if _issue_value(audit_summary, "outcome_matches_ambiguous")
        else "canonical_source_not_selected"
    )
    recommended_architecture = (
        "Hierarchical fallback canonical source with agreement gate, fixed event-relative primary window, "
        "canonical_outcome_id matching, disagreement classes, and trust metadata."
    )
    recommended_next_step = (
        "PROCEED_TO_PHASE9A5M1_CANONICAL_SOURCE_SELECTION_REVIEW"
        if not missing_critical
        else "RUN_MARKET_REACTION_AUDIT_REPAIR"
    )
    summary_row = {
        **_base(generated_ts, design_run_id),
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "canonical_source_strategies_designed": len(source_strategy_rows),
        "window_strategies_designed": len(window_rows),
        "outcome_matching_strategies_designed": len(matching_rows),
        "disagreement_strategies_designed": len(disagreement_rows),
        "trust_metadata_fields_designed": len(trust_rows),
        "repair_readiness": "READY_FOR_SOURCE_SELECTION_REVIEW" if not missing_critical else "BLOCKED_MISSING_INPUTS",
        "highest_remaining_risk": highest_risk,
        "recommended_canonical_architecture": recommended_architecture,
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "accuracy_evaluation_performed": 0,
        "accuracy_results_modified": 0,
        "market_reaction_values_modified": 0,
        "evaluation_rows_written": 0,
        "outcome_ledger_written": 0,
        "production_sheet_write_count": 0,
        "production_behavior_change_count": 0,
        "routing_changes": "FALSE",
        "weighting_changes": "FALSE",
        "calibration_changes": "FALSE",
        "ensemble_changes": "FALSE",
        "ready_for_outcome_source_repair_implementation": "FALSE",
        "ready_for_canonical_source_selection_review": "TRUE" if not missing_critical else "FALSE",
        "ready_for_accuracy_replication": "FALSE",
        "ready_for_production": "FALSE",
        "recommended_next_step": recommended_next_step,
        "notes": json.dumps(
            {
                "source_audit_final_interpretation": audit_summary.get("final_interpretation"),
                "market_reaction_trust_classification": audit_summary.get("market_reaction_trust_classification"),
                "pips_formula_mismatches": audit_summary.get("pips_formula_mismatches"),
                "window_issues": audit_summary.get("window_issues"),
                "source_direction_disagreements": audit_summary.get("source_direction_disagreements"),
                "outcome_matches_ambiguous": audit_summary.get("outcome_matches_ambiguous"),
                "accuracy_rows_high_sensitivity": audit_summary.get("accuracy_rows_high_sensitivity"),
                "highest_risk_source_pair": highest_pair,
                "missing_main_inputs": sorted(missing_main),
                "missing_diagnostics_inputs": sorted(missing_diag),
                "missing_critical_inputs": missing_critical,
                "design_only": True,
                "final_provider_decided": False,
            },
            sort_keys=True,
        ),
    }
    summary_rows = [summary_row]

    outputs = [
        (OUTPUT_DESIGN, DESIGN_HEADERS, design_rows),
        (OUTPUT_SOURCE, SOURCE_HEADERS, source_strategy_rows),
        (OUTPUT_WINDOW, WINDOW_HEADERS, window_rows),
        (OUTPUT_MATCHING, MATCHING_HEADERS, matching_rows),
        (OUTPUT_DISAGREEMENT, DISAGREEMENT_HEADERS, disagreement_rows),
        (OUTPUT_TRUST, TRUST_HEADERS, trust_rows),
        (OUTPUT_READINESS, READINESS_HEADERS, readiness_rows),
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
        "file_created": "automation/build_market_reaction_outcome_source_repair_design_v0.py",
        "sheets_written": {sheet_name: len(rows) for sheet_name, _, rows in outputs},
        "canonical_source_strategies_designed": len(source_strategy_rows),
        "window_strategies_designed": len(window_rows),
        "outcome_matching_strategies_designed": len(matching_rows),
        "disagreement_strategies_designed": len(disagreement_rows),
        "trust_metadata_fields_designed": len(trust_rows),
        "repair_readiness": summary_row["repair_readiness"],
        "highest_remaining_risk": highest_risk,
        "recommended_canonical_architecture": recommended_architecture,
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "accuracy_evaluation_performed": 0,
        "accuracy_results_modified": 0,
        "market_reaction_values_modified": 0,
        "evaluation_rows_written": 0,
        "outcome_ledger_written": 0,
        "production_sheet_write_count": 0,
        "production_behavior_change_count": 0,
        "ready_for_outcome_source_repair_implementation": False,
        "ready_for_canonical_source_selection_review": not bool(missing_critical),
        "ready_for_accuracy_replication": False,
        "ready_for_production": False,
        "recommended_next_step": recommended_next_step,
        "registry": registry,
    }


def main() -> None:
    result = build_market_reaction_outcome_source_repair_design_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
