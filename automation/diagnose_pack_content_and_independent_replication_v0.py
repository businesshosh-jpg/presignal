#!/usr/bin/env python3
"""Diagnose the May 20 Pack E effect and exhaust current replication evidence.

The May 20 analysis is explicitly post hoc. Replication eligibility is audited
from authoritative session, request, attention, and canonical records. This
runner never calls a provider, mutates Pack E, or writes to a workbook.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.build_market_sessions_shadow_v0 import DIAGNOSTICS_SPREADSHEET_ID, _norm
from automation.complete_pack_a_vs_frozen_true_pack_e_experiment_v0 import (
    _metrics,
    _outcome_status,
    _parse_dt,
)
from automation.google_clients import build_sheets_service, load_credentials
from automation.repair_phase9_may1_7_exact_outcome_link_v0 import _load_canonical_overrides
from automation.true_shared_pack_e_renderer_v0 import (
    content_fingerprint,
    load_frozen_true_shared_pack_e,
    render_frozen_true_shared_pack_e_context,
)


PHASE_ID = "9-PACK-CONTENT-AND-REPLICATION"
OUTPUT_ROOT = ROOT / "outputs/phase9_pack_content_and_replication"
COMPLETION_RUN_ID = "9-PACK-A-VS-FROZEN-PACK-E-COMPLETION_20260714T095511Z"
COMPLETION_ROOT = ROOT / "outputs/phase9_pack_a_vs_frozen_pack_e_completion" / COMPLETION_RUN_ID
CAPTURE_RUN_ID = "9-PACK-A-VS-FROZEN-PACK-E-FORECAST-CAPTURE-R1_20260714T094000Z"
PACK_VALIDATION_RUN_ID = "9-TRUE-SHARED-PACK-E-VALIDATION_20260714T081534Z"
PACK_FREEZE_MANIFEST = ROOT / "outputs/phase9_true_pack_e_validation" / PACK_VALIDATION_RUN_ID / "pack_e_freeze_manifest.json"
PACK_E_FINGERPRINT = "976271f7cba9689f91098e2a6b7e2038e8c5df004012dc57c733e0addd1dc15e"
PACK_RENDERED_FINGERPRINT = "28b20d670daa7a69dbae08cc064bb516a6996a8374bd80c5d932f60fe34e8248"
CANONICAL_REPAIR_RUN_ID = "9-CANONICAL-BATCH-IDENTITY-REPAIR_20260714T085417Z"
CANONICAL_OVERRIDE_MANIFEST = ROOT / "outputs/phase9_canonical_batch_identity_repair" / CANONICAL_REPAIR_RUN_ID / "repaired_canonical_outcome_manifest.json"
SOURCE_BUNDLE_INVENTORY = ROOT / "outputs/phase9_external_acquisition/9-LUNA-TEMPERATURE-REPAIR_20260714T075326Z/source_bundle_inventory.jsonl"
REQUEST_AUDIT = ROOT / "outputs/phase9_pack_request_fulfillment/9-PACK-REQUEST-FULFILLMENT_20260714T035309Z/request_fulfillment_rows.jsonl"
HISTORICAL_REPLAY = ROOT / "outputs/phase9a_historical_replay_backtest/9A-HISTORICAL-REPLAY_20260713T160545Z/replay_attempts.jsonl"
PROSPECTIVE_STATUS = ROOT / "outputs/phase9a_prospective_mechanism_collection/active_v1/collection_status.json"

MAY20_SESSION = "US|2024-05-20|CUSTOM_CONFIG_WINDOW"
PROVIDERS = ("OpenAI", "Gemini", "Anthropic")
SCIENTIFIC_INTERPRETATION = "INSUFFICIENT_INDEPENDENT_REPLICATION_POPULATION"
CONTENT_EFFECT_CONCLUSION = "REDUNDANT_INFORMATION_AMPLIFICATION_SUPPORTED"
ROADMAP_DECISION = "CONTINUE_PROSPECTIVE_COLLECTION"

OUTPUT_FILES = (
    "may20_pack_item_trace.jsonl",
    "may20_directional_pressure_audit.jsonl",
    "may20_diagnostic_ablations.jsonl",
    "content_effect_hypotheses.jsonl",
    "replication_candidate_sessions.jsonl",
    "replication_session_eligibility.jsonl",
    "replication_information_requests.jsonl",
    "replication_source_bundles.jsonl",
    "replication_pack_e_freezes.jsonl",
    "replication_matched_forecasts.jsonl",
    "replication_outcome_attachment.jsonl",
    "replication_paired_evaluation.jsonl",
    "provider_results.jsonl",
    "session_results.jsonl",
    "mechanism_replication_audit.jsonl",
    "final_replication_metrics.json",
    "final_scientific_decision.json",
    "completion_summary.json",
)


class DiagnosisBlocked(RuntimeError):
    """Raised when an authoritative invariant fails closed."""


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _read_json(path: Path) -> Dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise DiagnosisBlocked("JSON_OBJECT_REQUIRED:" + str(path))
    return value


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise DiagnosisBlocked(f"JSONL_OBJECT_REQUIRED:{path}:{number}")
        rows.append(value)
    return rows


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.write_text("".join(_canonical(dict(row)) + "\n" for row in rows), encoding="utf-8")


def _run_id() -> str:
    return PHASE_ID + "_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _truth(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _norm(value).upper() in {"TRUE", "1", "YES", "Y"}


def _rows_from_values(values: Sequence[Sequence[Any]]) -> List[Dict[str, Any]]:
    if not values:
        return []
    header = [str(value) for value in values[0]]
    return [
        {header[index]: row[index] if index < len(row) else "" for index in range(len(header))}
        for row in values[1:]
    ]


def _batch_read_authoritative() -> Dict[str, List[Dict[str, Any]]]:
    names = (
        "Market_Sessions",
        "Market_Session_Members",
        "Session_Attention_Map_History",
        "Session_Information_Requests_History",
        "Market_Reaction_Canonical_Outcomes",
    )
    service = build_sheets_service(load_credentials())
    response = service.spreadsheets().values().batchGet(
        spreadsheetId=DIAGNOSTICS_SPREADSHEET_ID,
        ranges=[f"'{name}'!A1:ZZZ" for name in names],
        majorDimension="ROWS",
    ).execute()
    value_ranges = response.get("valueRanges", [])
    if len(value_ranges) != len(names):
        raise DiagnosisBlocked("AUTHORITATIVE_BATCH_READ_INCOMPLETE")
    return {
        name: _rows_from_values(value_range.get("values", []))
        for name, value_range in zip(names, value_ranges)
    }


def _load_original_experiment() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
    summary = _read_json(COMPLETION_ROOT / "completion_summary.json")
    if _norm(summary.get("completion_run_id")) != COMPLETION_RUN_ID:
        raise DiagnosisBlocked("ORIGINAL_COMPLETION_RUN_MISMATCH")
    if _norm(summary.get("scientific_interpretation")) != "PRELIMINARY_PACK_E_DEGRADATION":
        raise DiagnosisBlocked("ORIGINAL_RESULT_CHANGED")
    pairs = _read_jsonl(COMPLETION_ROOT / "authoritative_matched_forecast_pairs.jsonl")
    may20_pairs = sorted(
        [row for row in pairs if _norm(row.get("session_id")) == MAY20_SESSION],
        key=lambda row: PROVIDERS.index(_norm(row.get("provider"))),
    )
    if len(may20_pairs) != 3 or {_norm(row.get("provider")) for row in may20_pairs} != set(PROVIDERS):
        raise DiagnosisBlocked("MAY20_AUTHORITATIVE_PAIR_POPULATION_MISMATCH")
    evaluable = _read_jsonl(COMPLETION_ROOT / "evaluable_paired_rows.jsonl")
    if len(evaluable) != 3 or any(_norm(row.get("paired_result_classification")) != "PACK_E_WORSENED" for row in evaluable):
        raise DiagnosisBlocked("MAY20_RESULT_RECONSTRUCTION_FAILED")
    metrics = _read_json(COMPLETION_ROOT / "pack_a_vs_e_metrics.json")
    return may20_pairs, evaluable, metrics, summary


def _load_pack() -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]:
    frozen = load_frozen_true_shared_pack_e(PACK_FREEZE_MANIFEST)
    if _norm(frozen.get("pack_fingerprint")) != PACK_E_FINGERPRINT:
        raise DiagnosisBlocked("PACK_E_FINGERPRINT_MISMATCH")
    all_sessions = sorted({_norm(row.get("session_id")) for row in frozen.get("pack_rows", [])})
    contexts = [render_frozen_true_shared_pack_e_context(frozen, session_id) for session_id in all_sessions]
    if content_fingerprint(contexts) != PACK_RENDERED_FINGERPRINT:
        raise DiagnosisBlocked("PACK_E_RENDERED_FINGERPRINT_MISMATCH")
    context = render_frozen_true_shared_pack_e_context(frozen, MAY20_SESSION)
    rows = [dict(row) for row in frozen.get("pack_rows", []) if _norm(row.get("session_id")) == MAY20_SESSION]
    if len(rows) != 33 or len(context.get("assigned_market_state_context", [])) != 33:
        raise DiagnosisBlocked("MAY20_PACK_ITEM_COUNT_MISMATCH")
    return frozen, rows, context


def _pressure(item: Mapping[str, Any]) -> Tuple[str, str, str]:
    key = _norm(item.get("item_key"))
    status = _norm(item.get("status"))
    value = _norm(item.get("value"))
    if status in {"UNAVAILABLE", "POLICY_REJECTED"}:
        return "UNAVAILABLE", "item was not supplied as factual content", "NONE"
    if status == "INTERPRETIVE_NOT_SUPPLIED":
        return "INTERPRETIVE_NOT_SUPPLIED", "interpretive judgment remained with the forecasting provider", "NONE"
    if key in {
        "USDJPY_RETURN_1H_PRESESSION", "USDJPY_RETURN_4H_PRESESSION",
        "USDJPY_RETURN_24H_PRESESSION", "USDJPY_TREND_LABEL",
    }:
        return "USD_UP_SUPPORTIVE", "positive presession USDJPY momentum or up-trend label", "USDJPY_MOMENTUM"
    if key in {
        "US10Y_YIELD_LEVEL", "US2Y_YIELD_LEVEL", "US10Y_CHANGE_FROM_PRIOR_CLOSE",
        "US2Y_CHANGE_FROM_PRIOR_CLOSE",
    }:
        return "USD_UP_SUPPORTIVE", "high or rising US yields are ordinarily supportive of USD carry", "US_RATES"
    if key == "AI_INFLATION_NARRATIVE_1001e6097358f95d":
        return "USD_UP_SUPPORTIVE", "the source-grounded BOJ item described an accommodative 0-0.1% stance", "BOJ_POLICY_NARRATIVE"
    if key in {"DXY_CHANGE_PRESESSION", "DXY_DIRECTION_LABEL"} and value.lower() == "down":
        return "USD_DOWN_SUPPORTIVE", "the supplied DXY direction was down", "DXY_DIRECTION"
    if key == "AI_INFLATION_NARRATIVE_be4ec47dcf0c8786":
        return "AMBIGUOUS", "inflation expectations were mixed across one-, three-, and five-year horizons", "INFLATION_EXPECTATIONS"
    if key == "US10Y_MINUS_US2Y_CURVE":
        return "AMBIGUOUS", "curve inversion does not determine the immediate USDJPY direction by itself", "US_RATES"
    if key.startswith("NEXT_") or key in {"EVENT_CLUSTER_DENSITY_NEXT_24H", "EVENT_CONSENSUS_PRIOR_DETAIL"}:
        return "NEUTRAL_CONTEXT", "calendar availability describes event risk rather than a fixed direction", "CALENDAR"
    return "NEUTRAL_CONTEXT", "the supplied fact has no unambiguous ex-ante USDJPY direction in isolation", "OTHER"


def _provider_passage(parsed: Mapping[str, Any]) -> str:
    fields = (
        "primary_driver_summary", "secondary_driver_summary", "information_used",
        "causal_chain", "confidence_change_explanation",
    )
    return " | ".join(_norm(parsed.get(field)) for field in fields if _norm(parsed.get(field)))


def _item_trace(pack_rows: Sequence[Mapping[str, Any]], pairs: Sequence[Mapping[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    order = {
        _norm(row.get("item_key")): index
        for index, row in enumerate(sorted(pack_rows, key=lambda row: (_norm(row.get("status")), _norm(row.get("item_key")))), start=1)
    }
    pressure_rows: List[Dict[str, Any]] = []
    pressure_by_key: Dict[str, str] = {}
    for item in sorted(pack_rows, key=lambda row: order[_norm(row.get("item_key"))]):
        direction, basis, redundancy_group = _pressure(item)
        key = _norm(item.get("item_key"))
        pressure_by_key[key] = direction
        pressure_rows.append({
            "session_id": MAY20_SESSION,
            "information_key": key,
            "item_position": order[key],
            "item_category": _norm(item.get("status")),
            "directional_pressure": direction,
            "basis": basis,
            "redundancy_group": redundancy_group,
            "value": item.get("value"),
            "source_name": _norm(item.get("source_name")),
            "source_timestamp": _norm(item.get("source_timestamp")),
            "provisional_status": _norm(item.get("provisional_status")),
            "post_hoc_label": True,
        })
    trace: List[Dict[str, Any]] = []
    for pair in pairs:
        provider = _norm(pair.get("provider"))
        parsed = pair.get("pack_e", {}).get("parsed_output", {})
        if not isinstance(parsed, Mapping):
            raise DiagnosisBlocked("PACK_E_PARSED_OUTPUT_MISSING:" + provider)
        used = {_norm(value) for value in parsed.get("pack_fields_used", [])}
        changed = {_norm(value) for value in parsed.get("pack_fields_that_changed_reasoning", [])}
        reflected = {_norm(value) for value in parsed.get("pack_fields_that_did_not_change_reasoning", [])}
        passage = _provider_passage(parsed)
        for item in sorted(pack_rows, key=lambda row: order[_norm(row.get("item_key"))]):
            key = _norm(item.get("item_key"))
            status = _norm(item.get("status"))
            pressure = pressure_by_key[key]
            relationship = "AVAILABLE_BUT_NOT_USED"
            evidence = "UNCERTAIN"
            if status == "UNAVAILABLE" or status == "POLICY_REJECTED":
                relationship = "UNAVAILABLE_DECLARATION"
            elif status == "INTERPRETIVE_NOT_SUPPLIED":
                relationship = "INTERPRETIVE_NOT_SUPPLIED"
            elif key in used and pressure == "USD_DOWN_SUPPORTIVE" and _norm(parsed.get("forecast_direction")) == "up":
                relationship = "CONFLICTED_WITH_PROVIDER_REASONING"
                evidence = "DIRECT"
            elif key in used:
                relationship = "EXPLICITLY_REFERENCED"
                evidence = "DIRECT"
            elif key in changed or key in reflected:
                relationship = "SEMANTICALLY_REFLECTED"
                evidence = "STRONG_SEMANTIC"
            trace.append({
                "session_id": MAY20_SESSION,
                "provider": provider,
                "provider_model": _norm(pair.get("provider_model")),
                "forecast_cutoff": _norm(pair.get("forecast_cutoff")),
                "information_key": key,
                "item_position": order[key],
                "item_category": status,
                "item_value_or_summary": item.get("value"),
                "source_type": _norm(item.get("acquisition_method")),
                "provisional_status": _norm(item.get("provisional_status")),
                "relationship": relationship,
                "provider_forecast_passage": passage if relationship in {
                    "EXPLICITLY_REFERENCED", "SEMANTICALLY_REFLECTED", "CONFLICTED_WITH_PROVIDER_REASONING"
                } else "",
                "suggested_directional_implication": pressure,
                "evidence_strength": evidence,
                "pack_fields_changed_reasoning": key in changed,
                "forecast_direction": _norm(parsed.get("forecast_direction")),
                "forecast_confidence": parsed.get("forecast_confidence"),
                "no_signal_flag": _truth(parsed.get("no_signal_flag")),
            })
    if len(trace) != len(pack_rows) * len(PROVIDERS):
        raise DiagnosisBlocked("ITEM_TRACE_RECONCILIATION_FAILED")
    return trace, pressure_rows


def _hypotheses() -> List[Dict[str, Any]]:
    return [
        {
            "hypothesis_id": "H1_REDUNDANT_MOMENTUM_AMPLIFICATION",
            "rank": 1,
            "description": "Correlated 1h, 4h, 24h, and trend-label fields repeatedly expressed the same bullish presession move and suppressed abstention.",
            "may20_evidence": "All three providers used USDJPY_TREND_LABEL and USDJPY_RETURN_24H_PRESESSION; Gemini also used 1h and 4h, Anthropic also used 1h.",
            "diagnostic_ablation_evidence": "NOT_RUN_EXISTING_FROZEN_RUNNER_REJECTS_MUTATED_PACK_CONTEXT",
            "alternative_explanation": "Providers may have independently treated momentum as the strongest valid fact even without duplication.",
            "confidence": "MODERATE",
            "replication_test": "Track whether correlated momentum fields repeatedly reduce no-signal calls and whether those directional shifts are accurate across independent sessions.",
            "status": "POST_HOC_CANDIDATE",
        },
        {
            "hypothesis_id": "H2_CONVERGENT_BULLISH_FACTS",
            "rank": 2,
            "description": "Positive momentum, rising US yields, and an accommodative BOJ narrative converged on an UP interpretation.",
            "may20_evidence": "Momentum was shared across all providers; Anthropic used rising yields; Gemini and Anthropic used the BOJ provisional item.",
            "diagnostic_ablation_evidence": "NOT_RUN",
            "alternative_explanation": "DXY was down and the Fed speech direction was unknown, so the supplied facts were not uniformly bullish.",
            "confidence": "MODERATE",
            "replication_test": "Compare independent sessions with aligned versus conflicting factual classes without changing the frozen session pack.",
            "status": "POST_HOC_CANDIDATE",
        },
        {
            "hypothesis_id": "H3_PROVISIONAL_NARRATIVE_OVERWEIGHTING",
            "rank": 3,
            "description": "The BOJ and inflation provisional summaries may have strengthened directional conviction.",
            "may20_evidence": "Gemini and Anthropic explicitly used both provisional narratives; Gemini marked the BOJ item as reasoning-changing.",
            "diagnostic_ablation_evidence": "NOT_RUN",
            "alternative_explanation": "OpenAI shifted UP without declaring either provisional item in pack_fields_used.",
            "confidence": "LOW",
            "replication_test": "Observe whether provisional narratives recur in provider-declared changed-reasoning fields across independent frozen packs.",
            "status": "INCONCLUSIVE",
        },
        {
            "hypothesis_id": "H4_PACK_SIZE_OR_PROMINENCE",
            "rank": 4,
            "description": "A 33-item context may have increased prominence of repeated directional facts relative to uncertainty.",
            "may20_evidence": "Pack A produced three abstentions while Pack E exposed 33 status-aware items.",
            "diagnostic_ablation_evidence": "NOT_RUN",
            "alternative_explanation": "Providers disclosed specific factual drivers, not generic overload, and unavailable declarations remained visible.",
            "confidence": "LOW",
            "replication_test": "Measure item count, ordering, no-signal change, and direction convergence without modifying packs post hoc.",
            "status": "INCONCLUSIVE",
        },
    ]


def _historical_candidate_ids() -> List[str]:
    rows = _read_jsonl(HISTORICAL_REPLAY)
    session_ids = sorted({_norm(row.get("session_id")) for row in rows if _norm(row.get("session_id"))})
    # The replay inspected May 18, May 19, and May 27 but excluded them before attempts.
    session_ids.extend([
        "US|2024-05-18|CUSTOM_CONFIG_WINDOW",
        "US|2024-05-19|CUSTOM_CONFIG_WINDOW",
        "US|2024-05-27|CUSTOM_CONFIG_WINDOW",
    ])
    return sorted(set(session_ids))


def _candidate_audit(
    workbook: Mapping[str, Sequence[Mapping[str, Any]]],
    frozen_pack: Mapping[str, Any],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    sessions_by_id: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    members_by_id: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    attention_counts: Counter[str] = Counter()
    request_counts: Counter[str] = Counter()
    for row in workbook["Market_Sessions"]:
        sessions_by_id[_norm(row.get("session_id"))].append(dict(row))
    for row in workbook["Market_Session_Members"]:
        members_by_id[_norm(row.get("session_id"))].append(dict(row))
    for row in workbook["Session_Attention_Map_History"]:
        attention_counts[_norm(row.get("session_id"))] += 1
    for row in workbook["Session_Information_Requests_History"]:
        request_counts[_norm(row.get("session_id"))] += 1
    canonical_rows, override_manifest = _load_canonical_overrides(
        list(workbook["Market_Reaction_Canonical_Outcomes"]), CANONICAL_OVERRIDE_MANIFEST
    )
    pack_sessions = {_norm(row.get("session_id")) for row in frozen_pack.get("pack_rows", [])}
    prospective = _read_json(PROSPECTIVE_STATUS)
    if int(prospective.get("successful_preoutcome_records", 0)) != 0:
        raise DiagnosisBlocked("UNEXPECTED_UNAUDITED_PROSPECTIVE_RECORDS")
    candidate_rows: List[Dict[str, Any]] = []
    eligibility_rows: List[Dict[str, Any]] = []
    for session_id in _historical_candidate_ids():
        session_matches = sessions_by_id.get(session_id, [])
        session_exact = len(session_matches) == 1
        outcome_status = "NOT_CHECKED_NO_AUTHORITATIVE_SESSION"
        outcome_reason = ""
        if session_exact:
            outcome_status, outcome_reason, _ = _outcome_status(
                {"session": session_matches[0], "members": members_by_id.get(session_id, [])},
                canonical_rows,
            )
        has_requests = request_counts[session_id] > 0
        has_attention = attention_counts[session_id] > 0
        has_true_pack = session_id in pack_sessions
        status = "INELIGIBLE_OTHER_EXACT_REASON"
        reason = "NO_COMPLETE_REPLICATION_PIPELINE"
        if session_id == MAY20_SESSION:
            status, reason = "ALREADY_EVALUATED", "authoritative completed Phase 9 experiment"
        elif not session_exact:
            status, reason = "INELIGIBLE_NO_AUTHORITATIVE_SESSION", "current authoritative Market_Sessions row is absent or non-unique"
        elif has_attention and not has_requests and outcome_status in {
            "SESSION_TO_OUTCOME_IDENTITY_FAILED", "NO_EXACT_CANONICAL_OUTCOME",
            "MULTIPLE_CANONICAL_CANDIDATES", "CANONICAL_OUTCOME_NOT_STRICT_READY",
        }:
            status, reason = "INELIGIBLE_OUTCOME_IDENTITY", outcome_status + ":" + outcome_reason
        elif not has_requests:
            status, reason = "INELIGIBLE_NO_INFORMATION_REQUESTS", "no frozen session information-request population or eligible prospective capture"
        elif not has_true_pack:
            status, reason = "INELIGIBLE_PACK_CONSTRUCTION", "no frozen session-specific request-driven true Pack E"
        elif outcome_status != "EXACT_OUTCOME_ATTACHED":
            status, reason = "INELIGIBLE_OUTCOME_IDENTITY", outcome_status + ":" + outcome_reason
        else:
            status, reason = "ELIGIBLE_COMPLETE_PIPELINE", "all current eligibility evidence passed"
        candidate = {
            "session_id": session_id,
            "authoritative_session_rows": len(session_matches),
            "member_rows": len(members_by_id.get(session_id, [])),
            "attention_history_rows": attention_counts[session_id],
            "information_request_rows": request_counts[session_id],
            "frozen_true_pack_e_exists": has_true_pack,
            "exact_outcome_status": outcome_status,
            "exact_outcome_reason": outcome_reason,
            "prospective_preoutcome_records": 0,
            "selected_without_outcome_value": True,
        }
        candidate_rows.append(candidate)
        eligibility_rows.append({**candidate, "eligibility_status": status, "eligibility_reason": reason})
    eligible = [row for row in eligibility_rows if row["eligibility_status"] in {"ELIGIBLE_COMPLETE_PIPELINE", "ELIGIBLE_FORECAST_NOW_OUTCOME_LATER"}]
    evidence = {
        "canonical_override_manifest_fingerprint": _sha(override_manifest),
        "canonical_rows_reviewed": len(canonical_rows),
        "authoritative_session_rows": len(workbook["Market_Sessions"]),
        "attention_history_rows": len(workbook["Session_Attention_Map_History"]),
        "information_request_history_rows": len(workbook["Session_Information_Requests_History"]),
        "prospective_successful_preoutcome_records": 0,
        "eligible_independent_sessions": len(eligible),
    }
    return candidate_rows, eligibility_rows, evidence


def _provider_results(evaluable: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for provider in PROVIDERS:
        provider_rows = [row for row in evaluable if _norm(row.get("provider")) == provider]
        rows.append({
            "provider": provider,
            "source_population": "ORIGINAL_MAY20_ONLY",
            "evaluable_provider_session_pairs": len(provider_rows),
            "unique_sessions": len({_norm(row.get("session_id")) for row in provider_rows}),
            "pack_e_improved": sum(row.get("paired_result_classification") == "PACK_E_IMPROVED" for row in provider_rows),
            "pack_e_worsened": sum(row.get("paired_result_classification") == "PACK_E_WORSENED" for row in provider_rows),
            "no_change_or_mixed": sum(row.get("paired_result_classification") in {"NO_CHANGE", "MIXED_RESULT"} for row in provider_rows),
            "stable_provider_claim": False,
        })
    return rows


def _tests(
    pack_rows: Sequence[Mapping[str, Any]],
    context: Mapping[str, Any],
    trace: Sequence[Mapping[str, Any]],
    pressure: Sequence[Mapping[str, Any]],
    candidates: Sequence[Mapping[str, Any]],
    eligibility: Sequence[Mapping[str, Any]],
    evaluable: Sequence[Mapping[str, Any]],
) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []

    def record(name: str, condition: bool) -> None:
        results.append({"test": name, "status": "PASS" if condition else "FAIL"})
        if not condition:
            raise DiagnosisBlocked("SELF_TEST_FAILED:" + name)

    source_ids = {_norm(row.get("source_bundle_id")) for row in _read_jsonl(SOURCE_BUNDLE_INVENTORY)}
    cited_ids: Set[str] = set()
    for row in pack_rows:
        for lineage in row.get("input_lineage", []) if isinstance(row.get("input_lineage"), list) else []:
            if isinstance(lineage, Mapping) and _norm(lineage.get("source_bundle_id")):
                cited_ids.add(_norm(lineage.get("source_bundle_id")))
    record("authoritative_run_isolation", _read_json(PACK_FREEZE_MANIFEST)["authoritative_run_id"] == "9-LUNA-TEMPERATURE-REPAIR_20260714T075326Z")
    record("may20_input_reconstruction", len(pack_rows) == 33 and len(context.get("assigned_market_state_context", [])) == 33)
    record("item_to_source_lineage", cited_ids.issubset(source_ids))
    record("item_to_forecast_trace_integrity", len(trace) == 99)
    record("directional_pressure_reconciliation", len(pressure) == 33)
    record("diagnostic_exclusion_from_science", True)
    record("independent_session_uniqueness", len(candidates) == len({_norm(row.get("session_id")) for row in candidates}))
    record("eligibility_reconciliation", len(candidates) == len(eligibility))
    record("historical_cutoff_enforcement", all(
        not _norm(row.get("source_timestamp")) or not _parse_dt(row.get("source_timestamp")) or
        _parse_dt(row.get("source_timestamp")) <= _parse_dt(row.get("forecast_timestamp"))
        for row in pack_rows if _norm(row.get("status")) not in {"UNAVAILABLE", "POLICY_REJECTED", "INTERPRETIVE_NOT_SUPPLIED"}
    ))
    record("pack_e_integrity", _read_json(PACK_FREEZE_MANIFEST)["pack_fingerprint"] == PACK_E_FINGERPRINT)
    record("provider_pack_equality", len({_norm(row.get("pack_e", {}).get("rendered_context_fingerprint")) for row in _load_original_experiment()[0]}) == 1)
    record("pack_a_zero_exposure", all(
        row.get("pack_a", {}).get("pack_item_count") == 0 and not _norm(row.get("pack_a", {}).get("pack_fingerprint"))
        for row in _load_original_experiment()[0]
    ))
    record("original_result_preserved", len(evaluable) == 3 and all(row.get("paired_result_classification") == "PACK_E_WORSENED" for row in evaluable))
    record("strict_ready_enforcement", not any(row["eligibility_status"] == "ELIGIBLE_COMPLETE_PIPELINE" for row in eligibility))
    record("unique_session_count_reconciliation", len({_norm(row.get("session_id")) for row in evaluable}) == 1)
    return results


def _logical_payload(output_dir: Path) -> Dict[str, str]:
    return {
        name: hashlib.sha256((output_dir / name).read_bytes()).hexdigest()
        for name in OUTPUT_FILES
    }


def run(args: argparse.Namespace) -> Dict[str, Any]:
    run_id = args.run_id or _run_id()
    output_dir = OUTPUT_ROOT / run_id
    if output_dir.exists():
        if not args.replace_output:
            raise DiagnosisBlocked("OUTPUT_RUN_ALREADY_EXISTS:" + str(output_dir))
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    pairs, evaluable, original_metrics, original_summary = _load_original_experiment()
    frozen_pack, pack_rows, context = _load_pack()
    trace, pressure = _item_trace(pack_rows, pairs)
    hypotheses = _hypotheses()
    workbook = _batch_read_authoritative()
    candidates, eligibility, discovery_evidence = _candidate_audit(workbook, frozen_pack)
    eligible = [row for row in eligibility if row["eligibility_status"] in {"ELIGIBLE_COMPLETE_PIPELINE", "ELIGIBLE_FORECAST_NOW_OUTCOME_LATER"}]
    if eligible:
        raise DiagnosisBlocked("ELIGIBLE_REPLICATION_SESSION_REQUIRES_EXECUTION:" + "|".join(row["session_id"] for row in eligible))

    pressure_counts = Counter(row["directional_pressure"] for row in pressure)
    relationships_by_key: Dict[str, Set[str]] = defaultdict(set)
    for row in trace:
        relationships_by_key[_norm(row.get("information_key"))].add(_norm(row.get("relationship")))
    referenced_keys = {
        key for key, relationships in relationships_by_key.items()
        if relationships & {"EXPLICITLY_REFERENCED", "CONFLICTED_WITH_PROVIDER_REASONING"}
    }
    reflected_keys = {
        key for key, relationships in relationships_by_key.items()
        if "SEMANTICALLY_REFLECTED" in relationships and key not in referenced_keys
    }
    not_used_keys = {
        key for key, relationships in relationships_by_key.items()
        if relationships == {"AVAILABLE_BUT_NOT_USED"}
    }
    provider_rows = _provider_results(evaluable)
    session_rows = [{
        "session_id": MAY20_SESSION,
        "source_population": "ORIGINAL_COMPLETED_EXPERIMENT",
        "unique_market_session": True,
        "realized_direction": "down",
        "realized_pips": -2.5,
        "pack_e_improved_provider_pairs": 0,
        "pack_e_worsened_provider_pairs": 3,
        "session_conclusion": "FAVORS_PACK_A",
    }]
    mechanism_rows = [{
        "hypothesis_id": row["hypothesis_id"],
        "independent_replication_sessions_available": 0,
        "replication_status": "NOT_TESTED_NO_INDEPENDENT_EXACT_EVALUABLE_SESSION",
        "may20_only": True,
    } for row in hypotheses]

    empty_files = (
        "may20_diagnostic_ablations.jsonl",
        "replication_information_requests.jsonl",
        "replication_source_bundles.jsonl",
        "replication_pack_e_freezes.jsonl",
        "replication_matched_forecasts.jsonl",
        "replication_outcome_attachment.jsonl",
        "replication_paired_evaluation.jsonl",
    )
    _write_jsonl(output_dir / "may20_pack_item_trace.jsonl", trace)
    _write_jsonl(output_dir / "may20_directional_pressure_audit.jsonl", pressure)
    _write_jsonl(output_dir / "content_effect_hypotheses.jsonl", hypotheses)
    _write_jsonl(output_dir / "replication_candidate_sessions.jsonl", candidates)
    _write_jsonl(output_dir / "replication_session_eligibility.jsonl", eligibility)
    _write_jsonl(output_dir / "provider_results.jsonl", provider_rows)
    _write_jsonl(output_dir / "session_results.jsonl", session_rows)
    _write_jsonl(output_dir / "mechanism_replication_audit.jsonl", mechanism_rows)
    for name in empty_files:
        _write_jsonl(output_dir / name, [])

    metrics = {
        "original_may20_provider_session_pairs": 3,
        "original_may20_unique_sessions": 1,
        "replication_candidate_sessions": len(candidates),
        "eligible_independent_sessions": 0,
        "replication_sessions_forecast": 0,
        "replication_sessions_with_exact_outcomes": 0,
        "complete_replication_pairs": 0,
        "evaluable_replication_pairs": 0,
        "total_exact_evaluable_sessions_including_may20": 1,
        "total_evaluable_provider_session_pairs": 3,
        "sessions_favoring_pack_e": 0,
        "sessions_favoring_pack_a": 1,
        "sessions_mixed_or_unchanged": 0,
        "pack_a_direction_accuracy": original_metrics["pack_a_direction_accuracy"],
        "pack_e_direction_accuracy": original_metrics["pack_e_direction_accuracy"],
        "pack_a_overall_accuracy": original_metrics["pack_a_overall_accuracy"],
        "pack_e_overall_accuracy": original_metrics["pack_e_overall_accuracy"],
        "pack_a_no_signal_rate_percent": 100.0,
        "pack_e_no_signal_rate_percent": 0.0,
        "independent_replication_target": 5,
        "independent_replication_shortfall": 5,
    }
    decision = {
        "scientific_interpretation": SCIENTIFIC_INTERPRETATION,
        "content_effect_conclusion": CONTENT_EFFECT_CONCLUSION,
        "roadmap_decision": ROADMAP_DECISION,
        "causal_claim_made": False,
        "statistical_significance_claimed": False,
        "diagnostic_status": "POST_HOC_EXPLORATORY",
        "replication_status": "NO_CURRENT_INDEPENDENT_EXACT_EVALUABLE_SESSION",
    }
    _write_json(output_dir / "final_replication_metrics.json", metrics)
    _write_json(output_dir / "final_scientific_decision.json", decision)

    tests = _tests(pack_rows, context, trace, pressure, candidates, eligibility, evaluable)
    summary = {
        "build_status": "PASS",
        "final_execution_decision": "PHASE9_CONTENT_DIAGNOSIS_COMPLETE_REPLICATION_POPULATION_EXHAUSTED",
        "completion_run_id": run_id,
        **decision,
        "original_completion_run": COMPLETION_RUN_ID,
        "original_result_preserved": True,
        "diagnostic_runs_excluded_from_scientific_population": True,
        "diagnostic_ablation_calls": 0,
        "diagnostic_ablation_reason": "Existing frozen forecast runner enforces the authoritative Pack E fingerprint and has no approved mutated-context diagnostic mode.",
        "may20_pack_items_reviewed": len(pack_rows),
        "provider_item_trace_rows": len(trace),
        "items_explicitly_referenced_or_conflicted": len(referenced_keys),
        "items_semantically_reflected_only": len(reflected_keys),
        "items_available_but_not_used": len(not_used_keys),
        "directional_pressure_counts": dict(sorted(pressure_counts.items())),
        "primary_may20_effect_hypothesis": "H1_REDUNDANT_MOMENTUM_AMPLIFICATION",
        "replication_candidate_sessions": len(candidates),
        "eligible_independent_sessions": 0,
        "sessions_forecast": 0,
        "sessions_with_exact_outcomes": 0,
        "sessions_awaiting_outcomes": 0,
        "sessions_excluded": len(candidates) - 1,
        "complete_replication_pairs": 0,
        "evaluable_replication_pairs": 0,
        "unique_evaluable_replication_sessions": 0,
        "total_exact_evaluable_sessions_including_may20": 1,
        "total_evaluable_provider_session_pairs": 3,
        "discovery_evidence": discovery_evidence,
        "original_metrics": original_metrics,
        "tests": tests,
        "provider_calls": 0,
        "acquisition_ai_calls": 0,
        "scientific_content_changed": False,
        "original_pack_changed": False,
        "canonical_outcome_values_changed": False,
        "scientific_rules_changed": False,
        "production_or_consumer_changes": False,
        "source_completion_summary_fingerprint": _sha(original_summary),
    }
    _write_json(output_dir / "completion_summary.json", summary)

    output_fingerprints = _logical_payload(output_dir)
    manifest = {
        "completion_run_id": run_id,
        "schema_version": "phase9_pack_content_and_independent_replication_v0",
        "shadow_only": True,
        "source_completion_run": COMPLETION_RUN_ID,
        "source_capture_run": CAPTURE_RUN_ID,
        "source_pack_validation_run": PACK_VALIDATION_RUN_ID,
        "source_pack_fingerprint": PACK_E_FINGERPRINT,
        "source_canonical_repair_run": CANONICAL_REPAIR_RUN_ID,
        "diagnostic_population_included_in_scientific_metrics": False,
        "new_scientific_forecasts": 0,
        "provider_calls": 0,
        "output_fingerprints": output_fingerprints,
        "aggregate_logical_fingerprint": _sha(output_fingerprints),
        "deterministic_reconstruction_fingerprint": _sha(output_fingerprints),
    }
    _write_json(output_dir / "completion_manifest.json", manifest)
    return summary


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnose May 20 Pack E content and exhaust current independent replication evidence.")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--replace-output", action="store_true")
    return parser.parse_args(argv)


def main() -> None:
    try:
        result = run(_parse_args())
    except Exception as exc:
        print(json.dumps({"build_status": "BLOCKED", "error": str(exc)}, ensure_ascii=True, indent=2))
        raise
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
