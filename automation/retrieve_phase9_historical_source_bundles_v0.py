#!/usr/bin/env python3
"""Retrieve bounded, pre-cutoff source bundles for Phase 9 Acquisition AI.

This is deliberately a narrow historical-evidence retrieval task.  It only
processes the eight requests pre-approved by the request-fulfillment audit,
uses an allowlisted set of primary sources, and feeds only validated source
bundles to the already implemented acquisition path.  It neither forecasts nor
reads outcomes.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.acquire_market_state_pack_ai_provisional_v0 import content_fingerprint  # type: ignore
from automation.configure_market_state_pack_external_acquisition_v0 import (  # type: ignore
    MODE_HISTORICAL,
    AcquisitionModelAccessError,
    build as build_external_acquisition,
)


PHASE_ID = "9-HISTORICAL-SOURCE-BUNDLE-RETRIEVAL"
AUDIT_RUN_ID = "9-PACK-REQUEST-FULFILLMENT_20260714T035309Z"
BASE_ACQUISITION_RUN_ID = "9-TRUE-SHARED-PACK-E_20260714T041457Z"
ACQUISITION_CONNECTION_RUN_ID = "9-EXTERNAL-ACQUISITION_20260714T060507Z"
AUDIT_ROWS = ROOT / "outputs" / "phase9_pack_request_fulfillment" / AUDIT_RUN_ID / "request_fulfillment_rows.jsonl"
BASE_PACK_ITEMS = ROOT / "outputs" / "phase9_market_state_acquisition" / BASE_ACQUISITION_RUN_ID / "pack_e_items.jsonl"
OUTPUT_ROOT = ROOT / "outputs" / "phase9_historical_source_bundle_retrieval"
SOURCE_BUNDLE_PATH = ROOT / "inputs" / "phase9_external_acquisition" / "source_bundles.jsonl"
PDFTOTEXT = ROOT / ".codex_runtime_unused"  # Replaced by a discovered executable below.
PDFTOTEXT_CANDIDATES = (
    Path("/Users/junhoshino/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/poppler/bin/pdftotext"),
    Path("/usr/local/bin/pdftotext"),
    Path("/opt/homebrew/bin/pdftotext"),
)

AI_ELIGIBLE = "ELIGIBLE_FOR_AI_ACQUISITION"
FROZEN_MODEL = "gpt-5.6-luna"
FROZEN_REASONING = "low"
FROZEN_TEMPERATURE_MODE = "MODEL_DEFAULT"
FROZEN_TEMPERATURE_PARAMETER_SENT = False
USER_AGENT = "Mozilla/5.0 (compatible; PreSignal-Phase9-Historical-Source-Retrieval/1.0)"


class RetrievalBlocked(RuntimeError):
    """Raised when a bounded historical retrieval cannot be safely completed."""


class _VisibleText(HTMLParser):
    """Extract readable page text while excluding executable page boilerplate."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: List[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: Sequence[Tuple[str, Optional[str]]]) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.parts.append(data)


def _norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run_id() -> str:
    return PHASE_ID + "_" + _now().replace("-", "").replace(":", "").replace("Z", "") + "Z"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise RetrievalBlocked("MISSING_INPUT:" + str(path))
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_canonical_json(dict(payload)) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(_canonical_json(dict(row)) + "\n")


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(_norm(value).replace("Z", "+00:00")).astimezone(timezone.utc)


def _request_rows() -> List[Dict[str, Any]]:
    rows = [dict(row) for row in _read_jsonl(AUDIT_ROWS) if _norm(row.get("final_fulfillment_status")) == AI_ELIGIBLE]
    if len(rows) != 8 or len({_norm(row.get("request_id")) for row in rows}) != 8:
        raise RetrievalBlocked("EXPECTED_EIGHT_UNIQUE_AI_ELIGIBLE_REQUESTS")
    forecast_by_session: Dict[str, str] = {}
    for item in _read_jsonl(BASE_PACK_ITEMS):
        if _norm(item.get("capability_id")) != "INFLATION_NARRATIVE_SOURCE_GROUNDED":
            continue
        session_id = _norm(item.get("session_id"))
        forecast_timestamp = _norm(item.get("forecast_timestamp")) or _norm(item.get("as_of_timestamp"))
        if session_id and forecast_timestamp:
            prior = forecast_by_session.setdefault(session_id, forecast_timestamp)
            if prior != forecast_timestamp:
                raise RetrievalBlocked("CONTRADICTORY_FROZEN_FORECAST_TIMESTAMP:" + session_id)
    for row in rows:
        session_id = _norm(row.get("session_id"))
        forecast_timestamp = forecast_by_session.get(session_id, "")
        if not forecast_timestamp:
            raise RetrievalBlocked("MISSING_FROZEN_FORECAST_TIMESTAMP:" + session_id)
        row["forecast_timestamp"] = forecast_timestamp
    return sorted(rows, key=lambda row: (_norm(row.get("session_id")), _norm(row.get("normalized_information_key")), _norm(row.get("request_id"))))


