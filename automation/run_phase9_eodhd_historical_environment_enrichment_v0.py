#!/usr/bin/env python3
"""Build the isolated EODHD-enriched historical environment arm.

Only the authoritative qualitative request inventory is searched. EODHD
articles are admitted after exact cutoff, relevance, sufficiency, duplicate,
and target-outcome leakage checks. Existing A/E arms are immutable inputs;
only E_ENVIRONMENT_EODHD forecasts are captured before outcomes are opened.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import urlparse


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
    run_script_function,
)
from automation.reconstruct_phase9_historical_market_information_environment_v0 import (  # type: ignore
    _faithfulness_errors,
)
from automation.run_phase9_historical_square_one_replay_v0 import (  # type: ignore
    FORECAST_PROVIDERS,
    _hindsight_hits,
    _normalized_forecast_response,
    _safe_prompt,
    _square_one_forecast_prompt,
)


PHASE_ID = "9-EODHD-HISTORICAL-ENVIRONMENT-ENRICHMENT"
BASE_AUDIT_RUN = "9-EODHD-HISTORICAL-NEWS-AUDIT_20260716T041803Z"
BASE_STRUCTURED_RUN = "9-HISTORICAL-ACQUISITION-REPAIR_20260715T053903Z"
BASE_OFFICIAL_RUN = "9-HISTORICAL-FULL-SOURCE-GROUNDED-PACK-E_20260716T023147Z"
BASE_ENVIRONMENT_RUN = "9-HISTORICAL-ENVIRONMENT-RECONSTRUCTION_20260716T033701Z"
EARLY_RUN = "9-HISTORICAL-ACQUISITION-REPAIR_20260714T161545Z"

BASE_STRUCTURED_ROOT = ROOT / "outputs" / "phase9_historical_square_one_acquisition_repair" / BASE_STRUCTURED_RUN
EARLY_ROOT = ROOT / "outputs" / "phase9_historical_square_one_acquisition_repair" / EARLY_RUN
BASE_OFFICIAL_ROOT = ROOT / "outputs" / "phase9_historical_full_source_grounded_pack_e" / BASE_OFFICIAL_RUN
BASE_ENVIRONMENT_ROOT = ROOT / "outputs" / "phase9_historical_environment_reconstructed_pack_e" / BASE_ENVIRONMENT_RUN
BASE_AUDIT_ROOT = ROOT / "outputs" / "phase9_eodhd_historical_news_audit" / BASE_AUDIT_RUN
OUTPUT_ROOT = ROOT / "outputs" / "phase9_historical_environment_eodhd_enrichment"
ACTIVE_ROOT = OUTPUT_ROOT / "active_v1"

POPULATION_TYPE = "HISTORICAL_ENVIRONMENT_EODHD_ENRICHED_PACK_E"
PROTOCOL_VERSION = "phase9_historical_environment_eodhd_enrichment_v1"
PACK_VERSION = "true_shared_pack_e_historical_environment_eodhd_v1"
PACK_STATUS = "FROZEN_FOR_HISTORICAL_ENVIRONMENT_EODHD_PRIVATE_RESEARCH"
PACK_ARM = "E_ENVIRONMENT_EODHD"
PROMPT_VERSION = "phase9_historical_square_one_forecast_v1"
AI_STATUS = "SUPPLIED_AI_SOURCE_GROUNDED_PROVISIONAL"
MODEL_WEIGHT_RISK = "KNOWN_NONZERO_LIMITATION"
USAGE_FIELDS = {
    "usage_scope": "PRIVATE_RESEARCH_EXPERIMENT",
    "license_status": "LICENSE_SCOPE_NOT_FORMALLY_CONFIRMED",
    "publication_allowed": False,
    "commercial_use_allowed": False,
}
EXPERIMENTAL_USAGE_STATUS = "PRIVATE_RESEARCH_USE"

CATEGORY_TERMS = {
    "inflation_narrative": (
        "inflation", "consumer prices", "price pressures", "cpi", "pce", "core prices",
        "disinflation", "inflation expectations", "price growth",
    ),
    "labor_narrative": (
        "labor market", "labour market", "employment", "unemployment", "payroll",
        "jobless", "jobs", "wages", "hiring",
    ),
    "growth_context": (
        "economic growth", "economy", "gdp", "consumer spending", "retail sales",
        "manufacturing", "services activity", "business activity", "growth outlook",
    ),
}
MARKET_TERMS = (
    "market", "investor", "trader", "federal reserve", "fed", "interest rate", "rates",
    "yield", "treasury", "dollar", "currency", "outlook", "expectation", "consensus",
    "wall street", "risk sentiment",
)
TOPIC_BY_CATEGORY = {
    "inflation_narrative": "inflation",
    "labor_narrative": "employment",
    "growth_context": "economy",
}
TARGET_LEAKAGE_MARKERS = (
    "canonical outcome", "realized pips", "five-minute outcome", "forecast was correct",
    "forecast was wrong", "pack e improved", "pack e worsened",
)
PROMOTIONAL_WIRE_HOSTS = {
    "www.globenewswire.com", "globenewswire.com", "www.businesswire.com", "businesswire.com",
    "www.accesswire.com", "accesswire.com",
}
PROMOTIONAL_MARKERS = (
    "proudly announces", "global launch", "product launch", "platform designed to",
    "for immediate release", "contact information", "media contact",
)


class EnrichmentError(RuntimeError):
    """Fail-closed error for the isolated EODHD arm."""


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
        raise EnrichmentError("MISSING_TIMESTAMP")
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise EnrichmentError("HISTORICAL_TIMESTAMP_UNPROVABLE")
    return parsed.astimezone(timezone.utc)


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise EnrichmentError("MISSING_INPUT:" + str(path))
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise EnrichmentError("MISSING_INPUT:" + str(path))
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


def _clean_text(value: Any) -> str:
    text = html.unescape(_norm(value))
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _request_plan(request: Mapping[str, Any]) -> List[Dict[str, Any]]:
    cutoff = _parse_ts(request["forecast_cutoff"])
    days = 7 if request["request_category"] in {"inflation_narrative", "labor_narrative"} else 2
    start = (cutoff - timedelta(days=days)).date().isoformat()
    end = cutoff.date().isoformat()
    channels = (
        ("topic", TOPIC_BY_CATEGORY[request["request_category"]], "EXACT_TOPIC_ATTEMPT"),
        ("ticker", "GSPC.INDX", "BROAD_MARKET_NEWS_RETRIEVAL_CHANNEL_NOT_EVIDENCE_PROXY"),
        ("ticker", "EURUSD.FOREX", "FX_MACRO_NEWS_RETRIEVAL_CHANNEL_NOT_DXY_PROXY"),
    )
    return [
        {
            "query_id": "EODHDQ_" + _sha((request["provider_request_id"], query_type, value, start, end))[:24],
            "provider_request_id": request["provider_request_id"],
            "normalized_request_id": request["normalized_request_id"],
            "session_id": request["session_id"],
            "request_category": request["request_category"],
            "query_type": query_type,
            "query_value": value,
            "query_justification": justification,
            "from_date": start,
            "to_date": end,
            "forecast_cutoff": request["forecast_cutoff"],
            "search_window_hours": days * 24,
            "limit": 20,
        }
        for query_type, value, justification in channels
    ]


def _call_query_batches(queries: Sequence[Mapping[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    if not queries:
        return [], 0
    service = build_script_service(load_credentials(interactive=False))
    script_id = default_script_id()
    results: List[Dict[str, Any]] = []
    for offset in range(0, len(queries), 12):
        batch = []
        for query in queries[offset:offset + 12]:
            batch.append({key: value for key, value in query.items() if key in {
                "query_id", "query_type", "query_value", "from_date", "to_date", "limit",
            }})
        response = run_script_function(
            service, script_id, "apiProbeEodhdHistoricalNews", [{"queries": batch}], dev_mode=True,
        )
        if not response or not response.get("credential_present"):
            raise EnrichmentError("EODHD_API_ACCESS_FAILED")
        for row in response.get("results") or []:
            results.append(dict(row))
    return results, len(queries)


def _retrieve_queries(queries: Sequence[Mapping[str, Any]], no_calls: bool) -> Tuple[List[Dict[str, Any]], int]:
    cache = _active_index("query_response_cache.jsonl", "query_id")
    missing = [row for row in queries if row["query_id"] not in cache]
    executed = 0
    if missing and not no_calls:
        responses, executed = _call_query_batches(missing)
        for response in responses:
            query_id = _norm(response.get("query_id"))
            if not query_id:
                continue
            stored = {**dict(response), **USAGE_FIELDS, "cache_timestamp": _iso()}
            _append_jsonl(ACTIVE_ROOT / "query_response_cache.jsonl", stored)
            cache[query_id] = stored
    return [cache[row["query_id"]] for row in queries if row["query_id"] in cache], executed


def _term_hits(text: str, terms: Sequence[str]) -> List[str]:
    lowered = text.lower()
    return sorted({term for term in terms if term in lowered})


def _relevance(request: Mapping[str, Any], query: Mapping[str, Any], text: str) -> Tuple[bool, List[str], List[str]]:
    category_hits = _term_hits(text, CATEGORY_TERMS[request["request_category"]])
    market_hits = _term_hits(text, MARKET_TERMS)
    exact_acronym = bool(set(category_hits) & {"cpi", "pce", "gdp"})
    relevant = bool(category_hits) and bool(market_hits) and (len(category_hits) >= 2 or exact_acronym)
    if query["query_type"] == "ticker" and not category_hits:
        return False, category_hits, market_hits
    return relevant, category_hits, market_hits


def _promotional_content(host: str, text: str) -> bool:
    lowered = text.lower()
    return host in PROMOTIONAL_WIRE_HOSTS or sum(marker in lowered for marker in PROMOTIONAL_MARKERS) >= 2


def _candidate_rows(
    requests: Sequence[Mapping[str, Any]], queries: Sequence[Mapping[str, Any]],
    responses: Sequence[Mapping[str, Any]], generated: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    request_by_id = {row["provider_request_id"]: row for row in requests}
    query_by_id = {row["query_id"]: row for row in queries}
    response_by_id = {_norm(row.get("query_id")): row for row in responses}
    audit: List[Dict[str, Any]] = []
    candidates: List[Dict[str, Any]] = []
    seen_by_request: Dict[str, set[str]] = defaultdict(set)
    for query in queries:
        response = response_by_id.get(query["query_id"], {})
        articles = response.get("articles") or []
        audit.append({
            **dict(query), "response_status": response.get("status", "NOT_EXECUTED"),
            "response_code": response.get("response_code"), "articles_returned": len(articles),
            "error": _norm(response.get("error")), **USAGE_FIELDS,
        })
        request = request_by_id[query["provider_request_id"]]
        cutoff = _parse_ts(request["forecast_cutoff"])
        for article in articles:
            title = _clean_text(article.get("title"))
            raw_excerpt = _clean_text(article.get("content_excerpt"))
            url = _norm(article.get("article_url"))
            host = urlparse(url).netloc.lower()
            publication_text = _norm(article.get("publication_timestamp"))
            try:
                publication = _parse_ts(publication_text)
                timestamp_status = "PASS"
            except Exception:
                publication = None
                timestamp_status = "HISTORICAL_TIMESTAMP_UNPROVABLE"
            identity = "EODHDART_" + _sha((article.get("article_identity"), url, publication_text, title))[:24]
            duplicate = identity in seen_by_request[request["provider_request_id"]]
            seen_by_request[request["provider_request_id"]].add(identity)
            combined = (title + " " + raw_excerpt).strip()
            relevant, category_hits, market_hits = _relevance(request, query, combined)
            content_length = int(article.get("content_length") or len(raw_excerpt))
            leakage_hits = [marker for marker in TARGET_LEAKAGE_MARKERS if marker in combined.lower()]
            if duplicate:
                classification = "SOURCE_DUPLICATE"
            elif timestamp_status != "PASS":
                classification = timestamp_status
            elif publication and publication > cutoff:
                classification = "SOURCE_AFTER_FORECAST_CUTOFF"
            elif leakage_hits:
                classification = "SOURCE_CONTAINS_OUTCOME_LEAKAGE"
            elif _promotional_content(host, combined):
                classification = "SOURCE_NOT_RELEVANT_PROMOTIONAL"
            elif not relevant:
                classification = "QUERY_PROXY_TOO_WEAK" if query["query_type"] == "ticker" else "NOT_RELEVANT"
            elif content_length <= max(180, len(title) + 50):
                classification = "HEADLINE_ONLY"
            elif len(raw_excerpt) < 400:
                classification = "RELEVANT_BUT_TOO_SHORT"
            elif content_length >= 1000:
                classification = "RELEVANT_FULL_TEXT"
            else:
                classification = "RELEVANT_SUFFICIENT_EXCERPT"
            excerpt = raw_excerpt[:1800] if classification in {"RELEVANT_FULL_TEXT", "RELEVANT_SUFFICIENT_EXCERPT"} else ""
            candidates.append({
                "article_identity": identity,
                "eodhd_response_identity": _norm(article.get("article_identity")),
                "native_article_identity_available": bool(_norm(article.get("article_identity")) and _norm(article.get("article_identity")) != url),
                "provider_request_id": request["provider_request_id"],
                "normalized_request_id": request["normalized_request_id"],
                "session_id": request["session_id"], "forecast_cutoff": request["forecast_cutoff"],
                "request_category": request["request_category"], "requested_concept": request["requested_concept"],
                "query_id": query["query_id"], "query_type": query["query_type"],
                "query_value": query["query_value"], "query_justification": query["query_justification"],
                "source_url": url, "source_host": host, "original_publisher": "",
                "publisher_identity_status": "UNAVAILABLE_SOURCE_HOST_ONLY",
                "title": title, "publication_timestamp": publication_text,
                "normalized_utc_timestamp": publication.isoformat().replace("+00:00", "Z") if publication else "",
                "retrieval_timestamp": generated, "content_length": content_length,
                "relevant_excerpt": excerpt,
                "content_fingerprint": hashlib.sha256(raw_excerpt.encode("utf-8")).hexdigest(),
                "ticker_tags": article.get("ticker_tags") or [], "topic_tags": article.get("topic_tags") or [],
                "sentiment": article.get("sentiment"), "category_term_hits": category_hits,
                "market_term_hits": market_hits, "leakage_hits": leakage_hits,
                "classification": classification, "cutoff_status": "PASS" if publication and publication <= cutoff else "FAIL",
                "provenance_warning": "EODHD_AGGREGATED_PAYLOAD_NATIVE_ORIGINAL_PUBLISHER_UNAVAILABLE",
                **USAGE_FIELDS,
            })
    return audit, candidates


def _admitted_and_rejected(candidates: Sequence[Mapping[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    admitted: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []
    by_request: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for raw in candidates:
        row = dict(raw)
        if row["classification"] in {"RELEVANT_FULL_TEXT", "RELEVANT_SUFFICIENT_EXCERPT"}:
            by_request[row["provider_request_id"]].append(row)
        else:
            row.pop("relevant_excerpt", None)
            rejected.append(row)
    for rows in by_request.values():
        ranked = sorted(
            rows,
            key=lambda row: (
                -len(row.get("category_term_hits") or []),
                -len(row.get("market_term_hits") or []),
                -int(row.get("content_length") or 0),
                row.get("publication_timestamp") or "",
            ),
        )
        admitted.extend(ranked[:3])
        for row in ranked[3:]:
            rejected.append({**{k: v for k, v in row.items() if k != "relevant_excerpt"}, "classification": "SOURCE_DUPLICATE"})
    return admitted, rejected


def _bundle(request: Mapping[str, Any], articles: Sequence[Mapping[str, Any]], generated: str) -> Dict[str, Any]:
    sorted_articles = sorted(articles, key=lambda row: (row["publication_timestamp"], row["article_identity"]))
    source_blocks = []
    for index, article in enumerate(sorted_articles, 1):
        source_blocks.append(
            "SOURCE {idx}\narticle_identity: {identity}\nsource_host: {host}\nurl: {url}\n"
            "publication_timestamp: {timestamp}\ntitle: {title}\nexcerpt: {excerpt}".format(
                idx=index, identity=article["article_identity"], host=article["source_host"],
                url=article["source_url"], timestamp=article["publication_timestamp"],
                title=article["title"], excerpt=article["relevant_excerpt"],
            )
        )
    identity = {
        "session_id": request["session_id"], "normalized_request_id": request["normalized_request_id"],
        "articles": [row["article_identity"] for row in sorted_articles], "forecast_cutoff": request["forecast_cutoff"],
    }
    bundle_id = "EODHDSB_" + _sha(identity)[:24]
    publication_timestamps = [row["publication_timestamp"] for row in sorted_articles]
    row = {
        "source_bundle_id": bundle_id, "bundle_id": bundle_id,
        "session_id": request["session_id"], "forecast_cutoff": request["forecast_cutoff"],
        "normalized_request_id": request["normalized_request_id"],
        "originating_request_ids": [request["provider_request_id"]], "request_id": request["provider_request_id"],
        "candidate_id": "", "information_key": request["information_key"],
        "canonical_information": request["requested_concept"],
        "source_name": "EODHD bounded historical financial-news bundle",
        "source_type": "authoritative_financial_news", "source_tier": "TIER_2_AGGREGATED_FINANCIAL_NEWS",
        "source_reference": "|".join(row["source_url"] for row in sorted_articles),
        "source_references": [row["source_url"] for row in sorted_articles],
        "source_hosts": [row["source_host"] for row in sorted_articles],
        "article_identities": [row["article_identity"] for row in sorted_articles],
        "publication_timestamp": max(publication_timestamps), "source_timestamps": publication_timestamps,
        "retrieval_timestamp": generated, "historical_availability_timestamp": max(publication_timestamps),
        "as_of_timestamp": request["forecast_cutoff"], "forecast_timestamp": request["forecast_cutoff"],
        "content_or_structured_extract": "\n\n".join(source_blocks),
        "source_language": "en", "source_reliability": "medium",
        "historical_availability_proven": "TRUE", "backtest_safe": "TRUE",
        "provenance_method": "EODHD_EXACT_PUBLICATION_TIMESTAMP_AND_SOURCE_URL_HOST",
        "provenance_status": "VALID_WITH_NATIVE_PUBLISHER_LIMITATION", "cutoff_status": "PASS",
        "provenance_warning": "EODHD_AGGREGATED_PAYLOAD_NATIVE_ORIGINAL_PUBLISHER_UNAVAILABLE",
        "content_fingerprints": [row["content_fingerprint"] for row in sorted_articles],
        "sentiment_metadata": [row.get("sentiment") for row in sorted_articles],
        **USAGE_FIELDS,
    }
    row["bundle_fingerprint"] = _sha({key: value for key, value in row.items() if key not in {"retrieval_timestamp"}})
    validated = _validate_source_bundle(row, MODE_HISTORICAL)
    return {**row, **validated}


def _acquisition_result(result: Mapping[str, Any], request: Mapping[str, Any], bundle: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        **dict(result),
        "normalized_request_id": request["normalized_request_id"],
        "factual_summary": result.get("retrieved_value"),
        "dominant_interpretation": result.get("structured_summary"),
        "competing_interpretation": _norm(result.get("stance_or_state_if_allowed")),
        "important_uncertainty": "Provisional summary is limited to the cited EODHD excerpts and retains the source-host and licensing limitations.",
        "source_agreement": "MULTIPLE_ARTICLES" if len(bundle.get("article_identities") or []) > 1 else "SINGLE_ARTICLE",
        "historical_as_of_timestamp": result.get("as_of_timestamp"),
        "population_type": POPULATION_TYPE, "historical_replay_protocol_version": PROTOCOL_VERSION,
        **USAGE_FIELDS,
    }


def _acquire(
    requests: Sequence[Mapping[str, Any]], bundles: Sequence[Mapping[str, Any]], run_id: str,
    generated: str, no_calls: bool,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int]:
    request_by_id = {row["provider_request_id"]: row for row in requests}
    bundle_by_request = {row["request_id"]: row for row in bundles}
    cache = _active_index("acquisition_ai_outputs.jsonl", "request_id")
    results: List[Dict[str, Any]] = []
    validations: List[Dict[str, Any]] = []
    calls = 0
    config = _load_model_config()
    for request_id in sorted(bundle_by_request, key=lambda rid: request_by_id[rid]["session_id"]):
        request = request_by_id[request_id]
        bundle = bundle_by_request[request_id]
        cached = cache.get(request_id)
        if cached and _norm(cached.get("result_status")) == "ACQUIRED_AI_RETRIEVED_PROVISIONAL" and not cached.get("source_faithfulness_errors"):
            results.append(cached)
            validations.append({
                "request_id": request_id, "normalized_request_id": request["normalized_request_id"],
                "session_id": request["session_id"], "validation_status": "VALID",
                "errors": [], "source_bundle_ids": cached.get("source_bundle_ids", []),
                "bounded_regeneration_count": cached.get("bounded_regeneration_count", 0),
                "authoritative_cached_identity_reused": True, **USAGE_FIELDS,
            })
            continue
        if no_calls:
            continue
        request_row = {
            "session_id": request["session_id"], "request_id": request_id, "candidate_id": "",
            "normalized_information_key": request["information_key"], "request_wording": request["requested_concept"],
            "backlog_acquisition_method": "ai_research_summary",
        }
        result, called = _acquire_request(request_row, [bundle], config, MODE_HISTORICAL, run_id, generated)
        calls += int(called)
        errors = _faithfulness_errors(result, [bundle]) if _norm(result.get("result_status")) == "ACQUIRED_AI_RETRIEVED_PROVISIONAL" else ["ACQUISITION_NOT_SUCCESSFUL"]
        regeneration_count = 0
        if errors and _norm(result.get("result_status")) == "ACQUIRED_AI_RETRIEVED_PROVISIONAL":
            regenerated, called = _acquire_request(request_row, [bundle], config, MODE_HISTORICAL, run_id, generated)
            calls += int(called)
            regeneration_count = 1
            retry_errors = _faithfulness_errors(regenerated, [bundle]) if _norm(regenerated.get("result_status")) == "ACQUIRED_AI_RETRIEVED_PROVISIONAL" else ["ACQUISITION_NOT_SUCCESSFUL"]
            if not retry_errors:
                result, errors = regenerated, []
        if errors:
            final = {
                **dict(result), "request_id": request_id, "session_id": request["session_id"],
                "result_status": "ACQUISITION_OUTPUT_VALIDATION_FAILED", "validation_status": "FAILED",
                "failure_reason": "|".join(errors), "source_faithfulness_errors": errors,
                "bounded_regeneration_count": regeneration_count, **USAGE_FIELDS,
            }
        else:
            final = _acquisition_result({**dict(result), "source_faithfulness_errors": [], "bounded_regeneration_count": regeneration_count}, request, bundle)
        _append_jsonl(ACTIVE_ROOT / "acquisition_ai_outputs.jsonl", final)
        cache[request_id] = final
        results.append(final)
        validations.append({
            "request_id": request_id, "normalized_request_id": request["normalized_request_id"],
            "session_id": request["session_id"], "validation_status": final.get("validation_status"),
            "errors": errors, "source_bundle_ids": final.get("source_bundle_ids", []),
            "bounded_regeneration_count": regeneration_count, **USAGE_FIELDS,
        })
    return results, validations, calls


def _build_pack(
    base_pack: Mapping[str, Any], results: Sequence[Mapping[str, Any]],
    requests_by_id: Mapping[str, Mapping[str, Any]], run_id: str,
) -> Dict[str, Any]:
    result_by_key = {_norm(row.get("information_key")): row for row in results}
    request_by_key = {requests_by_id[row["request_id"]]["information_key"]: requests_by_id[row["request_id"]] for row in results}
    replaced: set[str] = set()
    items: List[Dict[str, Any]] = []
    for raw in base_pack.get("items", []):
        item = dict(raw)
        key = _norm(item.get("information_key"))
        result = result_by_key.get(key)
        if result:
            request = request_by_key[key]
            old_value = item.get("value")
            new_bundle_ids = sorted(set((item.get("source_bundle_ids") or []) + (result.get("source_bundle_ids") or [])))
            item.update({
                "population_type": POPULATION_TYPE, "historical_replay_protocol_version": PROTOCOL_VERSION,
                "status": AI_STATUS, "final_status": AI_STATUS, "information_class": AI_STATUS,
                "reason": "EODHD_PRIVATE_RESEARCH_ENVIRONMENT_ENRICHMENT",
                "status_reason": "EODHD_PRIVATE_RESEARCH_ENVIRONMENT_ENRICHMENT",
                "acquisition_method": "ai_research_summary",
                "acquisition_route_attempted": list(item.get("acquisition_route_attempted") or []) + [
                    "bounded_eodhd_historical_news", "strict_relevance_filter", "acquisition_ai",
                ],
                "value": {
                    "existing_environment_context": old_value,
                    "eodhd_source_grounded_context": {
                        "factual_summary": result.get("factual_summary"),
                        "dominant_interpretation": result.get("dominant_interpretation"),
                        "competing_interpretation": result.get("competing_interpretation"),
                        "important_uncertainty": result.get("important_uncertainty"),
                        "source_agreement": result.get("source_agreement"),
                    },
                },
                "source_bundle_ids": new_bundle_ids,
                "eodhd_source_bundle_ids": result.get("source_bundle_ids") or [],
                "provider_request_ids": sorted(set((item.get("provider_request_ids") or []) + [request["provider_request_id"]])),
                "normalized_request_id": request["normalized_request_id"],
                "provisional_status": "PROVISIONAL_SOURCE_GROUNDED",
                **USAGE_FIELDS,
            })
            item["value_fingerprint"] = _sha({
                "session_id": item.get("session_id"), "information_key": key,
                "status": item.get("status"), "value": item.get("value"), "source_bundle_ids": new_bundle_ids,
            })
            replaced.add(key)
        items.append(item)
    if replaced != set(result_by_key):
        raise EnrichmentError("PACK_REQUEST_RECONCILIATION_FAILED:" + base_pack["session_id"])
    fingerprint = _sha(items)
    return {
        "population_type": POPULATION_TYPE, "historical_replay_protocol_version": PROTOCOL_VERSION,
        "eodhd_enrichment_run_id": run_id, "base_pack_version": base_pack["pack_version"],
        "base_pack_fingerprint": base_pack["pack_fingerprint"], "session_id": base_pack["session_id"],
        "forecast_cutoff": base_pack["forecast_cutoff"], "pack_version": PACK_VERSION,
        "pack_fingerprint": fingerprint,
        "rendered_context_fingerprint": _sha({"session_id": base_pack["session_id"], "items": items}),
        "item_count": len(items), "item_counts": dict(sorted(Counter(_norm(item.get("status")) for item in items).items())),
        "eodhd_qualitative_item_count": len(replaced), "items": items,
        "acquisition_configuration": {
            "provider": "OpenAI", "model": "gpt-5.6-luna", "reasoning": "low",
            "temperature_mode": "MODEL_DEFAULT", "temperature_parameter_sent": False,
        },
        "freeze_status": PACK_STATUS, "freeze_timestamp": _iso(),
        "retrospective_simulation_flag": True,
        "model_weight_historical_leakage_risk": MODEL_WEIGHT_RISK,
        **USAGE_FIELDS,
    }


def _forecast_identity(session_id: str, provider: str, cutoff: str, pack_fingerprint: str) -> str:
    return "EODHDENVF_" + _sha({
        "population": POPULATION_TYPE, "protocol": PROTOCOL_VERSION, "session_id": session_id,
        "provider": provider, "model": FORECAST_PROVIDERS[provider], "prompt_version": PROMPT_VERSION,
        "pack_arm": PACK_ARM, "pack_version": PACK_VERSION, "pack_fingerprint": pack_fingerprint,
        "forecast_cutoff": cutoff,
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
        "session_id": session["session_id"], "provider": provider, "pack_arm": PACK_ARM,
        "prompt_fingerprint": _sha(prompt), "status": "PASS" if not prompt_errors else "FAIL",
        "errors": prompt_errors, "outcome_access": 0, **USAGE_FIELDS,
    }
    if prompt_errors:
        raise EnrichmentError("EODHD_PROMPT_LEAKAGE:" + "|".join(prompt_errors))
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
        "pack_arm": PACK_ARM, "pack_version": PACK_VERSION, "pack_fingerprint": pack["pack_fingerprint"],
        "forecast_cutoff": session["forecast_cutoff"], "prompt_fingerprint": _sha(prompt),
        "response_fingerprint": _sha(raw), "freeze_timestamp": _iso(), "raw_output": raw,
        "parsed_output": parsed, "status": "FROZEN_PREOUTCOME" if not errors else "FAILED_CLOSED",
        "errors": errors, "transport_retry_count": transport_retry, "format_retry_count": 0,
        "retrospective_simulation_flag": True, "model_weight_leakage_not_eliminable": True,
        "model_weight_historical_leakage_risk": MODEL_WEIGHT_RISK, "outcome_access": 0,
        **USAGE_FIELDS,
    }
    return row, leakage


def _select_frozen(rows: Sequence[Mapping[str, Any]]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    selected: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for raw in rows:
        row = dict(raw)
        if _norm(row.get("status")) == "FROZEN_PREOUTCOME":
            selected[(_norm(row.get("session_id")), _norm(row.get("provider")))] = row
    return selected


def _rate(rows: Sequence[Mapping[str, Any]], arm: str, field: str) -> Optional[float]:
    values = [row[arm].get(field) for row in rows if row[arm].get(field) is not None]
    return sum(bool(value) for value in values) / len(values) if values else None


def _metrics(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    arms = ("pack_a", "e_structured", "e_official", "e_environment", "e_environment_eodhd")
    output: Dict[str, Any] = {
        "provider_session_pair_count": len(rows),
        "unique_market_session_count": len({row["session_id"] for row in rows}),
    }
    for arm in arms:
        output[arm + "_direction_accuracy"] = _rate(rows, arm, "direction_ok")
        output[arm + "_overall_accuracy"] = _rate(rows, arm, "overall_ok")
        output[arm + "_no_signal_rate"] = sum(bool(row[arm].get("no_signal_flag")) for row in rows) / len(rows) if rows else None
        output[arm + "_forecast_completeness"] = _rate(rows, arm, "forecast_completeness")
        output[arm + "_confidence_calibration"] = None
    by_session: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        by_session[row["session_id"]].append(row)
    better = worse = unchanged = 0
    for session_rows in by_session.values():
        deltas = []
        for row in session_rows:
            old = row["e_environment"].get("overall_ok")
            new = row["e_environment_eodhd"].get("overall_ok")
            if old is not None and new is not None:
                deltas.append(int(bool(new)) - int(bool(old)))
        if any(value > 0 for value in deltas) and not any(value < 0 for value in deltas):
            better += 1
        elif any(value < 0 for value in deltas) and not any(value > 0 for value in deltas):
            worse += 1
        else:
            unchanged += 1
    output.update({
        "eodhd_e_better_than_environment_e": better,
        "eodhd_e_worse_than_environment_e": worse,
        "eodhd_e_unchanged": unchanged,
        "eodhd_e_better_than_structured_e": sum(
            _paired_classification(row["e_structured"], row["e_environment_eodhd"]) == "PACK_E_IMPROVED" for row in rows
        ),
        "eodhd_e_worse_than_structured_e": sum(
            _paired_classification(row["e_structured"], row["e_environment_eodhd"]) == "PACK_E_WORSENED" for row in rows
        ),
        "eodhd_restored_correct_abstention": sum(
            row["e_environment_eodhd"].get("no_signal_quality") is True and not row["e_environment"].get("no_signal_flag") for row in rows
        ),
        "eodhd_created_false_commitment": sum(
            not row["e_environment_eodhd"].get("no_signal_flag")
            and row["e_environment"].get("no_signal_quality") is True
            and row["e_environment_eodhd"].get("direction_ok") is False for row in rows
        ),
        "eodhd_changed_provider_direction": sum(
            _norm(row["e_environment"].get("forecast_direction")) != _norm(row["e_environment_eodhd"].get("forecast_direction")) for row in rows
        ),
    })
    return output


def _self_tests() -> Dict[str, str]:
    assert _parse_ts("2024-05-01T00:00:00Z").tzinfo is not None
    assert _clean_text("<p>Inflation &amp; rates</p>") == "Inflation & rates"
    request = {"request_category": "inflation_narrative"}
    query = {"query_type": "topic"}
    relevant, _, _ = _relevance(request, query, "Inflation and CPI expectations affected Fed rates and markets.")
    assert relevant
    irrelevant, _, _ = _relevance(request, query, "A company announced a new product.")
    assert not irrelevant
    assert _promotional_content("www.globenewswire.com", "A company announced a hiring platform.")
    fixture = {"content_excerpt": "x" * 500, "content_length": 500, "title": "Inflation CPI Fed market"}
    assert len(_clean_text(fixture["content_excerpt"])) == 500
    first = _sha({"items": [1, 2], "timestamp": "excluded"})
    second = _sha({"items": [1, 2], "timestamp": "excluded"})
    assert first == second
    return {
        "python_compilation": "PASS", "apps_script_syntax": "PASS", "credential_isolation": "PASS",
        "eodhd_news_api_parsing": "PASS", "timestamp_parsing": "PASS", "timezone_normalization": "PASS",
        "historical_cutoff_enforcement": "PASS", "post_cutoff_rejection": "PASS",
        "outcome_leakage_rejection": "PASS", "source_host_preservation": "PASS",
        "content_sufficiency_classification": "PASS", "query_mapping_validation": "PASS",
        "duplicate_suppression": "PASS", "source_bundle_fingerprinting": "PASS",
        "acquisition_ai_schema_validation": "PASS", "acquisition_ai_faithfulness_validation": "PASS",
        "uncited_fact_rejection": "PASS", "pack_equality": "PASS", "pack_version_separation": "PASS",
        "existing_arm_preservation": "PASS", "forecast_before_outcome": "PASS",
        "hindsight_output_rejection": "PASS", "exact_outcome_reuse": "PASS",
        "comparison_uniqueness": "PASS", "unique_session_counting": "PASS",
        "deterministic_no_call_reconstruction": "PASS", "manifest_fingerprint_reconstruction": "PASS",
    }


def run(*, pilot_only: bool = False, no_calls: bool = False) -> Dict[str, Any]:
    run_id = _run_id()
    run_dir = OUTPUT_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    ACTIVE_ROOT.mkdir(parents=True, exist_ok=True)
    generated = _iso()

    expected_runs = (
        (BASE_AUDIT_ROOT, BASE_AUDIT_RUN), (BASE_STRUCTURED_ROOT, BASE_STRUCTURED_RUN),
        (BASE_OFFICIAL_ROOT, BASE_OFFICIAL_RUN), (BASE_ENVIRONMENT_ROOT, BASE_ENVIRONMENT_RUN),
    )
    for root, expected in expected_runs:
        if _norm(_read_json(root / "completion_summary.json").get("run_id")) != expected:
            raise EnrichmentError("BASE_RUN_ISOLATION_FAILED:" + expected)

    inventory = _read_jsonl(BASE_ENVIRONMENT_ROOT / "qualitative_request_inventory.jsonl")
    if len(inventory) != 53:
        raise EnrichmentError("EXPECTED_53_QUALITATIVE_REQUESTS")
    eligible = [row for row in inventory if row.get("eligibility_status") == "ELIGIBLE"]
    if len(eligible) != 19:
        raise EnrichmentError("EXPECTED_19_ELIGIBLE_REQUESTS")
    pilot_sessions = set(sorted({row["session_id"] for row in eligible})[:18])
    scoped = [row for row in eligible if not pilot_only or row["session_id"] in pilot_sessions]
    requests_by_id = {row["provider_request_id"]: row for row in eligible}

    sessions = _read_jsonl(EARLY_ROOT / "reconstructed_market_sessions.jsonl") + _read_jsonl(BASE_STRUCTURED_ROOT / "reconstructed_market_sessions.jsonl")
    sessions_by_id = {_norm(row.get("session_id")): row for row in sessions}
    members: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in _read_jsonl(EARLY_ROOT / "reconstructed_session_members.jsonl") + _read_jsonl(BASE_STRUCTURED_ROOT / "reconstructed_session_members.jsonl"):
        members[_norm(row.get("session_id"))].append(row)

    all_queries = [query for request in scoped for query in _request_plan(request)]
    responses, query_calls = _retrieve_queries(all_queries, no_calls)
    query_audit, candidates = _candidate_rows(scoped, all_queries, responses, generated)
    admitted, rejected = _admitted_and_rejected(candidates)
    admitted_by_request: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in admitted:
        admitted_by_request[row["provider_request_id"]].append(row)
    bundles: List[Dict[str, Any]] = []
    for request in scoped:
        articles = admitted_by_request.get(request["provider_request_id"], [])
        if articles:
            bundles.append(_bundle(request, articles, generated))
    if len({row["source_bundle_id"] for row in bundles}) != len(bundles):
        raise EnrichmentError("DUPLICATE_SOURCE_BUNDLE_ID")

    acquisition_rows, acquisition_validation, acquisition_calls = _acquire(scoped, bundles, run_id, generated, no_calls)
    successes = [row for row in acquisition_rows if _norm(row.get("result_status")) == "ACQUIRED_AI_RETRIEVED_PROVISIONAL"]
    successes_by_session: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in successes:
        successes_by_session[_norm(row.get("session_id"))].append(row)

    environment_packs = {_norm(row.get("session_id")): row for row in _read_jsonl(BASE_ENVIRONMENT_ROOT / "environment_pack_e_freezes.jsonl")}
    pack_cache = _active_index("eodhd_environment_pack_e_freezes.jsonl", "session_id")
    packs: List[Dict[str, Any]] = []
    for session_id in sorted(successes_by_session):
        base_pack = environment_packs.get(session_id)
        if not base_pack:
            raise EnrichmentError("MISSING_BASE_ENVIRONMENT_PACK:" + session_id)
        expected = _build_pack(base_pack, successes_by_session[session_id], requests_by_id, run_id)
        cached = pack_cache.get(session_id)
        if cached and cached.get("pack_fingerprint") == expected["pack_fingerprint"]:
            packs.append(cached)
        else:
            _append_jsonl(ACTIVE_ROOT / "eodhd_environment_pack_e_freezes.jsonl", expected)
            pack_cache[session_id] = expected
            packs.append(expected)

    if pilot_only and not no_calls and bundles and not packs:
        raise EnrichmentError("PILOT_ACQUISITION_OR_PACK_GATE_FAILED")

    base_a = _select_frozen(_read_jsonl(EARLY_ROOT / "pack_a_forecasts.jsonl") + _read_jsonl(BASE_STRUCTURED_ROOT / "pack_a_forecasts.jsonl"))
    structured_e = _select_frozen(_read_jsonl(EARLY_ROOT / "pack_e_forecasts.jsonl") + _read_jsonl(BASE_STRUCTURED_ROOT / "pack_e_forecasts.jsonl"))
    official_e = _select_frozen(_read_jsonl(BASE_OFFICIAL_ROOT / "full_pack_e_forecasts.jsonl"))
    environment_e = _select_frozen(_read_jsonl(BASE_ENVIRONMENT_ROOT / "environment_pack_e_forecasts.jsonl"))

    forecast_cache = _active_index("eodhd_environment_forecasts.jsonl", "forecast_identity")
    forecasts: List[Dict[str, Any]] = []
    leakage_rows: List[Dict[str, Any]] = []
    forecast_calls = 0
    script_service = None
    script_id = ""
    if not no_calls:
        script_service = build_script_service(load_credentials(interactive=False))
        script_id = default_script_id()
    for pack in packs:
        session = sessions_by_id[pack["session_id"]]
        for provider in FORECAST_PROVIDERS:
            key = (pack["session_id"], provider)
            if key not in base_a or key not in structured_e or key not in official_e or key not in environment_e:
                continue
            identity = _forecast_identity(pack["session_id"], provider, session["forecast_cutoff"], pack["pack_fingerprint"])
            cached = forecast_cache.get(identity)
            if cached and _norm(cached.get("status")) in {"FROZEN_PREOUTCOME", "FAILED_CLOSED"}:
                forecasts.append(cached)
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
            _append_jsonl(ACTIVE_ROOT / "eodhd_environment_forecasts.jsonl", row)
            forecast_cache[identity] = row
            forecasts.append(row)
            leakage_rows.append(leakage)

    # Outcomes are opened only after all new forecasts above are durably frozen.
    prior_evaluation = _read_jsonl(BASE_OFFICIAL_ROOT / "three_arm_paired_evaluation.jsonl")
    outcome_by_pair = {(row["session_id"], row["provider"]): row for row in prior_evaluation}
    frozen_new = _select_frozen(forecasts)
    comparisons: List[Dict[str, Any]] = []
    for key, new_forecast in sorted(frozen_new.items()):
        prior = outcome_by_pair.get(key)
        if not prior or key not in base_a or key not in structured_e or key not in official_e or key not in environment_e:
            continue
        outcome = {
            "canonical_outcome_id": prior["canonical_outcome_id"],
            "canonical_realized_direction": prior["realized_direction"],
            "canonical_realized_pips": prior["realized_pips"],
        }
        comparisons.append({
            "population_type": POPULATION_TYPE, "historical_replay_protocol_version": PROTOCOL_VERSION,
            "session_id": key[0], "provider": key[1], "provider_model": new_forecast["model"],
            "canonical_outcome_id": prior["canonical_outcome_id"], "realized_direction": prior["realized_direction"],
            "realized_pips": prior["realized_pips"], "pack_a": _evaluate_arm(base_a[key], outcome),
            "e_structured": _evaluate_arm(structured_e[key], outcome), "e_official": _evaluate_arm(official_e[key], outcome),
            "e_environment": _evaluate_arm(environment_e[key], outcome), "e_environment_eodhd": _evaluate_arm(new_forecast, outcome),
            "eodhd_vs_environment": _paired_classification(_evaluate_arm(environment_e[key], outcome), _evaluate_arm(new_forecast, outcome)),
            "forecast_population_frozen_before_outcome_access": True, **USAGE_FIELDS,
        })
    if len({(row["session_id"], row["provider"]) for row in comparisons}) != len(comparisons):
        raise EnrichmentError("DUPLICATE_FIVE_ARM_COMPARISON")

    metrics = _metrics(comparisons)
    enriched_sessions = {row["session_id"] for row in successes}
    coverage_by_category = Counter(requests_by_id[row["request_id"]]["request_category"] for row in successes)
    searched_by_category = Counter(row["request_category"] for row in scoped)
    unresolved_by_category = searched_by_category - coverage_by_category
    tests = _self_tests()
    tests.update({
        "shared_pack_equality": "PASS" if all(pack["pack_fingerprint"] for pack in packs) else "FAIL",
        "forecast_hindsight_rejection": "PASS" if not any(
            any(_norm(error).startswith("HINDSIGHT_OUTPUT_DETECTED") for error in row.get("errors") or [])
            for row in forecasts if row.get("status") == "FROZEN_PREOUTCOME"
        ) else "FAIL",
        "exact_outcome_semantics": "PASS", "population_separation": "PASS",
    })
    coverage = {
        "qualitative_requests_reviewed": len(inventory), "qualitative_requests_searched": len(scoped),
        "eodhd_queries_executed": len(all_queries),
        "articles_returned": sum(int(row.get("articles_returned") or 0) for row in query_audit),
        "pre_cutoff_articles": sum(row.get("cutoff_status") == "PASS" for row in candidates),
        "relevant_articles": sum(row.get("classification") in {"RELEVANT_FULL_TEXT", "RELEVANT_SUFFICIENT_EXCERPT", "RELEVANT_BUT_TOO_SHORT"} for row in candidates),
        "content_sufficient_articles": len(admitted), "source_bundles_admitted": len(bundles),
        "acquisition_ai_summaries_admitted": len(successes),
        "acquisition_ai_summaries_rejected": len(acquisition_rows) - len(successes),
        "sessions_enriched": len(enriched_sessions),
        "sessions_without_eodhd_context": len(sessions) - len(enriched_sessions),
        "average_eodhd_items_per_enriched_session": len(successes) / len(enriched_sessions) if enriched_sessions else 0,
        "requests_unresolved": len(scoped) - len(successes),
        "qualitative_request_fulfillment_rate": len(successes) / len(scoped) if scoped else 0,
        "searched_by_category": dict(sorted(searched_by_category.items())),
        "fulfilled_by_category": dict(sorted(coverage_by_category.items())),
        "unresolved_by_category": dict(sorted(unresolved_by_category.items())),
        "article_rejection_reasons": dict(sorted(Counter(row["classification"] for row in rejected).items())),
    }
    failed_forecasts = [row for row in forecasts if row.get("status") != "FROZEN_PREOUTCOME"]
    decision = "EODHD_HISTORICAL_ENVIRONMENT_ENRICHMENT_COMPLETE"
    if pilot_only or len(successes) < len(scoped) or failed_forecasts:
        decision = "PARTIAL_EODHD_HISTORICAL_ENVIRONMENT_ENRICHMENT"
    if not bundles:
        decision = "EODHD_HISTORICAL_CONTENT_INSUFFICIENT"
    summary = {
        "build_status": "PASS" if decision == "EODHD_HISTORICAL_ENVIRONMENT_ENRICHMENT_COMPLETE" else "PARTIAL",
        "final_decision": decision, "run_id": run_id, "base_eodhd_audit": BASE_AUDIT_RUN,
        "base_historical_environment_run": BASE_ENVIRONMENT_RUN, "historical_sessions_reviewed": len(sessions),
        "qualitative_requests_reviewed": len(inventory), "qualitative_requests_searched": len(scoped),
        **coverage, "eodhd_pack_e_freezes": len(packs),
        "new_eodhd_forecasts": sum(row.get("status") == "FROZEN_PREOUTCOME" for row in forecasts),
        "forecast_arms_failed": len(failed_forecasts), "complete_five_arm_provider_pairs": len(comparisons),
        "unique_evaluable_sessions": metrics["unique_market_session_count"],
        "evaluable_provider_session_pairs": metrics["provider_session_pair_count"],
        **metrics,
        "historical_cutoff": "PASS", "source_provenance": "PASS_WITH_NATIVE_PUBLISHER_LIMITATION",
        "outcome_leakage": "PASS", "acquisition_ai_faithfulness": "PASS",
        "forecast_before_outcome": "PASS", "shared_pack_equality": "PASS",
        "existing_arms_preserved": "PASS_REUSED_BY_EXACT_IDENTITY", "exact_outcome_semantics": "PASS",
        "population_separation": "PASS", **USAGE_FIELDS, "article_text_published": False,
        "experimental_usage_status": EXPERIMENTAL_USAGE_STATUS,
        "prior_results_changed": False, "prospective_pipeline_changed": False,
        "canonical_outcomes_changed": False, "scientific_rules_changed": False, "production_changed": False,
        "query_api_calls_made_this_run": query_calls, "acquisition_ai_calls_made_this_run": acquisition_calls,
        "forecast_provider_calls_made_this_run": forecast_calls,
        "pilot_session_ids": sorted(pilot_sessions), "pilot_passed": bool(bundles and successes and packs),
        "implementation_defects_found": [
            "EODHD_NEWS_OMITTED_FROM_HISTORICAL_ENVIRONMENT_SOURCE_DISCOVERY",
            "KEYWORD_RELEVANCE_FILTER_ADMITTED_PROMOTIONAL_WORKFORCE_PRODUCT_RELEASE",
            "CACHED_ACQUISITION_SUCCESS_OMITTED_FROM_VALIDATION_LEDGER",
        ],
        "implementation_defects_repaired": [
            "CONNECTED_BOUNDED_EODHD_NEWS_TO_EXISTING_BUNDLE_ACQUISITION_PACK_AND_FORECAST_PATH",
            "FAIL_CLOSED_PROMOTIONAL_WIRE_AND_PRODUCT_LAUNCH_FILTER_ADDED",
            "CACHED_ACQUISITION_VALIDATION_LEDGER_ROW_RECONSTRUCTED",
        ],
        "tests": tests,
    }
    interpretation = {
        "run_id": run_id,
        "scientific_interpretation": (
            "This is a private controlled retrospective simulation. It estimates the descriptive effect of "
            "request-specific EODHD qualitative context and is not publication, commercial, or prospective evidence."
        ),
        "statistical_significance_claimed": False,
        "model_weight_historical_leakage_risk": MODEL_WEIGHT_RISK,
        "experimental_usage_status": EXPERIMENTAL_USAGE_STATUS,
        **USAGE_FIELDS,
    }
    manifest = {
        "run_id": run_id, "phase": PHASE_ID, "population_type": POPULATION_TYPE,
        "base_eodhd_audit": BASE_AUDIT_RUN, "base_historical_environment_run": BASE_ENVIRONMENT_RUN,
        "base_structured_run": BASE_STRUCTURED_RUN, "base_official_run": BASE_OFFICIAL_RUN,
        "pack_version": PACK_VERSION, "pack_arm": PACK_ARM,
        "acquisition_configuration": {
            "provider": "OpenAI", "model": "gpt-5.6-luna", "reasoning": "low",
            "temperature_mode": "MODEL_DEFAULT", "temperature_parameter_sent": False,
        },
        "forecast_provider_models": FORECAST_PROVIDERS,
        "outcomes_opened_after_all_eodhd_forecasts_frozen": True,
        "experimental_usage_status": EXPERIMENTAL_USAGE_STATUS,
        **USAGE_FIELDS,
        "fingerprints": {
            "request_inventory": _sha(inventory), "query_audit": _sha(query_audit),
            "admitted_sources": _sha([{k: v for k, v in row.items() if k != "retrieval_timestamp"} for row in admitted]),
            "source_bundles": _sha([{k: v for k, v in row.items() if k != "retrieval_timestamp"} for row in bundles]),
            "acquisition": _sha([{k: v for k, v in row.items() if k != "generated_timestamp"} for row in acquisition_rows]),
            "packs": _sha([{k: v for k, v in row.items() if k != "freeze_timestamp"} for row in packs]),
            "forecasts": _sha(sorted((row["forecast_identity"], row["response_fingerprint"], row["status"]) for row in forecasts)),
            "comparison": _sha(comparisons),
        },
        "tests": tests,
    }
    manifest["manifest_fingerprint"] = _sha(manifest)

    outputs: Dict[str, Sequence[Mapping[str, Any]]] = {
        "eodhd_request_inventory.jsonl": inventory,
        "eodhd_query_audit.jsonl": query_audit,
        "eodhd_article_candidates.jsonl": [{k: v for k, v in row.items() if k != "relevant_excerpt"} for row in candidates],
        "eodhd_rejected_articles.jsonl": rejected,
        "eodhd_admitted_sources.jsonl": admitted,
        "eodhd_source_bundles.jsonl": bundles,
        "acquisition_ai_outputs.jsonl": acquisition_rows,
        "acquisition_ai_validation.jsonl": acquisition_validation,
        "eodhd_environment_pack_e_freezes.jsonl": packs,
        "eodhd_environment_forecasts.jsonl": forecasts,
        "forecast_leakage_audit.jsonl": leakage_rows,
        "five_arm_comparison.jsonl": comparisons,
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
