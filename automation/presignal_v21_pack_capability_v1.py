#!/usr/bin/env python3
"""Return-only authoritative v2.1 Episode-to-Pack E scientific compute.

This module is intentionally data-free: callers provide an Episode, selected
Attention, raw Information-Request response, and source acquisition records.
It contains no credential, network, workbook, provider, or persistence code.

Provenance:
* e5a0ff288eb1f6fc228936cb1c693ed2bb2ab80f
  automation/build_session_information_requests_v0.py
* e5a0ff288eb1f6fc228936cb1c693ed2bb2ab80f
  automation/build_true_shared_market_state_pack_e_v0.py
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, Iterable

from automation import presignal_v21_event_path_contract_v1 as episode_contract


SOURCE_COMMIT = "e5a0ff288eb1f6fc228936cb1c693ed2bb2ab80f"
REQUEST_SOURCE_PATH = "automation/build_session_information_requests_v0.py"
PACK_SOURCE_PATH = "automation/build_true_shared_market_state_pack_e_v0.py"
CAPABILITY_VERSION = "presignal_v21_episode_to_pack_capability_v1"

VALID_PRIORITIES = frozenset({"must_have", "useful", "optional", "low_value"})
VALID_CATEGORIES = frozenset({
    "treasury_yields", "fed_expectations", "dxy", "usdjpy_trend", "risk_sentiment", "equity_tone",
    "inflation_narrative", "labor_market_trend", "growth_context", "market_positioning",
    "upcoming_larger_events", "jpy_intervention_risk", "volatility", "historical_surprise_sensitivity",
    "event_consensus_detail", "other",
})
VALID_CHANNELS = frozenset({
    "fed_path", "treasury_yields", "usd_direction", "jpy_direction", "risk_sentiment",
    "inflation_expectations", "labor_market", "growth_outlook", "market_positioning",
    "event_importance", "low_direct_market_impact", "unknown",
})
VALID_ATTENTION_LABELS = frozenset({"PRIMARY_DRIVER", "SECONDARY_DRIVER", "WATCHLIST", "CONTEXT_ONLY", "IGNORE", "NO_SIGNAL"})
INTERPRETIVE_CATEGORIES = frozenset({"risk_sentiment", "market_positioning", "jpy_intervention_risk"})
POLICY_CATEGORIES = frozenset({"fed_expectations"})
PROXY_FIELDS = frozenset({"USD_INDEX_PROXY_LEVEL", "USD_INDEX_PROXY_CHANGE"})
BASE_FIELDS = frozenset({
    "USDJPY_RETURN_1H_PRESESSION", "USDJPY_RETURN_4H_PRESESSION", "USDJPY_RETURN_24H_PRESESSION",
    "USDJPY_TREND_LABEL", "USDJPY_REALIZED_VOL_1H_PRESESSION", "NEXT_HIGH_IMPORTANCE_EVENT_WITHIN_24H",
    "NEXT_HIGH_IMPORTANCE_EVENT_WITHIN_48H", "NEXT_CPI_OR_FOMC_WITHIN_72H", "NEXT_NFP_WITHIN_7D",
    "EVENT_CLUSTER_DENSITY_NEXT_24H", "US2Y_YIELD_LEVEL", "US10Y_YIELD_LEVEL",
    "US2Y_CHANGE_FROM_PRIOR_CLOSE", "US10Y_CHANGE_FROM_PRIOR_CLOSE", "US10Y_MINUS_US2Y_CURVE",
    "DXY_LEVEL", "DXY_CHANGE_PRESESSION", "DXY_DIRECTION_LABEL",
})
CALENDAR_FIELD = "EVENT_CONSENSUS_PRIOR_DETAIL"

PRIORITY_NORMALIZATION_MAP = {
    "critical": "must_have", "high": "must_have", "musthave": "must_have", "must_have": "must_have",
    "medium": "useful", "useful": "useful", "nice_to_have": "optional", "nice to have": "optional",
    "optional": "optional", "low": "low_value", "low_value": "low_value",
}
CATEGORY_NORMALIZATION_MAP = {
    "yield": "treasury_yields", "yields": "treasury_yields", "rates": "treasury_yields", "rate": "treasury_yields",
    "fed_path": "fed_expectations", "fed": "fed_expectations", "dollar_index": "dxy", "dollar index": "dxy",
    "fx_trend": "usdjpy_trend", "fx trend": "usdjpy_trend", "risk_tone": "risk_sentiment",
    "risk tone": "risk_sentiment", "equities": "equity_tone", "labor": "labor_market_trend",
    "positioning": "market_positioning", "boj_intervention": "jpy_intervention_risk",
    "consensus_detail": "event_consensus_detail", "other": "other",
}
FAMILY_BY_FIELD = {
    "USDJPY_": "usdjpy_trend", "NEXT_": "upcoming_larger_events",
    "EVENT_CLUSTER_": "upcoming_larger_events", "US2Y_": "treasury_yields",
    "US10Y_": "treasury_yields", "DXY_": "dxy",
}


class PackCapabilityError(ValueError):
    """Raised when a frozen Episode-to-Pack invariant is not satisfied."""


class FrozenDict(Mapping[str, Any]):
    """Small immutable mapping used for returned canonical objects."""

    __slots__ = ("_data",)

    def __init__(self, values: Mapping[str, Any]):
        self._data = dict(values)

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __iter__(self):
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __repr__(self) -> str:
        return f"FrozenDict({self._data!r})"


def to_plain_data(value: Any) -> Any:
    """Return a detached JSON-compatible copy of a canonical returned object."""
    if isinstance(value, Mapping):
        return {str(key): to_plain_data(nested) for key, nested in value.items()}
    if isinstance(value, tuple):
        return [to_plain_data(nested) for nested in value]
    if isinstance(value, list):
        return [to_plain_data(nested) for nested in value]
    return value


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return FrozenDict({str(key): _freeze(nested) for key, nested in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(nested) for nested in value)
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(to_plain_data(value), ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def checksum(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _short(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()[:24]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _require(value: Any, code: str) -> Any:
    if value is None or value == "" or value == []:
        raise PackCapabilityError(code)
    return value


def _utc(value: Any, code: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(_text(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise PackCapabilityError(code) from exc
    if parsed.tzinfo is None:
        raise PackCapabilityError(code)
    return parsed.astimezone(timezone.utc)


def _utc_text(value: Any, code: str) -> str:
    return _utc(value, code).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normal_text(value: Any) -> str:
    text = _text(value).lower().replace("u.s.", "us").replace("u s ", "us ")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    for before, after in {
        "treasury yields": "treasury yield", "fed funds expectations": "fed expectations",
        "dollar index": "dxy", "fx trend": "usdjpy trend", "risk tone": "risk sentiment",
    }.items():
        text = text.replace(before, after)
    return text


def _information_key(category: str, requested: str) -> str:
    normalized = _normal_text(requested).replace(" ", "_")
    return f"{category}|{normalized or 'unknown_information'}"


def _normal_list(value: Any, *, uppercase: bool = False) -> tuple[str, ...]:
    values = value if isinstance(value, (list, tuple)) else re.split(r"[|,;/]+", _text(value))
    result: list[str] = []
    for item in values:
        text = _text(item)
        text = text.upper() if uppercase else text
        if text and text not in result:
            result.append(text)
    return tuple(result)


def _normal_category(value: Any) -> tuple[str, bool]:
    raw = _text(value).lower().replace("-", "_")
    if raw in VALID_CATEGORIES:
        return raw, False
    normalized = CATEGORY_NORMALIZATION_MAP.get(raw)
    return (normalized, normalized != raw) if normalized else ("other", True)


def _normal_priority(value: Any) -> tuple[str, bool]:
    raw = _text(value).lower().replace("-", "_")
    if raw in VALID_PRIORITIES:
        return raw, False
    normalized = PRIORITY_NORMALIZATION_MAP.get(raw)
    return (normalized, normalized != raw) if normalized else ("useful", True)


def _normal_channel(value: Any) -> str:
    raw = _text(value).lower().replace("-", "_")
    return raw if raw in VALID_CHANNELS else "unknown"


def _raw_object(raw: Any) -> dict[str, Any]:
    if isinstance(raw, Mapping):
        return dict(raw)
    if not isinstance(raw, str):
        raise PackCapabilityError("REQUEST_RAW_OBJECT_REQUIRED")
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PackCapabilityError("REQUEST_RAW_JSON_INVALID") from exc
    if not isinstance(parsed, Mapping):
        raise PackCapabilityError("REQUEST_RAW_TOP_LEVEL_NOT_OBJECT")
    return dict(parsed)


def _validate_episode(episode: Mapping[str, Any], cutoff: Any) -> tuple[str, str]:
    try:
        episode_fingerprint = episode_contract.validate_episode(episode)
    except episode_contract.ContractValidationError as exc:
        raise PackCapabilityError("CANONICAL_EPISODE_INVALID:" + str(exc)) from exc
    cutoff_text = _utc_text(cutoff, "CUTOFF_INVALID")
    if cutoff_text != _text(episode.get("forecast_cutoff_ts")):
        raise PackCapabilityError("CUTOFF_EPISODE_LINEAGE_MISMATCH")
    return _text(episode["episode_id"]), episode_fingerprint


def _validate_attention(attention: Mapping[str, Any], *, episode_id: str, provider: str, model: str, cutoff: str) -> tuple[str, str]:
    attention_id = _text(attention.get("attention_id") or attention.get("attention_run_id"))
    _require(attention_id, "SELECTED_ATTENTION_ID_REQUIRED")
    if _text(attention.get("episode_id")) != episode_id:
        raise PackCapabilityError("SELECTED_ATTENTION_EPISODE_MISMATCH")
    state = _text(attention.get("selection_status") or attention.get("status")).upper()
    if state not in {"SELECTED", "SELECTED_FOR_INFORMATION_REQUESTS"}:
        raise PackCapabilityError("SELECTED_ATTENTION_STATE_REQUIRED")
    if _text(attention.get("provider")) not in {"", provider}:
        raise PackCapabilityError("SELECTED_ATTENTION_PROVIDER_MISMATCH")
    if _text(attention.get("model")) not in {"", model}:
        raise PackCapabilityError("SELECTED_ATTENTION_MODEL_MISMATCH")
    if _text(attention.get("forecast_cutoff_ts")) not in {"", cutoff}:
        raise PackCapabilityError("SELECTED_ATTENTION_CUTOFF_MISMATCH")
    labels = _normal_list(attention.get("attention_labels"), uppercase=True)
    if labels and not set(labels) <= VALID_ATTENTION_LABELS:
        raise PackCapabilityError("SELECTED_ATTENTION_LABEL_INVALID")
    fingerprint = checksum({
        "attention_id": attention_id, "episode_id": episode_id, "selection_status": state,
        "provider": provider, "model": model, "forecast_cutoff_ts": cutoff,
        "attention_labels": labels,
    })
    return attention_id, fingerprint


def compute_canonical_information_requests(
    episode: Mapping[str, Any], selected_attention: Mapping[str, Any], provider: str, model: str,
    prompt_version: str, raw_provider_response: Any, cutoff: str,
) -> tuple[FrozenDict, ...]:
    """Parse supplied Request output into deterministic canonical Requests.

    This is compute only.  The raw response must already have been obtained by
    an explicitly authorized caller.
    """
    episode_id, episode_fingerprint = _validate_episode(episode, cutoff)
    provider, model, prompt_version = _text(provider), _text(model), _text(prompt_version)
    _require(provider, "REQUEST_PROVIDER_REQUIRED"); _require(model, "REQUEST_MODEL_REQUIRED")
    _require(prompt_version, "REQUEST_PROMPT_VERSION_REQUIRED")
    attention_id, attention_fingerprint = _validate_attention(
        selected_attention, episode_id=episode_id, provider=provider, model=model, cutoff=cutoff,
    )
    parsed = _raw_object(raw_provider_response)
    if parsed.get("object") != "session_information_requirements" or parsed.get("status") != "ok":
        raise PackCapabilityError("REQUEST_RESPONSE_SCHEMA_INVALID")
    if _text(parsed.get("provider")) != provider:
        raise PackCapabilityError("REQUEST_RESPONSE_PROVIDER_MISMATCH")
    if "episode_id" in parsed and _text(parsed.get("episode_id")) != episode_id:
        raise PackCapabilityError("REQUEST_RESPONSE_EPISODE_MISMATCH")
    items = parsed.get("information_items")
    if not isinstance(items, list):
        raise PackCapabilityError("REQUEST_ITEMS_NOT_ARRAY")
    valid_event_ids = set(episode["member_event_ids"])
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for input_index, raw in enumerate(items, 1):
        if not isinstance(raw, Mapping):
            raise PackCapabilityError("REQUEST_ITEM_NOT_OBJECT")
        requested = _text(raw.get("requested_information"))
        _require(requested, "REQUESTED_INFORMATION_REQUIRED")
        dedupe_key = _normal_text(requested)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        category, category_normalized = _normal_category(raw.get("information_category"))
        priority, priority_normalized = _normal_priority(raw.get("priority"))
        linked_events = tuple(value for value in _normal_list(raw.get("linked_event_ids")) if value in valid_event_ids)
        linked_labels = tuple(value for value in _normal_list(raw.get("linked_attention_labels"), uppercase=True) if value in VALID_ATTENTION_LABELS)
        request_rank = raw.get("request_rank")
        try:
            rank = int(request_rank) if request_rank not in (None, "") else input_index
        except (TypeError, ValueError) as exc:
            raise PackCapabilityError("REQUEST_RANK_INVALID") from exc
        if rank <= 0:
            raise PackCapabilityError("REQUEST_RANK_INVALID")
        key = _information_key(category, requested)
        identity = {
            "episode_id": episode_id, "attention_fingerprint": attention_fingerprint,
            "provider": provider, "model": model, "prompt_version": prompt_version,
            "forecast_cutoff_ts": cutoff, "information_key": key,
        }
        rows.append({
            "object": "CANONICAL_INFORMATION_REQUEST", "request_identity": "PS21REQ_" + _short(identity),
            "request_rank": rank, "requested_information": requested, "information_key": key,
            "information_category": category, "priority": priority,
            "reason": _text(raw.get("reason"))[:160], "affected_channel": _normal_channel(raw.get("affected_channel")),
            "event_family_relevance": _text(raw.get("event_family_relevance"))[:120],
            "linked_event_ids": linked_events, "linked_attention_labels": linked_labels,
            "available_now": _text(raw.get("available_now")).lower() if _text(raw.get("available_now")).lower() in {"yes", "no", "unknown", "partial"} else "unknown",
            "suggested_source": _text(raw.get("suggested_source"))[:160],
            "expected_forecast_use": _text(raw.get("expected_forecast_use"))[:160],
            "is_market_state_candidate": bool(raw.get("is_market_state_candidate")) or category in {"treasury_yields", "dxy", "usdjpy_trend", "risk_sentiment", "equity_tone", "market_positioning", "jpy_intervention_risk", "volatility", "upcoming_larger_events"},
            "normalization": {"category_normalized": category_normalized, "priority_normalized": priority_normalized},
            "lineage": {"episode_id": episode_id, "episode_fingerprint": episode_fingerprint, "attention_id": attention_id, "attention_fingerprint": attention_fingerprint, "provider": provider, "model": model, "prompt_version": prompt_version, "forecast_cutoff_ts": cutoff, "raw_response_fingerprint": checksum(parsed)},
        })
    rows.sort(key=lambda row: (row["request_rank"], row["requested_information"], row["information_key"]))
    for order, row in enumerate(rows, 1):
        row["canonical_request_order"] = order
    return tuple(_freeze(row) for row in rows)


def _approved_source_ids(environment: Mapping[str, Any]) -> tuple[str, set[str]]:
    environment_id = _text(environment.get("environment_id"))
    _require(environment_id, "SOURCE_ENVIRONMENT_ID_REQUIRED")
    sources = environment.get("approved_source_ids") or environment.get("approved_sources")
    if isinstance(sources, Mapping):
        source_ids = {str(key) for key in sources}
    elif isinstance(sources, (list, tuple, set)):
        source_ids = {_text(value) for value in sources if _text(value)}
    else:
        raise PackCapabilityError("APPROVED_SOURCE_REGISTRY_REQUIRED")
    if not source_ids:
        raise PackCapabilityError("APPROVED_SOURCE_REGISTRY_REQUIRED")
    return environment_id, source_ids


def _capability_for_request(request: Mapping[str, Any]) -> tuple[str, str]:
    category, wording = _text(request.get("information_category")), _text(request.get("requested_information")).lower()
    if category in INTERPRETIVE_CATEGORIES:
        return "INTERPRETIVE_CONTEXT_NOT_ACQUIRED", "INTERPRETIVE_NOT_SUPPLIED"
    if category in POLICY_CATEGORIES:
        return "FED_EXPECTATIONS_POLICY_BLOCK", "POLICY_REJECTED"
    if category == "event_consensus_detail":
        return "EVENT_CONSENSUS_PRIOR_DETAIL", "CALENDAR_DERIVED"
    if category == "treasury_yields":
        return ("TREASURY_FULL_CURVE_AUCTION_DETAIL", "EXCLUDED") if any(token in wording for token in ("5y", "5-year", "5yr", "30", "auction", "across the curve")) else ("TREASURY_2Y_10Y_PRESESSION_STATE", "DETERMINISTIC")
    if category == "dxy":
        return ("DXY_24_48H_TREND_VOLATILITY", "EXCLUDED") if any(token in wording for token in ("24-48", "24 48", "volatility")) else ("DXY_PRESESSION_STATE", "COMPUTED")
    if category == "usdjpy_trend":
        return ("USDJPY_CROSS_ASSET_CORRELATION", "EXCLUDED") if "correlation" in wording else ("USDJPY_PRESESSION_STATE", "COMPUTED")
    if category == "upcoming_larger_events":
        return "UPCOMING_EVENT_CALENDAR", "CALENDAR_DERIVED"
    if category == "historical_surprise_sensitivity":
        return "HISTORICAL_EVENT_SENSITIVITY", "EXCLUDED"
    if category == "equity_tone":
        return "EQUITY_PRESESSION_TONE", "EXCLUDED"
    if category == "volatility":
        return "USDJPY_OPTION_IMPLIED_VOLATILITY", "EXCLUDED"
    if category == "labor_market_trend":
        return "LABOR_MARKET_CONTEXT", "EXCLUDED"
    if category == "growth_context":
        return "GROWTH_CONTEXT", "EXCLUDED"
    if category == "inflation_narrative":
        return "INFLATION_NARRATIVE_SOURCE_GROUNDED", "EXCLUDED"
    return "UNMAPPED_CAPABILITY", "EXCLUDED"


def _field_category(field: str) -> str:
    if field == CALENDAR_FIELD:
        return "event_consensus_detail"
    return next((category for prefix, category in FAMILY_BY_FIELD.items() if field.startswith(prefix)), "")


def _normal_source_items(record: Mapping[str, Any], request: Mapping[str, Any], *, cutoff: datetime, allowed_sources: set[str], default_acquired: str) -> tuple[dict[str, Any], ...]:
    source_items = record.get("source_items")
    if not isinstance(source_items, (list, tuple)) or not source_items:
        raise PackCapabilityError("SOURCE_ITEMS_REQUIRED")
    normalized: list[dict[str, Any]] = []
    for raw in source_items:
        if not isinstance(raw, Mapping):
            raise PackCapabilityError("SOURCE_ITEM_NOT_OBJECT")
        field = _text(raw.get("canonical_field"))
        if field in PROXY_FIELDS:
            raise PackCapabilityError("PROXY_SOURCE_EXCLUDED:" + field)
        if field not in BASE_FIELDS | {CALENDAR_FIELD}:
            raise PackCapabilityError("UNAUTHORIZED_CANONICAL_FIELD:" + field)
        if _field_category(field) != _text(request.get("information_category")):
            raise PackCapabilityError("SOURCE_FIELD_CATEGORY_MISMATCH:" + field)
        source_id = _text(raw.get("source_id") or record.get("source_id"))
        if source_id not in allowed_sources:
            raise PackCapabilityError("UNAUTHORIZED_SOURCE:" + source_id)
        source_ts = _utc(raw.get("source_timestamp") or record.get("source_timestamp"), "SOURCE_TIMESTAMP_REQUIRED")
        as_of = _utc(raw.get("as_of_timestamp") or record.get("as_of_timestamp"), "AS_OF_TIMESTAMP_REQUIRED")
        acquired = _utc(raw.get("acquisition_timestamp") or record.get("acquisition_timestamp") or default_acquired, "ACQUISITION_TIMESTAMP_REQUIRED")
        if source_ts > cutoff or as_of > cutoff or acquired > cutoff:
            raise PackCapabilityError("POST_CUTOFF_INFORMATION:" + field)
        if source_ts > as_of:
            raise PackCapabilityError("SOURCE_AFTER_AS_OF:" + field)
        method = _text(raw.get("acquisition_method") or record.get("acquisition_method"))
        _require(method, "ACQUISITION_METHOD_REQUIRED")
        normalized.append({
            "canonical_field": field, "value": raw.get("value"), "value_type": _text(raw.get("value_type")) or "scalar",
            "source_id": source_id, "source_name": _text(raw.get("source_name") or record.get("source_name")) or source_id,
            "source_identity": _text(raw.get("source_identity") or record.get("source_identity")),
            "source_timestamp": _utc_text(source_ts, "SOURCE_TIMESTAMP_REQUIRED"), "as_of_timestamp": _utc_text(as_of, "AS_OF_TIMESTAMP_REQUIRED"),
            "acquisition_timestamp": _utc_text(acquired, "ACQUISITION_TIMESTAMP_REQUIRED"), "acquisition_method": method,
        })
    fields = [item["canonical_field"] for item in normalized]
    if len(fields) != len(set(fields)):
        raise PackCapabilityError("DUPLICATE_SOURCE_FIELD_FOR_REQUEST")
    return tuple(sorted(normalized, key=lambda item: item["canonical_field"]))


def build_immutable_acquired_information_bundle(
    canonical_requests: Iterable[Mapping[str, Any]], supplied_acquisition_records: Iterable[Mapping[str, Any]],
    authorized_source_environment: Mapping[str, Any], cutoff: str, acquisition_timestamp: str,
) -> FrozenDict:
    """Validate supplied pre-cutoff source evidence and return an immutable bundle."""
    requests = tuple(canonical_requests)
    if not requests:
        raise PackCapabilityError("CANONICAL_REQUESTS_REQUIRED")
    cutoff_dt, acquisition_text = _utc(cutoff, "CUTOFF_INVALID"), _utc_text(acquisition_timestamp, "ACQUISITION_TIMESTAMP_REQUIRED")
    if _utc(acquisition_text, "ACQUISITION_TIMESTAMP_REQUIRED") > cutoff_dt:
        raise PackCapabilityError("BUNDLE_ACQUISITION_AFTER_CUTOFF")
    environment_id, allowed_sources = _approved_source_ids(authorized_source_environment)
    request_by_id = {_text(request.get("request_identity")): request for request in requests}
    if "" in request_by_id or len(request_by_id) != len(requests):
        raise PackCapabilityError("CANONICAL_REQUEST_IDENTITY_INVALID")
    records_by_id: dict[str, Mapping[str, Any]] = {}
    for record in supplied_acquisition_records:
        if not isinstance(record, Mapping):
            raise PackCapabilityError("ACQUISITION_RECORD_NOT_OBJECT")
        request_id = _text(record.get("request_identity"))
        if request_id not in request_by_id:
            raise PackCapabilityError("ACQUISITION_REQUEST_LINEAGE_MISMATCH")
        if request_id in records_by_id:
            raise PackCapabilityError("DUPLICATE_ACQUISITION_RECORD")
        records_by_id[request_id] = record
    items: list[dict[str, Any]] = []
    for request_id in sorted(request_by_id):
        request, record = request_by_id[request_id], records_by_id.get(request_id)
        capability_id, classification = _capability_for_request(request)
        if record is None:
            status, reason, source_items, raw = "UNAVAILABLE", "NO_SUPPLIED_ACQUISITION_RECORD", (), {}
        else:
            supplied_status = _text(record.get("status") or "SUPPLIED").upper()
            raw = dict(record)
            if supplied_status in {"UNAVAILABLE", "NOT_AVAILABLE"}:
                status, reason, source_items = "UNAVAILABLE", _text(record.get("reason")) or "SOURCE_NOT_AVAILABLE", ()
            else:
                if classification in {"INTERPRETIVE_NOT_SUPPLIED", "POLICY_REJECTED", "EXCLUDED"}:
                    raise PackCapabilityError("ACQUISITION_NOT_ADMISSIBLE_FOR_FROZEN_CAPABILITY:" + capability_id)
                source_items = _normal_source_items(record, request, cutoff=cutoff_dt, allowed_sources=allowed_sources, default_acquired=acquisition_text)
                status, reason = "SUPPLIED", ""
        identity = {"request_identity": request_id, "status": status, "source_items": source_items, "environment_id": environment_id}
        items.append({
            "object": "ACQUIRED_INFORMATION_ITEM", "acquired_information_id": "PS21ACQ_" + _short(identity),
            "request_identity": request_id, "information_key": _text(request.get("information_key")),
            "capability_id": capability_id, "capability_classification": classification, "status": status, "reason": reason,
            "source_items": source_items, "raw_record": raw, "raw_record_fingerprint": checksum(raw),
            "normalized_representation_fingerprint": checksum(source_items),
            "lineage": {"episode_id": request["lineage"]["episode_id"], "request_identity": request_id, "request_fingerprint": checksum(request), "authorized_source_environment_id": environment_id, "forecast_cutoff_ts": cutoff, "bundle_acquisition_timestamp": acquisition_text},
        })
    identity = {"requests": [row["request_identity"] for row in items], "items": items, "environment_id": environment_id, "cutoff": cutoff, "acquisition_timestamp": acquisition_text}
    return _freeze({
        "object": "IMMUTABLE_ACQUIRED_INFORMATION_BUNDLE", "bundle_id": "PS21BUNDLE_" + _short(identity),
        "bundle_fingerprint": checksum(identity), "forecast_cutoff_ts": cutoff, "acquisition_timestamp": acquisition_text,
        "authorized_source_environment_id": environment_id, "items": tuple(items),
        "request_fingerprint": checksum(requests), "capability_version": CAPABILITY_VERSION,
    })


FROZEN_PACK_E_RULES_V1 = _freeze({
    "rules_version": "true_shared_pack_e_v0", "source_commit": SOURCE_COMMIT,
    "base_fields": tuple(sorted(BASE_FIELDS)), "excluded_proxy_fields": tuple(sorted(PROXY_FIELDS)),
    "interpretive_categories": tuple(sorted(INTERPRETIVE_CATEGORIES)), "policy_categories": tuple(sorted(POLICY_CATEGORIES)),
    "ordering": "item_key_lexicographic", "deduplication": "canonical_field_content_fingerprint_fail_closed",
    "cutoff": "source_timestamp_as_of_and_acquisition_timestamp_must_not_exceed_forecast_cutoff",
})


def _rules_fingerprint(rules: Mapping[str, Any]) -> str:
    return checksum(rules)


def _pack_item(*, episode_id: str, field: str, request_keys: tuple[str, ...], request_ids: tuple[str, ...], source: Mapping[str, Any], cutoff: str) -> dict[str, Any]:
    classification = "CALENDAR_DERIVED" if field == CALENDAR_FIELD else ("COMPUTED" if field.startswith(("USDJPY_", "DXY_")) else "DETERMINISTIC")
    identity = {"pack_e_version": "true_shared_pack_e_v0", "episode_id": episode_id, "item_key": field, "status": classification, "value": source["value"], "as_of_timestamp": source["as_of_timestamp"], "input_lineage": [{"source_id": source["source_id"], "source_identity": source["source_identity"], "source_timestamp": source["source_timestamp"]}]}
    return {
        "object": "CANONICAL_PACK_E_ITEM", "pack_item_id": "true_pack_e|" + _short(identity), "item_key": field,
        "capability_id": field, "information_class": classification, "acquisition_method": source["acquisition_method"],
        "value": source["value"], "value_type": source["value_type"], "source_name": source["source_name"],
        "source_timestamp": source["source_timestamp"], "as_of_timestamp": source["as_of_timestamp"], "forecast_timestamp": cutoff,
        "input_lineage": identity["input_lineage"], "data_available_flag": "TRUE", "backtest_safe": "TRUE", "provisional_status": "FALSE",
        "status": classification, "reason": "", "requested_information_keys": request_keys, "request_identities": request_ids,
        "content_fingerprint": checksum(identity),
    }


def _declaration_item(*, episode_id: str, capability_id: str, status: str, reason: str, request_keys: tuple[str, ...], request_ids: tuple[str, ...], cutoff: str) -> dict[str, Any]:
    identity = {"pack_e_version": "true_shared_pack_e_v0", "episode_id": episode_id, "item_key": capability_id, "status": status, "value": "", "as_of_timestamp": cutoff, "input_lineage": []}
    return {
        "object": "CANONICAL_PACK_E_ITEM", "pack_item_id": "true_pack_e|" + _short(identity), "item_key": capability_id,
        "capability_id": capability_id, "information_class": status, "acquisition_method": "not_acquired", "value": "", "value_type": "none",
        "source_name": "", "source_timestamp": "", "as_of_timestamp": cutoff, "forecast_timestamp": cutoff, "input_lineage": [],
        "data_available_flag": "FALSE", "backtest_safe": "TRUE", "provisional_status": "UNAVAILABLE_AT_ASOF", "status": status,
        "reason": reason, "requested_information_keys": request_keys, "request_identities": request_ids, "content_fingerprint": checksum(identity),
    }


def assemble_canonical_pack_e(
    episode: Mapping[str, Any], canonical_requests: Iterable[Mapping[str, Any]], acquired_information_bundle: Mapping[str, Any],
    acquisition_manifest: Mapping[str, Any], frozen_pack_e_rules: Mapping[str, Any], cutoff: str,
) -> FrozenDict:
    """Assemble one canonical shared Pack E from validated immutable evidence."""
    episode_id, episode_fingerprint = _validate_episode(episode, cutoff)
    requests = tuple(canonical_requests)
    if not requests:
        raise PackCapabilityError("CANONICAL_REQUESTS_REQUIRED")
    if _rules_fingerprint(frozen_pack_e_rules) != _rules_fingerprint(FROZEN_PACK_E_RULES_V1):
        raise PackCapabilityError("FROZEN_PACK_E_RULES_MISMATCH")
    manifest_id = _text(acquisition_manifest.get("manifest_id"))
    _require(manifest_id, "ACQUISITION_MANIFEST_ID_REQUIRED")
    if _text(acquisition_manifest.get("bundle_id")) != _text(acquired_information_bundle.get("bundle_id")):
        raise PackCapabilityError("ACQUISITION_MANIFEST_BUNDLE_MISMATCH")
    if _text(acquisition_manifest.get("authorized_source_environment_id")) != _text(acquired_information_bundle.get("authorized_source_environment_id")):
        raise PackCapabilityError("ACQUISITION_MANIFEST_ENVIRONMENT_MISMATCH")
    if _text(acquired_information_bundle.get("forecast_cutoff_ts")) != cutoff:
        raise PackCapabilityError("BUNDLE_CUTOFF_LINEAGE_MISMATCH")
    request_by_id = {_text(row.get("request_identity")): row for row in requests}
    bundle_items = acquired_information_bundle.get("items")
    if not isinstance(bundle_items, tuple) or len(bundle_items) != len(request_by_id):
        raise PackCapabilityError("BUNDLE_ITEM_SET_INVALID")
    item_by_request = {_text(row.get("request_identity")): row for row in bundle_items}
    if set(item_by_request) != set(request_by_id):
        raise PackCapabilityError("BUNDLE_REQUEST_LINEAGE_MISMATCH")
    grouped_sources: dict[str, list[tuple[Mapping[str, Any], Mapping[str, Any]]]] = {}
    declarations: dict[str, list[Mapping[str, Any]]] = {}
    for request_id, request in request_by_id.items():
        if _text(request["lineage"].get("episode_id")) != episode_id:
            raise PackCapabilityError("REQUEST_EPISODE_LINEAGE_MISMATCH")
        acquired = item_by_request[request_id]
        capability_id, classification = _capability_for_request(request)
        if classification == "INTERPRETIVE_NOT_SUPPLIED":
            declarations.setdefault(capability_id, []).append(request)
        elif classification == "POLICY_REJECTED":
            declarations.setdefault(capability_id, []).append(request)
        elif classification == "EXCLUDED" or _text(acquired.get("status")) == "UNAVAILABLE":
            declarations.setdefault(capability_id, []).append(request)
        else:
            for source in acquired.get("source_items", ()):
                grouped_sources.setdefault(_text(source.get("canonical_field")), []).append((request, source))
    pack_items: list[dict[str, Any]] = []
    for field, entries in grouped_sources.items():
        first_source = entries[0][1]
        comparable = [canonical_json(source) for _, source in entries]
        if len(set(comparable)) != 1:
            raise PackCapabilityError("DUPLICATE_PACK_ITEM_CONFLICT:" + field)
        request_keys = tuple(sorted({_text(request.get("information_key")) for request, _ in entries}))
        request_ids = tuple(sorted({_text(request.get("request_identity")) for request, _ in entries}))
        pack_items.append(_pack_item(episode_id=episode_id, field=field, request_keys=request_keys, request_ids=request_ids, source=first_source, cutoff=cutoff))
    declaration_reasons = {
        "INTERPRETIVE_CONTEXT_NOT_ACQUIRED": ("INTERPRETIVE_NOT_SUPPLIED", "INTERPRETIVE_JUDGMENT_NOT_SHARED_AS_PACK_TRUTH"),
        "FED_EXPECTATIONS_POLICY_BLOCK": ("POLICY_REJECTED", "FROZEN_FED_EXPECTATIONS_EXCLUSION"),
        "TREASURY_2Y_10Y_PRESESSION_STATE": ("UNAVAILABLE", "APPROVED_TREASURY_SOURCE_UNAVAILABLE_AT_ASOF"),
        "TREASURY_FULL_CURVE_AUCTION_DETAIL": ("UNAVAILABLE", "APPROVED_2Y_10Y_SOURCE_DOES_NOT_PROVE_5Y_30Y_OR_AUCTION_DETAIL"),
        "DXY_PRESESSION_STATE": ("UNAVAILABLE", "APPROVED_DXY_SOURCE_UNAVAILABLE_AT_ASOF"),
        "DXY_24_48H_TREND_VOLATILITY": ("UNAVAILABLE", "FROZEN_DAILY_DXY_SOURCE_DOES_NOT_BUILD_24_48H_OR_VOLATILITY_MEASURE"),
        "USDJPY_PRESESSION_STATE": ("UNAVAILABLE", "APPROVED_USDJPY_SOURCE_UNAVAILABLE_AT_ASOF"),
        "USDJPY_CROSS_ASSET_CORRELATION": ("UNAVAILABLE", "CROSS_ASSET_CORRELATION_SOURCE_NOT_IMPLEMENTED"),
        "EQUITY_PRESESSION_TONE": ("UNAVAILABLE", "EQUITY_SOURCE_SNAPSHOT_NOT_AVAILABLE_IN_REPOSITORY"),
        "USDJPY_OPTION_IMPLIED_VOLATILITY": ("UNAVAILABLE", "OPTIONS_IMPLIED_VOLATILITY_SOURCE_NOT_AVAILABLE"),
        "LABOR_MARKET_CONTEXT": ("UNAVAILABLE", "LABOR_SERIES_SOURCE_BUNDLE_NOT_AVAILABLE_AT_ASOF"),
        "GROWTH_CONTEXT": ("UNAVAILABLE", "GROWTH_SERIES_SOURCE_BUNDLE_NOT_AVAILABLE_AT_ASOF"),
        "HISTORICAL_EVENT_SENSITIVITY": ("UNAVAILABLE", "OUTCOME_SAFE_HISTORICAL_EVENT_STUDY_NOT_BUILT"),
        "UPCOMING_EVENT_CALENDAR": ("UNAVAILABLE", "NAMED_EVENT_DATE_DETAIL_NOT_PROVEN_BY_EXISTING_HORIZON_FLAGS"),
        "EVENT_CONSENSUS_PRIOR_DETAIL": ("UNAVAILABLE", "SESSION_MEMBER_CONSENSUS_SOURCE_UNAVAILABLE"),
        "INFLATION_NARRATIVE_SOURCE_GROUNDED": ("UNAVAILABLE", "AI_SOURCE_BUNDLE_OR_RESEARCH_MODEL_NOT_AVAILABLE_AT_ASOF"),
        "UNMAPPED_CAPABILITY": ("UNAVAILABLE", "TOO_BROAD_REQUIRES_RENORMALIZATION"),
    }
    for capability_id, rows in declarations.items():
        if capability_id == "INTERPRETIVE_CONTEXT_NOT_ACQUIRED":
            status, reason = declaration_reasons[capability_id]
        elif capability_id == "FED_EXPECTATIONS_POLICY_BLOCK":
            status, reason = declaration_reasons[capability_id]
        else:
            status, reason = declaration_reasons[capability_id]
        keys = tuple(sorted({_text(row.get("information_key")) for row in rows}))
        ids = tuple(sorted({_text(row.get("request_identity")) for row in rows}))
        pack_items.append(_declaration_item(episode_id=episode_id, capability_id=capability_id, status=status, reason=reason, request_keys=keys, request_ids=ids, cutoff=cutoff))
    pack_items.sort(key=lambda row: row["item_key"])
    if len({row["item_key"] for row in pack_items}) != len(pack_items):
        raise PackCapabilityError("DUPLICATE_PACK_ITEM_KEY")
    identity = {"pack_e_version": "true_shared_pack_e_v0", "episode_id": episode_id, "forecast_cutoff_ts": cutoff, "items": pack_items, "request_fingerprint": checksum(requests), "bundle_fingerprint": acquired_information_bundle.get("bundle_fingerprint"), "manifest_id": manifest_id, "rules_fingerprint": _rules_fingerprint(frozen_pack_e_rules)}
    return _freeze({
        "object": "CANONICAL_SHARED_PACK_E", "pack_id": "PACK_E_SHARED_" + _short(identity), "pack_fingerprint": checksum(identity),
        "pack_e_version": "true_shared_pack_e_v0", "episode_id": episode_id, "episode_fingerprint": episode_fingerprint,
        "forecast_cutoff_ts": cutoff, "items": tuple(pack_items),
        "lineage": {"request_fingerprint": checksum(requests), "acquired_information_bundle_id": acquired_information_bundle["bundle_id"], "acquired_information_bundle_fingerprint": acquired_information_bundle["bundle_fingerprint"], "acquisition_manifest_id": manifest_id, "authorized_source_environment_id": acquired_information_bundle["authorized_source_environment_id"], "frozen_pack_e_rules_fingerprint": _rules_fingerprint(frozen_pack_e_rules), "source_commit": SOURCE_COMMIT},
    })


def run_offline_episode_to_pack_harness(
    *, episode: Mapping[str, Any], selected_attention: Mapping[str, Any], provider: str, model: str,
    prompt_version: str, raw_information_request_response: Any, supplied_acquisition_records: Iterable[Mapping[str, Any]],
    authorized_source_environment: Mapping[str, Any], acquisition_manifest: Mapping[str, Any], cutoff: str,
    acquisition_timestamp: str, frozen_pack_e_rules: Mapping[str, Any] = FROZEN_PACK_E_RULES_V1,
) -> FrozenDict:
    """Move 4 fixture harness; it does not compare an expected fingerprint."""
    requests = compute_canonical_information_requests(episode, selected_attention, provider, model, prompt_version, raw_information_request_response, cutoff)
    bundle = build_immutable_acquired_information_bundle(requests, supplied_acquisition_records, authorized_source_environment, cutoff, acquisition_timestamp)
    manifest = dict(acquisition_manifest)
    manifest.setdefault("bundle_id", bundle["bundle_id"])
    manifest.setdefault("authorized_source_environment_id", bundle["authorized_source_environment_id"])
    pack = assemble_canonical_pack_e(episode, requests, bundle, manifest, frozen_pack_e_rules, cutoff)
    return _freeze({"canonical_requests": requests, "acquired_information_bundle": bundle, "canonical_pack_e": pack, "checksums": {"requests": checksum(requests), "acquired_information_bundle": bundle["bundle_fingerprint"], "pack_e": pack["pack_fingerprint"]}, "lineage": pack["lineage"]})