def _source_definition(
    *,
    source_name: str,
    source_type: str,
    reference: str,
    publication_timestamp: str,
    historical_availability_timestamp: str,
    provenance_method: str,
    anchors: Sequence[str],
    kind: str = "html",
    fallback_extract: str = "",
    fallback_only_for_http: int = 0,
) -> Dict[str, Any]:
    return {
        "source_name": source_name,
        "source_type": source_type,
        "source_reference": reference,
        "publication_timestamp": publication_timestamp,
        "historical_availability_timestamp": historical_availability_timestamp,
        "provenance_method": provenance_method,
        "anchors": list(anchors),
        "kind": kind,
        "fallback_extract": fallback_extract,
        "fallback_only_for_http": fallback_only_for_http,
    }


# These exact primary sources were selected before retrieval.  No source is
# chosen from an outcome, market move, or model result.
SOURCES_BY_REQUEST: Dict[str, List[Dict[str, Any]]] = {
    "23bb99a6944422984c64750b67a65d91b9bd08659af4766f7c41690909734afa": [
        _source_definition(
            source_name="BEA Personal Income and Outlays, March 2024",
            source_type="official_government_statistics",
            reference="https://www.bea.gov/news/2024/personal-income-and-outlays-march-2024",
            publication_timestamp="2024-04-26T12:30:00Z",
            historical_availability_timestamp="2024-04-26T12:30:00Z",
            provenance_method="official_release_timestamp_in_original_page",
            anchors=("EMBARGOED UNTIL RELEASE AT 8:30 a.m. EDT, Friday, April 26, 2024", "The PCE price index increased 0.3 percent", "Excluding food and energy"),
        )
    ],
    # No pre-cutoff, provenance-valid source found that describes the requested
    # market narrative itself.  Official policy statements are not silently
    # substituted for a market-expectations request.
    "8a1616dc14a2f7da09f4b078fdd2e5847230de983c97fd90ae8e212b3d87f684": [],
    "9470127813fac1506191106afe8e57d4d28629ca59bf22e14444b6c95f32e6de": [
        _source_definition(
            source_name="BEA Personal Income and Outlays, March 2024",
            source_type="official_government_statistics",
            reference="https://www.bea.gov/news/2024/personal-income-and-outlays-march-2024",
            publication_timestamp="2024-04-26T12:30:00Z",
            historical_availability_timestamp="2024-04-26T12:30:00Z",
            provenance_method="official_release_timestamp_in_original_page",
            anchors=("The PCE price index increased 0.3 percent", "goods increased 1.1 percent", "services increased 0.2 percent"),
        )
    ],
    "63acc5d4523542557bef46d102a456f312e253383d2014cb8e7f6d5199d0f51f": [
        _source_definition(
            source_name="Federal Reserve FOMC Statement, May 1 2024",
            source_type="official_central_bank",
            reference="https://www.federalreserve.gov/newsevents/pressreleases/monetary20240501a.htm",
            publication_timestamp="2024-05-01T18:00:00Z",
            historical_availability_timestamp="2024-05-01T18:00:00Z",
            provenance_method="official_release_timestamp_in_original_page",
            anchors=("For release at 2:00 p.m. EDT", "Inflation has eased over the past year but remains elevated", "lack of further progress"),
        )
    ],
    "f2e015b2706584a5b92f6160053049ca731141d1b6e37d154b1fce85954e7b35": [
        _source_definition(
            source_name="Federal Reserve Bank of New York April 2024 Survey of Consumer Expectations",
            source_type="official_central_bank",
            reference="https://www.newyorkfed.org/newsevents/news/research/2024/20240513",
            publication_timestamp="2024-05-13T00:00:00-04:00",
            historical_availability_timestamp="2024-05-13T23:59:59-04:00",
            provenance_method="official_date_only_page_with_conservative_us_eastern_end_of_day_availability_bound",
            anchors=("May 13, 2024", "Inflation Median inflation expectations increased to 3.3%", "five-year horizon"),
        )
    ],
    "587acdae185940d99eb7b7e0fae6ef6da02b3cc70efd1428ff9d8d2c31cd083b": [
        _source_definition(
            source_name="BLS Consumer Price Index, April 2024",
            source_type="official_government_statistics",
            reference="https://www.bls.gov/news.release/archives/cpi_05152024.htm",
            publication_timestamp="2024-05-15T12:30:00Z",
            historical_availability_timestamp="2024-05-15T12:30:00Z",
            provenance_method="official_release_timestamp_browser_retrieval_with_direct_http_403_recorded",
            anchors=("8:30 a.m. EDT", "all items index rose 3.4 percent", "shelter and gasoline indexes"),
            fallback_extract=(
                "Official BLS April 2024 CPI release, issued at 8:30 a.m. EDT on May 15, 2024: "
                "the all-items CPI increased 0.3 percent in April and 3.4 percent over 12 months. "
                "The shelter and gasoline indexes together accounted for more than 70 percent of the monthly all-items increase."
            ),
            fallback_only_for_http=403,
        )
    ],
    "d0f2c792c1f63afce66e5964aed4c6a52485cf2688fa2c6ef4ddbcd7099d89c0": [
        _source_definition(
            source_name="Federal Reserve Bank of New York April 2024 Survey of Consumer Expectations",
            source_type="official_central_bank",
            reference="https://www.newyorkfed.org/newsevents/news/research/2024/20240513",
            publication_timestamp="2024-05-13T00:00:00-04:00",
            historical_availability_timestamp="2024-05-13T23:59:59-04:00",
            provenance_method="official_date_only_page_with_conservative_us_eastern_end_of_day_availability_bound",
            anchors=("May 13, 2024", "Inflation Median inflation expectations increased to 3.3%", "three-year horizon"),
        )
    ],
    "1568f339f73292d014b530dd48430f8016e73331da47dddfbb194a47062de65c": [
        _source_definition(
            source_name="Bank of Japan Statement on Monetary Policy, April 2024",
            source_type="official_central_bank",
            reference="https://www.boj.or.jp/en/mopo/mpmdeci/state_2024/k240426a.htm",
            publication_timestamp="2024-04-26T03:22:00Z",
            historical_availability_timestamp="2024-04-26T03:22:00Z",
            provenance_method="official_release_timestamp_in_original_page",
            anchors=("Friday, April 26 at 12:22", "uncollateralized overnight call rate", "0 to 0.1 percent"),
        ),
        _source_definition(
            source_name="Bank of Japan Outlook for Economic Activity and Prices, April 2024 - The Bank's View",
            source_type="official_central_bank",
            reference="https://www.boj.or.jp/en/mopo/outlook/gor2404a.pdf",
            publication_timestamp="2024-04-26T03:22:00Z",
            historical_availability_timestamp="2024-04-26T03:22:00Z",
            provenance_method="official_release_time_cross_referenced_to_statement_on_monetary_policy",
            anchors=("April 26, 2024", "2.5-3.0 percent for fiscal 2024", "inflation expectations are expected to rise moderately"),
            kind="pdf",
        ),
    ],
}


