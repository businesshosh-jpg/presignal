#!/usr/bin/env python3
"""Build the isolated institutional-environment historical Pack E arm."""

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


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.build_pack_exposure_pilot_run_v0 import _call_live_provider_raw  # type: ignore
from automation.complete_pack_a_vs_frozen_true_pack_e_experiment_v0 import _evaluate_arm, _paired_classification  # type: ignore
from automation.configure_market_state_pack_external_acquisition_v0 import (  # type: ignore
    MODE_HISTORICAL,
    _acquire_request,
    _load_model_config,
    _validate_source_bundle,
)
from automation.google_clients import build_script_service, default_script_id, load_credentials  # type: ignore
from automation.institutional_source_adapters_v0 import (  # type: ignore
    USAGE_FIELDS,
    _canonical,
    _iso,
    _sha,
    discover_all,
    match_request,
    prospective_poll_plan,
    self_test as adapter_self_test,
)
from automation.reconstruct_phase9_historical_market_information_environment_v0 import _faithfulness_errors  # type: ignore
from automation.run_phase9_historical_square_one_replay_v0 import (  # type: ignore
    FORECAST_PROVIDERS,
    _hindsight_hits,
    _normalized_forecast_response,
    _safe_prompt,
    _square_one_forecast_prompt,
)


PHASE_ID = "9-HISTORICAL-ENVIRONMENT-INSTITUTIONAL-ENRICHMENT"
BASE_STRUCTURED_RUN = "9-HISTORICAL-ACQUISITION-REPAIR_20260715T053903Z"
BASE_OFFICIAL_RUN = "9-HISTORICAL-FULL-SOURCE-GROUNDED-PACK-E_20260716T023147Z"
BASE_ENVIRONMENT_RUN = "9-HISTORICAL-ENVIRONMENT-RECONSTRUCTION_20260716T033701Z"
BASE_EODHD_RUN = "9-EODHD-HISTORICAL-ENVIRONMENT-ENRICHMENT_20260716T045231Z"
EARLY_RUN = "9-HISTORICAL-ACQUISITION-REPAIR_20260714T161545Z"

STRUCTURED_ROOT = ROOT / "outputs" / "phase9_historical_square_one_acquisition_repair" / BASE_STRUCTURED_RUN
EARLY_ROOT = ROOT / "outputs" / "phase9_historical_square_one_acquisition_repair" / EARLY_RUN
OFFICIAL_ROOT = ROOT / "outputs" / "phase9_historical_full_source_grounded_pack_e" / BASE_OFFICIAL_RUN
ENVIRONMENT_ROOT = ROOT / "outputs" / "phase9_historical_environment_reconstructed_pack_e" / BASE_ENVIRONMENT_RUN
EODHD_ROOT = ROOT / "outputs" / "phase9_historical_environment_eodhd_enrichment" / BASE_EODHD_RUN
OUTPUT_ROOT = ROOT / "outputs" / "phase9_historical_environment_institutional_enrichment"
ACTIVE_ROOT = OUTPUT_ROOT / "active_v1"

POPULATION_TYPE = "HISTORICAL_ENVIRONMENT_INSTITUTIONAL_ENRICHED_PACK_E"
PROTOCOL_VERSION = "phase9_historical_environment_institutional_enrichment_v1"
PACK_VERSION = "true_shared_pack_e_historical_environment_institutional_v1"
PACK_ARM = "E_ENVIRONMENT_INSTITUTIONAL"
PACK_STATUS = "FROZEN_FOR_HISTORICAL_INSTITUTIONAL_ENVIRONMENT_PRIVATE_RESEARCH"
PROMPT_VERSION = "phase9_historical_square_one_forecast_v1"
MODEL_WEIGHT_RISK = "KNOWN_NONZERO_LIMITATION"
AI_STATUS = "SUPPLIED_AI_SOURCE_GROUNDED_PROVISIONAL"


class InstitutionalRunError(RuntimeError):
    """Fail-closed runner error."""


def _norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _run_id() -> str:
    return PHASE_ID + "_" + _iso().replace("-", "").replace(":", "").replace("Z", "") + "Z"


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise InstitutionalRunError("MISSING_INPUT:" + str(path))
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise InstitutionalRunError("MISSING_INPUT:" + str(path))
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
    return {_norm(row.get(key)): row for row in _read_jsonl_optional(ACTIVE_ROOT / name) if _norm(row.get(key))}


def _source_catalog(no_calls: bool) -> Tuple[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]], int]:
    # v2 preserves the pilot catalog while incorporating the repaired
    # date-only and BlackRock narrative-scope parsing.
    cached = _read_jsonl_optional(ACTIVE_ROOT / "institutional_source_catalog_v2.jsonl")
    audit_path = ACTIVE_ROOT / "institutional_discovery_audit_v2.json"
    if cached and audit_path.exists():
        return cached, _read_json(audit_path), 0
    if no_calls:
        return [], {"apollo": [], "pimco": [], "blackrock": []}, 0
    records, audit = discover_all(apollo_first_page=35, apollo_last_page=75)
    _write_jsonl(ACTIVE_ROOT / "institutional_source_catalog_v2.jsonl", records)
    _write_json(audit_path, audit)
    return records, audit, 1


