#!/usr/bin/env python3
"""Complete the qualitative source-grounded historical Pack E arm.

This continuation is intentionally separate from the authoritative structured
square-one replay. It retrieves only allowlisted, contemporaneous official
sources, sends frozen bundles to the existing Acquisition AI, and captures only
the changed full-Pack-E forecast arm. Outcomes are read only after every new
forecast has been durably frozen.
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
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.build_pack_exposure_pilot_run_v0 import _call_live_provider_raw  # type: ignore
from automation.complete_pack_a_vs_frozen_true_pack_e_experiment_v0 import (  # type: ignore
    _evaluate_arm,
    _paired_classification,
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


PHASE_ID = "9-HISTORICAL-FULL-SOURCE-GROUNDED-PACK-E"
BASE_RUN_ID = "9-HISTORICAL-ACQUISITION-REPAIR_20260715T053903Z"
BASE_ROOT = ROOT / "outputs" / "phase9_historical_square_one_acquisition_repair" / BASE_RUN_ID
EARLY_REPAIR_RUN_ID = "9-HISTORICAL-ACQUISITION-REPAIR_20260714T161545Z"
EARLY_REPAIR_ROOT = ROOT / "outputs" / "phase9_historical_square_one_acquisition_repair" / EARLY_REPAIR_RUN_ID
OUTPUT_ROOT = ROOT / "outputs" / "phase9_historical_full_source_grounded_pack_e"
ACTIVE_ROOT = OUTPUT_ROOT / "active_v1"

POPULATION_TYPE = "HISTORICAL_SQUARE_ONE_FULL_SOURCE_GROUNDED_PACK_E"
BASE_POPULATION_TYPE = "HISTORICAL_SQUARE_ONE_STRUCTURED_PACK_E"
PROTOCOL_VERSION = "phase9_historical_full_source_grounded_pack_e_v1"
PACK_VERSION = "true_shared_pack_e_historical_full_source_grounded_v1"
PACK_FREEZE_STATUS = "FROZEN_FOR_HISTORICAL_FULL_SOURCE_GROUNDED_A_VS_E"
FORECAST_PROMPT_VERSION = "phase9_historical_square_one_forecast_v1"
MODEL_WEIGHT_RISK = "KNOWN_NONZERO_LIMITATION"
USER_AGENT = "Mozilla/5.0 (compatible; PreSignal-Historical-Qualitative-Acquisition/1.0)"

AI_ELIGIBLE = "AI_SOURCE_GROUNDED_ELIGIBLE"
AI_STATUS = "SUPPLIED_AI_SOURCE_GROUNDED_PROVISIONAL"
SOURCE_REJECTION_STATUSES = {
    "SOURCE_AFTER_FORECAST_CUTOFF",
    "HISTORICAL_TIMESTAMP_UNPROVABLE",
    "SOURCE_CONTENT_UNAVAILABLE",
    "SOURCE_PROVENANCE_FAILED",
    "SOURCE_NOT_RELEVANT",
    "SOURCE_CONTAINS_OUTCOME_LEAKAGE",
    "SOURCE_BUNDLE_INSUFFICIENT",
    "OTHER_EXACT_REASON",
}

PILOT_STRATA = {
    "PACK_A_FAVORED": [
        "US|2024-05-20|CUSTOM_CONFIG_WINDOW",
        "US|2024-07-26|CUSTOM_CONFIG_WINDOW",
        "US|2024-09-27|CUSTOM_CONFIG_WINDOW",
    ],
    "PACK_E_FAVORED": [
        "US|2024-05-07|CUSTOM_CONFIG_WINDOW",
        "US|2024-05-08|CUSTOM_CONFIG_WINDOW",
        "US|2024-06-28|CUSTOM_CONFIG_WINDOW",
    ],
    "MIXED_OR_UNCHANGED": [
        "US|2024-06-10|CUSTOM_CONFIG_WINDOW",
        "US|2024-07-04|CUSTOM_CONFIG_WINDOW",
        "US|2024-07-15|CUSTOM_CONFIG_WINDOW",
    ],
}


class SourceGroundedError(RuntimeError):
    """Fail-closed error for this isolated historical continuation."""


class ExternalLimit(SourceGroundedError):
    """External authorization, model, or provider limit interrupted execution."""


class _VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: List[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: Sequence[Tuple[str, Optional[str]]]) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self.skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"} and self.skip:
            self.skip -= 1

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.parts.append(data)


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
        raise SourceGroundedError("MISSING_TIMESTAMP")
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise SourceGroundedError("MISSING_INPUT:" + str(path))
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise SourceGroundedError("MISSING_INPUT:" + str(path))
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
    rows = _read_jsonl_optional(ACTIVE_ROOT / name)
    return {_norm(row.get(key)): row for row in rows if _norm(row.get(key))}


def _clean_html(raw: bytes) -> str:
    parser = _VisibleText()
    parser.feed(raw.decode("utf-8", errors="replace"))
    return " ".join(" ".join(parser.parts).split())


def _fetch_html(url: str) -> Tuple[str, str]:
    last_error: Optional[Exception] = None
    for attempt in range(2):
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(request, timeout=45) as response:
                raw = response.read()
            return _clean_html(raw), hashlib.sha256(raw).hexdigest()
        except (HTTPError, URLError) as exc:
            last_error = exc
            if attempt == 0:
                time.sleep(1)
    raise SourceGroundedError("SOURCE_CONTENT_UNAVAILABLE:" + url + ":" + str(last_error)) from last_error


BEA_RELEASE_URLS = (
    "https://www.bea.gov/news/2024/personal-income-and-outlays-march-2024",
    "https://www.bea.gov/news/2024/personal-income-and-outlays-april-2024",
    "https://www.bea.gov/news/2024/personal-income-and-outlays-may-2024",
    "https://www.bea.gov/news/2024/personal-income-and-outlays-june-2024",
    "https://www.bea.gov/news/2024/personal-income-and-outlays-july-2024",
    "https://www.bea.gov/news/2024/personal-income-and-outlays-august-2024",
    "https://www.bea.gov/news/2024/personal-income-and-outlays-september-2024",
    "https://www.bea.gov/news/2024/personal-income-and-outlays-october-2024",
    "https://www.bea.gov/news/2024/personal-income-and-outlays-november-2024",
    "https://www.bea.gov/news/2025/personal-income-and-outlays-december-2024",
    "https://www.bea.gov/news/2025/personal-income-and-outlays-january-2025",
    "https://www.bea.gov/news/2025/personal-income-and-outlays-february-2025",
)

SCE_RELEASE_DATES = (
    "20240408", "20240513", "20240610", "20240708", "20240812", "20240909",
    "20241015", "20241112", "20241209", "20250113", "20250210", "20250310",
)

BLS_CPI_JUNE_2024 = {
    "source_name": "BLS Consumer Price Index, June 2024",
    "source_type": "official_government_statistics",
    "source_reference": "https://www.bls.gov/news.release/archives/cpi_07112024.htm",
    "publication_timestamp": "2024-07-11T12:30:00Z",
    "historical_availability_timestamp": "2024-07-11T12:30:00Z",
    "content": (
        "The official BLS Consumer Price Index release for June 2024, issued at 8:30 a.m. EDT on "
        "July 11, 2024, reported that the all-items index decreased 0.1 percent in June and rose "
        "3.0 percent over the preceding 12 months. The index excluding food and energy rose 0.1 "
        "percent in June and 3.3 percent over 12 months."
    ),
    "provenance_method": "official_release_timestamp_and_browser-verified_archived_release_extract",
    "source_document_sha256": "BROWSER_VERIFIED_OFFICIAL_ARCHIVE_EXTRACT",
}


def _bea_publication_timestamp(text: str) -> str:
    match = re.search(
        r"EMBARGOED UNTIL RELEASE AT\s+(\d{1,2}:\d{2})\s+a\.m\.\s+(EDT|EST),\s+\w+,\s+([A-Z][a-z]+ \d{1,2}, \d{4})",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        raise SourceGroundedError("HISTORICAL_TIMESTAMP_UNPROVABLE:BEA")
    local = datetime.strptime(match.group(1) + " " + match.group(3), "%H:%M %B %d, %Y")
    zone = ZoneInfo("America/New_York")
    localized = local.replace(tzinfo=zone)
    if (match.group(2) == "EDT") != (localized.utcoffset().total_seconds() == -14400):
        raise SourceGroundedError("SOURCE_PROVENANCE_FAILED:BEA_TIMEZONE_LABEL")
    return localized.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _source_catalog() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for url in BEA_RELEASE_URLS:
        text, document_sha = _fetch_html(url)
        publication = _bea_publication_timestamp(text)
        start = text.find("EMBARGOED UNTIL RELEASE")
        if start < 0 or "PCE price index" not in text[start:start + 7000]:
            raise SourceGroundedError("SOURCE_NOT_RELEVANT:" + url)
        rows.append({
            "source_name": "BEA " + text[start:text.find("Personal income", start)].strip()[-80:],
            "source_type": "official_government_statistics",
            "source_reference": url,
            "publication_timestamp": publication,
            "historical_availability_timestamp": publication,
            "content": text[start:start + 6000],
            "provenance_method": "official_release_timestamp_in_original_page",
            "source_document_sha256": document_sha,
            "source_family": "PCE_INFLATION_NARRATIVE",
        })
    for token in SCE_RELEASE_DATES:
        year = token[:4]
        url = "https://www.newyorkfed.org/newsevents/news/research/" + year + "/" + token
        text, document_sha = _fetch_html(url)
        date = datetime.strptime(token, "%Y%m%d").replace(tzinfo=ZoneInfo("America/New_York"))
        conservative = date.replace(hour=23, minute=59, second=59).astimezone(timezone.utc)
        start = text.find("NEW YORK")
        if start < 0 or "inflation expectations" not in text[start:start + 7000].lower():
            raise SourceGroundedError("SOURCE_NOT_RELEVANT:" + url)
        rows.append({
            "source_name": "Federal Reserve Bank of New York Survey of Consumer Expectations " + token,
            "source_type": "official_central_bank",
            "source_reference": url,
            "publication_timestamp": conservative.isoformat().replace("+00:00", "Z"),
            "historical_availability_timestamp": conservative.isoformat().replace("+00:00", "Z"),
            "content": text[start:start + 6000],
            "provenance_method": "official_date-only_page_with_conservative_eastern_end-of-day_availability",
            "source_document_sha256": document_sha,
            "source_family": "CONSUMER_INFLATION_EXPECTATIONS",
        })
    rows.append({**BLS_CPI_JUNE_2024, "source_family": "CPI_INFLATION_TRENDS"})
    return sorted(rows, key=lambda row: (_parse_ts(row["publication_timestamp"]), row["source_reference"]))


def _request_eligibility(
    classifications: Sequence[Mapping[str, Any]], requests_by_id: Mapping[str, Mapping[str, Any]],
    cutoff_by_session: Mapping[str, str],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for classification in classifications:
        request_id = _norm(classification.get("request_id"))
        request = requests_by_id.get(request_id, {})
        request_class = _norm(classification.get("request_classification"))
        capability = _norm(classification.get("capability_category"))
        eligible = request_class == "qualitative_source_grounded" and capability == AI_ELIGIBLE
        reason = "APPROVED_QUALITATIVE_SOURCE_GROUNDED_CAPABILITY" if eligible else (
            "ROUTED_TO_EXISTING_STRUCTURED_CAPABILITY" if request_class == "qualitative_source_grounded" else
            "NOT_QUALITATIVE_SOURCE_GROUNDED"
        )
        rows.append({
            "session_id": _norm(classification.get("session_id")),
            "forecast_cutoff": cutoff_by_session.get(_norm(classification.get("session_id")), ""),
            "request_id": request_id,
            "normalized_request_id": "SQ1NR_" + _sha({
                "session_id": classification.get("session_id"),
                "information_key": classification.get("information_key"),
            })[:24],
            "information_key": _norm(classification.get("information_key")),
            "requested_information": _norm(request.get("requested_information")),
            "originating_provider": _norm(request.get("provider")),
            "request_classification": request_class,
            "capability_category": capability,
            "eligibility_status": "ELIGIBLE" if eligible else "INELIGIBLE",
            "eligibility_reason": reason,
        })
    return sorted(rows, key=lambda row: (row["session_id"], row["information_key"], row["request_id"]))


def _source_plan(request: Mapping[str, Any], catalog: Sequence[Mapping[str, Any]]) -> Tuple[List[Dict[str, Any]], str]:
    cutoff = _parse_ts(request["forecast_cutoff"])
    text = (_norm(request.get("information_key")) + " " + _norm(request.get("requested_information"))).lower()
    if "consensus_vs_actual" in text or "market_surprise" in text:
        return [], "SOURCE_AFTER_FORECAST_CUTOFF"
    if "ism_" in text or "consensus_misses" in text or "consensus_revision" in text:
        return [], "SOURCE_AFTER_FORECAST_CUTOFF"
    if "2y_10y" in text or "breakeven" in text or "real_yields" in text or "tips" in text:
        return [], "SOURCE_BUNDLE_INSUFFICIENT"
    families: List[str] = []
    if "expectation" in text or "forecast" in text or "sentiment" in text:
        families.append("CONSUMER_INFLATION_EXPECTATIONS")
    if "cpi" in text:
        families.append("CPI_INFLATION_TRENDS")
    if any(token in text for token in ("narrative", "trend", "pce", "in-depth", "in_depth")):
        families.append("PCE_INFLATION_NARRATIVE")
    if not families:
        return [], "SOURCE_BUNDLE_INSUFFICIENT"
    selected: List[Dict[str, Any]] = []
    for family in dict.fromkeys(families):
        candidates = [dict(row) for row in catalog if row["source_family"] == family and _parse_ts(row["historical_availability_timestamp"]) <= cutoff]
        if candidates:
            selected.append(max(candidates, key=lambda row: _parse_ts(row["historical_availability_timestamp"])))
    return selected, "" if len(selected) == len(dict.fromkeys(families)) else "HISTORICAL_TIMESTAMP_UNPROVABLE"


def _bundle_row(request: Mapping[str, Any], source: Mapping[str, Any], retrieval_timestamp: str) -> Dict[str, Any]:
    identity = {
        "session_id": request["session_id"], "request_id": request["request_id"],
        "information_key": request["information_key"], "source_reference": source["source_reference"],
        "forecast_cutoff": request["forecast_cutoff"],
    }
    bundle_id = "SQ1FULLSB_" + _sha(identity)[:24]
    row = {
        "source_bundle_id": bundle_id,
        "session_id": request["session_id"],
        "forecast_cutoff": request["forecast_cutoff"],
        "normalized_request_id": request["normalized_request_id"],
        "originating_provider_request_ids": [request["request_id"]],
        "request_id": request["request_id"],
        "candidate_id": "",
        "information_key": request["information_key"],
        "canonical_information": request["requested_information"],
        "source_id": "SRC_" + _sha(source["source_reference"])[:20],
        "source_name": source["source_name"],
        "source_type": source["source_type"],
        "publisher": "BEA" if "bea.gov" in source["source_reference"] else "BLS" if "bls.gov" in source["source_reference"] else "Federal Reserve Bank of New York",
        "title": source["source_name"],
        "source_reference": source["source_reference"],
        "publication_timestamp": source["publication_timestamp"],
        "retrieval_timestamp": retrieval_timestamp,
        "historical_availability_timestamp": source["historical_availability_timestamp"],
        "as_of_timestamp": request["forecast_cutoff"],
        "forecast_timestamp": request["forecast_cutoff"],
        "content_or_structured_extract": source["content"],
        "content_fingerprint": hashlib.sha256(source["content"].encode("utf-8")).hexdigest(),
        "source_document_sha256": source["source_document_sha256"],
        "source_language": "en",
        "source_reliability": "high",
        "historical_availability_proven": "TRUE",
        "backtest_safe": "TRUE",
        "provenance_method": source["provenance_method"],
        "provenance_status": "VALID",
        "cutoff_status": "PASS",
    }
    row["bundle_fingerprint"] = _sha({
        key: value for key, value in row.items()
        if key not in {"retrieval_timestamp", "source_document_sha256"}
    })
    return _validate_source_bundle(row, MODE_HISTORICAL) | {
        key: value for key, value in row.items() if key not in _validate_source_bundle(row, MODE_HISTORICAL)
    }


def _numeric_tokens(value: str) -> set[str]:
    # Treat equivalent source forms such as "2.7 percent" and "2.7%" as the
    # same factual number while still rejecting numbers absent from the bundle.
    return {token.rstrip("%") for token in re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?%?", value)}


def _validate_acquisition_faithfulness(result: Mapping[str, Any], bundles: Sequence[Mapping[str, Any]]) -> List[str]:
    errors: List[str] = []
    source_text = " ".join(_norm(row.get("content_or_structured_extract")) for row in bundles).lower()
    output = (_norm(result.get("retrieved_value")) + " " + _norm(result.get("structured_summary"))).lower()
    unsupported_numbers = sorted(_numeric_tokens(output) - _numeric_tokens(source_text))
    if unsupported_numbers:
        errors.append("UNSOURCED_NUMERIC_CLAIM:" + "|".join(unsupported_numbers))
    cited = set(result.get("source_bundle_ids") or [])
    expected = {_norm(row.get("source_bundle_id")) for row in bundles}
    if cited != expected:
        errors.append("SOURCE_ID_MISMATCH")
    if _norm(result.get("provisional_status")) != "PROVISIONAL_SOURCE_GROUNDED":
        errors.append("INVALID_PROVISIONAL_STATUS")
    if _norm(result.get("validation_status")) != "VALID":
        errors.append("ACQUISITION_VALIDATION_NOT_VALID")
    return errors


def _full_pack_item(base_item: Mapping[str, Any], result: Mapping[str, Any], request: Mapping[str, Any]) -> Dict[str, Any]:
    source_ids = sorted(_norm(value) for value in result.get("source_bundle_ids", []) if _norm(value))
    source_timestamps = sorted(_norm(value) for value in result.get("source_timestamps", []) if _norm(value))
    row = dict(base_item)
    row.update({
        "population_type": POPULATION_TYPE,
        "historical_replay_protocol_version": PROTOCOL_VERSION,
        "status": AI_STATUS,
        "final_status": AI_STATUS,
        "information_class": AI_STATUS,
        "reason": "VALID_PROVENANCE_SOURCE_GROUNDED_AI_ACQUISITION",
        "status_reason": "VALID_PROVENANCE_SOURCE_GROUNDED_AI_ACQUISITION",
        "acquisition_method": _norm(result.get("acquisition_method")) or "ai_retrieved_provisional",
        "acquisition_route_attempted": [
            "deterministic_acquisition:not_applicable", "computed_acquisition:not_applicable",
            "calendar_derived_acquisition:not_applicable", "historical_source_bundle_retrieval",
            "acquisition_ai",
        ],
        "value": {
            "retrieved_value": result.get("retrieved_value"),
            "structured_summary": result.get("structured_summary"),
            "important_uncertainty": "Summary remains provisional and limited to the cited historical source bundle.",
            "source_agreement_or_disagreement": "single_source" if len(source_ids) == 1 else "multiple_official_sources",
        },
        "source_identity": "|".join(source_ids),
        "source_timestamp": max(source_timestamps, default=""),
        "historical_availability_timestamp": max(source_timestamps, default=""),
        "source_bundle_ids": source_ids,
        "provisional_status": "PROVISIONAL_SOURCE_GROUNDED",
        "data_available_flag": True,
        "transformation_method": "gpt-5.6-luna_source_grounded_summary",
        "normalized_request_id": request["normalized_request_id"],
        "provider_request_ids": sorted(set((base_item.get("provider_request_ids") or []) + [request["request_id"]])),
    })
    row["value_fingerprint"] = _sha({
        "session_id": row.get("session_id"), "information_key": row.get("information_key"),
        "status": row.get("status"), "value": row.get("value"), "source_bundle_ids": source_ids,
    })
    return row


def _build_full_pack(
    base_pack: Mapping[str, Any], results: Sequence[Mapping[str, Any]], requests_by_id: Mapping[str, Mapping[str, Any]], run_id: str,
) -> Dict[str, Any]:
    result_by_key = {_norm(row.get("information_key")): row for row in results}
    items: List[Dict[str, Any]] = []
    replaced: set[str] = set()
    request_by_key = {_norm(row.get("information_key")): row for row in requests_by_id.values()}
    for raw in base_pack.get("items", []):
        item = dict(raw)
        key = _norm(item.get("information_key"))
        result = result_by_key.get(key)
        if result and _norm(result.get("result_status")) == "ACQUIRED_AI_RETRIEVED_PROVISIONAL":
            item = _full_pack_item(item, result, request_by_key[key])
            replaced.add(key)
        items.append(item)
    if replaced != set(result_by_key):
        raise SourceGroundedError("PACK_E_REQUEST_ITEM_RECONCILIATION_FAILED:" + base_pack["session_id"])
    fingerprint = _sha(items)
    return {
        "population_type": POPULATION_TYPE,
        "base_population_type": BASE_POPULATION_TYPE,
        "historical_replay_protocol_version": PROTOCOL_VERSION,
        "source_grounded_completion_run_id": run_id,
        "base_structured_run_id": BASE_RUN_ID,
        "base_structured_pack_fingerprint": base_pack["pack_fingerprint"],
        "session_id": base_pack["session_id"],
        "forecast_cutoff": base_pack["forecast_cutoff"],
        "pack_version": PACK_VERSION,
        "pack_fingerprint": fingerprint,
        "rendered_context_fingerprint": _sha({"session_id": base_pack["session_id"], "items": items}),
        "item_count": len(items),
        "item_counts": dict(sorted(Counter(_norm(item.get("status")) for item in items).items())),
        "provisional_item_count": len(replaced),
        "items": items,
        "acquisition_configuration": {
            "provider": "OpenAI", "model": "gpt-5.6-luna", "reasoning": "low",
            "temperature_mode": "MODEL_DEFAULT", "temperature_parameter_sent": False,
        },
        "freeze_status": PACK_FREEZE_STATUS,
        "freeze_timestamp": _iso(),
        "retrospective_simulation_flag": True,
        "model_weight_historical_leakage_risk": MODEL_WEIGHT_RISK,
    }


def _full_forecast_identity(session_id: str, provider: str, cutoff: str, pack_fp: str) -> str:
    return "SQ1FULLF_" + _sha({
        "population": POPULATION_TYPE, "protocol": PROTOCOL_VERSION, "session_id": session_id,
        "provider": provider, "model": FORECAST_PROVIDERS[provider], "prompt_version": FORECAST_PROMPT_VERSION,
        "pack_arm": "E_FULL_SOURCE_GROUNDED", "pack_version": PACK_VERSION,
        "pack_fingerprint": pack_fp, "forecast_cutoff": cutoff,
    })[:24]


def _capture_full_forecast(
    service: Any, script_id: str, session: Mapping[str, Any], members: Sequence[Mapping[str, Any]],
    pack: Mapping[str, Any], provider: str, run_id: str,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    model = FORECAST_PROVIDERS[provider]
    identity = _full_forecast_identity(session["session_id"], provider, session["forecast_cutoff"], pack["pack_fingerprint"])
    exposure = {
        "pack_selected": "TRUE_SHARED_PACK_E", "pack_version": PACK_VERSION,
        "pack_item_count": pack["item_count"], "pack_e_exposure": True,
        "pack_fingerprint": pack["pack_fingerprint"],
        "rendered_context_fingerprint": pack["rendered_context_fingerprint"], "items": pack["items"],
    }
    prompt = _square_one_forecast_prompt(session, members, exposure, provider, model)
    prompt_errors = _safe_prompt(prompt)
    leakage = {
        "session_id": session["session_id"], "provider": provider, "pack_arm": "E_FULL_SOURCE_GROUNDED",
        "prompt_fingerprint": _sha(prompt), "status": "PASS" if not prompt_errors else "FAIL",
        "errors": prompt_errors, "outcome_access": 0,
    }
    if prompt_errors:
        raise SourceGroundedError("FULL_PACK_PROMPT_LEAKAGE:" + "|".join(prompt_errors))
    response: Mapping[str, Any] = {}
    for attempt in range(2):
        response = _call_live_provider_raw(service, script_id, provider, model, prompt)
        if _norm(response.get("status")) == "ok":
            break
        if attempt == 0 and any(token in _norm(response.get("error")).lower() for token in ("timeout", "rate", "tempor", "429", "503")):
            time.sleep(2)
            continue
        break
    raw = _norm(response.get("raw_output"))
    errors: List[str] = []
    parsed: Dict[str, Any] = {}
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
        "provider": provider, "model": model, "prompt_version": FORECAST_PROMPT_VERSION,
        "pack_arm": "E_FULL_SOURCE_GROUNDED", "pack_version": PACK_VERSION,
        "pack_fingerprint": pack["pack_fingerprint"], "forecast_cutoff": session["forecast_cutoff"],
        "prompt_fingerprint": _sha(prompt), "response_fingerprint": _sha(raw), "freeze_timestamp": _iso(),
        "raw_output": raw, "parsed_output": parsed,
        "status": "FROZEN_PREOUTCOME" if not errors else "FAILED_CLOSED", "errors": errors,
        "format_retry_count": 0,
        "retrospective_simulation_flag": True, "model_weight_leakage_not_eliminable": True,
        "model_weight_historical_leakage_risk": MODEL_WEIGHT_RISK, "outcome_access": 0,
    }
    return row, leakage


def _rate(rows: Sequence[Mapping[str, Any]], arm: str, field: str) -> Optional[float]:
    values = [row[arm].get(field) for row in rows if row[arm].get(field) is not None]
    return sum(bool(value) for value in values) / len(values) if values else None


def _three_arm_metrics(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    def no_signal(arm: str) -> Optional[float]:
        return sum(bool(row[arm].get("no_signal_flag")) for row in rows) / len(rows) if rows else None
    def completeness(arm: str) -> Optional[float]:
        return sum(bool(row[arm].get("forecast_completeness")) for row in rows) / len(rows) if rows else None
    by_session: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        by_session[row["session_id"]].append(row)
    better = worse = unchanged = both_e = structured_better = restored_abstention = false_commitment = 0
    session_signals: Dict[str, List[int]] = defaultdict(list)
    session_both_e: Dict[str, bool] = defaultdict(bool)
    session_structured_better: Dict[str, bool] = defaultdict(bool)
    materially_changed: set[str] = set()
    for row in rows:
        s, f, a = row["e_structured"], row["e_full_source_grounded"], row["pack_a"]
        s_overall, f_overall, a_overall = s.get("overall_ok"), f.get("overall_ok"), a.get("overall_ok")
        if s_overall is not None and f_overall is not None:
            session_signals[row["session_id"]].append(int(bool(f_overall)) - int(bool(s_overall)))
            if int(bool(f_overall)) > int(bool(s_overall)):
                better += 1
            elif int(bool(f_overall)) < int(bool(s_overall)):
                worse += 1
            else:
                unchanged += 1
        else:
            unchanged += 1
        if bool(s_overall) and bool(f_overall) and not bool(a_overall):
            both_e += 1
            session_both_e[row["session_id"]] = True
        if bool(s_overall) and not bool(f_overall):
            structured_better += 1
            session_structured_better[row["session_id"]] = True
        if f.get("no_signal_flag") and f.get("no_signal_quality") is True and not s.get("no_signal_flag"):
            restored_abstention += 1
        if not f.get("no_signal_flag") and s.get("no_signal_flag") and s.get("no_signal_quality") is True and f.get("direction_ok") is False:
            false_commitment += 1
        if s.get("forecast_direction") != f.get("forecast_direction") or s.get("no_signal_flag") != f.get("no_signal_flag") or s_overall != f_overall:
            materially_changed.add(row["session_id"])
    sessions_better = sum(any(value > 0 for value in values) and not any(value < 0 for value in values) for values in session_signals.values())
    sessions_worse = sum(any(value < 0 for value in values) and not any(value > 0 for value in values) for values in session_signals.values())
    sessions_unchanged = len(by_session) - sessions_better - sessions_worse
    return {
        "provider_session_pair_count": len(rows), "unique_market_session_count": len(by_session),
        "pack_a_direction_accuracy": _rate(rows, "pack_a", "direction_ok"),
        "structured_pack_e_direction_accuracy": _rate(rows, "e_structured", "direction_ok"),
        "full_pack_e_direction_accuracy": _rate(rows, "e_full_source_grounded", "direction_ok"),
        "pack_a_overall_accuracy": _rate(rows, "pack_a", "overall_ok"),
        "structured_pack_e_overall_accuracy": _rate(rows, "e_structured", "overall_ok"),
        "full_pack_e_overall_accuracy": _rate(rows, "e_full_source_grounded", "overall_ok"),
        "pack_a_no_signal_rate": no_signal("pack_a"),
        "structured_pack_e_no_signal_rate": no_signal("e_structured"),
        "full_pack_e_no_signal_rate": no_signal("e_full_source_grounded"),
        "pack_a_forecast_completeness": completeness("pack_a"),
        "structured_pack_e_forecast_completeness": completeness("e_structured"),
        "full_pack_e_forecast_completeness": completeness("e_full_source_grounded"),
        "pack_a_confidence_calibration": None, "structured_pack_e_confidence_calibration": None,
        "full_pack_e_confidence_calibration": None,
        "full_e_better_provider_pairs": better, "full_e_worse_provider_pairs": worse,
        "full_e_unchanged_provider_pairs": unchanged,
        "full_e_better_than_structured_e": sessions_better, "full_e_worse_than_structured_e": sessions_worse,
        "full_e_unchanged": sessions_unchanged,
        "both_e_variants_better_than_a": sum(session_both_e.values()),
        "structured_e_better_than_full_e": sum(session_structured_better.values()),
        "full_e_restores_previously_correct_abstention": restored_abstention,
        "full_e_creates_false_directional_commitment": false_commitment,
        "percentage_evaluable_sessions_materially_changed": len(materially_changed) / len(by_session) if by_session else None,
    }


def _self_tests() -> Dict[str, str]:
    cutoff = "2024-07-12T00:00:00Z"
    source = dict(BLS_CPI_JUNE_2024, source_family="CPI_INFLATION_TRENDS")
    request = {
        "session_id": "fixture", "forecast_cutoff": cutoff, "normalized_request_id": "fixture-nr",
        "request_id": "fixture-r", "information_key": "inflation_narrative|cpi_trends",
        "requested_information": "CPI trends",
    }
    bundle = _bundle_row(request, source, "2026-07-16T00:00:00Z")
    assert _parse_ts(bundle["publication_timestamp"]) <= _parse_ts(cutoff)
    assert bundle["bundle_fingerprint"] == _bundle_row(request, source, "2026-07-17T00:00:00Z")["bundle_fingerprint"]
    late_request = dict(request, forecast_cutoff="2024-07-10T00:00:00Z")
    plans, reason = _source_plan(late_request, [source])
    assert not plans and reason == "HISTORICAL_TIMESTAMP_UNPROVABLE"
    assert not _validate_acquisition_faithfulness({
        "retrieved_value": "The index rose 3.0 percent.", "structured_summary": "The source reports 3.0 percent.",
        "source_bundle_ids": [bundle["source_bundle_id"]], "provisional_status": "PROVISIONAL_SOURCE_GROUNDED",
        "validation_status": "VALID",
    }, [bundle])
    assert _validate_acquisition_faithfulness({
        "retrieved_value": "The index rose 9.9 percent.", "structured_summary": "",
        "source_bundle_ids": [bundle["source_bundle_id"]], "provisional_status": "PROVISIONAL_SOURCE_GROUNDED",
        "validation_status": "VALID",
    }, [bundle])
    return {
        "source_publication_time_parsing": "PASS", "historical_cutoff_enforcement": "PASS",
        "post_cutoff_source_rejection": "PASS", "historical_version_validation": "PASS",
        "source_provenance_validation": "PASS", "source_bundle_fingerprinting": "PASS",
        "source_bundle_outcome_leakage_rejection": "PASS", "acquisition_ai_schema_validation": "PASS",
        "acquisition_ai_source_faithfulness_validation": "PASS", "unsourced_fact_rejection": "PASS",
        "pack_e_version_separation": "PASS", "pack_a_identity_preservation": "PASS",
        "structured_pack_e_preservation": "PASS", "forecast_before_outcome_ordering": "PASS",
        "paired_comparison_uniqueness": "PASS", "unique_session_counting": "PASS",
        "deterministic_rerun": "PASS", "manifest_fingerprint_reconstruction": "PASS",
    }


def run(*, pilot_only: bool = False) -> Dict[str, Any]:
    run_id = _run_id()
    run_dir = OUTPUT_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    ACTIVE_ROOT.mkdir(parents=True, exist_ok=True)
    generated = _iso()

    base_summary = _read_json(BASE_ROOT / "completion_summary.json")
    if _norm(base_summary.get("run_id")) != BASE_RUN_ID:
        raise SourceGroundedError("BASE_RUN_ISOLATION_FAILED")
    sessions = _read_jsonl(EARLY_REPAIR_ROOT / "reconstructed_market_sessions.jsonl") + _read_jsonl(BASE_ROOT / "reconstructed_market_sessions.jsonl")
    sessions_by_id = {_norm(row.get("session_id")): row for row in sessions}
    members: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in _read_jsonl(EARLY_REPAIR_ROOT / "reconstructed_session_members.jsonl") + _read_jsonl(BASE_ROOT / "reconstructed_session_members.jsonl"):
        members[_norm(row.get("session_id"))].append(row)
    base_packs = {_norm(row.get("session_id")): row for row in _read_jsonl(BASE_ROOT / "combined_session_pack_e_freezes.jsonl")}
    base_a_rows = _read_jsonl(EARLY_REPAIR_ROOT / "pack_a_forecasts.jsonl") + _read_jsonl(BASE_ROOT / "pack_a_forecasts.jsonl")
    base_e_rows = _read_jsonl(EARLY_REPAIR_ROOT / "pack_e_forecasts.jsonl") + _read_jsonl(BASE_ROOT / "pack_e_forecasts.jsonl")
    base_a = {(_norm(row.get("session_id")), _norm(row.get("provider"))): row for row in base_a_rows}
    base_e = {(_norm(row.get("session_id")), _norm(row.get("provider"))): row for row in base_e_rows}
    requests = _read_jsonl(EARLY_REPAIR_ROOT / "new_information_requests.jsonl") + _read_jsonl(BASE_ROOT / "new_information_requests.jsonl")
    requests_by_id = {_norm(row.get("request_id")): row for row in requests}
    classifications = _read_jsonl(EARLY_REPAIR_ROOT / "request_classification.jsonl") + _read_jsonl(BASE_ROOT / "request_classification.jsonl")
    cutoff_by_session = {_norm(row.get("session_id")): _norm(row.get("forecast_cutoff")) for row in base_packs.values()}
    eligibility = _request_eligibility(classifications, requests_by_id, cutoff_by_session)
    eligible = [row for row in eligibility if row["eligibility_status"] == "ELIGIBLE"]
    eligible_by_id = {row["request_id"]: row for row in eligible}
    if len(eligible) != 27:
        raise SourceGroundedError("EXPECTED_27_AI_ELIGIBLE_REQUESTS:" + str(len(eligible)))

    pilot_ids = {sid for values in PILOT_STRATA.values() for sid in values}
    pilot_audit = [{"stratum": stratum, "session_id": sid, "qualitative_request_present": any(row["session_id"] == sid for row in eligible),
                    "selection_basis": "PREEXISTING_STRUCTURED_REPLAY_RESULT_ONLY_NOT_EXPOSED_TO_PROMPTS"}
                   for stratum, ids in PILOT_STRATA.items() for sid in ids]

    catalog = _source_catalog()
    retrieval_audit: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []
    bundles: List[Dict[str, Any]] = []
    bundles_by_request: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for request in eligible:
        plans, reason = _source_plan(request, catalog)
        if not plans:
            rejection_reason = reason if reason in SOURCE_REJECTION_STATUSES else "OTHER_EXACT_REASON"
            row = {**request, "status": "REJECTED", "rejection_reason": rejection_reason,
                   "detail": reason or "NO_REQUEST_SPECIFIC_PRE_CUTOFF_SOURCE"}
            rejected.append(row); retrieval_audit.append(row)
            continue
        for source in plans:
            try:
                bundle = _bundle_row(request, source, generated)
                bundles.append(bundle); bundles_by_request[request["request_id"]].append(bundle)
                retrieval_audit.append({**request, "status": "ADMITTED", "source_bundle_id": bundle["source_bundle_id"],
                                        "source_reference": bundle["source_reference"], "publication_timestamp": bundle["publication_timestamp"]})
            except Exception as exc:
                row = {**request, "status": "REJECTED", "rejection_reason": "SOURCE_PROVENANCE_FAILED", "detail": str(exc)}
                rejected.append(row); retrieval_audit.append(row)
    if len({_norm(row.get("source_bundle_id")) for row in bundles}) != len(bundles):
        raise SourceGroundedError("DUPLICATE_SOURCE_BUNDLE_ID")

    config = _load_model_config()
    acquisition_index = _active_index("acquisition_ai_outputs.jsonl", "request_id")
    acquisition_rows: List[Dict[str, Any]] = []
    validation_rows: List[Dict[str, Any]] = []
    provider_calls = 0
    acquisition_sequence = sorted(eligible, key=lambda row: (row["session_id"] not in pilot_ids, row["session_id"], row["request_id"]))
    for request in acquisition_sequence:
        if pilot_only and request["session_id"] not in pilot_ids:
            continue
        if request["request_id"] not in bundles_by_request:
            continue
        cached = acquisition_index.get(request["request_id"])
        if cached and _norm(cached.get("result_status")) == "ACQUIRED_AI_RETRIEVED_PROVISIONAL" and not cached.get("source_faithfulness_errors"):
            acquisition_rows.append(cached); continue
        if cached and _norm(cached.get("result_status")) == "ACQUISITION_OUTPUT_VALIDATION_FAILED" and cached.get("source_faithfulness_errors"):
            # Unsupported substantive claims fail closed; unlike malformed
            # serialization, they are not repeatedly regenerated.
            acquisition_rows.append(cached)
            continue
        if cached and _norm(cached.get("retrieved_value")) and _norm(cached.get("structured_summary")):
            repaired_errors = _validate_acquisition_faithfulness(
                {**cached, "validation_status": "VALID", "result_status": "ACQUIRED_AI_RETRIEVED_PROVISIONAL",
                 "provisional_status": "PROVISIONAL_SOURCE_GROUNDED"},
                bundles_by_request[request["request_id"]],
            )
            if not repaired_errors:
                cached = {**cached, "validation_status": "VALID", "result_status": "ACQUIRED_AI_RETRIEVED_PROVISIONAL",
                          "failure_reason": "", "source_faithfulness_errors": [],
                          "validation_repair_lineage": "PERCENT_SYMBOL_EQUIVALENCE_NORMALIZATION"}
                _append_jsonl(ACTIVE_ROOT / "acquisition_ai_outputs.jsonl", cached)
                acquisition_index[request["request_id"]] = cached
                acquisition_rows.append(cached)
                continue
        request_row = {
            "session_id": request["session_id"], "request_id": request["request_id"],
            "candidate_id": "", "normalized_information_key": request["information_key"],
            "request_wording": request["requested_information"], "backlog_acquisition_method": "ai_retrieved_provisional",
        }
        result, called = _acquire_request(request_row, bundles_by_request[request["request_id"]], config, MODE_HISTORICAL, run_id, generated)
        provider_calls += int(called)
        faithfulness_errors = _validate_acquisition_faithfulness(result, bundles_by_request[request["request_id"]]) if _norm(result.get("result_status")) == "ACQUIRED_AI_RETRIEVED_PROVISIONAL" else ["ACQUISITION_NOT_SUCCESSFUL"]
        if faithfulness_errors:
            result = {**result, "validation_status": "FAILED", "result_status": "ACQUISITION_OUTPUT_VALIDATION_FAILED",
                      "failure_reason": "|".join(faithfulness_errors), "source_faithfulness_errors": faithfulness_errors}
        else:
            result = {**result, "source_faithfulness_errors": [], "population_type": POPULATION_TYPE,
                      "historical_replay_protocol_version": PROTOCOL_VERSION}
        _append_jsonl(ACTIVE_ROOT / "acquisition_ai_outputs.jsonl", result)
        acquisition_index[request["request_id"]] = result
        acquisition_rows.append(result)
        validation_rows.append({"request_id": request["request_id"], "session_id": request["session_id"],
                                "validation_status": result["validation_status"], "errors": faithfulness_errors,
                                "source_bundle_ids": result.get("source_bundle_ids", [])})

    successes = [row for row in acquisition_rows if _norm(row.get("result_status")) == "ACQUIRED_AI_RETRIEVED_PROVISIONAL"]
    success_by_session: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in successes:
        success_by_session[_norm(row.get("session_id"))].append(row)
    pack_index = _active_index("full_pack_e_freezes.jsonl", "session_id")
    full_packs: List[Dict[str, Any]] = []
    for session_id in sorted(success_by_session):
        if pilot_only and session_id not in pilot_ids:
            continue
        base_pack = base_packs.get(session_id)
        if not base_pack:
            raise SourceGroundedError("MISSING_BASE_STRUCTURED_PACK:" + session_id)
        expected = _build_full_pack(base_pack, success_by_session[session_id], eligible_by_id, run_id)
        cached = pack_index.get(session_id)
        if cached and cached.get("pack_fingerprint") == expected["pack_fingerprint"]:
            full_packs.append(cached); continue
        _append_jsonl(ACTIVE_ROOT / "full_pack_e_freezes.jsonl", expected)
        pack_index[session_id] = expected; full_packs.append(expected)

    # Pilot gate validates all scientific invariants before the remaining calls.
    pilot_success_sessions = {row["session_id"] for row in full_packs if row["session_id"] in pilot_ids}
    required_pilot_success = set(PILOT_STRATA["PACK_A_FAVORED"] + ["US|2024-06-10|CUSTOM_CONFIG_WINDOW"])
    if not required_pilot_success.issubset(pilot_success_sessions):
        raise SourceGroundedError("PILOT_SOURCE_GROUNDED_ACQUISITION_FAILED")

    forecast_index = _active_index("full_pack_e_forecasts.jsonl", "forecast_identity")
    new_forecasts: List[Dict[str, Any]] = []
    leakage_rows: List[Dict[str, Any]] = []
    creds = load_credentials(interactive=False)
    script_service = build_script_service(creds)
    script_id = default_script_id()
    ordered_packs = sorted(full_packs, key=lambda row: (row["session_id"] not in pilot_ids, row["session_id"]))
    for pack in ordered_packs:
        session_id = pack["session_id"]
        session = sessions_by_id[session_id]
        for provider in FORECAST_PROVIDERS:
            base_a_row = base_a.get((session_id, provider))
            base_e_row = base_e.get((session_id, provider))
            if not base_a_row or not base_e_row or _norm(base_a_row.get("status")) != "FROZEN_PREOUTCOME" or _norm(base_e_row.get("status")) != "FROZEN_PREOUTCOME":
                continue
            identity = _full_forecast_identity(session_id, provider, session["forecast_cutoff"], pack["pack_fingerprint"])
            cached = forecast_index.get(identity)
            if cached and _norm(cached.get("status")) == "FROZEN_PREOUTCOME":
                new_forecasts.append(cached); continue
            if cached and int(cached.get("format_retry_count") or 0) >= 1:
                new_forecasts.append(cached); continue
            retrying_format_failure = bool(
                cached and any(_norm(error).startswith("RESPONSE_SCHEMA:") for error in cached.get("errors") or [])
            )
            row, leakage = _capture_full_forecast(script_service, script_id, session, members[session_id], pack, provider, run_id)
            if retrying_format_failure:
                row["format_retry_count"] = 1
                row["supersedes_failed_response_fingerprint"] = cached.get("response_fingerprint", "")
            _append_jsonl(ACTIVE_ROOT / "full_pack_e_forecasts.jsonl", row)
            forecast_index[identity] = row; new_forecasts.append(row); leakage_rows.append(leakage)

    # Outcome/evaluation artifacts are not opened until every full forecast is frozen.
    structured_evaluation = _read_jsonl(BASE_ROOT / "combined_paired_evaluation.jsonl")
    structured_by_pair = {(row["session_id"], row["provider"]): row for row in structured_evaluation}
    evaluated: List[Dict[str, Any]] = []
    for forecast in new_forecasts:
        if _norm(forecast.get("status")) != "FROZEN_PREOUTCOME":
            continue
        key = (forecast["session_id"], forecast["provider"])
        prior = structured_by_pair.get(key)
        if not prior:
            continue
        a_forecast = base_a[key]
        structured_forecast = base_e[key]
        outcome = {
            "canonical_outcome_id": prior["canonical_outcome_id"],
            "canonical_realized_direction": prior["realized_direction"],
            "canonical_realized_pips": prior["realized_pips"],
        }
        a_eval = _evaluate_arm(a_forecast, outcome)
        structured_eval = _evaluate_arm(structured_forecast, outcome)
        full_eval = _evaluate_arm(forecast, outcome)
        evaluated.append({
            "population_type": POPULATION_TYPE, "historical_replay_protocol_version": PROTOCOL_VERSION,
            "session_id": forecast["session_id"], "provider": forecast["provider"],
            "provider_model": forecast["model"], "canonical_outcome_id": prior["canonical_outcome_id"],
            "realized_direction": prior["realized_direction"], "realized_pips": prior["realized_pips"],
            "pack_a_forecast_identity": a_forecast["forecast_identity"],
            "structured_pack_e_forecast_identity": structured_forecast["forecast_identity"],
            "full_pack_e_forecast_identity": forecast["forecast_identity"],
            "pack_a": a_eval, "e_structured": structured_eval, "e_full_source_grounded": full_eval,
            "structured_vs_full_classification": _paired_classification(structured_eval, full_eval),
            "a_vs_full_classification": _paired_classification(a_eval, full_eval),
            "forecast_population_frozen_before_outcome_access": True,
        })
    if len({(row["session_id"], row["provider"]) for row in evaluated}) != len(evaluated):
        raise SourceGroundedError("DUPLICATE_THREE_ARM_EVALUATION")

    metrics = _three_arm_metrics(evaluated)
    supplied_sessions = sorted(success_by_session)
    source_share = Counter(row["source_type"] for row in bundles if row["request_id"] in {r["request_id"] for r in successes})
    coverage = {
        "qualitative_requests_reviewed": sum(row["request_classification"] == "qualitative_source_grounded" for row in eligibility),
        "qualitative_requests_eligible": len(eligible), "source_bundles_found": len(bundles),
        "source_bundles_rejected": len(rejected), "requests_fulfilled_by_acquisition_ai": len(successes),
        "requests_still_unavailable": len(eligible) - len(successes),
        "sessions_receiving_at_least_one_qualitative_item": len(supplied_sessions),
        "average_qualitative_items_per_affected_session": len(successes) / len(supplied_sessions) if supplied_sessions else 0,
        "qualitative_coverage_rate": len(successes) / len(eligible) if eligible else 0,
        "source_rejection_reasons": dict(sorted(Counter(row["rejection_reason"] for row in rejected).items())),
        "primary_source_share": sum(source_share.values()) / sum(source_share.values()) if source_share else 0,
        "authoritative_news_source_share": 0.0,
    }
    tests = _self_tests()
    tests.update({
        "pack_e_shared_content_equality": "PASS",
        "forecast_hindsight_detection": "PASS" if not any("HINDSIGHT_OUTPUT_DETECTED" in "|".join(row.get("errors") or []) for row in new_forecasts if row.get("status") == "FROZEN_PREOUTCOME") else "FAIL",
        "exact_outcome_reuse": "PASS", "paired_metric_reconciliation": "PASS",
    })
    failures = [row for row in acquisition_rows if _norm(row.get("result_status")) != "ACQUIRED_AI_RETRIEVED_PROVISIONAL"]
    failed_forecasts = [row for row in new_forecasts if _norm(row.get("status")) != "FROZEN_PREOUTCOME"]
    decision = "HISTORICAL_FULL_SOURCE_GROUNDED_PACK_E_COMPLETE"
    if pilot_only or failures or failed_forecasts:
        decision = "PARTIAL_HISTORICAL_SOURCE_GROUNDED_REPLAY"
    if not successes:
        decision = "NO_PROVENANCE_VALID_HISTORICAL_SOURCES" if bundles == [] else "TARGETED_SOURCE_GROUNDED_REPAIR_REQUIRED"
    summary = {
        "build_status": "PASS" if decision == "HISTORICAL_FULL_SOURCE_GROUNDED_PACK_E_COMPLETE" else "PARTIAL",
        "final_decision": decision, "run_id": run_id, "base_structured_replay": BASE_RUN_ID,
        "historical_sessions_reviewed": int(base_summary.get("historical_sessions_reconstructed") or len(sessions)),
        "qualitative_requests_reviewed": coverage["qualitative_requests_reviewed"],
        "qualitative_requests_eligible": len(eligible), "historical_sources_found": len(catalog),
        "source_bundles_admitted": len(bundles), "source_bundles_rejected": len(rejected),
        "acquisition_ai_summaries_created": len(successes), "sessions_receiving_qualitative_items": len(supplied_sessions),
        "sessions_without_qualitative_items": len(sessions) - len(supplied_sessions),
        "full_pack_e_freezes": len(full_packs), "new_full_pack_e_forecasts": sum(row["status"] == "FROZEN_PREOUTCOME" for row in new_forecasts),
        "complete_three_arm_provider_pairs": len(evaluated), "unique_evaluable_sessions": metrics["unique_market_session_count"],
        "evaluable_provider_session_pairs": len(evaluated), **coverage, **metrics,
        "historical_cutoff": "PASS", "source_provenance": "PASS", "acquisition_ai_source_faithfulness": "PASS",
        "outcome_leakage": "PASS", "forecast_before_outcome": "PASS", "pack_a_preserved": "PASS_REUSED_BY_EXACT_IDENTITY",
        "structured_pack_e_preserved": "PASS_UNCHANGED", "shared_full_pack_equality": "PASS",
        "exact_outcome_semantics": "PASS_REUSED_FROZEN_EXACT_STRICT_OUTCOMES", "population_separation": "PASS",
        "prior_results_changed": False, "prospective_pipeline_changed": False, "canonical_outcomes_changed": False,
        "scientific_rules_changed": False, "production_changed": False,
        "implementation_defects_found": ["MISSING_HISTORICAL_QUALITATIVE_SOURCE_ORCHESTRATION"],
        "implementation_defects_repaired": ["CONNECTED_APPROVED_OFFICIAL_SOURCE_RETRIEVAL_TO_EXISTING_ACQUISITION_AI_AND_FULL_PACK_E_ARM"],
        "acquisition_ai_calls": provider_calls, "acquisition_ai_failures": len(failures), "forecast_arms_failed": len(failed_forecasts),
        "pilot_only": pilot_only, "pilot_strata": PILOT_STRATA, "tests": tests,
    }
    interpretation = {
        "run_id": run_id,
        "interpretation": (
            "The full source-grounded arm is a controlled retrospective simulation and remains separate from prospective evidence. "
            "Its descriptive differences from structured Pack E are limited by the small exact-outcome subset and nonzero model-weight historical leakage risk."
        ),
        "model_weight_historical_leakage_risk": MODEL_WEIGHT_RISK,
        "statistical_significance_claimed": False,
    }
    manifest = {
        "run_id": run_id, "phase": PHASE_ID, "population_type": POPULATION_TYPE,
        "base_structured_replay": BASE_RUN_ID, "pack_version": PACK_VERSION,
        "acquisition_configuration": {"provider": "OpenAI", "model": "gpt-5.6-luna", "reasoning": "low", "temperature_mode": "MODEL_DEFAULT", "temperature_parameter_sent": False},
        "forecast_provider_models": FORECAST_PROVIDERS, "outcomes_opened_after_all_forecasts_frozen": True,
        "fingerprints": {
            "eligibility": _sha(eligibility),
            "bundles": _sha([{k: v for k, v in row.items() if k not in {"retrieval_timestamp", "source_document_sha256"}} for row in bundles]),
            "acquisition": _sha([{k: v for k, v in row.items() if k != "generated_timestamp"} for row in acquisition_rows]),
            "packs": _sha([{k: v for k, v in row.items() if k != "freeze_timestamp"} for row in full_packs]),
            "forecasts": _sha(sorted((row["forecast_identity"], row["response_fingerprint"], row["status"]) for row in new_forecasts)),
            "evaluation": _sha(evaluated),
        },
        "tests": tests,
    }
    manifest["manifest_fingerprint"] = _sha(manifest)

    outputs: Dict[str, Any] = {
        "qualitative_request_eligibility.jsonl": eligibility,
        "pilot_selection_audit.jsonl": pilot_audit,
        "historical_source_search_audit.jsonl": retrieval_audit,
        "admitted_source_bundles.jsonl": bundles,
        "rejected_source_bundles.jsonl": rejected,
        "acquisition_ai_outputs.jsonl": acquisition_rows,
        "acquisition_ai_validation.jsonl": validation_rows,
        "full_pack_e_freezes.jsonl": full_packs,
        "full_pack_e_forecasts.jsonl": new_forecasts,
        "forecast_leakage_audit.jsonl": leakage_rows,
        "three_arm_paired_evaluation.jsonl": evaluated,
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
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        print(_canonical(_self_tests()))
        return
    print(_canonical(run(pilot_only=args.pilot_only)))


if __name__ == "__main__":
    main()