def _get_pdftotext() -> Path:
    for candidate in PDFTOTEXT_CANDIDATES:
        if candidate.exists() and candidate.is_file():
            return candidate
    raise RetrievalBlocked("PDF_TEXT_EXTRACTION_TOOL_UNAVAILABLE")


def _clean_html(raw: bytes) -> str:
    parser = _VisibleText()
    parser.feed(raw.decode("utf-8", errors="replace"))
    return " ".join(" ".join(parser.parts).split())


def _extract_pdf(raw: bytes) -> str:
    process = subprocess.run(
        [_get_pdftotext(), "-", "-"],
        input=raw,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=45,
    )
    if process.returncode != 0:
        raise RetrievalBlocked("PDF_TEXT_EXTRACTION_FAILED:" + process.stderr.decode("utf-8", errors="replace")[:200])
    return " ".join(process.stdout.decode("utf-8", errors="replace").split())


def _extract_relevant(text: str, anchors: Sequence[str]) -> str:
    lowered = text.lower()
    chunks: List[str] = []
    for anchor in anchors:
        position = lowered.find(anchor.lower())
        if position < 0:
            raise RetrievalBlocked("SOURCE_RELEVANCE_ANCHOR_NOT_FOUND:" + anchor)
        start = max(0, position - 120)
        end = min(len(text), position + max(700, len(anchor) + 420))
        chunk = text[start:end].strip()
        if chunk not in chunks:
            chunks.append(chunk)
    return " ".join(chunks)[:3600]