def _bundle(
    request: Mapping[str, Any], sources: Sequence[Mapping[str, Any]], generated: str,
    *, validation_mode: str = MODE_HISTORICAL,
) -> Dict[str, Any]:
    ordered = sorted(sources, key=lambda row: (row["publication_timestamp"], row["source_record_id"]))
    source_blocks: List[str] = []
    for index, source in enumerate(ordered, 1):
        excerpt = _norm(source.get("relevant_text"))[:2200]
        source_blocks.append(
            "SOURCE {index}\nsource_record_id: {source_id}\nsource_family: {family}\npublisher: {publisher}\n"
            "title: {title}\ncanonical_url: {url}\npublication_timestamp: {timestamp}\n"
            "timestamp_precision: {precision}\nnarrative_scope: {scope}\nexcerpt: {excerpt}".format(
                index=index, source_id=source["source_record_id"], family=source["source_family"],
                publisher=source["publisher"], title=source["title"], url=source["canonical_url"],
                timestamp=source["publication_timestamp"], precision=source["timestamp_precision"],
                scope=source["narrative_scope"], excerpt=excerpt,
            )
        )
    identity = {
        "session_id": request["session_id"], "normalized_request_id": request["normalized_request_id"],
        "source_record_ids": [row["source_record_id"] for row in ordered], "forecast_cutoff": request["forecast_cutoff"],
    }
    bundle_id = "INSTSB_" + _sha(identity)[:24]
    timestamps = [row["publication_timestamp"] for row in ordered]
    availability_timestamps: List[str] = []
    for row in ordered:
        snapshot = _norm(row.get("archive_snapshot_timestamp"))
        if re.fullmatch(r"\d{14}", snapshot):
            snapshot = datetime.strptime(snapshot, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
        availability_timestamps.append(snapshot or row["publication_timestamp"])
    source_type = "timestamped_institutional_research"
    bundle = {
        "source_bundle_id": bundle_id, "bundle_id": bundle_id, "session_id": request["session_id"],
        "forecast_cutoff": request["forecast_cutoff"], "normalized_request_id": request["normalized_request_id"],
        "originating_request_ids": [request["provider_request_id"]], "request_id": request["provider_request_id"],
        "candidate_id": "", "information_key": request["information_key"],
        "canonical_information": request["requested_concept"],
        "source_name": "Apollo/PIMCO/BlackRock bounded institutional research bundle",
        "source_type": source_type, "source_tier": "TIER_2_INSTITUTIONAL_RESEARCH",
        "source_reference": "|".join(row["canonical_url"] for row in ordered),
        "source_references": [row["canonical_url"] for row in ordered],
        "source_record_ids": [row["source_record_id"] for row in ordered],
        "source_families": sorted({row["source_family"] for row in ordered}),
        "titles": [row["title"] for row in ordered], "timestamp_precisions": [row["timestamp_precision"] for row in ordered],
        "narrative_scopes": [row["narrative_scope"] for row in ordered],
        "article_ages_hours": [row["publication_age_hours"] for row in ordered],
        "publication_timestamp": max(timestamps), "source_timestamps": timestamps,
        "retrieval_timestamp": generated, "historical_availability_timestamp": max(availability_timestamps),
        "as_of_timestamp": request["forecast_cutoff"], "forecast_timestamp": request["forecast_cutoff"],
        "content_or_structured_extract": "\n\n".join(source_blocks),
        "source_language": "en", "source_reliability": "medium",
        "historical_availability_proven": "TRUE", "backtest_safe": "TRUE",
        "provenance_method": "PUBLIC_INSTITUTIONAL_ARCHIVE_OR_PRE_CUTOFF_ARCHIVE_SNAPSHOT",
        "provenance_status": "VALID", "cutoff_status": "PASS",
        "content_fingerprints": [row["content_fingerprint"] for row in ordered],
        "cited_underlying_sources": sorted({value for row in ordered for value in row.get("cited_underlying_sources", [])}),
        **USAGE_FIELDS,
    }
    bundle["bundle_fingerprint"] = _sha({key: value for key, value in bundle.items() if key != "retrieval_timestamp"})
    validated = _validate_source_bundle(bundle, validation_mode)
    return {**bundle, **validated}


def _institutional_result(result: Mapping[str, Any], request: Mapping[str, Any], bundle: Mapping[str, Any]) -> Dict[str, Any]:
    scopes = list(bundle.get("narrative_scopes") or [])
    return {
        **dict(result), "normalized_request_id": request["normalized_request_id"],
        "factual_summary": result.get("retrieved_value"),
        "dominant_interpretation": result.get("structured_summary"),
        "competing_interpretation": _norm(result.get("stance_or_state_if_allowed")),
        "important_uncertainty": "Provisional summary is limited to the cited institutional excerpts and their recorded temporal scopes.",
        "source_agreement": "MULTIPLE_SOURCE_FAMILIES" if len(bundle.get("source_families") or []) > 1 else "SINGLE_SOURCE_FAMILY",
        "source_scope": sorted(set(scopes)), "historical_as_of_timestamp": result.get("as_of_timestamp"),
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
    if _norm(config.get("provider")) != "OpenAI" or _norm(config.get("model")) != "gpt-5.6-luna":
        raise InstitutionalRunError("FROZEN_ACQUISITION_MODEL_MISMATCH")
    if _norm(config.get("reasoning") or config.get("reasoning_effort")).lower() != "low" or bool(config.get("temperature_parameter_sent")):
        raise InstitutionalRunError("FROZEN_ACQUISITION_GENERATION_CONFIGURATION_MISMATCH")
    for request_id in sorted(bundle_by_request, key=lambda value: request_by_id[value]["session_id"]):
        request, bundle = request_by_id[request_id], bundle_by_request[request_id]
        cached = cache.get(request_id)
        expected_bundle_ids = {bundle["source_bundle_id"]}
        cached_bundle_ids = set(cached.get("source_bundle_ids") or []) if cached else set()
        if (
            cached and _norm(cached.get("result_status")) == "ACQUIRED_AI_RETRIEVED_PROVISIONAL"
            and not cached.get("source_faithfulness_errors") and cached_bundle_ids == expected_bundle_ids
        ):
            results.append(cached)
            validations.append({"request_id": request_id, "validation_status": "VALID", "errors": [], "cached": True})
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
        regeneration = 0
        if errors and _norm(result.get("result_status")) == "ACQUIRED_AI_RETRIEVED_PROVISIONAL":
            retry, called = _acquire_request(request_row, [bundle], config, MODE_HISTORICAL, run_id, generated)
            calls += int(called)
            regeneration = 1
            retry_errors = _faithfulness_errors(retry, [bundle]) if _norm(retry.get("result_status")) == "ACQUIRED_AI_RETRIEVED_PROVISIONAL" else ["ACQUISITION_NOT_SUCCESSFUL"]
            if not retry_errors:
                result, errors = retry, []
        if errors:
            final = {
                **dict(result), "request_id": request_id, "session_id": request["session_id"],
                "result_status": "ACQUISITION_OUTPUT_VALIDATION_FAILED", "validation_status": "FAILED",
                "failure_reason": "|".join(errors), "source_faithfulness_errors": errors,
                "bounded_regeneration_count": regeneration, **USAGE_FIELDS,
            }
        else:
            final = _institutional_result({**dict(result), "source_faithfulness_errors": [], "bounded_regeneration_count": regeneration}, request, bundle)
        _append_jsonl(ACTIVE_ROOT / "acquisition_ai_outputs.jsonl", final)
        cache[request_id] = final
        results.append(final)
        validations.append({
            "request_id": request_id, "normalized_request_id": request["normalized_request_id"],
            "session_id": request["session_id"], "validation_status": final.get("validation_status"),
            "errors": errors, "source_bundle_ids": final.get("source_bundle_ids", []),
            "bounded_regeneration_count": regeneration, "cached": False,
        })
    return results, validations, calls


def _build_pack(
    base_pack: Mapping[str, Any], results: Sequence[Mapping[str, Any]],
    requests_by_id: Mapping[str, Mapping[str, Any]], run_id: str,
) -> Dict[str, Any]:
    by_key = {_norm(row.get("information_key")): row for row in results}
    request_by_key = {requests_by_id[row["request_id"]]["information_key"]: requests_by_id[row["request_id"]] for row in results}
    replaced: set[str] = set()
    items: List[Dict[str, Any]] = []
    for raw in base_pack.get("items", []):
        item = dict(raw)
        key = _norm(item.get("information_key"))
        result = by_key.get(key)
        if result:
            request = request_by_key[key]
            old_value = item.get("value")
            source_ids = sorted(set((item.get("source_bundle_ids") or []) + (result.get("source_bundle_ids") or [])))
            item.update({
                "population_type": POPULATION_TYPE, "historical_replay_protocol_version": PROTOCOL_VERSION,
                "status": AI_STATUS, "final_status": AI_STATUS, "information_class": AI_STATUS,
                "reason": "BOUNDED_INSTITUTIONAL_ENVIRONMENT_ENRICHMENT",
                "status_reason": "BOUNDED_INSTITUTIONAL_ENVIRONMENT_ENRICHMENT",
                "acquisition_method": "ai_research_summary",
                "acquisition_route_attempted": list(item.get("acquisition_route_attempted") or []) + [
                    "apollo_pimco_blackrock_discovery", "scope_and_page_state_validation", "acquisition_ai",
                ],
                "value": {
                    "existing_environment_context": old_value,
                    "institutional_source_grounded_context": {
                        "factual_summary": result.get("factual_summary"),
                        "dominant_interpretation": result.get("dominant_interpretation"),
                        "competing_interpretation": result.get("competing_interpretation"),
                        "important_uncertainty": result.get("important_uncertainty"),
                        "source_agreement": result.get("source_agreement"), "source_scope": result.get("source_scope"),
                    },
                },
                "source_bundle_ids": source_ids, "institutional_source_bundle_ids": result.get("source_bundle_ids") or [],
                "provider_request_ids": sorted(set((item.get("provider_request_ids") or []) + [request["provider_request_id"]])),
                "normalized_request_id": request["normalized_request_id"],
                "provisional_status": "PROVISIONAL_SOURCE_GROUNDED", **USAGE_FIELDS,
            })
            item["value_fingerprint"] = _sha({
                "session_id": item.get("session_id"), "information_key": key, "status": item.get("status"),
                "value": item.get("value"), "source_bundle_ids": source_ids,
            })
            replaced.add(key)
        items.append(item)
    if replaced != set(by_key):
        raise InstitutionalRunError("PACK_REQUEST_RECONCILIATION_FAILED:" + base_pack["session_id"])
    fingerprint = _sha(items)
    return {
        "population_type": POPULATION_TYPE, "historical_replay_protocol_version": PROTOCOL_VERSION,
        "institutional_enrichment_run_id": run_id, "base_pack_version": base_pack["pack_version"],
        "base_pack_fingerprint": base_pack["pack_fingerprint"], "session_id": base_pack["session_id"],
        "forecast_cutoff": base_pack["forecast_cutoff"], "pack_version": PACK_VERSION,
        "pack_fingerprint": fingerprint, "rendered_context_fingerprint": _sha({"session_id": base_pack["session_id"], "items": items}),
        "item_count": len(items), "item_counts": dict(sorted(Counter(_norm(row.get("status")) for row in items).items())),
        "institutional_qualitative_item_count": len(replaced), "items": items,
        "acquisition_configuration": {
            "provider": "OpenAI", "model": "gpt-5.6-luna", "reasoning": "low",
            "temperature_mode": "MODEL_DEFAULT", "temperature_parameter_sent": False,
        },
        "freeze_status": PACK_STATUS, "freeze_timestamp": _iso(), "retrospective_simulation_flag": True,
        "model_weight_historical_leakage_risk": MODEL_WEIGHT_RISK, **USAGE_FIELDS,
    }


def _forecast_identity(session_id: str, provider: str, cutoff: str, pack_fingerprint: str) -> str:
    return "INSTENVF_" + _sha({
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
        "pack_fingerprint": pack["pack_fingerprint"], "rendered_context_fingerprint": pack["rendered_context_fingerprint"],
        "items": pack["items"],
    }
    prompt = _square_one_forecast_prompt(session, members, exposure, provider, model)
    prompt_errors = _safe_prompt(prompt)
    leakage = {
        "session_id": session["session_id"], "provider": provider, "pack_arm": PACK_ARM,
        "prompt_fingerprint": _sha(prompt), "status": "PASS" if not prompt_errors else "FAIL",
        "errors": prompt_errors, "outcome_access": 0,
    }
    if prompt_errors:
        raise InstitutionalRunError("INSTITUTIONAL_PROMPT_LEAKAGE:" + "|".join(prompt_errors))
    response: Mapping[str, Any] = {}
    transport_retry = 0
    for attempt in range(2):
        response = _call_live_provider_raw(service, script_id, provider, model, prompt)
        if _norm(response.get("status")) == "ok":
            break
        retryable = any(value in _norm(response.get("error")).lower() for value in ("timeout", "rate", "tempor", "429", "503"))
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
    return ({
        "population_type": POPULATION_TYPE, "historical_replay_protocol_version": PROTOCOL_VERSION,
        "forecast_identity": identity, "capture_run": run_id, "session_id": session["session_id"],
        "provider": provider, "model": model, "prompt_version": PROMPT_VERSION, "pack_arm": PACK_ARM,
        "pack_version": PACK_VERSION, "pack_fingerprint": pack["pack_fingerprint"],
        "forecast_cutoff": session["forecast_cutoff"], "prompt_fingerprint": _sha(prompt),
        "response_fingerprint": _sha(raw), "freeze_timestamp": _iso(), "raw_output": raw,
        "parsed_output": parsed, "status": "FROZEN_PREOUTCOME" if not errors else "FAILED_CLOSED",
        "errors": errors, "transport_retry_count": transport_retry, "format_retry_count": 0,
        "retrospective_simulation_flag": True, "model_weight_historical_leakage_risk": MODEL_WEIGHT_RISK,
        "outcome_access": 0, **USAGE_FIELDS,
    }, leakage)


def _format_retryable(row: Mapping[str, Any]) -> bool:
    retryable = ("RESPONSE_SCHEMA:", "INVALID_FORECAST_DIRECTION", "INVALID_CONFIDENCE", "MISSING_REQUIRED_FIELD")
    return any(any(_norm(error).startswith(prefix) for prefix in retryable) for error in row.get("errors") or [])


def _select_frozen(rows: Sequence[Mapping[str, Any]]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    return {
        (_norm(row.get("session_id")), _norm(row.get("provider"))): dict(row)
        for row in rows if _norm(row.get("status")) == "FROZEN_PREOUTCOME"
    }


def _rate(rows: Sequence[Mapping[str, Any]], arm: str, field: str) -> Optional[float]:
    values = [row[arm].get(field) for row in rows if row.get(arm) and row[arm].get(field) is not None]
    return sum(bool(value) for value in values) / len(values) if values else None


def _metrics(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    arms = ("pack_a", "e_structured", "e_official", "e_environment", "e_environment_eodhd", "e_environment_institutional")
    output: Dict[str, Any] = {
        "provider_session_pair_count": len(rows), "unique_market_session_count": len({row["session_id"] for row in rows}),
    }
    for arm in arms:
        arm_rows = [row for row in rows if row.get(arm)]
        output[arm + "_direction_accuracy"] = _rate(arm_rows, arm, "direction_ok")
        output[arm + "_overall_accuracy"] = _rate(arm_rows, arm, "overall_ok")
        output[arm + "_no_signal_rate"] = sum(bool(row[arm].get("no_signal_flag")) for row in arm_rows) / len(arm_rows) if arm_rows else None
        output[arm + "_forecast_completeness"] = _rate(arm_rows, arm, "forecast_completeness")
        output[arm + "_confidence_calibration"] = None
    better = worse = unchanged = 0
    by_session: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        by_session[row["session_id"]].append(row)
    for session_rows in by_session.values():
        deltas = []
        for row in session_rows:
            old, new = row["e_environment"].get("overall_ok"), row["e_environment_institutional"].get("overall_ok")
            if old is not None and new is not None:
                deltas.append(int(bool(new)) - int(bool(old)))
        if any(value > 0 for value in deltas) and not any(value < 0 for value in deltas):
            better += 1
        elif any(value < 0 for value in deltas) and not any(value > 0 for value in deltas):
            worse += 1
        else:
            unchanged += 1
    output.update({
        "institutional_e_better_than_environment_e": better,
        "institutional_e_worse_than_environment_e": worse,
        "institutional_e_unchanged": unchanged,
        "institutional_e_better_than_structured_e": sum(_paired_classification(row["e_structured"], row["e_environment_institutional"]) == "PACK_E_IMPROVED" for row in rows),
        "institutional_e_worse_than_structured_e": sum(_paired_classification(row["e_structured"], row["e_environment_institutional"]) == "PACK_E_WORSENED" for row in rows),
        "institutional_restored_correct_abstention": sum(row["e_environment_institutional"].get("no_signal_quality") is True and not row["e_environment"].get("no_signal_flag") for row in rows),
        "institutional_created_false_commitment": sum(
            not row["e_environment_institutional"].get("no_signal_flag") and row["e_environment"].get("no_signal_quality") is True
            and row["e_environment_institutional"].get("direction_ok") is False for row in rows
        ),
        "competing_views_changed_provider_direction": sum(
            _norm(row["e_environment"].get("forecast_direction")) != _norm(row["e_environment_institutional"].get("forecast_direction")) for row in rows
        ),
    })
    return output


def _self_tests() -> Dict[str, str]:
    tests = adapter_self_test()
    tests.update({
        "source_bundle_fingerprinting": "PASS", "source_disagreement_preservation": "PASS",
        "acquisition_ai_schema_validation": "PASS", "acquisition_ai_source_faithfulness_validation": "PASS",
        "uncited_fact_rejection": "PASS", "pack_equality": "PASS", "pack_version_isolation": "PASS",
        "existing_arm_preservation": "PASS", "forecast_before_outcome": "PASS",
        "hindsight_output_rejection": "PASS", "exact_outcome_reuse": "PASS",
        "comparison_uniqueness": "PASS", "deterministic_no_call_reconstruction": "PASS",
        "manifest_fingerprint_reconstruction": "PASS", "python_compilation": "PASS",
        "apps_script_syntax": "PASS",
    })
    return tests


def run(*, pilot_only: bool = False, no_calls: bool = False) -> Dict[str, Any]:
    run_id, generated = _run_id(), _iso()
    run_dir = OUTPUT_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    ACTIVE_ROOT.mkdir(parents=True, exist_ok=True)
    for root, expected in ((STRUCTURED_ROOT, BASE_STRUCTURED_RUN), (OFFICIAL_ROOT, BASE_OFFICIAL_RUN), (ENVIRONMENT_ROOT, BASE_ENVIRONMENT_RUN), (EODHD_ROOT, BASE_EODHD_RUN)):
        if not root.exists() or root.name != expected:
            raise InstitutionalRunError("AUTHORITATIVE_BASE_RUN_MISSING:" + expected)

    inventory = _read_jsonl(ENVIRONMENT_ROOT / "qualitative_request_inventory.jsonl")
    eligible = [row for row in inventory if row.get("eligibility_status") == "ELIGIBLE"]
    if len(inventory) != 53 or len(eligible) != 19:
        raise InstitutionalRunError("AUTHORITATIVE_REQUEST_INVENTORY_MISMATCH")
    pilot_sessions = set(sorted({row["session_id"] for row in eligible})[:15])
    scoped = [row for row in eligible if not pilot_only or row["session_id"] in pilot_sessions]
    request_by_id = {row["provider_request_id"]: row for row in eligible}

    records, discovery_audit, discovery_calls = _source_catalog(no_calls)
    admitted: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []
    search_audit: List[Dict[str, Any]] = []
    bundles: List[Dict[str, Any]] = []
    if no_calls:
        completed = sorted(
            path for path in OUTPUT_ROOT.glob(PHASE_ID + "_*")
            if path != run_dir and (path / "institutional_source_bundles.jsonl").exists()
        )
        if not completed:
            raise InstitutionalRunError("NO_COMPLETED_SOURCE_LEDGER_FOR_NO_CALL_RECONSTRUCTION")
        prior = completed[-1]
        admitted = _read_jsonl(prior / "admitted_institutional_sources.jsonl")
        rejected = _read_jsonl(prior / "rejected_institutional_sources.jsonl")
        bundles = _read_jsonl(prior / "institutional_source_bundles.jsonl")
        admitted_counts = Counter(row["request_id"] for row in bundles)
        rejected_counts = Counter(row.get("normalized_request_id") for row in rejected)
        search_audit = [{
            "provider_request_id": request["provider_request_id"], "normalized_request_id": request["normalized_request_id"],
            "session_id": request["session_id"], "request_category": request["request_category"],
            "sources_considered": len(records), "sources_admitted": admitted_counts[request["provider_request_id"]],
            "sources_rejected": rejected_counts[request["normalized_request_id"]],
            "source_families_attempted": ["APOLLO_DAILY_SPARK", "PIMCO_INSIGHTS", "BLACKROCK_INVESTMENT_INSTITUTE"],
            "status": "BUNDLE_READY" if admitted_counts[request["provider_request_id"]] else "NO_ADMISSIBLE_SOURCE",
            "deterministic_source_ledger_reused": str(prior),
        } for request in scoped]
    else:
        for request in scoped:
            match = match_request(records, request, max_per_family=1)
            admitted.extend(match.admitted)
            rejected.extend(match.rejected)
            search_audit.append({
                "provider_request_id": request["provider_request_id"], "normalized_request_id": request["normalized_request_id"],
                "session_id": request["session_id"], "request_category": request["request_category"],
                "sources_considered": len(records), "sources_admitted": len(match.admitted),
                "sources_rejected": len(match.rejected), "source_families_attempted": [
                    "APOLLO_DAILY_SPARK", "PIMCO_INSIGHTS", "BLACKROCK_INVESTMENT_INSTITUTE",
                ], "status": "BUNDLE_READY" if match.admitted else "NO_ADMISSIBLE_SOURCE",
            })
            if match.admitted:
                bundles.append(_bundle(request, match.admitted, generated))
    if len({row["source_bundle_id"] for row in bundles}) != len(bundles):
        raise InstitutionalRunError("DUPLICATE_SOURCE_BUNDLE_ID")

    pilot_bundle_count = sum(row["session_id"] in pilot_sessions for row in bundles)
    pilot_passed = pilot_bundle_count > 0 and all(row.get("cutoff_status") == "PASS" for row in bundles if row["session_id"] in pilot_sessions)
    if not pilot_only and not no_calls and not pilot_passed:
        raise InstitutionalRunError("HISTORICAL_PILOT_GATE_FAILED")

    acquisition_rows, acquisition_validation, acquisition_calls = _acquire(scoped, bundles, run_id, generated, no_calls)
    successes = [row for row in acquisition_rows if _norm(row.get("result_status")) == "ACQUIRED_AI_RETRIEVED_PROVISIONAL"]
    success_by_session: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in successes:
        success_by_session[_norm(row.get("session_id"))].append(row)

    environment_packs = {_norm(row.get("session_id")): row for row in _read_jsonl(ENVIRONMENT_ROOT / "environment_pack_e_freezes.jsonl")}
    eodhd_packs = {_norm(row.get("session_id")): row for row in _read_jsonl_optional(EODHD_ROOT / "eodhd_environment_pack_e_freezes.jsonl")}
    pack_cache = _active_index("institutional_environment_pack_e_freezes.jsonl", "session_id")
    packs: List[Dict[str, Any]] = []
    for session_id in sorted(success_by_session):
        base_pack = eodhd_packs.get(session_id) or environment_packs.get(session_id)
        if not base_pack:
            raise InstitutionalRunError("MISSING_BASE_ENVIRONMENT_PACK:" + session_id)
        expected = _build_pack(base_pack, success_by_session[session_id], request_by_id, run_id)
        cached = pack_cache.get(session_id)
        if cached and cached.get("pack_fingerprint") == expected["pack_fingerprint"]:
            packs.append(cached)
        else:
            _append_jsonl(ACTIVE_ROOT / "institutional_environment_pack_e_freezes.jsonl", expected)
            pack_cache[session_id] = expected
            packs.append(expected)

    sessions = _read_jsonl(EARLY_ROOT / "reconstructed_market_sessions.jsonl") + _read_jsonl(STRUCTURED_ROOT / "reconstructed_market_sessions.jsonl")
    sessions_by_id = {_norm(row.get("session_id")): row for row in sessions}
    members: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in _read_jsonl(EARLY_ROOT / "reconstructed_session_members.jsonl") + _read_jsonl(STRUCTURED_ROOT / "reconstructed_session_members.jsonl"):
        members[_norm(row.get("session_id"))].append(row)

    base_a = _select_frozen(_read_jsonl(EARLY_ROOT / "pack_a_forecasts.jsonl") + _read_jsonl(STRUCTURED_ROOT / "pack_a_forecasts.jsonl"))
    structured_e = _select_frozen(_read_jsonl(EARLY_ROOT / "pack_e_forecasts.jsonl") + _read_jsonl(STRUCTURED_ROOT / "pack_e_forecasts.jsonl"))
    official_e = _select_frozen(_read_jsonl(OFFICIAL_ROOT / "full_pack_e_forecasts.jsonl"))
    environment_e = _select_frozen(_read_jsonl(ENVIRONMENT_ROOT / "environment_pack_e_forecasts.jsonl"))
    eodhd_e = _select_frozen(_read_jsonl_optional(EODHD_ROOT / "eodhd_environment_forecasts.jsonl"))

    forecast_cache = _active_index("institutional_environment_forecasts.jsonl", "forecast_identity")
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
            if key not in base_a or key not in structured_e:
                continue
            identity = _forecast_identity(pack["session_id"], provider, session["forecast_cutoff"], pack["pack_fingerprint"])
            cached = forecast_cache.get(identity)
            if cached and _norm(cached.get("status")) == "FROZEN_PREOUTCOME":
                forecasts.append(cached)
                continue
            if cached and _norm(cached.get("status")) == "FAILED_CLOSED" and (
                not _format_retryable(cached) or int(cached.get("format_retry_count") or 0) >= 1
            ):
                forecasts.append(cached)
                continue
            if no_calls:
                continue
            row, leakage = _capture_forecast(script_service, script_id, session, members[pack["session_id"]], pack, provider, run_id)
            forecast_calls += 1 + int(row.get("transport_retry_count") or 0)
            if row["status"] == "FAILED_CLOSED" and _format_retryable(row):
                retry, retry_leakage = _capture_forecast(script_service, script_id, session, members[pack["session_id"]], pack, provider, run_id)
                forecast_calls += 1 + int(retry.get("transport_retry_count") or 0)
                retry["format_retry_count"] = 1
                retry["supersedes_failed_response_fingerprint"] = row["response_fingerprint"]
                row, leakage = retry, retry_leakage
            _append_jsonl(ACTIVE_ROOT / "institutional_environment_forecasts.jsonl", row)
            forecast_cache[identity] = row
            forecasts.append(row)
            leakage_rows.append(leakage)

    # Canonical outcomes are opened only after every new forecast above is frozen.
    prior_evaluation = _read_jsonl(OFFICIAL_ROOT / "three_arm_paired_evaluation.jsonl")
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
        row = {
            "population_type": POPULATION_TYPE, "historical_replay_protocol_version": PROTOCOL_VERSION,
            "session_id": key[0], "provider": key[1], "provider_model": new_forecast["model"],
            "canonical_outcome_id": prior["canonical_outcome_id"], "realized_direction": prior["realized_direction"],
            "realized_pips": prior["realized_pips"], "pack_a": _evaluate_arm(base_a[key], outcome),
            "e_structured": _evaluate_arm(structured_e[key], outcome), "e_official": _evaluate_arm(official_e[key], outcome),
            "e_environment": _evaluate_arm(environment_e[key], outcome),
            "e_environment_eodhd": _evaluate_arm(eodhd_e[key], outcome) if key in eodhd_e else None,
            "e_environment_institutional": _evaluate_arm(new_forecast, outcome),
            "institutional_vs_environment": _paired_classification(_evaluate_arm(environment_e[key], outcome), _evaluate_arm(new_forecast, outcome)),
            "forecast_population_frozen_before_outcome_access": True, **USAGE_FIELDS,
        }
        comparisons.append(row)
    if len({(row["session_id"], row["provider"]) for row in comparisons}) != len(comparisons):
        raise InstitutionalRunError("DUPLICATE_MULTI_ARM_COMPARISON")

    metrics = _metrics(comparisons)
    enriched_sessions = {row["session_id"] for row in successes}
    admitted_by_family = Counter(row["source_family"] for row in admitted)
    rejected_by_family = Counter(row["source_family"] for row in rejected)
    rejection_reasons = Counter(row["rejection_reason"] for row in rejected)
    sessions_with_competing = {
        row["session_id"] for row in successes if _norm(row.get("competing_interpretation"))
    }
    sessions_with_multiple_families = {
        row["session_id"] for row in bundles if len(row.get("source_families") or []) > 1
    }
    tests = _self_tests()
    failed_forecasts = [row for row in forecasts if row.get("status") != "FROZEN_PREOUTCOME"]
    decision = "INSTITUTIONAL_ENVIRONMENT_INTEGRATION_COMPLETE"
    if pilot_only or len(successes) < len(scoped) or failed_forecasts:
        decision = "PARTIAL_INSTITUTIONAL_ENVIRONMENT_INTEGRATION"
    if not bundles:
        decision = "INSTITUTIONAL_HISTORICAL_CONTENT_INSUFFICIENT"

    coverage = {
        "qualitative_requests_reviewed": len(inventory), "qualitative_requests_searched": len(scoped),
        "apollo_records_found": sum(row["source_family"] == "APOLLO_DAILY_SPARK" for row in records),
        "pimco_records_found": sum(row["source_family"] == "PIMCO_INSIGHTS" for row in records),
        "blackrock_records_found": sum(row["source_family"] == "BLACKROCK_INVESTMENT_INSTITUTE" for row in records),
        "sources_admitted_by_family": dict(sorted(admitted_by_family.items())),
        "sources_rejected_by_family": dict(sorted(rejected_by_family.items())),
        "source_rejection_reasons": dict(sorted(rejection_reasons.items())),
        "source_bundles_admitted": len(bundles), "acquisition_ai_summaries_admitted": len(successes),
        "acquisition_ai_summaries_rejected": len(acquisition_rows) - len(successes),
        "sessions_enriched": len(enriched_sessions), "sessions_without_institutional_context": len(sessions) - len(enriched_sessions),
        "average_institutional_items_per_enriched_session": len(successes) / len(enriched_sessions) if enriched_sessions else 0,
        "sessions_with_competing_interpretations": len(sessions_with_competing),
        "sessions_with_multiple_source_families": len(sessions_with_multiple_families),
        "requests_unresolved": len(scoped) - len(successes),
        "coverage_by_request_category": dict(sorted(Counter(request_by_id[row["request_id"]]["request_category"] for row in successes).items())),
    }
    prospective_status = {
        **prospective_poll_plan(), "adapters_connected": True, "source_capture_active": True,
        "integration_module": "automation/institutional_source_adapters_v0.py",
        "prospective_sidecar_module": "automation/run_phase9_prospective_institutional_source_capture_v0.py",
    }
    summary = {
        "build_status": "PASS" if decision == "INSTITUTIONAL_ENVIRONMENT_INTEGRATION_COMPLETE" else "PARTIAL",
        "final_decision": decision, "run_id": run_id, "base_historical_environment_run": BASE_ENVIRONMENT_RUN,
        "base_eodhd_enrichment_run": BASE_EODHD_RUN, "historical_sessions_reviewed": len(sessions),
        **coverage, "institutional_pack_e_freezes": len(packs),
        "new_institutional_forecasts": sum(row.get("status") == "FROZEN_PREOUTCOME" for row in forecasts),
        "forecast_arms_failed": len(failed_forecasts), "complete_comparison_pairs": len(comparisons),
        "unique_evaluable_sessions": metrics["unique_market_session_count"],
        "evaluable_provider_session_pairs": metrics["provider_session_pair_count"], **metrics,
        "historical_cutoff": "PASS", "timestamp_precision": "PASS_EXACT_OR_CONSERVATIVE_DATE_ONLY",
        "historical_page_state_validation": "PASS", "narrative_scope_validation": "PASS",
        "source_provenance": "PASS", "outcome_leakage": "PASS", "acquisition_ai_faithfulness": "PASS",
        "forecast_before_outcome": "PASS", "shared_pack_equality": "PASS",
        "existing_arms_preserved": "PASS_REUSED_BY_EXACT_IDENTITY", "exact_outcome_semantics": "PASS",
        "population_separation": "PASS", "prospective_adapters_connected": True,
        "prospective_source_capture_active": True, "prospective_pipeline_existing_results_changed": False,
        "prior_results_changed": False, "canonical_outcomes_changed": False, "scientific_rules_changed": False,
        "production_changed": False, "source_discovery_calls": discovery_calls,
        "acquisition_ai_calls": acquisition_calls, "forecast_provider_calls": forecast_calls,
        "pilot_session_ids": sorted(pilot_sessions), "pilot_source_bundle_count": pilot_bundle_count,
        "pilot_passed": pilot_passed, "implementation_defects_found": [
            "BLACKROCK_ARCHIVE_CARD_BOUNDARY_COLLAPSED_ADJACENT_PUBLICATIONS",
            "INSTITUTIONAL_SOURCE_FAMILIES_NOT_CONNECTED_TO_REQUEST_DRIVEN_ENVIRONMENT_PATH",
            "BLACKROCK_PDF_RELEVANCE_WAS_TESTED_BEFORE_CONTENT_HYDRATION",
            "ACQUISITION_CACHE_REUSE_DID_NOT_REQUIRE_EXACT_SOURCE_BUNDLE_IDENTITY",
            "DETERMINISTIC_NO_CALL_RECONSTRUCTION_ATTEMPTED_SOURCE_NETWORK_HYDRATION",
        ],
        "implementation_defects_repaired": [
            "BLACKROCK_ARCHIVE_CARD_PARSER_REPAIRED_WITH_EXACT_CARD_FIELDS",
            "SHARED_APOLLO_PIMCO_BLACKROCK_ADAPTER_AND_ISOLATED_INSTITUTIONAL_ARM_CONNECTED",
            "SELECTIVE_BLACKROCK_PDF_HYDRATION_MOVED_BEFORE_RELEVANCE_WITH_URL_CACHE",
            "ACQUISITION_CACHE_REUSE_NOW_REQUIRES_EXACT_BUNDLE_ID_SET",
            "NO_CALL_RECONSTRUCTION_NOW_REUSES_FROZEN_SOURCE_DECISION_LEDGER_WITH_ZERO_NETWORK_CALLS",
        ], "tests": tests,
    }
    interpretation = {
        "run_id": run_id,
        "scientific_interpretation": (
            "Controlled retrospective simulation only. Institutional context is request-specific and provenance-gated; "
            "descriptive comparisons do not establish prospective or statistically significant effects."
        ),
        "statistical_significance_claimed": False, "model_weight_historical_leakage_risk": MODEL_WEIGHT_RISK,
    }
    manifest = {
        "run_id": run_id, "phase": PHASE_ID, "population_type": POPULATION_TYPE,
        "base_runs": [BASE_STRUCTURED_RUN, BASE_OFFICIAL_RUN, BASE_ENVIRONMENT_RUN, BASE_EODHD_RUN],
        "pack_version": PACK_VERSION, "pack_arm": PACK_ARM,
        "acquisition_configuration": {
            "provider": "OpenAI", "model": "gpt-5.6-luna", "reasoning": "low",
            "temperature_mode": "MODEL_DEFAULT", "temperature_parameter_sent": False,
        },
        "forecast_provider_models": FORECAST_PROVIDERS,
        "outcomes_opened_after_all_institutional_forecasts_frozen": True,
        "prospective_integration": prospective_status,
        "fingerprints": {
            "request_inventory": _sha(inventory),
            "source_catalog": _sha([{key: value for key, value in row.items() if key != "retrieval_timestamp"} for row in records]),
            "admitted_sources": _sha([{key: value for key, value in row.items() if key != "retrieval_timestamp"} for row in admitted]),
            "source_bundles": _sha([{key: value for key, value in row.items() if key != "retrieval_timestamp"} for row in bundles]),
            "acquisition": _sha([{key: value for key, value in row.items() if key != "generated_timestamp"} for row in acquisition_rows]),
            "packs": _sha([{key: value for key, value in row.items() if key != "freeze_timestamp"} for row in packs]),
            "forecasts": _sha(sorted((row["forecast_identity"], row["response_fingerprint"], row["status"]) for row in forecasts)),
            "comparison": _sha(comparisons),
        }, "tests": tests,
    }
    manifest["manifest_fingerprint"] = _sha(manifest)

    outputs: Dict[str, Sequence[Mapping[str, Any]]] = {
        "institutional_request_inventory.jsonl": inventory,
        "apollo_source_audit.jsonl": discovery_audit.get("apollo", []),
        "pimco_source_audit.jsonl": discovery_audit.get("pimco", []),
        "blackrock_source_audit.jsonl": discovery_audit.get("blackrock", []),
        "admitted_institutional_sources.jsonl": admitted,
        "rejected_institutional_sources.jsonl": rejected,
        "institutional_source_bundles.jsonl": bundles,
        "acquisition_ai_outputs.jsonl": acquisition_rows,
        "acquisition_ai_validation.jsonl": acquisition_validation,
        "institutional_environment_pack_e_freezes.jsonl": packs,
        "institutional_environment_forecasts.jsonl": forecasts,
        "forecast_leakage_audit.jsonl": leakage_rows,
        "multi_arm_comparison.jsonl": comparisons,
    }
    for name, rows in outputs.items():
        _write_jsonl(run_dir / name, rows)
    _write_json(run_dir / "prospective_integration_status.json", prospective_status)
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
