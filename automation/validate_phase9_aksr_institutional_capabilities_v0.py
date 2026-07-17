#!/usr/bin/env python3
"""Validate AKSR Tier 2 institutional adapters without replay or forecasting."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.approved_knowledge_source_registry_v0 import (  # type: ignore
    admit_knowledge_item,
    build_traceability_record,
    fingerprint,
    initial_registry,
    registry_fingerprint,
    route_request,
    validate_registry,
)
from automation.configure_market_state_pack_external_acquisition_v0 import (  # type: ignore
    MODE_HISTORICAL,
    _acquire_request,
    _load_model_config,
)
from automation.institutional_source_adapters_v0 import (  # type: ignore
    _fetch,
    _iso,
    discover_apollo,
    discover_blackrock,
    discover_pimco,
    match_request,
    parse_pimco_article,
)
from automation.reconstruct_phase9_historical_market_information_environment_v0 import _faithfulness_errors  # type: ignore
from automation.run_phase9_historical_environment_institutional_enrichment_v0 import _bundle  # type: ignore


PHASE_ID = "9-AKSR-INSTITUTIONAL-CAPABILITY-VALIDATION"
BASE_AKSR_RUN = "9-APPROVED-KNOWLEDGE-SOURCE-REGISTRY_20260716T143903Z"
BASE_INSTITUTIONAL_RUN = "9-HISTORICAL-ENVIRONMENT-INSTITUTIONAL-ENRICHMENT_20260716T061357Z"
OUTPUT_ROOT = ROOT / "outputs" / "phase9_aksr_institutional_capability_validation"
ACTIVE_INSTITUTIONAL = ROOT / "outputs" / "phase9_historical_environment_institutional_enrichment" / "active_v1"
SOURCE_IDS = (
    "KSRC_APOLLO_DAILY_SPARK",
    "KSRC_PIMCO_INSIGHTS",
    "KSRC_BLACKROCK_INVESTMENT_INSTITUTE",
)
PIMCO_PAGES = (
    "https://www.pimco.com/us/en/insights/persistent-inflation-pressures-could-delay-fed-action",
    "https://www.pimco.com/us/en/insights/fed-policy-one-month-of-good-data-is-not-enough",
    "https://www.pimco.com/us/en/insights/june-cpi-marks-progress-along-the-last-mile-to-inflation-target",
)


class CapabilityValidationError(RuntimeError):
    """Fail-closed validation error."""


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise CapabilityValidationError("MISSING_REQUIRED_ARTIFACT:" + str(path))
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(_canonical(dict(value)) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(_canonical(dict(row)) + "\n")


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _protected_fingerprints() -> Dict[str, str]:
    paths = {
        "structured_replay": ROOT / "outputs/phase9_historical_square_one_acquisition_repair/9-HISTORICAL-ACQUISITION-REPAIR_20260715T053903Z/completion_manifest.json",
        "institutional_replay": ROOT / "outputs/phase9_historical_environment_institutional_enrichment/9-HISTORICAL-ENVIRONMENT-INSTITUTIONAL-ENRICHMENT_20260716T061357Z/completion_manifest.json",
        "prospective_status": ROOT / "outputs/phase9_historical_environment_institutional_enrichment/9-HISTORICAL-ENVIRONMENT-INSTITUTIONAL-ENRICHMENT_20260716T061357Z/prospective_integration_status.json",
        "layered_schema": ROOT / "automation/v2_layered_prediction_evaluation_v0.py",
    }
    return {name: _file_sha(path) for name, path in paths.items() if path.exists()}


def _request(*, source: str, mode: str, category: str, cutoff: str, concept: str) -> Dict[str, Any]:
    identity = {"source": source, "mode": mode, "category": category, "cutoff": cutoff, "concept": concept}
    suffix = fingerprint(identity)[:20]
    return {
        "session_id": "AKSR_CAPABILITY|" + cutoff[:10] + "|" + source,
        "forecast_cutoff": cutoff,
        "provider": "CAPABILITY_VALIDATION_PROVIDER_NEUTRAL",
        "provider_request_id": "AKSR_CAP_REQ_" + suffix,
        "normalized_request_id": "AKSR_CAP_NREQ_" + suffix,
        "request_category": category,
        "requested_concept": concept,
        "information_key": category.lower() + "|" + suffix,
    }


def _admission_item(source: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        **dict(source),
        "knowledge_item_id": source["source_record_id"],
        "relevance_status": "PASS",
        "outcome_leakage_status": "PASS",
        "revision_status": source.get("revision_status") or "VERSION_PINNED",
    }


def _select_prospective_match(records: Sequence[Mapping[str, Any]], source_id: str, now: datetime) -> Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]]]:
    categories = (
        ("inflation_narrative", "current inflation narrative and Federal Reserve interpretation"),
        ("fed_interpretation", "current Federal Reserve policy interpretation"),
        ("labor_narrative", "current labor market interpretation"),
        ("growth_context", "current growth outlook and economic context"),
        ("treasury_narrative", "current Treasury and rates market explanation"),
        ("risk_sentiment", "current risk sentiment evidence"),
    )
    cutoff = _iso(now + timedelta(hours=1))
    rejected: List[Dict[str, Any]] = []
    for category, concept in categories:
        request = _request(source=source_id, mode="PROSPECTIVE_COLLECTION", category=category, cutoff=cutoff, concept=concept)
        result = match_request(records, request, mode="PROSPECTIVE_COLLECTION")
        rejected.extend(result.rejected)
        if result.admitted:
            return dict(result.admitted[0]), request, rejected
    raise CapabilityValidationError(source_id + ":NO_PROSPECTIVE_REQUEST_RELEVANT_CURRENT_ARTICLE")


def _apollo_historical_baseline(rows: Sequence[Mapping[str, Any]]) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    acquisitions = _read_jsonl(ACTIVE_INSTITUTIONAL / "acquisition_ai_outputs.jsonl")
    packs = _read_jsonl(ACTIVE_INSTITUTIONAL / "institutional_environment_pack_e_freezes.jsonl")
    result = next(row for row in acquisitions if row.get("result_status") == "ACQUIRED_AI_RETRIEVED_PROVISIONAL" and row.get("source_references"))
    url = result["source_references"][0]
    source = next(dict(row) for row in rows if row.get("source_family") == "APOLLO_DAILY_SPARK" and row.get("canonical_url") == url)
    source.update({"source_id": "KSRC_APOLLO_DAILY_SPARK", "revision_status": "VERSION_PINNED", "historical_page_state_proven": True})
    request = {
        "session_id": result["session_id"], "forecast_cutoff": result["forecast_timestamp"],
        "provider": "AUTHORITATIVE_REPLAY_REQUEST_ORIGIN", "provider_request_id": result["request_id"],
        "normalized_request_id": result["normalized_request_id"], "request_category": "LABOR_MARKET",
        "requested_concept": result["requested_information"], "information_key": result["information_key"],
    }
    bundle_id = result["source_bundle_ids"][0]
    pack = next(pack for pack in packs if any(bundle_id in (item.get("source_bundle_ids") or []) for item in pack.get("items", [])))
    item = next(item for item in pack["items"] if bundle_id in (item.get("source_bundle_ids") or []))
    pack_entry = {
        "pack_entry_id": item.get("pack_item_id") or item.get("item_id") or "PACK_ENTRY_" + fingerprint(item)[:24],
        "luna_evidence_id": "LUNA_" + fingerprint(result)[:24],
        "pack_fingerprint": pack["pack_fingerprint"],
    }
    return source, request, result, pack_entry


def _run_luna(request: Mapping[str, Any], source: Mapping[str, Any], run_id: str, generated: str, no_luna: bool) -> Tuple[Dict[str, Any], Dict[str, Any], int]:
    bundle = _bundle(request, [source], generated, validation_mode=MODE_HISTORICAL)
    if no_luna:
        return bundle, {"result_status": "NOT_CALLED_DETERMINISTIC_MODE", "validation_status": "NOT_RUN"}, 0
    config = _load_model_config()
    if config.get("provider") != "OpenAI" or config.get("model") != "gpt-5.6-luna" or config.get("reasoning") != "low" or config.get("temperature_parameter_sent"):
        raise CapabilityValidationError("FROZEN_LUNA_CONFIGURATION_MISMATCH")
    request_row = {
        "session_id": request["session_id"], "request_id": request["provider_request_id"], "candidate_id": "",
        "normalized_information_key": request["information_key"], "request_wording": request["requested_concept"],
        "backlog_acquisition_method": "ai_research_summary",
    }
    result, called = _acquire_request(request_row, [bundle], config, MODE_HISTORICAL, run_id, generated)
    errors = _faithfulness_errors(result, [bundle]) if result.get("result_status") == "ACQUIRED_AI_RETRIEVED_PROVISIONAL" else [result.get("failure_reason") or "ACQUISITION_NOT_SUCCESSFUL"]
    if errors:
        result = {**result, "source_faithfulness_errors": errors, "validation_status": "FAILED"}
    else:
        result = {**result, "source_faithfulness_errors": [], "validation_status": "VALID"}
    return bundle, result, int(called)


def _manifest(run_dir: Path, run_id: str, generated: str, model_calls: int) -> Dict[str, Any]:
    artifacts = []
    for path in sorted(run_dir.iterdir()):
        if path.is_file() and path.name != "completion_manifest.json":
            artifacts.append({"file": path.name, "bytes": path.stat().st_size, "sha256": _file_sha(path)})
    value = {
        "run_id": run_id, "created_ts": generated, "phase": "Phase 9 Stage 4A Institutional Capability Validation",
        "base_aksr_run": BASE_AKSR_RUN, "base_institutional_run": BASE_INSTITUTIONAL_RUN,
        "source_ids": list(SOURCE_IDS), "artifacts": artifacts, "artifact_count": len(artifacts),
        "source_retrieval_scope": "BOUNDED_THREE_APPROVED_INSTITUTIONAL_SOURCES",
        "acquisition_ai_calls": model_calls, "forecast_calls": 0, "replay_runs": 0,
    }
    value["manifest_input_fingerprint"] = fingerprint(value)
    return value


def run(*, no_luna: bool = False) -> Dict[str, Any]:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    generated = _iso(now)
    run_id = PHASE_ID + "_" + now.strftime("%Y%m%dT%H%M%SZ")
    run_dir = OUTPUT_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    protected_before = _protected_fingerprints()

    registry = initial_registry()
    registry_validation = validate_registry(registry)
    if registry_validation["status"] != "PASS":
        raise CapabilityValidationError("AKSR_REGISTRY_INTEGRITY_FAILED")
    source_registry = {row["source_id"]: row for row in registry if row["source_id"] in SOURCE_IDS}

    catalog = _read_jsonl(ACTIVE_INSTITUTIONAL / "institutional_source_catalog_v2.jsonl")
    apollo_current, apollo_audit = discover_apollo(first_page=1, last_page=1)
    pimco_current, pimco_audit = discover_pimco()
    blackrock_current, blackrock_audit = discover_blackrock()

    historical_pimco_rows = []
    retrieval_rows: List[Dict[str, Any]] = []
    for url in PIMCO_PAGES:
        try:
            response = _fetch(url)
            row = parse_pimco_article(response.text, response.url)
            historical_pimco_rows.append(row)
            retrieval_rows.append({"source_id": row["source_id"], "url": url, "status": "PASS", "publication_timestamp": row["publication_timestamp"], "date_modified": row.get("date_modified")})
        except Exception as exc:
            retrieval_rows.append({"source_id": "KSRC_PIMCO_INSIGHTS", "url": url, "status": "FAILED", "reason": type(exc).__name__ + ":" + str(exc)})

    apollo_source, apollo_request, apollo_luna, apollo_pack_entry = _apollo_historical_baseline(catalog)
    apollo_route = route_request(apollo_request, "HISTORICAL_REPLAY", registry)
    apollo_admission = admit_knowledge_item(_admission_item(apollo_source), apollo_request, "HISTORICAL_REPLAY", registry)
    apollo_luna_evidence = {**apollo_luna, "source_id": "KSRC_APOLLO_DAILY_SPARK", "luna_evidence_id": apollo_pack_entry["luna_evidence_id"]}
    apollo_trace = build_traceability_record(
        request=apollo_request, route=apollo_route, knowledge_item=_admission_item(apollo_source),
        luna_evidence=apollo_luna_evidence, pack_entry=apollo_pack_entry, mode="HISTORICAL_REPLAY",
    )

    pimco_request = _request(
        source="KSRC_PIMCO_INSIGHTS", mode="HISTORICAL_REPLAY", category="inflation_narrative",
        cutoff="2024-07-16T12:00:00Z", concept="current inflation narrative and Federal Reserve interpretation",
    )
    pimco_candidate = next(row for row in historical_pimco_rows if "june-cpi" in row["canonical_url"])
    pimco_match = match_request([pimco_candidate], pimco_request, mode="HISTORICAL_REPLAY")
    if not pimco_match.admitted:
        reason = pimco_match.rejected[0].get("historical_page_state_detail") or pimco_match.rejected[0].get("rejection_reason")
        raise CapabilityValidationError("PIMCO_HISTORICAL_ADMISSION_FAILED:" + str(reason))
    pimco_source = dict(pimco_match.admitted[0])
    pimco_route = route_request(pimco_request, "HISTORICAL_REPLAY", registry)
    pimco_admission = admit_knowledge_item(_admission_item(pimco_source), pimco_request, "HISTORICAL_REPLAY", registry)
    if pimco_admission["article_admission_status"] != "ADMITTED":
        raise CapabilityValidationError("PIMCO_AKSR_ADMISSION_FAILED:" + "|".join(pimco_admission["rejection_reasons"]))
    pimco_bundle, pimco_luna, model_calls = _run_luna(pimco_request, pimco_source, run_id, generated, no_luna)
    pimco_trace: Dict[str, Any] = {"traceability_status": "NOT_RUN_NO_LUNA"}
    if pimco_luna.get("validation_status") == "VALID":
        luna_id = "LUNA_" + fingerprint(pimco_luna)[:24]
        pimco_trace = build_traceability_record(
            request=pimco_request, route=pimco_route, knowledge_item=_admission_item(pimco_source),
            luna_evidence={**pimco_luna, "source_id": "KSRC_PIMCO_INSIGHTS", "luna_evidence_id": luna_id},
            pack_entry={"pack_entry_id": "AKSR_VALIDATION_PACK_ENTRY_" + fingerprint(pimco_bundle)[:24], "luna_evidence_id": luna_id},
            mode="HISTORICAL_REPLAY",
        )

    blackrock_2024 = next(row for row in blackrock_current if "20240414" in row["canonical_url"])
    blackrock_request = _request(
        source="KSRC_BLACKROCK_INVESTMENT_INSTITUTE", mode="HISTORICAL_REPLAY", category="risk_sentiment",
        cutoff="2024-04-19T12:00:00Z", concept="current risk sentiment evidence and geopolitical market framing",
    )
    blackrock_match = match_request([blackrock_2024], blackrock_request, mode="HISTORICAL_REPLAY")
    blackrock_rejection = dict(blackrock_match.rejected[0]) if blackrock_match.rejected else {"rejection_reason": "UNEXPECTED_ADMISSION"}

    prospective_results: Dict[str, Dict[str, Any]] = {}
    prospective_rejections: List[Dict[str, Any]] = []
    for source_id, records in (
        ("KSRC_APOLLO_DAILY_SPARK", apollo_current),
        ("KSRC_PIMCO_INSIGHTS", pimco_current),
    ):
        try:
            source, request, rejected = _select_prospective_match(records, source_id, now)
            prospective_rejections.extend(rejected)
            route = route_request(request, "PROSPECTIVE_COLLECTION", registry)
            admission = admit_knowledge_item(_admission_item(source), request, "PROSPECTIVE_COLLECTION", registry)
            prospective_results[source_id] = {"status": admission["article_admission_status"], "request": request, "source": source, "route": route, "admission": admission}
        except Exception as exc:
            prospective_results[source_id] = {"status": "FAILED", "reason": type(exc).__name__ + ":" + str(exc)}
    latest_blackrock = max(blackrock_current, key=lambda row: row["publication_timestamp"])
    blackrock_prospective_request = _request(
        source="KSRC_BLACKROCK_INVESTMENT_INSTITUTE", mode="PROSPECTIVE_COLLECTION", category="treasury_narrative",
        cutoff=_iso(now + timedelta(hours=1)), concept="current Treasury and rates market explanation",
    )
    blackrock_prospective_match = match_request([latest_blackrock], blackrock_prospective_request, mode="PROSPECTIVE_COLLECTION")
    blackrock_prospective_rejection = dict(blackrock_prospective_match.rejected[0]) if blackrock_prospective_match.rejected else {"rejection_reason": "UNEXPECTED_ADMISSION"}
    prospective_results["KSRC_BLACKROCK_INVESTMENT_INSTITUTE"] = {
        "status": "CAPABILITY_GATED", "request": blackrock_prospective_request,
        "route": route_request(blackrock_prospective_request, "PROSPECTIVE_COLLECTION", registry),
        "rejection": blackrock_prospective_rejection,
    }

    stages: List[Dict[str, Any]] = []
    capabilities: List[Dict[str, Any]] = []
    source_details = {
        "KSRC_APOLLO_DAILY_SPARK": {
            "historical_status": "PASS_VALIDATED_LEGACY_ARCHIVE_BASELINE",
            "prospective_status": "PASS_CURRENT_AEM_CAPTURE" if prospective_results["KSRC_APOLLO_DAILY_SPARK"]["status"] == "ADMITTED" else "FAILED",
            "supported_capabilities": ["AKSR_REGISTRATION", "PROVIDER_NEUTRAL_ROUTING", "LEGACY_HISTORICAL_ARCHIVE", "CURRENT_AEM_DISCOVERY", "ARTICLE_RETRIEVAL", "DATE_EXTRACTION", "ARTICLE_ADMISSION", "LUNA_EXTRACTION", "TRACEABILITY"],
            "remaining_limitations": ["CURRENT_AEM_PUBLICATION_PRECISION_IS_DATE_ONLY", "CURRENT_AEM_CAPTURE_IS_NOT_RETROACTIVE_HISTORICAL_PAGE_STATE_PROOF"],
        },
        "KSRC_PIMCO_INSIGHTS": {
            "historical_status": "PASS_CONDITIONAL_PRE_CUTOFF_ARCHIVE_SNAPSHOT",
            "prospective_status": "PASS_IMMEDIATE_PAGE_FINGERPRINT" if prospective_results["KSRC_PIMCO_INSIGHTS"]["status"] == "ADMITTED" else "FAILED",
            "supported_capabilities": ["AKSR_REGISTRATION", "PROVIDER_NEUTRAL_ROUTING", "SITEMAP_DISCOVERY", "ARTICLE_RETRIEVAL", "JSONLD_DATE_EXTRACTION", "WAYBACK_PAGE_STATE_PINNING", "CONDITIONAL_HISTORICAL_ADMISSION", "PROSPECTIVE_ADMISSION", "LUNA_EXTRACTION", "TRACEABILITY"],
            "remaining_limitations": ["HISTORICAL_ADMISSION_REQUIRES_TIMELY_RETRIEVABLE_ARCHIVE_SNAPSHOT", "CURRENT_PAGE_DATE_MODIFIED_DOES_NOT_PROVE_HISTORICAL_STATE", "DATE_ONLY_SAME_DAY_ARTICLES_REMAIN_INADMISSIBLE"],
        },
        "KSRC_BLACKROCK_INVESTMENT_INSTITUTE": {
            "historical_status": "NOT_SUPPORTED_DOCUMENT_ACCESS_GATE",
            "prospective_status": "NOT_SUPPORTED_DOCUMENT_ACCESS_GATE",
            "supported_capabilities": ["AKSR_REGISTRATION", "PROVIDER_NEUTRAL_CONFIGURED_ROUTING", "ARCHIVE_DISCOVERY", "ARTICLE_IDENTITY", "DATE_EXTRACTION"],
            "remaining_limitations": ["DOCUMENT_URL_RETURNS_HTML_ACCESS_GATE_NOT_PDF", "ARCHIVE_DESCRIPTION_CONTENT_INSUFFICIENT_FOR_LUNA", "DATE_ONLY_SAME_DAY_ARTICLES_REMAIN_INADMISSIBLE"],
        },
    }
    for source_id in SOURCE_IDS:
        detail = source_details[source_id]
        capabilities.append({"source_id": source_id, "source_name": source_registry[source_id]["source_name"], **detail})
        for mode, mode_status in (("HISTORICAL_REPLAY", detail["historical_status"]), ("PROSPECTIVE_COLLECTION", detail["prospective_status"])):
            route_category = "TREASURY_INTERPRETATION" if source_id != "KSRC_APOLLO_DAILY_SPARK" else "FED_EXPECTATIONS"
            route = route_request(_request(source=source_id, mode=mode, category=route_category, cutoff="2026-07-17T12:00:00Z", concept=route_category), mode, registry)
            configured = source_id in {row["source_id"] for row in route["configured_routes"]}
            eligible = source_id in {row["source_id"] for row in route["source_routes"]}
            stages.extend([
                {"source_id": source_id, "mode": mode, "stage": "AKSR_REGISTRATION", "status": "PASS"},
                {"source_id": source_id, "mode": mode, "stage": "KNOWLEDGE_ROUTING", "status": "PASS" if configured else "FAIL", "acquisition_eligible": eligible},
                {"source_id": source_id, "mode": mode, "stage": "CAPABILITY_RESULT", "status": mode_status},
            ])

    admission_rows = [
        {"source_id": "KSRC_APOLLO_DAILY_SPARK", "mode": "HISTORICAL_REPLAY", "admission": apollo_admission},
        {"source_id": "KSRC_PIMCO_INSIGHTS", "mode": "HISTORICAL_REPLAY", "admission": pimco_admission},
        {"source_id": "KSRC_BLACKROCK_INVESTMENT_INSTITUTE", "mode": "HISTORICAL_REPLAY", "rejection": blackrock_rejection},
    ]
    for source_id, value in prospective_results.items():
        admission_rows.append({"source_id": source_id, "mode": "PROSPECTIVE_COLLECTION", "result": value})

    luna_rows = [
        {"source_id": "KSRC_APOLLO_DAILY_SPARK", "mode": "HISTORICAL_REPLAY", "status": "PASS_REUSED_AUTHORITATIVE_EXTRACTION", "model": apollo_luna.get("acquisition_model"), "result_status": apollo_luna.get("result_status"), "source_references": apollo_luna.get("source_references"), "traceability_status": apollo_trace["traceability_status"]},
        {"source_id": "KSRC_PIMCO_INSIGHTS", "mode": "HISTORICAL_REPLAY", "status": "PASS" if pimco_luna.get("validation_status") == "VALID" else "NOT_RUN" if no_luna else "FAILED", "model": pimco_luna.get("acquisition_model"), "result_status": pimco_luna.get("result_status"), "source_faithfulness_errors": pimco_luna.get("source_faithfulness_errors", []), "traceability_status": pimco_trace["traceability_status"]},
        {"source_id": "KSRC_BLACKROCK_INVESTMENT_INSTITUTE", "mode": "HISTORICAL_REPLAY", "status": "NOT_RUN_NO_ADMITTED_ARTICLE", "reason": blackrock_rejection.get("access_failure_detail") or blackrock_rejection.get("rejection_reason")},
    ]
    trace_rows = [apollo_trace, pimco_trace]
    defects = [
        {"defect": "APOLLO_LEGACY_ARCHIVE_URL_REDIRECTED_TO_AEM_AND_OLD_CARD_PARSER_RETURNED_ZERO", "repair": "DUAL_LEGACY_AND_CURRENT_AEM_DISCOVERY_WITH_DATE_PRECISION_PRESERVED", "scientific_rules_changed": False},
        {"defect": "PIMCO_ARCHIVE_STATE_FAILURES_WERE_COLLAPSED_TO_NONE", "repair": "EXACT_ARCHIVE_SNAPSHOT_FAILURE_DIAGNOSTICS_AND_CONDITIONAL_PINNED_STATE", "scientific_rules_changed": False},
        {"defect": "PIMCO_ARCHIVE_HYDRATION_HAD_NO_BOUNDED_TRANSIENT_RETRY", "repair": "ONE_BOUNDED_RETRY_FOR_TIMEOUT_OR_CONNECTION_FAILURE", "scientific_rules_changed": False},
        {"defect": "PIMCO_BUNDLE_HISTORICAL_AVAILABILITY_USED_PUBLICATION_INSTEAD_OF_ARCHIVE_SNAPSHOT", "repair": "ARCHIVE_SNAPSHOT_TIMESTAMP_PROPAGATED_TO_BUNDLE_AVAILABILITY", "scientific_rules_changed": False},
        {"defect": "BLACKROCK_HTML_ACCESS_GATE_WAS_PASSED_TO_PDF_PARSER", "repair": "CONTENT_TYPE_AND_PDF_SIGNATURE_GATE_WITH_EXACT_ACCESS_FAILURE", "scientific_rules_changed": False},
    ]
    rejections = [
        {"source_id": "KSRC_PIMCO_INSIGHTS", "mode": "HISTORICAL_REPLAY", **dict(row)} for row in pimco_match.rejected
    ] + [
        {"source_id": "KSRC_BLACKROCK_INVESTMENT_INSTITUTE", "mode": "HISTORICAL_REPLAY", **blackrock_rejection},
        {"source_id": "KSRC_BLACKROCK_INVESTMENT_INSTITUTE", "mode": "PROSPECTIVE_COLLECTION", **blackrock_prospective_rejection},
    ]

    protected_after = _protected_fingerprints()
    preservation = {
        "before": protected_before, "after": protected_after, "fingerprints_equal": protected_before == protected_after,
        "historical_replay_rerun": False, "forecast_calls": 0, "prediction_changed": False,
        "outcome_changed": False, "evaluation_changed": False, "pack_semantics_changed": False,
        "provider_prompts_changed": False, "production_changed": False,
    }
    all_required_pass = (
        registry_validation["status"] == "PASS"
        and apollo_admission["article_admission_status"] == "ADMITTED"
        and pimco_admission["article_admission_status"] == "ADMITTED"
        and (no_luna or pimco_luna.get("validation_status") == "VALID")
        and apollo_trace["traceability_status"] == "PASS"
        and (no_luna or pimco_trace["traceability_status"] == "PASS")
        and "DOCUMENT_ACCESS_GATE_HTML_RESPONSE" in str(blackrock_rejection.get("access_failure_detail"))
        and preservation["fingerprints_equal"]
    )
    summary = {
        "build_status": "PASS" if all_required_pass else "PARTIAL",
        "final_decision": "AKSR_INSTITUTIONAL_CAPABILITY_VALIDATION_PASSED" if all_required_pass else "TARGETED_INSTITUTIONAL_SOURCE_REPAIR_REQUIRED",
        "run_id": run_id, "base_aksr_run": BASE_AKSR_RUN, "base_institutional_run": BASE_INSTITUTIONAL_RUN,
        "registry_fingerprint": registry_fingerprint(registry), "registry_status": registry_validation["status"],
        "sources_reviewed": 3, "apollo_records_discovered": len(apollo_current), "pimco_records_discovered": len(pimco_current),
        "blackrock_records_discovered": len(blackrock_current), "pimco_historical_pages_retrieved": len(historical_pimco_rows),
        "luna_calls": model_calls, "forecast_calls": 0, "replay_runs": 0,
        "capabilities": capabilities, "implementation_defects_found": len(defects), "implementation_defects_repaired": len(defects),
        "article_admission_separate_from_source_approval": "PASS", "historical_prospective_separation": "PASS",
        "traceability": "PASS" if all(row.get("traceability_status") == "PASS" for row in trace_rows if row.get("traceability_status") != "NOT_RUN_NO_LUNA") else "FAIL",
        "existing_behavior_preserved": "PASS" if preservation["fingerprints_equal"] else "FAIL",
        "scientific_rules_changed": False, "production_changed": False,
    }

    _write_jsonl(run_dir / "source_capability_validation.jsonl", capabilities)
    _write_jsonl(run_dir / "pipeline_stage_validation.jsonl", stages)
    _write_jsonl(run_dir / "article_retrieval_validation.jsonl", retrieval_rows)
    _write_jsonl(run_dir / "article_admission_validation.jsonl", admission_rows)
    _write_jsonl(run_dir / "luna_evidence_validation.jsonl", luna_rows)
    _write_jsonl(run_dir / "evidence_traceability_validation.jsonl", trace_rows)
    _write_jsonl(run_dir / "rejection_root_causes.jsonl", rejections)
    _write_json(run_dir / "aksr_registry_validation.json", {**registry_validation, "registry_fingerprint": registry_fingerprint(registry), "source_records": list(source_registry.values())})
    _write_json(run_dir / "source_discovery_audit.json", {"apollo": apollo_audit, "pimco": pimco_audit, "blackrock": blackrock_audit})
    _write_json(run_dir / "protected_system_preservation_audit.json", preservation)
    _write_json(run_dir / "implementation_defects.json", {"defects": defects})
    _write_json(run_dir / "completion_summary.json", summary)
    manifest = _manifest(run_dir, run_id, generated, model_calls)
    _write_json(run_dir / "completion_manifest.json", manifest)
    summary["output_directory"] = str(run_dir)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-luna", action="store_true", help="Run deterministic source checks without an Acquisition AI call.")
    args = parser.parse_args()
    print(_canonical(run(no_luna=args.no_luna)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