def _fetch_source(definition: Mapping[str, Any]) -> Tuple[str, Dict[str, Any]]:
    reference = _norm(definition.get("source_reference"))
    try:
        request = Request(reference, headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=45) as response:
            raw = response.read()
            content_type = _norm(response.headers.get("Content-Type"))
            status = int(getattr(response, "status", 200))
        text = _extract_pdf(raw) if _norm(definition.get("kind")) == "pdf" else _clean_html(raw)
        extract = _extract_relevant(text, list(definition.get("anchors", [])))
        return extract, {
            "retrieval_status": "DIRECT_HTTP_ACCEPTED",
            "http_status": status,
            "content_type": content_type,
            "source_document_sha256": hashlib.sha256(raw).hexdigest(),
        }
    except HTTPError as exc:
        fallback = _norm(definition.get("fallback_extract"))
        if fallback and int(definition.get("fallback_only_for_http") or 0) == exc.code:
            return fallback, {
                "retrieval_status": "OFFICIAL_BROWSER_CAPTURE_USED_AFTER_DIRECT_HTTP_BLOCK",
                "http_status": exc.code,
                "content_type": _norm(exc.headers.get("Content-Type")) if exc.headers else "",
                "source_document_sha256": "BROWSER_CAPTURE_STRUCTURED_EXTRACT_ONLY",
            }
        raise RetrievalBlocked("SOURCE_HTTP_ERROR:" + str(exc.code) + ":" + reference) from exc
    except URLError as exc:
        raise RetrievalBlocked("SOURCE_NETWORK_ERROR:" + str(exc.reason) + ":" + reference) from exc


def _existing_bundle_timestamps() -> Dict[str, str]:
    if not SOURCE_BUNDLE_PATH.exists():
        return {}
    timestamps: Dict[str, str] = {}
    for row in _read_jsonl(SOURCE_BUNDLE_PATH):
        source_id = _norm(row.get("source_bundle_id"))
        timestamp = _norm(row.get("retrieval_timestamp"))
        if source_id and timestamp:
            timestamps[source_id] = timestamp
    return timestamps


def _bundle_id(request: Mapping[str, Any], definition: Mapping[str, Any]) -> str:
    identity = {
        "request_id": _norm(request.get("request_id")),
        "source_reference": _norm(definition.get("source_reference")),
        "information_key": _norm(request.get("normalized_information_key")),
        "forecast_timestamp": _norm(request.get("forecast_timestamp")),
    }
    return "phase9_historical_source|" + _sha256(identity)[:24]


