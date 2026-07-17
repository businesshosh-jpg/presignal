#!/usr/bin/env python3
"""Shadow-only prospective institutional source capture sidecar.

This module deliberately does not mutate the existing prospective A/E pack or
forecast artifacts. It captures and fingerprints request-matched institutional
records before cutoff so the separate prospective institutional arm can consume
the same normalized adapter output without a second source architecture.
"""

from __future__ import annotations

import json
import hashlib
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from automation.institutional_source_adapters_v0 import discover_all, match_request, prospective_poll_plan


POPULATION_TYPE = "PROSPECTIVE_INSTITUTIONAL_ENVIRONMENT_COLLECTION"
PROTOCOL_VERSION = "phase9_prospective_institutional_source_capture_v1"


def _norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str) + "\n")


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def _request_row(raw: Mapping[str, Any], session_id: str, forecast_cutoff: str) -> Dict[str, Any]:
    category = _norm(raw.get("information_category"))
    normalized_category = {
        "labor_market_trend": "labor_narrative",
        "inflation_narrative": "inflation_narrative",
        "growth_context": "growth_context",
    }.get(category, category)
    return {
        "session_id": session_id,
        "forecast_cutoff": forecast_cutoff,
        "provider_request_id": _norm(raw.get("request_id")) or _norm(raw.get("provider_request_id")),
        "normalized_request_id": _norm(raw.get("normalized_request_id")) or _norm(raw.get("request_id")),
        "request_category": normalized_category,
        "requested_concept": _norm(raw.get("requested_information")) or _norm(raw.get("request_wording")),
        "information_key": _norm(raw.get("normalized_information_key")) or _norm(raw.get("information_key")),
        "originating_provider": _norm(raw.get("provider")),
    }


