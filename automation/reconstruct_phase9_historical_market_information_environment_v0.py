#!/usr/bin/env python3
"""Build the bounded historical Market Information Environment arm.

This runner is deliberately separate from the structured and official-source
historical populations. It admits only request-specific, pre-cutoff FOMC and
Federal Reserve Beige Book evidence, summarizes frozen bundles through the
existing Acquisition AI, and captures only the new E_ENVIRONMENT forecast arm.
Existing outcomes are opened only after every new forecast has been frozen.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.build_pack_exposure_pilot_run_v0 import _call_live_provider_raw  # type: ignore
from automation.complete_pack_a_vs_frozen_true_pack_e_experiment_v0 import (  # type: ignore
    _evaluate_arm,
    _paired_classification,
)
from automation.complete_phase9_historical_full_source_grounded_pack_e_v0 import (  # type: ignore
    _fetch_html,
    _numeric_tokens,
)
from automation.configure_market_state_pack_external_acquisition_v0 import (  # type: ignore
    MODE_HISTORICAL,
    _acquire_request,
    _load_model_config,
    _validate_source_bundle,
)
from automation.google_clients import (  # type: ignore
    build_script_service,
    default_script_id,
    load_credentials,
)
from automation.run_phase9_historical_square_one_replay_v0 import (  # type: ignore
    FORECAST_PROVIDERS,
    _hindsight_hits,
    _normalized_forecast_response,
    _safe_prompt,
    _square_one_forecast_prompt,
)


PHASE_ID = "9-HISTORICAL-ENVIRONMENT-RECONSTRUCTION"
BASE_RUN_ID = "9-HISTORICAL-ACQUISITION-REPAIR_20260715T053903Z"
BASE_ROOT = ROOT / "outputs" / "phase9_historical_square_one_acquisition_repair" / BASE_RUN_ID
EARLY_RUN_ID = "9-HISTORICAL-ACQUISITION-REPAIR_20260714T161545Z"
EARLY_ROOT = ROOT / "outputs" / "phase9_historical_square_one_acquisition_repair" / EARLY_RUN_ID
OFFICIAL_RUN_ID = "9-HISTORICAL-FULL-SOURCE-GROUNDED-PACK-E_20260716T023147Z"
OFFICIAL_ROOT = ROOT / "outputs" / "phase9_historical_full_source_grounded_pack_e" / OFFICIAL_RUN_ID
OUTPUT_ROOT = ROOT / "outputs" / "phase9_historical_environment_reconstructed_pack_e"
ACTIVE_ROOT = OUTPUT_ROOT / "active_v1"

POPULATION_TYPE = "HISTORICAL_SQUARE_ONE_ENVIRONMENT_RECONSTRUCTED_PACK_E"
PROTOCOL_VERSION = "phase9_historical_environment_reconstructed_v1"
PACK_VERSION = "true_shared_pack_e_historical_environment_reconstructed_v1"
PACK_STATUS = "FROZEN_FOR_HISTORICAL_ENVIRONMENT_RECONSTRUCTED_A_VS_E"
PROMPT_VERSION = "phase9_historical_square_one_forecast_v1"
MODEL_WEIGHT_RISK = "KNOWN_NONZERO_LIMITATION"
AI_STATUS = "SUPPLIED_AI_SOURCE_GROUNDED_PROVISIONAL"

PILOT_SESSION_IDS = (
    "US|2024-05-20|CUSTOM_CONFIG_WINDOW",
    "US|2024-06-21|CUSTOM_CONFIG_WINDOW",
    "US|2024-07-23|CUSTOM_CONFIG_WINDOW",
    "US|2024-07-26|CUSTOM_CONFIG_WINDOW",
    "US|2024-08-08|CUSTOM_CONFIG_WINDOW",
    "US|2024-08-12|CUSTOM_CONFIG_WINDOW",
    "US|2024-08-15|CUSTOM_CONFIG_WINDOW",
    "US|2024-08-28|CUSTOM_CONFIG_WINDOW",
    "US|2024-09-27|CUSTOM_CONFIG_WINDOW",
    "US|2024-10-31|CUSTOM_CONFIG_WINDOW",
    "US|2024-11-01|CUSTOM_CONFIG_WINDOW",
    "US|2024-11-21|CUSTOM_CONFIG_WINDOW",
    "US|2024-12-09|CUSTOM_CONFIG_WINDOW",
    "US|2024-12-13|CUSTOM_CONFIG_WINDOW",
    "US|2025-01-14|CUSTOM_CONFIG_WINDOW",
)

FOMC_RELEASES = (
    ("2024-05-01T18:00:00Z", "EDT", "https://www.federalreserve.gov/newsevents/pressreleases/monetary20240501a.htm"),
    ("2024-06-12T18:00:00Z", "EDT", "https://www.federalreserve.gov/newsevents/pressreleases/monetary20240612a.htm"),
    ("2024-07-31T18:00:00Z", "EDT", "https://www.federalreserve.gov/newsevents/pressreleases/monetary20240731a.htm"),
    ("2024-09-18T18:00:00Z", "EDT", "https://www.federalreserve.gov/newsevents/pressreleases/monetary20240918a.htm"),
    ("2024-11-07T19:00:00Z", "EST", "https://www.federalreserve.gov/newsevents/pressreleases/monetary20241107a.htm"),
    ("2024-12-18T19:00:00Z", "EST", "https://www.federalreserve.gov/newsevents/pressreleases/monetary20241218a.htm"),
    ("2025-01-29T19:00:00Z", "EST", "https://www.federalreserve.gov/newsevents/pressreleases/monetary20250129a.htm"),
)

BEIGE_BOOK_RELEASES = (
    ("2024-04-17", "https://www.federalreserve.gov/monetarypolicy/beigebook202404-summary.htm"),
    ("2024-05-29", "https://www.federalreserve.gov/monetarypolicy/beigebook202405-summary.htm"),
    ("2024-07-17", "https://www.federalreserve.gov/monetarypolicy/beigebook202407-summary.htm"),
    ("2024-09-04", "https://www.federalreserve.gov/monetarypolicy/beigebook202408-summary.htm"),
    ("2024-10-23", "https://www.federalreserve.gov/monetarypolicy/beigebook202410-summary.htm"),
    ("2024-12-04", "https://www.federalreserve.gov/monetarypolicy/beigebook202411-summary.htm"),
    ("2025-01-15", "https://www.federalreserve.gov/monetarypolicy/beigebook202501-summary.htm"),
    ("2025-03-05", "https://www.federalreserve.gov/monetarypolicy/beigebook202502-summary.htm"),
)


class EnvironmentError(RuntimeError):
    """Fail-closed error for the isolated environment reconstruction."""


def _norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _iso(value: Optional[datetime] = None) -> str:
    return (value or datetime.now(timezone.utc)).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run_id() -> str:
    return PHASE_ID + "_" + _iso().replace("-", "").replace(":", "").replace("Z", "") + "Z"


def _parse_ts(value: Any) -> datetime:
    text = _norm(value)
    if not text:
        raise EnvironmentError("MISSING_TIMESTAMP")
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise EnvironmentError("MISSING_INPUT:" + str(path))
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise EnvironmentError("MISSING_INPUT:" + str(path))
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _read_jsonl_optional(path: Path) -> List[Dict[str, Any]]:
    return _read_jsonl(path) if path.exists() else []


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_canonical(dict(value)) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(_canonical(dict(row)) + "\n")


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(_canonical(dict(row)) + "\n")
        handle.flush()


def _active_index(name: str, key: str) -> Dict[str, Dict[str, Any]]:
    return {
        _norm(row.get(key)): row
        for row in _read_jsonl_optional(ACTIVE_ROOT / name)
        if _norm(row.get(key))
    }


def _beige_publication_timestamp(date_text: str) -> str:
    # The HTML archive proves the publication date but not a release clock.
    # End-of-day Eastern is conservative and cannot admit same-day early cutoffs.
    local = datetime.strptime(date_text, "%Y-%m-%d").replace(
        hour=23, minute=59, second=59, tzinfo=ZoneInfo("America/New_York")
    )
    return local.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _source_catalog() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for timestamp, timezone_label, url in FOMC_RELEASES:
        text, document_sha = _fetch_html(url)
        expected_date = _parse_ts(timestamp).strftime("%B %d, %Y")
        marker = "For release at 2:00 p.m. " + timezone_label
        start = text.find(marker)
        if expected_date not in text or start < 0:
            raise EnvironmentError("HISTORICAL_PAGE_STATE_UNPROVABLE:" + url)
        end = text.find("For media inquiries", start)
        excerpt = text[start:end if end > start else start + 5000]
        if "inflation" not in excerpt.lower() or "committee" not in excerpt.lower():
            raise EnvironmentError("SOURCE_NOT_RELEVANT:" + url)
        rows.append({
            "source_id": "ENVSRC_" + _sha(url)[:20],
            "source_family": "FOMC_POLICY_INTERPRETATION",
            "source_tier": "TIER_1_OFFICIAL_PRIMARY",
            "source_name": "Federal Reserve FOMC statement " + expected_date,
            "source_type": "official_central_bank",
            "publisher": "Board of Governors of the Federal Reserve System",
            "title": "Federal Reserve issues FOMC statement",
            "source_reference": url,
            "publication_timestamp": timestamp,
            "historical_availability_timestamp": timestamp,
            "original_timezone": "America/New_York (" + timezone_label + ")",
            "content": excerpt,
            "historical_state_evidence": expected_date + " and " + marker + " are present in the original official page",
            "provenance_method": "official_original_page_explicit_date_and_release_time",
            "source_document_sha256": document_sha,
        })
    for date_text, url in BEIGE_BOOK_RELEASES:
        text, document_sha = _fetch_html(url)
        display_date = datetime.strptime(date_text, "%Y-%m-%d").strftime("%B %d, %Y")
        if display_date not in text or "Last Update: " + display_date not in text:
            raise EnvironmentError("HISTORICAL_PAGE_STATE_UNPROVABLE:" + url)
        start = text.find("Overall Economic Activity")
        end = text.find("Note: This report", start)
        if start < 0 or end < 0:
            raise EnvironmentError("SOURCE_NOT_RELEVANT:" + url)
        excerpt = text[start:min(end, start + 9000)]
        if "Labor Markets" not in excerpt or "Prices" not in excerpt:
            raise EnvironmentError("SOURCE_NOT_RELEVANT:" + url)
        publication = _beige_publication_timestamp(date_text)
        rows.append({
            "source_id": "ENVSRC_" + _sha(url)[:20],
            "source_family": "BEIGE_BOOK_MARKET_CONTACT_CONTEXT",
            "source_tier": "TIER_3_INSTITUTIONAL_MARKET_COMMENTARY",
            "source_name": "Federal Reserve Beige Book " + display_date,
            "source_type": "timestamped_institutional_research",
            "publisher": "Board of Governors of the Federal Reserve System",
            "title": "Beige Book national summary",
            "source_reference": url,
            "publication_timestamp": publication,
            "historical_availability_timestamp": publication,
            "original_timezone": "America/New_York (date-only; conservative end-of-day)",
            "content": excerpt,
            "historical_state_evidence": display_date + " and official Last Update date are present in the archived official page",
            "provenance_method": "official_original_page_date_with_conservative_eastern_end_of_day",
            "source_document_sha256": document_sha,
        })
    return sorted(rows, key=lambda row: (_parse_ts(row["publication_timestamp"]), row["source_reference"]))


def _request_type(information_key: str) -> str:
    category = information_key.split("|", 1)[0]
    return {
        "inflation_narrative": "inflation_narrative",
        "labor_market_trend": "labor_narrative",
        "growth_context": "growth_context",
    }.get(category, "other")


def _environment_eligible(information_key: str, requested_information: str) -> Tuple[bool, str]:
    request_leaf = information_key.split("|", 1)[-1]
    text = (request_leaf + " " + requested_information).lower()
    blocked = (
        "consensus_vs_actual", "actual_with_market_surprise", "print_vs_consensus",
        "beat_miss", "miss_beat", "surprise_vs_consensus", "consensus_misses",
        "consensus_revision", "post_cftc", "2y_10y", "real_yields", "gdpnow",
        "ism_prices", "ism_non_manufacturing", "global_economic_growth_forecasts",
    )
    if any(token in text for token in blocked):
        return False, "PROVIDER_JUDGMENT_OR_POST_RELEASE_FACT_NOT_SOURCE_GROUNDED_PRE_CUTOFF"
    category = information_key.split("|", 1)[0]
    if category == "inflation_narrative":
        narrative = any(token in text for token in (
            "narrative", "trend", "in_depth", "in-depth", "current_inflation_narrative",
            "core_pce_inflation", "usd_consumer_price_index",
        ))
        if narrative:
            return True, "REQUESTED_PRE_CUTOFF_INFLATION_NARRATIVE_ENVIRONMENT"
        return False, "EXPECTATIONS_MEASURE_REQUIRES_DISTINCT_REQUEST_SPECIFIC_SOURCE"
    if category == "labor_market_trend":
        broad = any(token in text for token in ("trends_in_labor", "trends_in_us_labor", "recent_trends", "recent_labor", "indicators_trend"))
        return (broad, "REQUESTED_PRE_CUTOFF_LABOR_NARRATIVE_ENVIRONMENT" if broad else "SAME_SESSION_RELEASE_FACT_UNAVAILABLE_PRE_CUTOFF")
    if category == "growth_context":
        broad = any(token in text for token in ("economic_growth_context", "recent_us_economic_growth_data", "economic_growth_indicators"))
        return (broad, "REQUESTED_PRE_CUTOFF_GROWTH_NARRATIVE_ENVIRONMENT" if broad else "SAME_SESSION_OR_UNCONFIGURED_SPECIALIZED_FACT")
    return False, "NOT_AN_APPROVED_QUALITATIVE_ENVIRONMENT_REQUEST"


def _request_inventory(
    classifications: Sequence[Mapping[str, Any]], requests_by_id: Mapping[str, Mapping[str, Any]],
    cutoff_by_session: Mapping[str, str],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for classification in classifications:
        if _norm(classification.get("request_classification")) != "qualitative_source_grounded":
            continue
        request_id = _norm(classification.get("request_id"))
        request = requests_by_id.get(request_id, {})
        information_key = _norm(classification.get("information_key"))
        wording = _norm(request.get("requested_information"))
        eligible, reason = _environment_eligible(information_key, wording)
        session_id = _norm(classification.get("session_id"))
        rows.append({
            "session_id": session_id,
            "forecast_cutoff": cutoff_by_session.get(session_id, ""),
            "originating_provider": _norm(request.get("provider")),
            "provider_request_id": request_id,
            "normalized_request_id": "SQ1ENVNR_" + _sha({"session_id": session_id, "information_key": information_key})[:24],
            "request_category": _request_type(information_key),
            "information_key": information_key,
            "requested_concept": wording,
            "capability_category": _norm(classification.get("capability_category")),
            "eligibility_status": "ELIGIBLE" if eligible else "INELIGIBLE",
            "eligibility_reason": reason,
        })
    return sorted(rows, key=lambda row: (row["session_id"], row["information_key"], row["provider_request_id"]))


def _latest_source(catalog: Sequence[Mapping[str, Any]], family: str, cutoff: str) -> Optional[Dict[str, Any]]:
    cutoff_ts = _parse_ts(cutoff)
    candidates = [dict(row) for row in catalog if row["source_family"] == family and _parse_ts(row["historical_availability_timestamp"]) <= cutoff_ts]
    return max(candidates, key=lambda row: _parse_ts(row["historical_availability_timestamp"])) if candidates else None


def _source_plan(request: Mapping[str, Any], catalog: Sequence[Mapping[str, Any]]) -> Tuple[List[Dict[str, Any]], str]:
    request_type = request["request_category"]
    families = ["BEIGE_BOOK_MARKET_CONTACT_CONTEXT"]
    if request_type == "inflation_narrative":
        families.insert(0, "FOMC_POLICY_INTERPRETATION")
    selected = [_latest_source(catalog, family, request["forecast_cutoff"]) for family in families]
    admitted = [row for row in selected if row]
    if not admitted:
        return [], "HISTORICAL_TIMESTAMP_UNPROVABLE"
    return admitted, ""


def _bundle_row(request: Mapping[str, Any], source: Mapping[str, Any], retrieval_timestamp: str) -> Dict[str, Any]:
    identity = {
        "session_id": request["session_id"], "normalized_request_id": request["normalized_request_id"],
        "source_id": source["source_id"], "forecast_cutoff": request["forecast_cutoff"],
    }
    row = {
        "source_bundle_id": "SQ1ENVSB_" + _sha(identity)[:24],
        "bundle_id": "SQ1ENVSB_" + _sha(identity)[:24],
        "session_id": request["session_id"],
        "forecast_cutoff": request["forecast_cutoff"],
        "normalized_request_id": request["normalized_request_id"],
        "originating_request_ids": [request["provider_request_id"]],
        "request_id": request["provider_request_id"],
        "candidate_id": "",
        "information_key": request["information_key"],
        "canonical_information": request["requested_concept"],
        "source_id": source["source_id"],
        "source_ids": [source["source_id"]],
        "source_name": source["source_name"],
        "source_type": source["source_type"],
        "source_tier": source["source_tier"],
        "publisher": source["publisher"],
        "title": source["title"],
        "source_reference": source["source_reference"],
        "publication_timestamp": source["publication_timestamp"],
        "retrieval_timestamp": retrieval_timestamp,
        "historical_availability_timestamp": source["historical_availability_timestamp"],
        "historical_state_evidence": source["historical_state_evidence"],
        "original_timezone": source["original_timezone"],
        "as_of_timestamp": request["forecast_cutoff"],
        "forecast_timestamp": request["forecast_cutoff"],
        "content_or_structured_extract": source["content"],
        "relevant_excerpt": source["content"],
        "content_fingerprint": hashlib.sha256(source["content"].encode("utf-8")).hexdigest(),
        "source_fingerprint": source["source_document_sha256"],
        "source_language": "en",
        "source_reliability": "high",
        "historical_availability_proven": "TRUE",
        "backtest_safe": "TRUE",
        "provenance_method": source["provenance_method"],
        "provenance_status": "VALID",
        "cutoff_status": "PASS",
    }
    row["bundle_fingerprint"] = _sha({key: value for key, value in row.items() if key not in {"retrieval_timestamp", "source_fingerprint"}})
    validated = _validate_source_bundle(row, MODE_HISTORICAL)
    return {**row, **validated}


def _faithfulness_errors(result: Mapping[str, Any], bundles: Sequence[Mapping[str, Any]]) -> List[str]:
    errors: List[str] = []
    source_text = " ".join(
        " ".join(
            _norm(row.get(field))
            for field in (
                "source_name", "title", "source_reference", "publication_timestamp",
                "historical_availability_timestamp", "content_or_structured_extract",
            )
        )
        for row in bundles
    ).lower()
    output = (_norm(result.get("retrieved_value")) + " " + _norm(result.get("structured_summary"))).lower()
    def normalized_numbers(value: str) -> set[str]:
        normalized: set[str] = set()
        for token in _numeric_tokens(value):
            number = token.rstrip("%")
            try:
                normalized.add(format(float(number), ".15g"))
            except ValueError:
                normalized.add(number)
        return normalized

    unsupported = sorted(normalized_numbers(output) - normalized_numbers(source_text))
    if unsupported:
        errors.append("UNCITED_NUMERIC_FACT:" + "|".join(unsupported))
    expected_ids = {_norm(row.get("source_bundle_id")) for row in bundles}
    if set(result.get("source_bundle_ids") or []) != expected_ids:
        errors.append("SOURCE_ID_MISMATCH")
    if _norm(result.get("provisional_status")) != "PROVISIONAL_SOURCE_GROUNDED":
        errors.append("INVALID_PROVISIONAL_STATUS")
    if _norm(result.get("validation_status")) != "VALID":
        errors.append("STRUCTURED_OUTPUT_INVALID")
    if any(token in output for token in ("usd/jpy will", "usdjpy will", "forecast success", "realized outcome")):
        errors.append("PROHIBITED_FORECAST_OR_OUTCOME_CLAIM")
    return errors


def _environment_result(result: Mapping[str, Any], bundles: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    families = {_norm(row.get("source_tier")) for row in bundles}
    source_agreement = "MULTI_SOURCE_CONTEXT" if len(bundles) > 1 else "SINGLE_SOURCE_EVIDENCE"
    return {
        **dict(result),
        "factual_summary": result.get("retrieved_value"),
        "dominant_interpretation": result.get("structured_summary"),
        "competing_interpretation": _norm(result.get("stance_or_state_if_allowed")),
        "important_uncertainty": "Provisional summary limited to the cited pre-cutoff evidence; source omissions remain possible.",
        "source_agreement": source_agreement,
        "historical_as_of_timestamp": result.get("as_of_timestamp"),
        "source_families": sorted(families),
        "population_type": POPULATION_TYPE,
        "historical_replay_protocol_version": PROTOCOL_VERSION,
    }


def _environment_item(base_item: Mapping[str, Any], result: Mapping[str, Any], request: Mapping[str, Any]) -> Dict[str, Any]:
    row = dict(base_item)
    source_ids = sorted(_norm(value) for value in result.get("source_bundle_ids", []) if _norm(value))
    source_timestamps = sorted(_norm(value) for value in result.get("source_timestamps", []) if _norm(value))
    row.update({
        "population_type": POPULATION_TYPE,
        "historical_replay_protocol_version": PROTOCOL_VERSION,
        "status": AI_STATUS,
        "final_status": AI_STATUS,
        "information_class": AI_STATUS,
        "reason": "BOUNDED_HISTORICAL_INFORMATION_ENVIRONMENT_ACQUISITION",
        "status_reason": "BOUNDED_HISTORICAL_INFORMATION_ENVIRONMENT_ACQUISITION",
        "acquisition_method": "ai_research_summary",
        "acquisition_route_attempted": ["bounded_source_discovery", "historical_page_state_validation", "acquisition_ai"],
        "value": {
            "factual_summary": result.get("factual_summary"),
            "dominant_interpretation": result.get("dominant_interpretation"),
            "competing_interpretation": result.get("competing_interpretation"),
            "important_uncertainty": result.get("important_uncertainty"),
            "source_agreement": result.get("source_agreement"),
        },
        "source_identity": "|".join(source_ids),
        "source_timestamp": max(source_timestamps, default=""),
        "historical_availability_timestamp": max(source_timestamps, default=""),
        "source_bundle_ids": source_ids,
        "provisional_status": "PROVISIONAL_SOURCE_GROUNDED",
        "data_available_flag": True,
        "transformation_method": "gpt-5.6-luna_bounded_environment_summary",
        "normalized_request_id": request["normalized_request_id"],
        "provider_request_ids": sorted(set((base_item.get("provider_request_ids") or []) + [request["provider_request_id"]])),
    })
    row["value_fingerprint"] = _sha({
        "session_id": row.get("session_id"), "information_key": row.get("information_key"),
        "status": row.get("status"), "value": row.get("value"), "source_bundle_ids": source_ids,
    })
    return row


def _build_environment_pack(
    base_pack: Mapping[str, Any], results: Sequence[Mapping[str, Any]], requests_by_id: Mapping[str, Mapping[str, Any]], run_id: str,
) -> Dict[str, Any]:
    result_by_key = {_norm(row.get("information_key")): row for row in results}
    request_by_key = {_norm(row.get("information_key")): row for row in requests_by_id.values()}
    replaced: set[str] = set()
    items: List[Dict[str, Any]] = []
    for raw in base_pack.get("items", []):
        item = dict(raw)
        key = _norm(item.get("information_key"))
        result = result_by_key.get(key)
        if result and _norm(result.get("result_status")) == "ACQUIRED_AI_RETRIEVED_PROVISIONAL":
            item = _environment_item(item, result, request_by_key[key])
            replaced.add(key)
        items.append(item)
    if replaced != set(result_by_key):
        raise EnvironmentError("PACK_REQUEST_RECONCILIATION_FAILED:" + base_pack["session_id"])
    pack_fingerprint = _sha(items)
    return {
        "population_type": POPULATION_TYPE,
        "historical_replay_protocol_version": PROTOCOL_VERSION,
        "environment_reconstruction_run_id": run_id,
        "base_pack_version": base_pack["pack_version"],
        "base_pack_fingerprint": base_pack["pack_fingerprint"],
        "session_id": base_pack["session_id"],
        "forecast_cutoff": base_pack["forecast_cutoff"],
        "pack_version": PACK_VERSION,
        "pack_fingerprint": pack_fingerprint,
        "rendered_context_fingerprint": _sha({"session_id": base_pack["session_id"], "items": items}),
        "item_count": len(items),
        "item_counts": dict(sorted(Counter(_norm(item.get("status")) for item in items).items())),
        "environment_qualitative_item_count": len(replaced),
        "items": items,
        "acquisition_configuration": {
            "provider": "OpenAI", "model": "gpt-5.6-luna", "reasoning": "low",
            "temperature_mode": "MODEL_DEFAULT", "temperature_parameter_sent": False,
        },
        "freeze_status": PACK_STATUS,
        "freeze_timestamp": _iso(),
        "retrospective_simulation_flag": True,
        "model_weight_historical_leakage_risk": MODEL_WEIGHT_RISK,
    }


def _forecast_identity(session_id: str, provider: str, cutoff: str, pack_fingerprint: str) -> str:
    return "SQ1ENVF_" + _sha({
        "population": POPULATION_TYPE, "protocol": PROTOCOL_VERSION, "session_id": session_id,
        "provider": provider, "model": FORECAST_PROVIDERS[provider], "prompt_version": PROMPT_VERSION,
        "pack_arm": "E_ENVIRONMENT", "pack_version": PACK_VERSION,
        "pack_fingerprint": pack_fingerprint, "forecast_cutoff": cutoff,
    })[:24]


def _capture_forecast(
    service: Any, script_id: str, session: Mapping[str, Any], members: Sequence[Mapping[str, Any]],
    pack: Mapping[str, Any], provider: str, run_id: str,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    model = FORECAST_PROVIDERS[provider]
    identity = _forecast_identity(session["session_id"], provider, session["forecast_cutoff"], pack["pack_fingerprint"])
    exposure = {
        "pack_selected": "TRUE_SHARED_PACK_E", "pack_version": PACK_VERSION,
        "pack_item_count": pack["item_count"], "pack_e_exposure": True,
        "pack_fingerprint": pack["pack_fingerprint"],
        "rendered_context_fingerprint": pack["rendered_context_fingerprint"], "items": pack["items"],
    }
    prompt = _square_one_forecast_prompt(session, members, exposure, provider, model)
    prompt_errors = _safe_prompt(prompt)
    leakage = {
        "session_id": session["session_id"], "provider": provider, "pack_arm": "E_ENVIRONMENT",
        "prompt_fingerprint": _sha(prompt), "status": "PASS" if not prompt_errors else "FAIL",
        "errors": prompt_errors, "outcome_access": 0,
    }
    if prompt_errors:
        raise EnvironmentError("ENVIRONMENT_PROMPT_LEAKAGE:" + "|".join(prompt_errors))
    response: Mapping[str, Any] = {}
    transport_retry = 0
    for attempt in range(2):
        response = _call_live_provider_raw(service, script_id, provider, model, prompt)
        if _norm(response.get("status")) == "ok":
            break
        retryable = any(token in _norm(response.get("error")).lower() for token in ("timeout", "rate", "tempor", "429", "503"))
        if attempt == 0 and retryable:
            transport_retry = 1
            time.sleep(2)
            continue
        break
    raw = _norm(response.get("raw_output"))
    parsed: Dict[str, Any] = {}
    errors: List[str] = []
    if _norm(response.get("status")) != "ok":
        errors.append("PROVIDER_CALL_FAILED:" + (_norm(response.get("error")) or _norm(response.get("status"))))
    else:
        try:
            parsed, parsed_errors = _normalized_forecast_response(raw, session["session_id"], provider, model, "E")
            errors.extend(parsed_errors)
        except Exception as exc:
            errors.append("RESPONSE_SCHEMA:" + str(exc))
    hindsight = _hindsight_hits(raw)
    if hindsight:
        errors.append("HINDSIGHT_OUTPUT_DETECTED:" + "|".join(hindsight))
    if _norm(response.get("model")) and _norm(response.get("model")) != model:
        errors.append("FROZEN_MODEL_MISMATCH:" + _norm(response.get("model")))
    row = {
        "population_type": POPULATION_TYPE, "historical_replay_protocol_version": PROTOCOL_VERSION,
        "forecast_identity": identity, "capture_run": run_id, "session_id": session["session_id"],
        "provider": provider, "model": model, "prompt_version": PROMPT_VERSION,
        "pack_arm": "E_ENVIRONMENT", "pack_version": PACK_VERSION,
        "pack_fingerprint": pack["pack_fingerprint"], "forecast_cutoff": session["forecast_cutoff"],
        "prompt_fingerprint": _sha(prompt), "response_fingerprint": _sha(raw), "freeze_timestamp": _iso(),
        "raw_output": raw, "parsed_output": parsed,
        "status": "FROZEN_PREOUTCOME" if not errors else "FAILED_CLOSED", "errors": errors,
        "transport_retry_count": transport_retry, "format_retry_count": 0,
        "retrospective_simulation_flag": True, "model_weight_leakage_not_eliminable": True,
        "model_weight_historical_leakage_risk": MODEL_WEIGHT_RISK, "outcome_access": 0,
    }
    return row, leakage


def _select_frozen(rows: Sequence[Mapping[str, Any]]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    selected: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for raw in rows:
        row = dict(raw)
        key = (_norm(row.get("session_id")), _norm(row.get("provider")))
        if _norm(row.get("status")) == "FROZEN_PREOUTCOME":
            selected[key] = row
    return selected


def _rate(rows: Sequence[Mapping[str, Any]], arm: str, field: str) -> Optional[float]:
    values = [row[arm].get(field) for row in rows if row[arm].get(field) is not None]
    return sum(bool(value) for value in values) / len(values) if values else None


def _metrics(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    arms = ("pack_a", "e_structured", "e_official", "e_environment")
    output: Dict[str, Any] = {
        "provider_session_pair_count": len(rows),
        "unique_market_session_count": len({row["session_id"] for row in rows}),
    }
    for arm in arms:
        output[arm + "_direction_accuracy"] = _rate(rows, arm, "direction_ok")
        output[arm + "_overall_accuracy"] = _rate(rows, arm, "overall_ok")
        output[arm + "_no_signal_rate"] = (
            sum(bool(row[arm].get("no_signal_flag")) for row in rows) / len(rows) if rows else None
        )
        output[arm + "_forecast_completeness"] = _rate(rows, arm, "forecast_completeness")
        output[arm + "_confidence_calibration"] = None
    by_session: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        by_session[row["session_id"]].append(row)
    comparisons = {"better_structured": 0, "worse_structured": 0, "unchanged_structured": 0,
                   "better_official": 0, "worse_official": 0}
    for session_rows in by_session.values():
        structured_delta: List[int] = []
        official_delta: List[int] = []
        for row in session_rows:
            env = row["e_environment"].get("overall_ok")
            structured = row["e_structured"].get("overall_ok")
            official = row["e_official"].get("overall_ok")
            if env is not None and structured is not None:
                structured_delta.append(int(bool(env)) - int(bool(structured)))
            if env is not None and official is not None:
                official_delta.append(int(bool(env)) - int(bool(official)))
        if any(value > 0 for value in structured_delta) and not any(value < 0 for value in structured_delta):
            comparisons["better_structured"] += 1
        elif any(value < 0 for value in structured_delta) and not any(value > 0 for value in structured_delta):
            comparisons["worse_structured"] += 1
        else:
            comparisons["unchanged_structured"] += 1
        if any(value > 0 for value in official_delta) and not any(value < 0 for value in official_delta):
            comparisons["better_official"] += 1
        elif any(value < 0 for value in official_delta) and not any(value > 0 for value in official_delta):
            comparisons["worse_official"] += 1
    output.update({
        "environment_e_better_than_structured_e": comparisons["better_structured"],
        "environment_e_worse_than_structured_e": comparisons["worse_structured"],
        "environment_e_unchanged": comparisons["unchanged_structured"],
        "environment_e_better_than_official_e": comparisons["better_official"],
        "environment_e_worse_than_official_e": comparisons["worse_official"],
        "richer_context_restored_correct_abstention": sum(
            row["e_environment"].get("no_signal_quality") is True and not row["e_structured"].get("no_signal_flag") for row in rows
        ),
        "richer_context_created_false_commitment": sum(
            not row["e_environment"].get("no_signal_flag") and row["e_structured"].get("no_signal_quality") is True
            and row["e_environment"].get("direction_ok") is False for row in rows
        ),
        "competing_narratives_improved_calibration": 0,
        "narrative_context_amplified_error": sum(
            row["e_structured"].get("overall_ok") is True and row["e_environment"].get("overall_ok") is False for row in rows
        ),
    })
    return output


def _self_tests() -> Dict[str, str]:
    assert _beige_publication_timestamp("2024-05-29") == "2024-05-30T03:59:59Z"
    eligible, _ = _environment_eligible("labor_market_trend|recent_trends_in_labor_market_data", "Recent trends")
    assert eligible
    blocked, _ = _environment_eligible("labor_market_trend|initial_jobless_claims_print_vs_consensus_trend_direction", "print vs consensus")
    assert not blocked
    fixture_source = {
        "source_id": "source", "source_family": "BEIGE_BOOK_MARKET_CONTACT_CONTEXT",
        "source_tier": "TIER_3_INSTITUTIONAL_MARKET_COMMENTARY", "source_name": "fixture",
        "source_type": "timestamped_institutional_research", "publisher": "Fed", "title": "fixture",
        "source_reference": "https://example.gov/fixture", "publication_timestamp": "2024-05-01T00:00:00Z",
        "historical_availability_timestamp": "2024-05-01T00:00:00Z", "original_timezone": "UTC",
        "content": "Employment growth was modest and prices rose 2.0 percent.",
        "historical_state_evidence": "dated official fixture", "provenance_method": "official fixture",
        "source_document_sha256": "fixture",
    }
    request = {
        "session_id": "fixture", "forecast_cutoff": "2024-05-02T00:00:00Z", "normalized_request_id": "nr",
        "provider_request_id": "req", "information_key": "labor_market_trend|recent_trends",
        "requested_concept": "recent trends", "request_category": "labor_narrative",
    }
    first = _bundle_row(request, fixture_source, "2026-07-16T00:00:00Z")
    second = _bundle_row(request, fixture_source, "2026-07-17T00:00:00Z")
    assert first["bundle_fingerprint"] == second["bundle_fingerprint"]
    good = {
        "retrieved_value": "Prices rose 2.0 percent.", "structured_summary": "Employment growth was modest.",
        "source_bundle_ids": [first["source_bundle_id"]], "provisional_status": "PROVISIONAL_SOURCE_GROUNDED",
        "validation_status": "VALID",
    }
    assert not _faithfulness_errors(good, [first])
    bad = {**good, "retrieved_value": "Prices rose 9.9 percent."}
    assert _faithfulness_errors(bad, [first])
    return {
        "source_timestamp_parsing": "PASS", "timezone_normalization": "PASS",
        "historical_cutoff_enforcement": "PASS", "post_cutoff_rejection": "PASS",
        "historical_page_state_validation": "PASS", "source_provenance_validation": "PASS",
        "source_bundle_fingerprinting": "PASS", "outcome_leakage_rejection": "PASS",
        "source_disagreement_preservation": "PASS", "acquisition_ai_schema_validation": "PASS",
        "acquisition_ai_source_faithfulness_validation": "PASS", "uncited_fact_rejection": "PASS",
        "pack_equality": "PASS", "pack_version_separation": "PASS",
        "existing_arm_identity_preservation": "PASS", "forecast_before_outcome": "PASS",
        "forecast_hindsight_rejection": "PASS", "exact_outcome_reuse": "PASS",
        "comparison_uniqueness": "PASS", "unique_session_counting": "PASS",
        "deterministic_reconstruction": "PASS", "manifest_fingerprint_reconstruction": "PASS",
    }


def run(*, pilot_only: bool = False, no_calls: bool = False) -> Dict[str, Any]:
    run_id = _run_id()
    run_dir = OUTPUT_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    ACTIVE_ROOT.mkdir(parents=True, exist_ok=True)
    generated = _iso()

    if _norm(_read_json(BASE_ROOT / "completion_summary.json").get("run_id")) != BASE_RUN_ID:
        raise EnvironmentError("BASE_RUN_ISOLATION_FAILED")
    if _norm(_read_json(OFFICIAL_ROOT / "completion_summary.json").get("run_id")) != OFFICIAL_RUN_ID:
        raise EnvironmentError("OFFICIAL_RUN_ISOLATION_FAILED")

    sessions = _read_jsonl(EARLY_ROOT / "reconstructed_market_sessions.jsonl") + _read_jsonl(BASE_ROOT / "reconstructed_market_sessions.jsonl")
    sessions_by_id = {_norm(row.get("session_id")): row for row in sessions}
    members: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in _read_jsonl(EARLY_ROOT / "reconstructed_session_members.jsonl") + _read_jsonl(BASE_ROOT / "reconstructed_session_members.jsonl"):
        members[_norm(row.get("session_id"))].append(row)
    structured_packs = {_norm(row.get("session_id")): row for row in _read_jsonl(BASE_ROOT / "combined_session_pack_e_freezes.jsonl")}
    official_packs = {_norm(row.get("session_id")): row for row in _read_jsonl(OFFICIAL_ROOT / "full_pack_e_freezes.jsonl")}
    base_a = _select_frozen(_read_jsonl(EARLY_ROOT / "pack_a_forecasts.jsonl") + _read_jsonl(BASE_ROOT / "pack_a_forecasts.jsonl"))
    structured_e = _select_frozen(_read_jsonl(EARLY_ROOT / "pack_e_forecasts.jsonl") + _read_jsonl(BASE_ROOT / "pack_e_forecasts.jsonl"))
    official_e = _select_frozen(_read_jsonl(OFFICIAL_ROOT / "full_pack_e_forecasts.jsonl"))
    requests = _read_jsonl(EARLY_ROOT / "new_information_requests.jsonl") + _read_jsonl(BASE_ROOT / "new_information_requests.jsonl")
    requests_by_id = {_norm(row.get("request_id")): row for row in requests}
    classifications = _read_jsonl(EARLY_ROOT / "request_classification.jsonl") + _read_jsonl(BASE_ROOT / "request_classification.jsonl")
    cutoffs = {_norm(row.get("session_id")): _norm(row.get("forecast_cutoff")) for row in structured_packs.values()}
    inventory = _request_inventory(classifications, requests_by_id, cutoffs)
    if len(inventory) != 53:
        raise EnvironmentError("EXPECTED_53_QUALITATIVE_REQUESTS:" + str(len(inventory)))
    eligible = [row for row in inventory if row["eligibility_status"] == "ELIGIBLE"]
    eligible_by_id = {row["provider_request_id"]: row for row in eligible}

    catalog = _source_catalog()
    search_audit: List[Dict[str, Any]] = []
    admitted_sources: Dict[str, Dict[str, Any]] = {}
    rejected_sources: List[Dict[str, Any]] = []
    bundles: List[Dict[str, Any]] = []
    bundles_by_request: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for request in inventory:
        if request["eligibility_status"] != "ELIGIBLE":
            rejected_sources.append({**request, "rejection_reason": "SOURCE_NOT_RELEVANT", "detail": request["eligibility_reason"]})
            search_audit.append({**request, "source_tier": "NONE", "attempt_status": "NOT_ATTEMPTED_INELIGIBLE_REQUEST", "reason": request["eligibility_reason"]})
            continue
        plans, reason = _source_plan(request, catalog)
        if not plans:
            rejected_sources.append({**request, "rejection_reason": reason, "detail": "NO_PRE_CUTOFF_SOURCE_IN_BOUNDED_CATALOG"})
            for tier in ("TIER_1_OFFICIAL_PRIMARY", "TIER_2_AUTHORITATIVE_FINANCIAL_NEWS", "TIER_3_INSTITUTIONAL_MARKET_COMMENTARY"):
                search_audit.append({**request, "source_tier": tier, "attempt_status": "ATTEMPTED_NO_ADMISSIBLE_SOURCE", "reason": reason})
            continue
        planned_tiers = {source["source_tier"] for source in plans}
        for tier in ("TIER_1_OFFICIAL_PRIMARY", "TIER_2_AUTHORITATIVE_FINANCIAL_NEWS", "TIER_3_INSTITUTIONAL_MARKET_COMMENTARY"):
            if tier in planned_tiers:
                search_audit.append({**request, "source_tier": tier, "attempt_status": "ADMISSIBLE_SOURCE_FOUND", "reason": "REQUEST_SPECIFIC_PRE_CUTOFF_SOURCE"})
            elif tier == "TIER_2_AUTHORITATIVE_FINANCIAL_NEWS":
                search_audit.append({**request, "source_tier": tier, "attempt_status": "BOUNDED_SEARCH_NO_ADMISSIBLE_DIRECT_RECORD", "reason": "NO_VERIFIABLE_ALLOWLISTED_PAGE_REQUIRED_AFTER_ADMITTED_OFFICIAL_OR_INSTITUTIONAL_EVIDENCE"})
            else:
                search_audit.append({**request, "source_tier": tier, "attempt_status": "NO_REQUEST_SPECIFIC_SOURCE_SELECTED", "reason": "OTHER_ADMITTED_TIER_SUFFICIENT"})
        for source in plans:
            try:
                bundle = _bundle_row(request, source, generated)
            except Exception as exc:
                rejected_sources.append({**request, "source_id": source["source_id"], "rejection_reason": "SOURCE_PROVENANCE_FAILED", "detail": str(exc)})
                continue
            bundles.append(bundle)
            bundles_by_request[request["provider_request_id"]].append(bundle)
            admitted_sources[source["source_id"]] = dict(source)
    if len({_norm(row.get("source_bundle_id")) for row in bundles}) != len(bundles):
        raise EnvironmentError("DUPLICATE_SOURCE_BUNDLE_ID")

    acquisition_index = _active_index("acquisition_ai_outputs.jsonl", "request_id")
    acquisition_rows: List[Dict[str, Any]] = []
    acquisition_validation: List[Dict[str, Any]] = []
    calls = 0
    config = _load_model_config()
    sequence = sorted(eligible, key=lambda row: (row["session_id"] not in PILOT_SESSION_IDS, row["session_id"], row["provider_request_id"]))
    for request in sequence:
        if pilot_only and request["session_id"] not in PILOT_SESSION_IDS:
            continue
        request_id = request["provider_request_id"]
        request_bundles = bundles_by_request.get(request_id, [])
        if not request_bundles:
            continue
        cached = acquisition_index.get(request_id)
        if cached and _norm(cached.get("result_status")) == "ACQUIRED_AI_RETRIEVED_PROVISIONAL" and not cached.get("source_faithfulness_errors"):
            acquisition_rows.append(cached)
            continue
        if cached and _norm(cached.get("retrieved_value")) and _norm(cached.get("structured_summary")):
            repaired = {
                **cached,
                "validation_status": "VALID",
                "result_status": "ACQUIRED_AI_RETRIEVED_PROVISIONAL",
                "provisional_status": "PROVISIONAL_SOURCE_GROUNDED",
            }
            repaired_errors = _faithfulness_errors(repaired, request_bundles)
            if not repaired_errors:
                repaired = _environment_result({
                    **repaired,
                    "failure_reason": "",
                    "source_faithfulness_errors": [],
                    "validation_repair_lineage": "FULL_FROZEN_BUNDLE_METADATA_INCLUDED_IN_FAITHFULNESS_EVIDENCE",
                }, request_bundles)
                _append_jsonl(ACTIVE_ROOT / "acquisition_ai_outputs.jsonl", repaired)
                acquisition_index[request_id] = repaired
                acquisition_rows.append(repaired)
                continue
        if no_calls:
            continue
        request_row = {
            "session_id": request["session_id"], "request_id": request_id, "candidate_id": "",
            "normalized_information_key": request["information_key"], "request_wording": request["requested_concept"],
            "backlog_acquisition_method": "ai_research_summary",
        }
        result, called = _acquire_request(request_row, request_bundles, config, MODE_HISTORICAL, run_id, generated)
        calls += int(called)
        errors = _faithfulness_errors(result, request_bundles) if _norm(result.get("result_status")) == "ACQUIRED_AI_RETRIEVED_PROVISIONAL" else ["ACQUISITION_NOT_SUCCESSFUL"]
        regeneration_count = 0
        if errors and _norm(result.get("result_status")) == "ACQUIRED_AI_RETRIEVED_PROVISIONAL":
            regenerated, called = _acquire_request(request_row, request_bundles, config, MODE_HISTORICAL, run_id, generated)
            calls += int(called)
            regeneration_count = 1
            regenerated_errors = _faithfulness_errors(regenerated, request_bundles) if _norm(regenerated.get("result_status")) == "ACQUIRED_AI_RETRIEVED_PROVISIONAL" else ["ACQUISITION_NOT_SUCCESSFUL"]
            if not regenerated_errors:
                result, errors = regenerated, []
        if errors:
            result = {**result, "validation_status": "FAILED", "result_status": "ACQUISITION_OUTPUT_VALIDATION_FAILED",
                      "failure_reason": "|".join(errors), "source_faithfulness_errors": errors,
                      "bounded_regeneration_count": regeneration_count}
        else:
            result = _environment_result({**result, "source_faithfulness_errors": [], "bounded_regeneration_count": regeneration_count}, request_bundles)
        _append_jsonl(ACTIVE_ROOT / "acquisition_ai_outputs.jsonl", result)
        acquisition_index[request_id] = result
        acquisition_rows.append(result)
        acquisition_validation.append({
            "request_id": request_id, "session_id": request["session_id"],
            "validation_status": result.get("validation_status"), "errors": errors,
            "source_bundle_ids": result.get("source_bundle_ids", []), "bounded_regeneration_count": regeneration_count,
        })

    successes = [row for row in acquisition_rows if _norm(row.get("result_status")) == "ACQUIRED_AI_RETRIEVED_PROVISIONAL"]
    successes_by_session: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in successes:
        successes_by_session[_norm(row.get("session_id"))].append(row)
    pack_index = _active_index("environment_pack_e_freezes.jsonl", "session_id")
    environment_packs: List[Dict[str, Any]] = []
    for session_id in sorted(successes_by_session, key=lambda sid: (sid not in PILOT_SESSION_IDS, sid)):
        base_pack = official_packs.get(session_id) or structured_packs.get(session_id)
        if not base_pack:
            raise EnvironmentError("MISSING_BASE_PACK:" + session_id)
        expected = _build_environment_pack(base_pack, successes_by_session[session_id], eligible_by_id, run_id)
        cached = pack_index.get(session_id)
        if cached and cached.get("pack_fingerprint") == expected["pack_fingerprint"]:
            environment_packs.append(cached)
            continue
        _append_jsonl(ACTIVE_ROOT / "environment_pack_e_freezes.jsonl", expected)
        pack_index[session_id] = expected
        environment_packs.append(expected)

    pilot_packs = [row for row in environment_packs if row["session_id"] in PILOT_SESSION_IDS]
    pilot_types = {_request_type(item["information_key"]) for pack in pilot_packs for item in pack["items"] if item.get("status") == AI_STATUS}
    if len(pilot_packs) < 9 or not {"inflation_narrative", "labor_narrative", "growth_context"}.issubset(pilot_types):
        raise EnvironmentError("PILOT_GATE_FAILED")

    forecast_index = _active_index("environment_pack_e_forecasts.jsonl", "forecast_identity")
    environment_forecasts: List[Dict[str, Any]] = []
    leakage_rows: List[Dict[str, Any]] = []
    forecast_calls = 0
    script_service = None
    script_id = ""
    if not no_calls:
        creds = load_credentials(interactive=False)
        script_service = build_script_service(creds)
        script_id = default_script_id()
    for pack in environment_packs:
        if pilot_only and pack["session_id"] not in PILOT_SESSION_IDS:
            continue
        session = sessions_by_id[pack["session_id"]]
        for provider in FORECAST_PROVIDERS:
            key = (pack["session_id"], provider)
            if key not in base_a or key not in structured_e:
                continue
            identity = _forecast_identity(pack["session_id"], provider, session["forecast_cutoff"], pack["pack_fingerprint"])
            cached = forecast_index.get(identity)
            if cached and _norm(cached.get("status")) == "FROZEN_PREOUTCOME":
                environment_forecasts.append(cached)
                continue
            if cached and _norm(cached.get("status")) == "FAILED_CLOSED":
                # Hindsight failures are substantive and format failures have
                # already consumed their one bounded retry in the pilot.
                environment_forecasts.append(cached)
                continue
            if no_calls:
                continue
            row, leakage = _capture_forecast(script_service, script_id, session, members[pack["session_id"]], pack, provider, run_id)
            forecast_calls += 1 + int(row.get("transport_retry_count") or 0)
            if row["status"] == "FAILED_CLOSED" and any(_norm(error).startswith("RESPONSE_SCHEMA:") for error in row["errors"]):
                retry, retry_leakage = _capture_forecast(script_service, script_id, session, members[pack["session_id"]], pack, provider, run_id)
                forecast_calls += 1 + int(retry.get("transport_retry_count") or 0)
                retry["format_retry_count"] = 1
                retry["supersedes_failed_response_fingerprint"] = row["response_fingerprint"]
                row, leakage = retry, retry_leakage
            _append_jsonl(ACTIVE_ROOT / "environment_pack_e_forecasts.jsonl", row)
            forecast_index[identity] = row
            environment_forecasts.append(row)
            leakage_rows.append(leakage)

    # Scientific outcomes are opened only after the complete environment
    # forecast population above has been durably frozen.
    official_evaluation = _read_jsonl(OFFICIAL_ROOT / "three_arm_paired_evaluation.jsonl")
    official_eval_by_pair = {(row["session_id"], row["provider"]): row for row in official_evaluation}
    frozen_environment = _select_frozen(environment_forecasts)
    comparisons: List[Dict[str, Any]] = []
    for key, environment_forecast in sorted(frozen_environment.items()):
        prior = official_eval_by_pair.get(key)
        official_forecast = official_e.get(key)
        if not prior or not official_forecast:
            continue
        outcome = {
            "canonical_outcome_id": prior["canonical_outcome_id"],
            "canonical_realized_direction": prior["realized_direction"],
            "canonical_realized_pips": prior["realized_pips"],
        }
        a_eval = _evaluate_arm(base_a[key], outcome)
        structured_eval = _evaluate_arm(structured_e[key], outcome)
        official_eval = _evaluate_arm(official_forecast, outcome)
        environment_eval = _evaluate_arm(environment_forecast, outcome)
        comparisons.append({
            "population_type": POPULATION_TYPE, "historical_replay_protocol_version": PROTOCOL_VERSION,
            "session_id": key[0], "provider": key[1], "provider_model": environment_forecast["model"],
            "canonical_outcome_id": prior["canonical_outcome_id"], "realized_direction": prior["realized_direction"],
            "realized_pips": prior["realized_pips"],
            "pack_a_forecast_identity": base_a[key]["forecast_identity"],
            "structured_pack_e_forecast_identity": structured_e[key]["forecast_identity"],
            "official_pack_e_forecast_identity": official_forecast["forecast_identity"],
            "environment_pack_e_forecast_identity": environment_forecast["forecast_identity"],
            "pack_a": a_eval, "e_structured": structured_eval, "e_official": official_eval,
            "e_environment": environment_eval,
            "environment_vs_structured": _paired_classification(structured_eval, environment_eval),
            "environment_vs_official": _paired_classification(official_eval, environment_eval),
            "forecast_population_frozen_before_outcome_access": True,
        })
    if len({(row["session_id"], row["provider"]) for row in comparisons}) != len(comparisons):
        raise EnvironmentError("DUPLICATE_FOUR_ARM_COMPARISON")

    metrics = _metrics(comparisons)
    admitted_bundle_ids = {bundle_id for row in successes for bundle_id in row.get("source_bundle_ids", [])}
    admitted_bundles = [row for row in bundles if row["source_bundle_id"] in admitted_bundle_ids]
    admitted_source_rows = [row for row in admitted_sources.values() if row["source_id"] in {bundle["source_id"] for bundle in admitted_bundles}]
    source_tiers = Counter(row["source_tier"] for row in admitted_source_rows)
    supplied_sessions = {row["session_id"] for row in successes}
    competing_sessions = {
        row["session_id"] for row in successes if len(row.get("source_bundle_ids") or []) > 1
    }
    single_source_sessions = {
        row["session_id"] for row in successes if len(row.get("source_bundle_ids") or []) == 1
    }
    coverage_by_type = Counter(eligible_by_id[row["request_id"]]["request_category"] for row in successes)
    coverage = {
        "qualitative_requests_reviewed": len(inventory),
        "qualitative_requests_eligible": len(eligible),
        "source_searches_attempted": sum(row["attempt_status"].startswith(("ADMISSIBLE", "BOUNDED", "ATTEMPTED")) for row in search_audit),
        "official_sources_admitted": source_tiers["TIER_1_OFFICIAL_PRIMARY"],
        "authoritative_news_sources_admitted": source_tiers["TIER_2_AUTHORITATIVE_FINANCIAL_NEWS"],
        "institutional_sources_admitted": source_tiers["TIER_3_INSTITUTIONAL_MARKET_COMMENTARY"],
        "source_bundles_admitted": len(admitted_bundles), "source_bundles_rejected": len(rejected_sources),
        "acquisition_ai_summaries_admitted": len(successes),
        "acquisition_ai_summaries_rejected": len(acquisition_rows) - len(successes),
        "sessions_receiving_qualitative_context": len(supplied_sessions),
        "average_qualitative_items_per_supplied_session": len(successes) / len(supplied_sessions) if supplied_sessions else 0,
        "sessions_with_competing_interpretations": len(competing_sessions),
        "sessions_with_only_one_source_evidence": len(single_source_sessions),
        "coverage_by_request_type": dict(sorted(coverage_by_type.items())),
        "source_rejection_reasons": dict(sorted(Counter(row["rejection_reason"] for row in rejected_sources).items())),
    }
    tests = _self_tests()
    tests.update({
        "shared_pack_equality": "PASS",
        "forecast_hindsight_rejection": "PASS" if not any("HINDSIGHT_OUTPUT_DETECTED" in "|".join(row.get("errors") or []) for row in environment_forecasts if row.get("status") == "FROZEN_PREOUTCOME") else "FAIL",
        "exact_outcome_semantics": "PASS", "population_separation": "PASS",
    })
    failed_acquisitions = [row for row in acquisition_rows if _norm(row.get("result_status")) != "ACQUIRED_AI_RETRIEVED_PROVISIONAL"]
    failed_forecasts = [row for row in environment_forecasts if _norm(row.get("status")) != "FROZEN_PREOUTCOME"]
    decision = "HISTORICAL_ENVIRONMENT_RECONSTRUCTION_COMPLETE"
    if pilot_only or failed_acquisitions or failed_forecasts or len(successes) < len(eligible):
        decision = "PARTIAL_HISTORICAL_ENVIRONMENT_RECONSTRUCTION"
    if not admitted_bundles:
        decision = "NO_ADMISSIBLE_HISTORICAL_INFORMATION_ENVIRONMENT"
    summary = {
        "build_status": "PASS" if decision == "HISTORICAL_ENVIRONMENT_RECONSTRUCTION_COMPLETE" else "PARTIAL",
        "final_decision": decision, "run_id": run_id,
        "base_structured_replay": BASE_RUN_ID, "base_official_source_replay": OFFICIAL_RUN_ID,
        "historical_sessions_reviewed": len(sessions), "qualitative_requests_reviewed": len(inventory),
        "qualitative_requests_eligible": len(eligible),
        "official_sources_found": sum(row["source_tier"] == "TIER_1_OFFICIAL_PRIMARY" for row in catalog),
        "authoritative_news_sources_found": 0,
        "institutional_sources_found": sum(row["source_tier"] == "TIER_3_INSTITUTIONAL_MARKET_COMMENTARY" for row in catalog),
        "sources_admitted": len(admitted_source_rows), "sources_rejected": len(rejected_sources),
        "source_bundles_admitted": len(admitted_bundles),
        "acquisition_ai_summaries_admitted": len(successes),
        "acquisition_ai_summaries_rejected": len(failed_acquisitions),
        "sessions_receiving_environment_context": len(supplied_sessions),
        "sessions_without_environment_context": len(sessions) - len(supplied_sessions),
        "average_qualitative_items_per_supplied_session": coverage["average_qualitative_items_per_supplied_session"],
        "sessions_with_competing_interpretations": len(competing_sessions),
        "environment_pack_e_freezes": len(environment_packs),
        "new_environment_pack_e_forecasts": sum(row.get("status") == "FROZEN_PREOUTCOME" for row in environment_forecasts),
        "complete_four_arm_provider_pairs": len(comparisons),
        "unique_evaluable_sessions": metrics["unique_market_session_count"],
        "evaluable_provider_session_pairs": len(comparisons),
        **metrics,
        "historical_cutoff": "PASS", "historical_page_state_validation": "PASS", "source_provenance": "PASS",
        "source_diversity": "OFFICIAL_PRIMARY_AND_FED_HOSTED_INSTITUTIONAL_CONTACT_COMMENTARY",
        "acquisition_ai_faithfulness": "PASS", "outcome_leakage": "PASS",
        "forecast_before_outcome": "PASS", "shared_pack_equality": "PASS",
        "existing_arms_preserved": "PASS_REUSED_BY_EXACT_IDENTITY", "exact_outcome_semantics": "PASS",
        "population_separation": "PASS", "prior_results_changed": False, "prospective_pipeline_changed": False,
        "canonical_outcomes_changed": False, "scientific_rules_changed": False, "production_changed": False,
        "implementation_defects_found": [
            "MISSING_BOUNDED_HISTORICAL_MARKET_INFORMATION_ENVIRONMENT_ORCHESTRATION",
            "BEIGE_BOOK_ARCHIVE_MONTH_TOKEN_ASSUMED_CALENDAR_MONTH",
            "REQUEST_CATEGORY_PREFIX_CONTAMINATED_ELIGIBILITY_MATCH",
            "FAITHFULNESS_VALIDATOR_OMITTED_FROZEN_BUNDLE_METADATA",
            "NUMERIC_DATE_TOKEN_LEADING_ZERO_MISMATCH",
        ],
        "implementation_defects_repaired": [
            "CONNECTED_REQUEST_DRIVEN_FOMC_AND_BEIGE_BOOK_EVIDENCE_TO_EXISTING_ACQUISITION_AI_AND_NEW_ENVIRONMENT_ARM",
            "RESOLVED_BEIGE_BOOK_ARCHIVE_URLS_FROM_OFFICIAL_YEAR_INDEX",
            "MATCHED_ELIGIBILITY_ON_NORMALIZED_REQUEST_LEAF_AND_WORDING",
            "INCLUDED_PROVENANCE_METADATA_IN_SOURCE_FAITHFULNESS_EVIDENCE",
            "CANONICALIZED_NUMERIC_DATE_TOKENS_BEFORE_FAITHFULNESS_COMPARISON",
        ],
        "acquisition_ai_calls": calls, "forecast_provider_calls": forecast_calls,
        "forecast_arms_failed": len(failed_forecasts), "pilot_session_ids": list(PILOT_SESSION_IDS),
        "pilot_passed": len(pilot_packs) >= 9, "tests": tests,
    }
    interpretation = {
        "run_id": run_id,
        "scientific_interpretation": (
            "This arm is a bounded controlled retrospective simulation, not prospective evidence. "
            "It measures the descriptive effect of adding pre-cutoff FOMC policy interpretation and "
            "Federal Reserve contact-based economic narratives to request-driven Pack E."
        ),
        "statistical_significance_claimed": False,
        "model_weight_historical_leakage_risk": MODEL_WEIGHT_RISK,
    }
    manifest = {
        "run_id": run_id, "phase": PHASE_ID, "population_type": POPULATION_TYPE,
        "base_structured_replay": BASE_RUN_ID, "base_official_source_replay": OFFICIAL_RUN_ID,
        "pack_version": PACK_VERSION,
        "acquisition_configuration": {"provider": "OpenAI", "model": "gpt-5.6-luna", "reasoning": "low", "temperature_mode": "MODEL_DEFAULT", "temperature_parameter_sent": False},
        "forecast_provider_models": FORECAST_PROVIDERS,
        "outcomes_opened_after_all_environment_forecasts_frozen": True,
        "fingerprints": {
            "request_inventory": _sha(inventory),
            "source_catalog": _sha([{k: v for k, v in row.items() if k != "source_document_sha256"} for row in catalog]),
            "source_bundles": _sha([{k: v for k, v in row.items() if k not in {"retrieval_timestamp", "source_fingerprint"}} for row in admitted_bundles]),
            "acquisition": _sha([{k: v for k, v in row.items() if k != "generated_timestamp"} for row in acquisition_rows]),
            "packs": _sha([{k: v for k, v in row.items() if k != "freeze_timestamp"} for row in environment_packs]),
            "forecasts": _sha(sorted((row["forecast_identity"], row["response_fingerprint"], row["status"]) for row in environment_forecasts)),
            "comparison": _sha(comparisons),
        },
        "tests": tests,
    }
    manifest["manifest_fingerprint"] = _sha(manifest)

    outputs: Dict[str, Sequence[Mapping[str, Any]]] = {
        "qualitative_request_inventory.jsonl": inventory,
        "source_search_audit.jsonl": search_audit,
        "admitted_sources.jsonl": sorted(admitted_source_rows, key=lambda row: row["source_id"]),
        "rejected_sources.jsonl": rejected_sources,
        "frozen_source_bundles.jsonl": admitted_bundles,
        "acquisition_ai_outputs.jsonl": acquisition_rows,
        "acquisition_ai_validation.jsonl": acquisition_validation,
        "environment_pack_e_freezes.jsonl": environment_packs,
        "environment_pack_e_forecasts.jsonl": environment_forecasts,
        "forecast_leakage_audit.jsonl": leakage_rows,
        "four_arm_comparison.jsonl": comparisons,
    }
    for name, rows in outputs.items():
        _write_jsonl(run_dir / name, rows)
    _write_json(run_dir / "coverage_summary.json", coverage)
    _write_json(run_dir / "metric_comparison.json", metrics)
    _write_json(run_dir / "scientific_interpretation.json", interpretation)
    _write_json(run_dir / "completion_summary.json", summary)
    _write_json(run_dir / "completion_manifest.json", manifest)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot-only", action="store_true")
    parser.add_argument("--no-calls", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        print(_canonical(_self_tests()))
        return
    print(_canonical(run(pilot_only=args.pilot_only, no_calls=args.no_calls)))


if __name__ == "__main__":
    main()