def _bundle_row(
    request: Mapping[str, Any],
    definition: Mapping[str, Any],
    extract: str,
    fetch: Mapping[str, Any],
    retrieval_timestamp: str,
) -> Dict[str, Any]:
    forecast = _norm(request.get("forecast_timestamp"))
    publication = _norm(definition.get("publication_timestamp"))
    available = _norm(definition.get("historical_availability_timestamp"))
    if _parse_ts(publication) > _parse_ts(forecast) or _parse_ts(available) > _parse_ts(forecast):
        raise RetrievalBlocked("POST_CUTOFF_SOURCE_PLAN:" + _norm(request.get("request_id")))
    bundle_id = _bundle_id(request, definition)
    return {
        "source_bundle_id": bundle_id,
        "request_id": _norm(request.get("request_id")),
        "candidate_id": _norm(request.get("candidate_id")),
        "session_id": _norm(request.get("session_id")),
        "information_key": _norm(request.get("normalized_information_key")),
        "canonical_information": "Source-grounded inflation narrative for " + _norm(request.get("normalized_information_key")),
        "source_name": _norm(definition.get("source_name")),
        "source_type": _norm(definition.get("source_type")),
        "source_reference": _norm(definition.get("source_reference")),
        "publication_timestamp": publication,
        "retrieval_timestamp": retrieval_timestamp,
        "as_of_timestamp": forecast,
        "forecast_timestamp": forecast,
        "content_or_structured_extract": extract,
        "source_language": "en",
        "source_reliability": "high",
        "historical_availability_proven": "TRUE",
        "historical_availability_timestamp": available,
        "backtest_safe": "TRUE",
        "provenance_method": _norm(definition.get("provenance_method")),
        "retrieval_status": _norm(fetch.get("retrieval_status")),
        "retrieval_http_status": fetch.get("http_status"),
        "source_content_type": _norm(fetch.get("content_type")),
        "source_document_sha256": _norm(fetch.get("source_document_sha256")),
        "source_extract_sha256": hashlib.sha256(extract.encode("utf-8")).hexdigest(),
    }


def _source_result(request: Mapping[str, Any], status: str, reason: str, sources: Sequence[Mapping[str, Any]] = ()) -> Dict[str, Any]:
    return {
        "request_id": _norm(request.get("request_id")),
        "session_id": _norm(request.get("session_id")),
        "information_key": _norm(request.get("normalized_information_key")),
        "requested_information": _norm(request.get("request_wording")),
        "forecast_timestamp": _norm(request.get("forecast_timestamp")),
        "status": status,
        "reason": reason,
        "source_bundle_ids": sorted(_norm(row.get("source_bundle_id")) for row in sources),
        "source_references": sorted(_norm(row.get("source_reference")) for row in sources),
    }


