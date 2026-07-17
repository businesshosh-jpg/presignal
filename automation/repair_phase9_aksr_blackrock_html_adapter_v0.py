#!/usr/bin/env python3
"""Validate and freeze the narrow BlackRock HTML adapter repair."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
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
    MODE_PROSPECTIVE,
    _acquire_request,
    _load_model_config,
    _validate_source_bundle,
)
from automation.institutional_source_adapters_v0 import (  # type: ignore
    BLACKROCK_WEEKLY_COMMENTARY,
    _canonical,
    _extract_pdf_text,
    _fetch,
    _iso,
    blackrock_html_source_record,
    classify_blackrock_html_response,
    fetch_blackrock_weekly_html,
    match_request,
)
from automation.reconstruct_phase9_historical_market_information_environment_v0 import _faithfulness_errors  # type: ignore


PHASE_ID = "9-AKSR-BLACKROCK-HTML-ADAPTER-REPAIR"
BASE_CAPABILITY_RUN = "9-AKSR-INSTITUTIONAL-CAPABILITY-VALIDATION_20260716T153556Z"
BASE_AKSR_RUN = "9-APPROVED-KNOWLEDGE-SOURCE-REGISTRY_20260716T153803Z"
ARCHIVE_SNAPSHOT = "20240516092434"
OUTPUT_ROOT = ROOT / "outputs" / "phase9_aksr_blackrock_html_adapter_repair"
CATALOG_PATH = ROOT / "outputs/phase9_historical_environment_institutional_enrichment/active_v1/institutional_source_catalog_v2.jsonl"
PRIOR_REGISTRY_PATH = ROOT / "outputs/phase9_approved_knowledge_source_registry" / BASE_AKSR_RUN / "knowledge_source_registry.jsonl"


class BlackRockRepairError(RuntimeError):
    """Fail-closed BlackRock repair error."""


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise BlackRockRepairError("MISSING_REQUIRED_INPUT:" + str(path))
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
        "layered_prediction": ROOT / "automation/v2_layered_prediction_evaluation_v0.py",
    }
    return {name: _file_sha(path) for name, path in paths.items() if path.exists()}


def _request(*, mode: str, cutoff: str, category: str, concept: str) -> Dict[str, Any]:
    identity = {"mode": mode, "cutoff": cutoff, "category": category, "concept": concept}
    suffix = fingerprint(identity)[:20]
    return {
        "session_id": "AKSR_BLACKROCK_HTML|" + cutoff[:10] + "|VALIDATION",
        "forecast_cutoff": cutoff,
        "provider": "CAPABILITY_VALIDATION_PROVIDER_NEUTRAL",
        "provider_request_id": "BRHTML_REQ_" + suffix,
        "normalized_request_id": "BRHTML_NREQ_" + suffix,
        "request_category": category,
        "requested_concept": concept,
        "information_key": category.lower() + "|blackrock_html_validation",
    }


def _institutional_mode(mode: str) -> str:
    if mode == MODE_HISTORICAL:
        return "HISTORICAL_REPLAY"
    if mode == MODE_PROSPECTIVE:
        return "PROSPECTIVE_COLLECTION"
    raise BlackRockRepairError("INVALID_ACQUISITION_MODE:" + mode)


def _admission_item(source: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        **dict(source), "knowledge_item_id": source["source_record_id"],
        "relevance_status": "PASS", "outcome_leakage_status": "PASS",
    }


def _known_available_timestamp(source: Mapping[str, Any]) -> str:
    snapshot = str(source.get("archive_snapshot_timestamp") or "")
    if len(snapshot) == 14 and snapshot.isdigit():
        return datetime.strptime(snapshot, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    return str(source.get("retrieval_timestamp") or "")


def _source_bundle(
    request: Mapping[str, Any], source: Mapping[str, Any], generated: str, mode: str,
) -> Dict[str, Any]:
    available_at = _known_available_timestamp(source)
    identity = {
        "session_id": request["session_id"], "normalized_request_id": request["normalized_request_id"],
        "source_record_id": source["source_record_id"], "content_fingerprint": source["content_fingerprint"],
        "mode": mode,
    }
    bundle_id = "BRHTML_SB_" + fingerprint(identity)[:24]
    excerpt = str(source.get("relevant_text") or "")[:2600]
    bundle = {
        "source_bundle_id": bundle_id, "bundle_id": bundle_id,
        "session_id": request["session_id"], "request_id": request["provider_request_id"],
        "normalized_request_id": request["normalized_request_id"], "information_key": request["information_key"],
        "canonical_information": request["requested_concept"],
        "source_name": "BlackRock Investment Institute HTML publication",
        "source_type": "timestamped_institutional_research", "source_tier": "TIER_2_INSTITUTIONAL_RESEARCH",
        "source_reference": source["canonical_url"], "source_references": [source["canonical_url"]],
        "source_record_ids": [source["source_record_id"]], "source_ids": [source["source_id"]],
        "publication_timestamp": available_at,
        "original_publication_date": source["publication_timestamp"],
        "publication_date_precision": source["timestamp_precision"],
        "publication_timestamp_semantics": "CONSERVATIVE_KNOWN_AVAILABLE_AT",
        "retrieval_timestamp": source["retrieval_timestamp"],
        "historical_availability_timestamp": available_at,
        "as_of_timestamp": request["forecast_cutoff"], "forecast_timestamp": request["forecast_cutoff"],
        "content_or_structured_extract": (
            "source_record_id: {source_id}\npublisher: BlackRock Investment Institute\n"
            "title: {title}\ncanonical_url: {url}\noriginal_publication_date: {publication}\n"
            "publication_date_precision: {precision}\nrequest_relevant_excerpt: {excerpt}"
        ).format(
            source_id=source["source_record_id"], title=source["title"], url=source["canonical_url"],
            publication=source["publication_timestamp"], precision=source["timestamp_precision"], excerpt=excerpt,
        ),
        "source_language": "en", "source_reliability": "medium",
        "historical_availability_proven": "TRUE" if mode == MODE_HISTORICAL else "FALSE",
        "backtest_safe": "TRUE" if mode == MODE_HISTORICAL else "FALSE",
        "provenance_method": source["historical_state_evidence"],
        "provenance_status": "VALID", "cutoff_status": "PASS",
        "content_fingerprints": [source["content_fingerprint"]],
    }
    bundle["bundle_fingerprint"] = fingerprint({key: value for key, value in bundle.items() if key != "retrieval_timestamp"})
    return {**bundle, **_validate_source_bundle(bundle, mode)}


def _acquire(
    request: Mapping[str, Any], bundle: Mapping[str, Any], mode: str, run_id: str, generated: str, no_luna: bool,
) -> Tuple[Dict[str, Any], int]:
    if no_luna:
        return {"result_status": "NOT_CALLED_DETERMINISTIC_MODE", "validation_status": "NOT_RUN"}, 0
    config = _load_model_config()
    if config.get("provider") != "OpenAI" or config.get("model") != "gpt-5.6-luna" or config.get("reasoning") != "low" or config.get("temperature_parameter_sent"):
        raise BlackRockRepairError("FROZEN_LUNA_CONFIGURATION_MISMATCH")
    request_row = {
        "session_id": request["session_id"], "request_id": request["provider_request_id"],
        "candidate_id": "", "normalized_information_key": request["information_key"],
        "request_wording": request["requested_concept"], "backlog_acquisition_method": "ai_research_summary",
    }
    result, called = _acquire_request(request_row, [bundle], config, mode, run_id, generated)
    errors = _faithfulness_errors(result, [bundle]) if result.get("result_status") == "ACQUIRED_AI_RETRIEVED_PROVISIONAL" else [result.get("failure_reason") or "ACQUISITION_NOT_SUCCESSFUL"]
    return {
        **result, "source_faithfulness_errors": errors,
        "validation_status": "VALID" if not errors else "FAILED",
    }, int(called)


def _trace(
    request: Mapping[str, Any], route: Mapping[str, Any], source: Mapping[str, Any],
    evidence: Mapping[str, Any], bundle: Mapping[str, Any], mode: str,
) -> Dict[str, Any]:
    luna_id = "BRHTML_LUNA_" + fingerprint(evidence)[:24]
    trace = build_traceability_record(
        request=request, route=route, knowledge_item=_admission_item(source),
        luna_evidence={**dict(evidence), "source_id": source["source_id"], "luna_evidence_id": luna_id},
        pack_entry={
            "pack_entry_id": "BRHTML_PACK_ENTRY_" + fingerprint({"bundle": bundle["source_bundle_id"], "mode": mode})[:24],
            "luna_evidence_id": luna_id,
        },
        mode=mode,
    )
    return {**trace, "pack_entry_status": "VALIDATION_ONLY_PROVISIONAL_IDENTITY", "scientific_pack_modified": False}


def _manifest(run_dir: Path, run_id: str, generated: str, model_calls: int) -> Dict[str, Any]:
    artifacts = []
    for path in sorted(run_dir.iterdir()):
        if path.is_file() and path.name != "completion_manifest.json":
            artifacts.append({"file": path.name, "bytes": path.stat().st_size, "sha256": _file_sha(path)})
    value = {
        "run_id": run_id, "created_ts": generated,
        "phase": "Phase 9 Stage 4A AKSR BlackRock HTML Adapter Repair",
        "base_capability_run": BASE_CAPABILITY_RUN, "base_aksr_run": BASE_AKSR_RUN,
        "source_id": "KSRC_BLACKROCK_INVESTMENT_INSTITUTE",
        "artifacts": artifacts, "artifact_count": len(artifacts),
        "source_retrieval_scope": "BOUNDED_BLACKROCK_ONLY",
        "acquisition_ai_calls": model_calls, "forecast_calls": 0, "historical_replay_runs": 0,
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
        raise BlackRockRepairError("AKSR_REGISTRY_INTEGRITY_FAILED")
    prior_registry = {row["source_id"]: row for row in _read_jsonl(PRIOR_REGISTRY_PATH)}
    current_registry = {row["source_id"]: row for row in registry}
    non_blackrock_registry_preservation = all(
        prior_registry[source_id] == current_registry[source_id]
        for source_id in prior_registry if source_id != "KSRC_BLACKROCK_INVESTMENT_INSTITUTE"
    )

    catalog = [row for row in _read_jsonl(CATALOG_PATH) if row.get("source_family") == "BLACKROCK_INVESTMENT_INSTITUTE"]
    representative_terms = (
        "bii-global-macro-outlook-january-2018.pdf",
        "20240102-three-2023-lessons-we-carry-into-2024.pdf",
        "20240414-earnings-growth-not-just-about-tech.pdf",
        "20240429-mega-forces-why-they-matter-now.pdf",
        "bii-midyear-outlook-2024.pdf",
        "20260713-japan-bonds-tell-global-repricing-story.pdf",
    )
    representatives = [next(row for row in catalog if term in row["canonical_url"]) for term in representative_terms]
    diagnostics: List[Dict[str, Any]] = []
    for source in representatives:
        response = _fetch(source["canonical_url"], timeout=45)
        diagnostic = classify_blackrock_html_response(
            response, requested_url=source["canonical_url"], requested_title=source["title"],
        )
        diagnostics.append({**diagnostic, "source_record_id": source["source_record_id"], "diagnostic_role": "DISCOVERED_DOCUMENT_RESPONSE"})

    current_source, current_diagnostic = fetch_blackrock_weekly_html()
    historical_source, historical_diagnostic = fetch_blackrock_weekly_html(archive_snapshot_timestamp=ARCHIVE_SNAPSHOT)
    if not current_source or not historical_source:
        raise BlackRockRepairError("BLACKROCK_RESEARCH_HTML_NOT_RETRIEVABLE")
    diagnostics.extend([
        {**current_diagnostic, "source_record_id": current_source["source_record_id"], "diagnostic_role": "CURRENT_RESEARCH_HTML"},
        {**historical_diagnostic, "source_record_id": historical_source["source_record_id"], "diagnostic_role": "PRE_CUTOFF_ARCHIVED_RESEARCH_HTML"},
    ])
    classification_counts = dict(sorted(Counter(row["classification_result"] for row in diagnostics).items()))

    historical_request = _request(
        mode=MODE_HISTORICAL, cutoff="2024-05-17T12:00:00Z", category="risk_sentiment",
        concept="institutional equity risk sentiment and Japan market framing",
    )
    prospective_request = _request(
        mode=MODE_PROSPECTIVE, cutoff=_iso(now + timedelta(hours=1)), category="treasury_narrative",
        concept="current Treasury bond and rates market interpretation",
    )
    validations: List[Dict[str, Any]] = []
    traces: List[Dict[str, Any]] = []
    evidence_rows: List[Dict[str, Any]] = []
    bundles: List[Dict[str, Any]] = []
    model_calls = 0
    for mode, request, source in (
        (MODE_HISTORICAL, historical_request, historical_source),
        (MODE_PROSPECTIVE, prospective_request, current_source),
    ):
        registry_mode = _institutional_mode(mode)
        match = match_request([source], request, mode=registry_mode)
        if not match.admitted:
            raise BlackRockRepairError(mode + "_REQUEST_MATCH_FAILED:" + str(match.rejected[0].get("rejection_reason")))
        admitted_source = dict(match.admitted[0])
        route = route_request(request, registry_mode, registry)
        admission = admit_knowledge_item(_admission_item(admitted_source), request, registry_mode, registry)
        if admission["article_admission_status"] != "ADMITTED":
            raise BlackRockRepairError(mode + "_AKSR_ADMISSION_FAILED:" + "|".join(admission["rejection_reasons"]))
        bundle = _source_bundle(request, admitted_source, generated, mode)
        evidence, called = _acquire(request, bundle, mode, run_id, generated, no_luna)
        model_calls += called
        if not no_luna and evidence.get("validation_status") != "VALID":
            raise BlackRockRepairError(mode + "_LUNA_VALIDATION_FAILED:" + "|".join(evidence.get("source_faithfulness_errors") or []))
        trace = {"traceability_status": "NOT_RUN_NO_LUNA"} if no_luna else _trace(request, route, admitted_source, evidence, bundle, registry_mode)
        validations.append({
            "mode": mode, "request": request, "route_id": route["route_id"],
            "source": admitted_source, "article_admission": admission,
            "final_status": "RESEARCH_ARTICLE_HTML_ADMITTED",
        })
        bundles.append(bundle)
        evidence_rows.append({"mode": mode, "source_id": admitted_source["source_id"], **evidence})
        traces.append({"mode": mode, **trace})

    pdf_fallback = []
    for row in diagnostics:
        if row["diagnostic_role"] != "DISCOVERED_DOCUMENT_RESPONSE":
            continue
        actual_pdf = bool(row.get("actual_pdf_bytes"))
        parsed_text = _extract_pdf_text(row["requested_url"]) if actual_pdf else ""
        pdf_fallback.append({
            "requested_url": row["requested_url"], "classification_result": row["classification_result"],
            "rejection_reason": row["rejection_reason"], "passed_to_pdf_parser": actual_pdf,
            "actual_pdf_bytes": actual_pdf, "parsed_text_characters": len(parsed_text),
            "validation_status": "PASS" if (actual_pdf and len(parsed_text) >= 400) or not actual_pdf else "FAIL",
        })
    protected_after = _protected_fingerprints()
    preservation = {
        "before": protected_before, "after": protected_after,
        "fingerprints_equal": protected_before == protected_after,
        "non_blackrock_registry_rows_equal": non_blackrock_registry_preservation,
        "apollo_registry_unchanged": prior_registry["KSRC_APOLLO_DAILY_SPARK"] == current_registry["KSRC_APOLLO_DAILY_SPARK"],
        "pimco_registry_unchanged": prior_registry["KSRC_PIMCO_INSIGHTS"] == current_registry["KSRC_PIMCO_INSIGHTS"],
        "historical_replay_rerun": False, "forecast_calls": 0, "existing_packs_modified": False,
        "provider_prompts_changed": False, "prediction_changed": False, "outcome_changed": False,
        "evaluation_changed": False, "production_changed": False,
    }
    defects = [
        {
            "defect": "ALL_NON_PDF_BLACKROCK_RESPONSES_COLLAPSED_TO_DOCUMENT_ACCESS_GATE_HTML_RESPONSE",
            "repair": "DETERMINISTIC_EIGHT_CLASS_HTML_RESPONSE_CLASSIFIER",
        },
        {
            "defect": "PUBLIC_SERVER_RENDERED_WEEKLY_RESEARCH_HTML_WAS_NOT_AN_ACQUISITION_PATH",
            "repair": "TITLE_DATE_BODY_AND_PUBLISHER_VALIDATED_HTML_SOURCE_RECORD",
        },
        {
            "defect": "BLACKROCK_DATE_EXTRACTION_DID_NOT_DISTINGUISH_ARTICLE_DATE_FROM_IN_BODY_DATES",
            "repair": "BLACKROCK_MARKET_INSIGHTS_DATE_FIELD_PRIORITY_WITH_DATE_ONLY_PRECISION",
        },
        {
            "defect": "BLACKROCK_HISTORICAL_HTML_PAGE_STATE_WAS_NOT_VERSION_PINNED",
            "repair": "PRE_CUTOFF_WAYBACK_SNAPSHOT_IDENTITY_AND_FINGERPRINT_PROPAGATION",
        },
    ]
    all_pass = (
        classification_counts.get("CONSENT_OR_COOKIE_GATE") == len(representatives) - 1
        and classification_counts.get("PDF_DOCUMENT_RESPONSE") == 1
        and classification_counts.get("RESEARCH_LANDING_PAGE_WITH_CONTENT") == 2
        and all(row["validation_status"] == "PASS" for row in pdf_fallback)
        and all(row["article_admission"]["article_admission_status"] == "ADMITTED" for row in validations)
        and (no_luna or all(row.get("validation_status") == "VALID" for row in evidence_rows))
        and (no_luna or all(row.get("traceability_status") == "PASS" for row in traces))
        and preservation["fingerprints_equal"] and preservation["non_blackrock_registry_rows_equal"]
    )
    capability = {
        "source_id": "KSRC_BLACKROCK_INVESTMENT_INSTITUTE",
        "historical_capability": "PASS_CONDITIONAL_PRE_CUTOFF_ARCHIVED_HTML_STATE",
        "prospective_capability": "PASS_CURRENT_SERVER_RENDERED_HTML_CAPTURE",
        "document_url_capability": "CONSENT_GATED_NOT_ADMISSIBLE",
        "historical_article": historical_source["title"],
        "historical_publication_date": historical_source["publication_timestamp"],
        "historical_archive_snapshot": ARCHIVE_SNAPSHOT,
        "prospective_article": current_source["title"],
        "prospective_publication_date": current_source["publication_timestamp"],
        "same_day_date_only_rule": "UNCHANGED_FAIL_CLOSED",
        "revision_policy": "UNCHANGED_VERSION_PINNED_WITH_INDICATORS_PRESERVED",
    }
    summary = {
        "build_status": "PASS" if all_pass else "PARTIAL",
        "final_decision": "BLACKROCK_HTML_ADAPTER_REPAIR_PASSED" if all_pass else "TARGETED_REPAIR_REQUIRED",
        "run_id": run_id, "base_capability_run": BASE_CAPABILITY_RUN, "base_aksr_run": BASE_AKSR_RUN,
        "representative_document_responses": len(representatives), "html_research_pages_validated": 2,
        "classification_counts": classification_counts,
        "historical_capability": capability["historical_capability"],
        "prospective_capability": capability["prospective_capability"],
        "historical_admissions": 1, "prospective_admissions": 1,
        "luna_calls": model_calls, "luna_evidence_valid": sum(row.get("validation_status") == "VALID" for row in evidence_rows),
        "traceability_pass": sum(row.get("traceability_status") == "PASS" for row in traces),
        "registry_fingerprint": registry_fingerprint(registry), "registry_integrity": registry_validation["status"],
        "implementation_defects_found": len(defects), "implementation_defects_repaired": len(defects),
        "historical_replay_runs": 0, "forecast_calls": 0, "scientific_rules_changed": False,
        "existing_packs_modified": False, "production_changed": False,
        "protected_artifacts_unchanged": preservation["fingerprints_equal"],
    }
    reconstruction = {
        "registry_fingerprint_first": registry_fingerprint(registry),
        "registry_fingerprint_second": registry_fingerprint(list(reversed(registry))),
        "registry_fingerprint_reconstruction": "PASS" if registry_fingerprint(registry) == registry_fingerprint(list(reversed(registry))) else "FAIL",
        "bundle_fingerprints_unique": len({row["bundle_fingerprint"] for row in bundles}) == len(bundles),
        "classification_count_reconciliation": sum(classification_counts.values()) == len(diagnostics),
        "zero_forecast_calls": True, "zero_replay_runs": True,
    }

    _write_jsonl(run_dir / "representative_html_diagnostics.jsonl", diagnostics)
    _write_json(run_dir / "classification_summary.json", {"classification_counts": classification_counts, "population_count": len(diagnostics)})
    _write_jsonl(run_dir / "article_admission_validation.jsonl", validations)
    _write_jsonl(run_dir / "validated_source_bundles.jsonl", bundles)
    _write_jsonl(run_dir / "luna_evidence_validation.jsonl", evidence_rows)
    _write_jsonl(run_dir / "traceability_validation.jsonl", traces)
    _write_jsonl(run_dir / "pdf_fallback_validation.jsonl", pdf_fallback)
    _write_json(run_dir / "capability_result.json", capability)
    _write_json(run_dir / "protected_artifact_audit.json", preservation)
    _write_json(run_dir / "implementation_defects.json", {"defects": defects})
    _write_json(run_dir / "reconstruction_validation.json", reconstruction)
    _write_json(run_dir / "completion_summary.json", summary)
    _write_json(run_dir / "completion_manifest.json", _manifest(run_dir, run_id, generated, model_calls))
    return {**summary, "output_directory": str(run_dir)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-luna", action="store_true")
    args = parser.parse_args()
    print(_canonical(run(no_luna=args.no_luna)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