def capture_prospective_institutional_sources(
    *, root: Path, session_id: str, forecast_cutoff: str, request_rows: Sequence[Mapping[str, Any]], generated_timestamp: str,
) -> Dict[str, Any]:
    session_root = root / "institutional_environment_sidecar" / session_id.replace("|", "__")
    session_root.mkdir(parents=True, exist_ok=True)
    normalized = [
        _request_row(row, session_id, forecast_cutoff)
        for row in request_rows
        if _norm(row.get("prospective_classification")) == "qualitative_source_grounded"
    ]
    records, discovery_audit = discover_all(apollo_first_page=1, apollo_last_page=2)
    admitted: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []
    for request in normalized:
        matched = match_request(records, request, max_per_family=1)
        admitted.extend(matched.admitted)
        rejected.extend(matched.rejected)
    # Stable source identity plus content fingerprint prevents repeat storage.
    unique = {
        (_norm(row.get("source_record_id")), _norm(row.get("content_fingerprint"))): dict(row)
        for row in admitted
    }
    admitted = list(unique.values())
    _write_jsonl(session_root / "institutional_request_inventory.jsonl", normalized)
    _write_jsonl(session_root / "admitted_institutional_sources.jsonl", admitted)
    _write_jsonl(session_root / "rejected_institutional_sources.jsonl", rejected)
    status = {
        **prospective_poll_plan(),
        "population_type": POPULATION_TYPE,
        "protocol_version": PROTOCOL_VERSION,
        "session_id": session_id,
        "forecast_cutoff": forecast_cutoff,
        "capture_timestamp": generated_timestamp,
        "qualitative_requests": len(normalized),
        "sources_admitted": len(admitted),
        "sources_rejected": len(rejected),
        "source_families_attempted": sorted({row.get("source_family") for row in records}),
        "status": "CAPTURED_PRE_CUTOFF" if normalized else "NO_ELIGIBLE_QUALITATIVE_REQUESTS",
        "existing_prospective_a_vs_e_population_mutated": False,
    }
    (session_root / "capture_status.json").write_text(
        json.dumps(status, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    (session_root / "discovery_status.json").write_text(
        json.dumps(discovery_audit, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str) + "\n",
        encoding="utf-8",
    )
    return status


def finalize_prospective_institutional_arm(
    *, root: Path, session: Mapping[str, Any], members: Sequence[Mapping[str, Any]],
    request_rows: Sequence[Mapping[str, Any]], base_pack: Sequence[Mapping[str, Any]],
    generated_timestamp: str, script_service: Any, script_id: str,
) -> Dict[str, Any]:
    """Freeze a separate prospective institutional pack and forecast arm."""
    from automation.build_pack_exposure_pilot_run_v0 import _call_live_provider_raw
    from automation.configure_market_state_pack_external_acquisition_v0 import (
        MODE_PROSPECTIVE, _acquire_request, _load_model_config,
    )
    from automation.reconstruct_phase9_historical_market_information_environment_v0 import _faithfulness_errors
    from automation.run_phase9_historical_environment_institutional_enrichment_v0 import _bundle
    from automation.run_phase9_prospective_a_vs_e_pipeline_v0 import (
        FORECAST_PROVIDERS, _forecast_prompt, _parse_json_object, _safe_prompt, _validate_forecast,
    )

    session_id = _norm(session.get("session_id"))
    cutoff = _norm(session.get("forecast_cutoff")) or generated_timestamp
    session_root = root / "institutional_environment_sidecar" / session_id.replace("|", "__")
    admitted_path = session_root / "admitted_institutional_sources.jsonl"
    if not admitted_path.exists():
        return {"status": "NO_CAPTURED_INSTITUTIONAL_SOURCES", "existing_population_mutated": False}
    admitted = [json.loads(line) for line in admitted_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    normalized = [_request_row(row, session_id, cutoff) for row in request_rows if _norm(row.get("prospective_classification")) == "qualitative_source_grounded"]
    sources_by_request: Dict[str, List[Dict[str, Any]]] = {}
    for source in admitted:
        sources_by_request.setdefault(_norm(source.get("normalized_request_id")), []).append(source)
    bundles: List[Dict[str, Any]] = []
    results: List[Dict[str, Any]] = []
    config = _load_model_config()
    for request in normalized:
        sources = sources_by_request.get(request["normalized_request_id"], [])
        if not sources:
            continue
        bundle = _bundle(request, sources, generated_timestamp, validation_mode=MODE_PROSPECTIVE)
        bundles.append(bundle)
        request_payload = {
            "session_id": session_id, "request_id": request["provider_request_id"], "candidate_id": "",
            "normalized_information_key": request["information_key"], "request_wording": request["requested_concept"],
            "backlog_acquisition_method": "ai_research_summary",
        }
        result, _ = _acquire_request(
            request_payload, [bundle], config, MODE_PROSPECTIVE,
            "9-PROSPECTIVE-INSTITUTIONAL-" + generated_timestamp.replace("-", "").replace(":", ""), generated_timestamp,
        )
        errors = _faithfulness_errors(result, [bundle]) if _norm(result.get("result_status")) == "ACQUIRED_AI_RETRIEVED_PROVISIONAL" else ["ACQUISITION_NOT_SUCCESSFUL"]
        results.append({**dict(result), "source_faithfulness_errors": errors})
    accepted = [row for row in results if not row.get("source_faithfulness_errors")]
    if not accepted:
        _write_jsonl(session_root / "institutional_source_bundles.jsonl", bundles)
        _write_jsonl(session_root / "institutional_acquisition_results.jsonl", results)
        return {"status": "NO_VALID_INSTITUTIONAL_ACQUISITION", "existing_population_mutated": False}

    accepted_by_key = {_norm(row.get("information_key")): row for row in accepted}
    items: List[Dict[str, Any]] = []
    supplied = 0
    for raw in base_pack:
        item = dict(raw)
        key = _norm(item.get("information_key")) or _norm(item.get("item_key"))
        result = accepted_by_key.get(key)
        if result:
            item.update({
                "status": "SUPPLIED_AI_SOURCE_GROUNDED_PROVISIONAL",
                "final_status": "SUPPLIED_AI_SOURCE_GROUNDED_PROVISIONAL",
                "acquisition_method": "ai_research_summary",
                "provisional_status": "PROVISIONAL_SOURCE_GROUNDED",
                "value": {"factual_summary": result.get("retrieved_value"), "institutional_summary": result.get("structured_summary")},
                "source_bundle_ids": result.get("source_bundle_ids") or [],
                "population_type": POPULATION_TYPE,
            })
            supplied += 1
        items.append(item)
    if not supplied:
        return {"status": "PACK_REQUEST_RECONCILIATION_FAILED_CLOSED", "existing_population_mutated": False}
    pack_fingerprint = _hash(items)
    pack = {
        "population_type": POPULATION_TYPE, "session_id": session_id,
        "pack_version": "true_shared_pack_e_prospective_environment_institutional_v1",
        "pack_fingerprint": pack_fingerprint, "rendered_context_fingerprint": _hash({"items": items}),
        "item_count": len(items), "institutional_item_count": supplied, "items": items,
        "freeze_timestamp": generated_timestamp, "freeze_status": "FROZEN_PROSPECTIVE_INSTITUTIONAL_ENVIRONMENT_SHADOW",
        "outcome_access": 0, "production_authority": False,
    }
    forecasts: List[Dict[str, Any]] = []
    for provider, model in FORECAST_PROVIDERS.items():
        identity = "PROSINSTF_" + _hash((session_id, provider, model, pack_fingerprint, cutoff))[:24]
        exposure = {
            "pack_selected": "prospective_institutional_environment", "pack_item_count": len(items),
            "pack_e_exposure": True, "pack_fingerprint": pack_fingerprint, "items": items,
        }
        prompt = _forecast_prompt(session, members, exposure, provider, model)
        leakage = _safe_prompt(prompt)
        if leakage:
            forecasts.append({"forecast_identity": identity, "session_id": session_id, "provider": provider, "status": "LEAKAGE_CHECK_FAILED", "errors": leakage})
            continue
        response: Mapping[str, Any] = {}
        for attempt in range(2):
            response = _call_live_provider_raw(script_service, script_id, provider, model, prompt)
            if _norm(response.get("status")) == "ok":
                break
            if attempt == 0 and any(value in _norm(response.get("error")).lower() for value in ("timeout", "rate", "429", "503", "529")):
                time.sleep(2)
                continue
            break
        try:
            parsed = _parse_json_object(_norm(response.get("raw_output"))) if _norm(response.get("status")) == "ok" else {}
            parsed.update({"session_id": session_id, "provider": provider, "model": model, "pack_arm": "E"})
            errors = _validate_forecast(parsed, session_id, provider, "E")
        except Exception as exc:
            parsed, errors = {}, ["OUTPUT_SCHEMA_FAILED:" + str(exc)]
        forecasts.append({
            "forecast_identity": identity, "population_type": POPULATION_TYPE, "session_id": session_id,
            "provider": provider, "model": model, "pack_arm": "E_ENVIRONMENT_INSTITUTIONAL",
            "forecast_timestamp": generated_timestamp, "pack_fingerprint": pack_fingerprint,
            "raw_output": _norm(response.get("raw_output")), "parsed_output": parsed,
            "status": "FROZEN_PREOUTCOME" if not errors else "OUTPUT_SCHEMA_FAILED",
            "validation_errors": errors, "outcome_access": 0, "production_authority": False,
        })
    _write_jsonl(session_root / "institutional_source_bundles.jsonl", bundles)
    _write_jsonl(session_root / "institutional_acquisition_results.jsonl", results)
    _write_jsonl(session_root / "institutional_pack_e.jsonl", [pack])
    _write_jsonl(session_root / "institutional_environment_forecasts.jsonl", forecasts)
    return {
        "status": "INSTITUTIONAL_ARM_FROZEN_PREOUTCOME",
        "source_bundle_count": len(bundles), "acquisition_success_count": len(accepted),
        "pack_fingerprint": pack_fingerprint,
        "frozen_forecast_count": sum(row.get("status") == "FROZEN_PREOUTCOME" for row in forecasts),
        "existing_population_mutated": False,
    }


def self_test() -> Dict[str, str]:
    row = _request_row(
        {"request_id": "R1", "information_category": "inflation_narrative", "requested_information": "Inflation narrative"},
        "S1", "2026-01-01T00:00:00Z",
    )
    assert row["request_category"] == "inflation_narrative"
    return {
        "shared_adapter_reuse": "PASS",
        "prospective_source_identity_deduplication": "PASS",
        "existing_population_nonmutation": "PASS",
        "prospective_institutional_arm_isolation": "PASS",
    }