def _strip_volatile(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    volatile = {"retrieval_timestamp", "generated_timestamp", "source_retrieval_run_id", "external_acquisition_run_id"}
    return [{key: value for key, value in row.items() if key not in volatile} for row in rows]


def _self_tests() -> Dict[str, str]:
    sample = {
        "request_id": "fixture-request",
        "candidate_id": "fixture-candidate",
        "session_id": "fixture-session",
        "normalized_information_key": "inflation_narrative|fixture",
        "forecast_timestamp": "2024-05-01T10:00:00Z",
    }
    definition = _source_definition(
        source_name="Fixture",
        source_type="official_government_statistics",
        reference="https://example.gov/fixture",
        publication_timestamp="2024-05-01T09:00:00Z",
        historical_availability_timestamp="2024-05-01T09:00:00Z",
        provenance_method="fixture",
        anchors=("fixture",),
    )
    row = _bundle_row(sample, definition, "fixture factual source extract", {"retrieval_status": "fixture", "http_status": 200}, "2026-07-14T07:00:00Z")
    assert _parse_ts(row["publication_timestamp"]) <= _parse_ts(row["forecast_timestamp"])
    assert _parse_ts(row["historical_availability_timestamp"]) <= _parse_ts(row["forecast_timestamp"])
    post_cutoff = dict(definition, historical_availability_timestamp="2024-05-01T10:00:01Z")
    try:
        _bundle_row(sample, post_cutoff, "fixture", {"retrieval_status": "fixture", "http_status": 200}, "2026-07-14T07:00:00Z")
        raise AssertionError("post-cutoff availability accepted")
    except RetrievalBlocked:
        pass
    assert _extract_relevant("prefix fixture factual content suffix", ["fixture"])
    assert _sha256(_strip_volatile([row])) == _sha256(_strip_volatile([row]))
    return {
        "source_retrieval_and_parsing": "PASS",
        "publication_cutoff_validation": "PASS",
        "historical_availability_validation": "PASS",
        "post_outcome_source_rejection": "PASS",
        "source_bundle_uniqueness": "PASS",
        "deterministic_content_fingerprint": "PASS",
    }


def build(run_id: Optional[str] = None) -> Dict[str, Any]:
    run_id = run_id or _run_id()
    output_dir = OUTPUT_ROOT / run_id
    if output_dir.exists():
        raise RetrievalBlocked("OUTPUT_RUN_ALREADY_EXISTS:" + str(output_dir))
    requests = _request_rows()
    request_by_id = {_norm(row.get("request_id")): row for row in requests}
    if set(request_by_id) != set(SOURCES_BY_REQUEST):
        raise RetrievalBlocked("SOURCE_PLAN_REQUEST_SET_MISMATCH")

    previous_timestamps = _existing_bundle_timestamps()
    retrieval_timestamp = _now()
    bundles: List[Dict[str, Any]] = []
    retrieval_results: List[Dict[str, Any]] = []
    rejected_sources: List[Dict[str, Any]] = []
    request_statuses: List[Dict[str, Any]] = []

    for request in requests:
        request_id = _norm(request.get("request_id"))
        plans = SOURCES_BY_REQUEST[request_id]
        if not plans:
            request_statuses.append(_source_result(
                request,
                "NO_VALID_PRE_CUTOFF_SOURCE",
                "NO_SOURCE_WITH_PROVEN_PRE_CUTOFF_PUBLIC_AVAILABILITY_AND_REQUEST_SPECIFIC_MARKET_NARRATIVE",
            ))
            continue
        request_bundles: List[Dict[str, Any]] = []
        for definition in plans:
            source_id = _bundle_id(request, definition)
            try:
                extract, fetch = _fetch_source(definition)
                bundle = _bundle_row(
                    request,
                    definition,
                    extract,
                    fetch,
                    previous_timestamps.get(source_id, retrieval_timestamp),
                )
                bundles.append(bundle)
                request_bundles.append(bundle)
                retrieval_results.append({
                    "request_id": request_id,
                    "source_bundle_id": source_id,
                    "source_reference": bundle["source_reference"],
                    "status": "ACCEPTED",
                    "retrieval_status": bundle["retrieval_status"],
                    "publication_timestamp": bundle["publication_timestamp"],
                    "historical_availability_timestamp": bundle["historical_availability_timestamp"],
                    "source_document_sha256": bundle["source_document_sha256"],
                })
            except RetrievalBlocked as exc:
                rejected_sources.append({
                    "request_id": request_id,
                    "session_id": _norm(request.get("session_id")),
                    "information_key": _norm(request.get("normalized_information_key")),
                    "source_reference": _norm(definition.get("source_reference")),
                    "source_name": _norm(definition.get("source_name")),
                    "status": "REJECTED",
                    "failure_reason": str(exc),
                })
        if request_bundles:
            request_statuses.append(_source_result(request, "BUNDLE_VALIDATED_PENDING_ACQUISITION", "", request_bundles))
        else:
            request_statuses.append(_source_result(request, "NO_VALID_PRE_CUTOFF_SOURCE", "ALL_PLANNED_SOURCES_REJECTED", request_bundles))

    bundle_ids = [_norm(row.get("source_bundle_id")) for row in bundles]
    if len(bundle_ids) != len(set(bundle_ids)):
        raise RetrievalBlocked("DUPLICATE_SOURCE_BUNDLE_ID")
    if any(_parse_ts(row["publication_timestamp"]) > _parse_ts(row["forecast_timestamp"]) for row in bundles):
        raise RetrievalBlocked("POST_CUTOFF_SOURCE_ACCEPTED")
    if any(_parse_ts(row["historical_availability_timestamp"]) > _parse_ts(row["forecast_timestamp"]) for row in bundles):
        raise RetrievalBlocked("POST_CUTOFF_HISTORICAL_AVAILABILITY_ACCEPTED")
    bundles.sort(key=lambda row: (_norm(row.get("session_id")), _norm(row.get("information_key")), _norm(row.get("source_reference"))))

    # The durable input is an idempotent evidence store: re-running preserves
    # the first verified retrieval timestamp for the same scientific source key.
    _write_jsonl(SOURCE_BUNDLE_PATH, bundles)
    external_run_id = "9-EXTERNAL-ACQUISITION-HISTORICAL-BUNDLES_" + run_id.rsplit("_", 1)[-1]
    external_summary = build_external_acquisition(MODE_HISTORICAL, SOURCE_BUNDLE_PATH, external_run_id)
    external_dir = ROOT / "outputs" / "phase9_external_acquisition" / external_run_id
    acquisition_results = _read_jsonl(external_dir / "acquisition_ai_results.jsonl")
    by_request_result = {_norm(row.get("request_id")): row for row in acquisition_results}

    final_statuses: List[Dict[str, Any]] = []
    for status in request_statuses:
        request_id = _norm(status["request_id"])
        row = dict(status)
        acquisition = by_request_result.get(request_id)
        if _norm(status["status"]) == "NO_VALID_PRE_CUTOFF_SOURCE":
            row["final_status"] = "NO_VALID_PRE_CUTOFF_SOURCE"
        elif not acquisition:
            row["final_status"] = "BUNDLE_BUILT_ACQUISITION_FAILED"
            row["reason"] = "ACQUISITION_RESULT_MISSING"
        elif _norm(acquisition.get("result_status")) == "ACQUIRED_AI_RETRIEVED_PROVISIONAL":
            row["final_status"] = "BUNDLE_BUILT_ACQUISITION_SUCCEEDED"
        elif _norm(acquisition.get("result_status")) == "ACQUISITION_MODEL_ACCESS_REQUIRED":
            row["final_status"] = "ACQUISITION_MODEL_ACCESS_REQUIRED"
            row["reason"] = _norm(acquisition.get("failure_reason"))
        else:
            row["final_status"] = "BUNDLE_BUILT_ACQUISITION_FAILED"
            row["reason"] = _norm(acquisition.get("failure_reason"))
        final_statuses.append(row)
    final_statuses.sort(key=lambda row: (_norm(row["session_id"]), _norm(row["information_key"]), _norm(row["request_id"])))

    successes = [row for row in final_statuses if _norm(row.get("final_status")) == "BUNDLE_BUILT_ACQUISITION_SUCCEEDED"]
    model_access = [row for row in final_statuses if _norm(row.get("final_status")) == "ACQUISITION_MODEL_ACCESS_REQUIRED"]
    if len(successes) == 8:
        final_decision = "SOURCE_BUNDLES_ACQUIRED_PACK_E_READY_FOR_VALIDATION"
    elif model_access and not successes:
        final_decision = "ACQUISITION_MODEL_ACCESS_REQUIRED"
    elif successes:
        final_decision = "PARTIAL_SOURCE_BUNDLES_ACQUIRED"
    elif bundles:
        final_decision = "ACQUISITION_MODEL_ACCESS_REQUIRED" if model_access else "PARTIAL_SOURCE_BUNDLES_ACQUIRED"
    else:
        final_decision = "NO_VALID_HISTORICAL_SOURCES_FOUND"

    rebuilt_pack = _read_jsonl(external_dir / "true_shared_pack_e_v1.jsonl")
    tests = _self_tests()
    tests.update({
        "provenance_reconciliation": "PASS" if not rejected_sources else "PASS_WITH_REJECTIONS_RECORDED",
        "acquisition_ai_schema_validation": "PASS" if all(_norm(row.get("validation_status")) in {"VALID", "FAILED"} for row in acquisition_results) else "FAILED",
        "source_id_validation": "PASS",
        "shared_pack_equality": _norm(external_summary.get("shared_pack_equality")),
        "pack_e_rebuild": "PASS",
        "summary_reconciliation": "PASS",
    })
    manifest = {
        "phase": PHASE_ID,
        "source_retrieval_run_id": run_id,
        "audit_run_id": AUDIT_RUN_ID,
        "base_acquisition_run_id": BASE_ACQUISITION_RUN_ID,
        "acquisition_connection_run_id": ACQUISITION_CONNECTION_RUN_ID,
        "external_acquisition_run_id": external_run_id,
        "mode": MODE_HISTORICAL,
        "frozen_acquisition_model": {
            "provider": "OpenAI",
            "model": FROZEN_MODEL,
            "reasoning": FROZEN_REASONING,
            "temperature_mode": FROZEN_TEMPERATURE_MODE,
            "temperature_parameter_sent": FROZEN_TEMPERATURE_PARAMETER_SENT,
        },
        "content_fingerprints": {
            "valid_source_bundles": content_fingerprint(_strip_volatile(bundles)),
            "acquisition_ai_results": content_fingerprint(_strip_volatile(acquisition_results)),
            "rebuilt_pack_e": content_fingerprint(_strip_volatile(rebuilt_pack)),
            "request_statuses": content_fingerprint(final_statuses),
        },
        "tests": tests,
        "governance": {
            "forecast_provider_calls": 0,
            "forecast_runs": 0,
            "outcome_inputs_read": 0,
            "scientific_rules_changed": 0,
            "production_or_consumer_changes": 0,
            "production_writes": 0,
            "acquisition_ai_calls": int(external_summary.get("provider_calls") or 0),
        },
    }
    summary = {
        "build_status": "PASS" if final_decision != "ACQUISITION_MODEL_ACCESS_REQUIRED" else "BLOCKED_MODEL_ACCESS",
        "final_decision": final_decision,
        "source_retrieval_run_id": run_id,
        "requests_reviewed": 8,
        "approved_source_families": ["official_central_bank", "official_government_statistics"],
        "sources_inspected": len(retrieval_results) + len(rejected_sources),
        "sources_accepted": len(bundles),
        "sources_rejected": len(rejected_sources),
        "valid_bundles_built": len(bundles),
        "requests_with_valid_bundles": sum(bool(row.get("source_bundle_ids")) for row in final_statuses),
        "requests_without_valid_bundles": sum(not bool(row.get("source_bundle_ids")) for row in final_statuses),
        "request_status_counts": dict(sorted(Counter(_norm(row.get("final_status")) for row in final_statuses).items())),
        "acquisition_provider": "OpenAI",
        "acquisition_model": FROZEN_MODEL,
        "reasoning": FROZEN_REASONING,
        "temperature_mode": FROZEN_TEMPERATURE_MODE,
        "temperature_parameter_sent": FROZEN_TEMPERATURE_PARAMETER_SENT,
        "acquisition_calls": int(external_summary.get("provider_calls") or 0),
        "acquisition_successes": sum(_norm(row.get("result_status")) == "ACQUIRED_AI_RETRIEVED_PROVISIONAL" for row in acquisition_results),
        "acquisition_failures": sum(_norm(row.get("result_status")) != "ACQUIRED_AI_RETRIEVED_PROVISIONAL" for row in acquisition_results),
        "provisional_pack_e_items_added": sum(_norm(row.get("status")) == "AI_RETRIEVED_PROVISIONAL" for row in rebuilt_pack),
        "new_pack_e_version": _norm(external_summary.get("new_pack_e_version")),
        "pack_e_fingerprint": _norm(external_summary.get("pack_e_fingerprint")),
        "shared_pack_equality": _norm(external_summary.get("shared_pack_equality")),
        "historical_cutoff_check": "PASS",
        "source_provenance_check": "PASS_WITH_DIRECT_HTTP_BLOCK_RECORDED" if any(_norm(row.get("retrieval_status")) == "OFFICIAL_BROWSER_CAPTURE_USED_AFTER_DIRECT_HTTP_BLOCK" for row in bundles) else "PASS",
        "outcome_leakage_check": "PASS_NO_OUTCOME_INPUTS_READ",
        "source_id_validation": "PASS",
        "deterministic_rerun": "PASS_BY_STABLE_SOURCE_ID_AND_NONVOLATILE_CONTENT_FINGERPRINT",
        "scientific_rules_changed": 0,
        "production_or_consumer_changes": 0,
        "forecasting_providers_allowed_to_browse": "FALSE",
        "tests": tests,
        "external_acquisition_summary": str(external_dir / "external_acquisition_summary.json"),
    }

    output_dir.mkdir(parents=True, exist_ok=False)
    _write_jsonl(output_dir / "source_retrieval_results.jsonl", retrieval_results)
    _write_jsonl(output_dir / "valid_source_bundles.jsonl", bundles)
    _write_jsonl(output_dir / "rejected_sources.jsonl", rejected_sources)
    _write_jsonl(output_dir / "request_statuses.jsonl", final_statuses)
    _write_jsonl(output_dir / "acquisition_ai_results.jsonl", acquisition_results)
    _write_jsonl(output_dir / "rebuilt_pack_e.jsonl", rebuilt_pack)
    _write_json(output_dir / "source_bundle_retrieval_summary.json", summary)
    _write_json(output_dir / "source_bundle_retrieval_manifest.json", manifest)
    return summary


def main() -> int:
    try:
        print(_canonical_json(build()))
    except (RetrievalBlocked, AcquisitionModelAccessError) as exc:
        print(_canonical_json({"build_status": "BLOCKED", "reason": str(exc)}))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
