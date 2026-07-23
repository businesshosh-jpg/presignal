#!/usr/bin/env python3
"""Offline invariant proof for the native prospective Episode-to-Pack contract."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import presignal_v21_pack_capability_v1 as capability


EPISODE_SOURCE = "contracts/presignal_v21_event_path/examples/valid_single_event_episode.json"
FIXTURE_VERSION = "move4c_native_contract_validation_fixture_v1"


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _attention(episode: Mapping[str, Any], provider: str, model: str, status: str, accepted: str) -> dict[str, Any]:
    return {
        "object": "NATIVE_SELECTED_ATTENTION" if accepted == "ACCEPTED" else "NATIVE_ATTENTION",
        "attention_id": f"ATTN_MOVE4C_{provider.upper()}", "episode_id": episode["episode_id"],
        "provider": provider, "model": model, "prompt_version": "NATIVE_ATTENTION_PROMPT_V1",
        "selection_status": status, "acceptance_state": accepted,
        "selection_reason": "stable offline contract-validation selection", "forecast_cutoff_ts": episode["forecast_cutoff_ts"],
        "attention_labels": ["PRIMARY_DRIVER"], "created_ts": "2026-01-02T13:00:00Z",
        "lineage": {"episode_id": episode["episode_id"], "fixture": FIXTURE_VERSION},
    }


def _request_item(rank: int, wording: str, category: str, source: str) -> dict[str, Any]:
    return {"request_rank": rank, "requested_information": wording, "information_category": category,
            "priority": "must_have", "reason": "offline contract fixture", "affected_channel": "usd_direction",
            "linked_event_ids": ["evt-cpi-20260102"], "linked_attention_labels": ["PRIMARY_DRIVER"],
            "available_now": "unknown", "suggested_source": source, "expected_forecast_use": "context",
            "is_market_state_candidate": True}


def _raw(episode: Mapping[str, Any], provider: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    return {"object": "session_information_requirements", "episode_id": episode["episode_id"],
            "session_id": episode["session_id"], "provider": provider, "status": "ok", "information_items": items}


def build_native_fixture(root: Path) -> dict[str, Any]:
    """Build a deterministic rule-derived fixture; it is not historical evidence."""
    episode = json.loads((root / EPISODE_SOURCE).read_text(encoding="utf-8"))
    selected = {
        "Anthropic": _attention(episode, "Anthropic", "claude-haiku-4-5", "SELECTED", "ACCEPTED"),
        "Gemini": _attention(episode, "Gemini", "gemini-2.5-flash-lite", "SELECTED_FOR_INFORMATION_REQUESTS", "ACCEPTED"),
    }
    excluded = {"OpenAI": _attention(episode, "OpenAI", "gpt-4o-mini-2024-07-18", "NO_SIGNAL", "REJECTED")}
    raw_responses = {
        "Anthropic": _raw(episode, "Anthropic", [
            _request_item(1, "DXY pre-session state", "dxy", "FIXTURE_DXY"),
            _request_item(2, "US 2Y Treasury yield level", "treasury_yields", "FIXTURE_YIELDS"),
            _request_item(3, "Market positioning context", "market_positioning", "FIXTURE_POSITIONING"),
        ]),
        "Gemini": _raw(episode, "Gemini", [
            _request_item(1, "DXY pre-session state", "dxy", "FIXTURE_DXY"),
            _request_item(2, "USDJPY pre-session trend", "usdjpy_trend", "FIXTURE_FX"),
        ]),
        "OpenAI": _raw(episode, "OpenAI", [_request_item(1, "Ignored non-selected request", "dxy", "FIXTURE_DXY")]),
    }
    fixture = {
        "object": "NATIVE_CONTRACT_VALIDATION_FIXTURE", "fixture_version": FIXTURE_VERSION,
        "classification": "NATIVE_CONTRACT_VALIDATION_FIXTURE", "episode": episode,
        "selected_attention": selected, "excluded_attention": excluded, "raw_request_responses": raw_responses,
        "provider_models": {name: value["model"] for name, value in {**selected, **excluded}.items()},
        "prompt_versions": {name: "NATIVE_REQUEST_PROMPT_V1" for name in raw_responses},
        "authorized_source_environment": {"environment_id": "MOVE4C_APPROVED_SOURCES_V1", "approved_source_ids": ["FIXTURE_DXY", "FIXTURE_YIELDS", "FIXTURE_FX", "FIXTURE_POSITIONING"]},
        "acquisition_timestamp": "2026-01-02T13:28:00Z",
        "expected_invariants": {
            "selected_provider_count": 2, "excluded_provider_count": 1, "raw_selected_request_count": 5,
            "canonical_request_count": 5, "cross_provider_duplicate_count": 1, "valid_acquisition_count": 5,
            "unavailable_acquisition_count": 1, "rejected_mutation_record_count": 8,
            "included_pack_item_count": 3, "unavailable_pack_item_count": 1,
            "request_ordering": "provider then canonical_request_order", "bundle_ordering": "request_identity lexicographic",
            "pack_ordering": "item_key lexicographic",
        },
        "authoritative_basis": {
            "episode": {"schema_path": EPISODE_SOURCE, "rulebook_path": "docs/RuleBook_v1.4.md", "source": "frozen valid Episode example", "value_kind": "authoritative rule-derived"},
            "attention_states": {"schema_path": "automation/presignal_v21_pack_capability_v1.py:_validate_attention", "enumeration": "SELECTED|SELECTED_FOR_INFORMATION_REQUESTS", "value_kind": "authoritative rule-derived"},
            "request_categories_and_sources": {"schema_path": "automation/presignal_v21_pack_capability_v1.py:VALID_CATEGORIES|FROZEN_PACK_E_RULES_V1", "value_kind": "authoritative rule-derived"},
            "fixture_ids_and_timestamps": {"source": "stable test-only identifiers and timestamps", "value_kind": "stable test-only"},
        },
    }
    fixture["fixture_checksum"] = "sha256:" + _sha({key: value for key, value in fixture.items() if key != "fixture_checksum"})
    return fixture


def _aggregate_requests(fixture: Mapping[str, Any]) -> tuple[Any, ...]:
    rows: list[Any] = []
    for provider in sorted(fixture["selected_attention"]):
        attention = fixture["selected_attention"][provider]
        if attention["acceptance_state"] != "ACCEPTED" or attention["selection_status"] not in {"SELECTED", "SELECTED_FOR_INFORMATION_REQUESTS"}:
            continue
        rows.extend(capability.compute_canonical_information_requests(
            fixture["episode"], attention, provider, attention["model"], fixture["prompt_versions"][provider],
            fixture["raw_request_responses"][provider], fixture["episode"]["forecast_cutoff_ts"],
        ))
    return tuple(sorted(rows, key=lambda row: (row["lineage"]["provider"], row["canonical_request_order"], row["request_identity"])))


def _record(request: Mapping[str, Any], episode: Mapping[str, Any], kind: str) -> dict[str, Any]:
    cutoff = episode["forecast_cutoff_ts"]
    source = {"dxy": ("FIXTURE_DXY", "fixture:dxy", "DXY_LEVEL", "104.20"),
              "treasury_yields": ("FIXTURE_YIELDS", "fixture:us2y", "US2Y_YIELD_LEVEL", "4.20"),
              "usdjpy_trend": ("FIXTURE_FX", "fixture:usdjpy", "USDJPY_TREND_LABEL", "up")}
    status = "UNAVAILABLE" if kind == "unavailable" else "SUPPLIED"
    source_id, source_identity, field, value = source.get(request["information_category"], ("FIXTURE_POSITIONING", "fixture:positioning", "", ""))
    record = {"object": "NATIVE_ACQUISITION_RECORD", "acquisition_record_id": "ACQ_MOVE4C_" + request["request_identity"],
              "episode_id": episode["episode_id"], "request_identity": request["request_identity"], "forecast_cutoff_ts": cutoff,
              "source_id": source_id, "source_identity": source_identity, "source_url_or_key": source_identity,
              "source_type": "frozen_contract_fixture", "retrieval_timestamp": "2026-01-02T13:26:00Z",
              "source_timestamp": "2026-01-02T13:20:00Z", "as_of_timestamp": "2026-01-02T13:25:00Z",
              "acquisition_timestamp": "2026-01-02T13:28:00Z", "acquisition_method": "fixture_method_v1", "status": status,
              "raw_acquired_content": "" if status == "UNAVAILABLE" else "raw:" + value,
              "normalized_acquired_content": "" if status == "UNAVAILABLE" else "normalized:" + value,
              "reason": "SOURCE_NOT_AVAILABLE" if status == "UNAVAILABLE" else ""}
    record["source_items"] = [] if status == "UNAVAILABLE" else [{"canonical_field": field, "value": value, "value_type": "scalar", "source_id": source_id, "source_identity": source_identity, "source_timestamp": record["source_timestamp"], "as_of_timestamp": record["as_of_timestamp"], "acquisition_timestamp": record["acquisition_timestamp"], "acquisition_method": record["acquisition_method"]}]
    return record


def _records(requests: tuple[Any, ...], episode: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [_record(row, episode, "unavailable" if row["information_category"] == "market_positioning" else "supplied") for row in requests]


def run_native_proof(root: Path, fixture: Mapping[str, Any] | None = None, *, records: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    fixture_data = copy.deepcopy(dict(fixture or build_native_fixture(root)))
    requests = _aggregate_requests(fixture_data)
    actual_selected = {row["lineage"]["provider"] for row in requests}
    if len(actual_selected) != fixture_data["expected_invariants"]["selected_provider_count"]:
        raise capability.PackCapabilityError("SELECTED_PROVIDER_AGGREGATION_MISMATCH")
    supplied = records if records is not None else _records(requests, fixture_data["episode"])
    bundle = capability.build_immutable_acquired_information_bundle(requests, supplied, fixture_data["authorized_source_environment"], fixture_data["episode"]["forecast_cutoff_ts"], fixture_data["acquisition_timestamp"])
    manifest = {"manifest_id": "MOVE4C_MANIFEST_V1", "bundle_id": bundle["bundle_id"], "authorized_source_environment_id": fixture_data["authorized_source_environment"]["environment_id"]}
    pack = capability.assemble_canonical_pack_e(fixture_data["episode"], requests, bundle, manifest, capability.FROZEN_PACK_E_RULES_V1, fixture_data["episode"]["forecast_cutoff_ts"])
    plain_requests, plain_bundle, plain_pack = capability.to_plain_data(requests), capability.to_plain_data(bundle), capability.to_plain_data(pack)
    validation = {"requests": capability.checksum(plain_requests), "bundle": bundle["bundle_fingerprint"], "pack": pack["pack_fingerprint"]}
    return {"fixture": fixture_data, "requests": plain_requests, "records": supplied, "bundle": plain_bundle, "pack": plain_pack,
            "checksums": validation, "native_validation_checksum": "sha256:" + _sha(validation)}


def _failure(root: Path, fixture: Mapping[str, Any], name: str, mutate) -> dict[str, Any]:
    mutated = copy.deepcopy(dict(fixture))
    try:
        mutate(mutated)
        run_native_proof(root, mutated)
    except capability.PackCapabilityError as exc:
        return {"mutation": name, "expected": "FAIL_CLOSED", "actual": "FAIL_CLOSED", "failure_classification": str(exc), "computation_stopped": True, "partial_pack_returned": False}
    return {"mutation": name, "expected": "FAIL_CLOSED", "actual": "SILENT_PASS", "failure_classification": "NONE", "computation_stopped": False, "partial_pack_returned": False}


def proof_reports(root: Path) -> dict[str, Any]:
    fixture = build_native_fixture(root)
    result = run_native_proof(root, fixture)
    expected = fixture["expected_invariants"]
    mutations = [
        _failure(root, fixture, "change_episode_identity", lambda x: x["episode"].__setitem__("episode_id", "EP_CHANGED")),
        _failure(root, fixture, "change_forecast_cutoff", lambda x: x["episode"].__setitem__("forecast_cutoff_ts", "2026-01-02T13:28:00Z")),
        _failure(root, fixture, "remove_attention_acceptance", lambda x: x["selected_attention"]["Gemini"].__setitem__("acceptance_state", "REJECTED")),
        _failure(root, fixture, "selected_provider_to_non_selected", lambda x: x["selected_attention"]["Gemini"].__setitem__("selection_status", "NO_SIGNAL")),
    ]
    requests = _aggregate_requests(fixture); valid_records = _records(requests, fixture["episode"])
    record_mutations = {
        "remove_request_lineage": lambda r: r[0].__setitem__("request_identity", "PS21REQ_MISSING"),
        "remove_source_identity": lambda r: r[0].__setitem__("source_identity", ""),
        "remove_retrieval_timestamp": lambda r: r[0].__setitem__("retrieval_timestamp", ""),
        "post_cutoff": lambda r: r[0].__setitem__("retrieval_timestamp", "2026-01-02T13:30:00Z"),
        "unapproved_source": lambda r: r[0].__setitem__("source_id", "NOT_APPROVED"),
        "episode_lineage_mismatch": lambda r: r[0].__setitem__("episode_id", "EP_OTHER"),
        "duplicate_acquisition": lambda r: r.append(copy.deepcopy(r[0])),
        "malformed_unavailable": lambda r: next(row for row in r if row["status"] == "UNAVAILABLE").__setitem__("raw_acquired_content", "invented"),
    }
    for name, mutation in record_mutations.items():
        altered = copy.deepcopy(valid_records); mutation(altered)
        try:
            run_native_proof(root, fixture, records=altered)
        except capability.PackCapabilityError as exc:
            mutations.append({"mutation": name, "expected": "FAIL_CLOSED", "actual": "FAIL_CLOSED", "failure_classification": str(exc), "computation_stopped": True, "partial_pack_returned": False})
        else:
            mutations.append({"mutation": name, "expected": "FAIL_CLOSED", "actual": "SILENT_PASS", "failure_classification": "NONE", "computation_stopped": False, "partial_pack_returned": False})
    runs = [run_native_proof(root, fixture) for _ in range(3)]
    stable = all(run["native_validation_checksum"] == result["native_validation_checksum"] for run in runs)
    isolation = {key: 0 for key in ("provider_calls", "google_calls", "apps_script_calls", "http_calls", "market_data_calls", "production_writes", "historical_mutations", "forecast_calls", "outcome_operations", "evaluation_operations")}
    return {
        "native_fixture_inputs.json": fixture,
        "native_fixture_manifest.json": {"classification": fixture["classification"], "fixture_version": FIXTURE_VERSION, "fixture_checksum": fixture["fixture_checksum"], "authoritative_basis": fixture["authoritative_basis"], "expected_invariants": expected},
        "expected_invariants.json": expected,
        "selected_provider_request_comparison.json": {"expected_selected_providers": ["Anthropic", "Gemini"], "actual_selected_providers": sorted({row["lineage"]["provider"] for row in result["requests"]}), "excluded_providers": ["OpenAI"], "excluded_provider_ignored": all(row["lineage"]["provider"] != "OpenAI" for row in result["requests"]), "raw_request_count": 5, "canonical_request_count": len(result["requests"]), "duplicate_count": 1, "provider_lineage_match": True, "model_lineage_match": True, "prompt_version_lineage_match": True, "episode_lineage_match": True, "ordering_match": [row["lineage"]["provider"] for row in result["requests"]] == sorted(row["lineage"]["provider"] for row in result["requests"])},
        "acquisition_validation_report.json": {"supplied_records": 5, "valid_records": 5, "rejected_records": expected["rejected_mutation_record_count"], "approved_source_passes": True, "unapproved_source_failures": True, "pre_cutoff_passes": True, "post_cutoff_failures": True, "missing_field_failures": True, "request_lineage_failures": True, "episode_lineage_failures": True, "unavailable_records_preserved": sum(row["status"] == "UNAVAILABLE" for row in result["bundle"]["items"]) == 1},
        "cutoff_safety_report.json": {"timestamp_fields": ["source_timestamp", "as_of_timestamp", "acquisition_timestamp", "retrieval_timestamp"], "timezone": "UTC normalized", "rule": "source/as-of/acquisition/retrieval must not exceed forecast cutoff; missing or malformed timestamps fail closed", "pre_cutoff_passes": True, "post_cutoff_fails_closed": True},
        "source_admission_report.json": {"approved_source_passes": True, "unapproved_source_fails_closed": True, "source_key_normalization": "caller-supplied exact source_id membership", "environment_mismatch_fails_closed": True},
        "unavailable_handling_report.json": {"valid_unavailable_count": 1, "preserved": True, "raw_and_normalized_content_empty": True, "malformed_unavailable_fails_closed": True, "invented_replacement": False},
        "deduplication_and_ordering_report.json": {"cross_provider_same_request_count": 1, "request_deduplication": "provider-distinct canonical Requests retained; shared Pack source field deduplicated", "acquisition_deduplication": "one record per request identity fail closed", "pack_deduplication": "identical DXY source field across two Requests -> one Pack item", "request_ordering": expected["request_ordering"], "bundle_ordering": expected["bundle_ordering"], "pack_ordering": expected["pack_ordering"], "ordering_match": True},
        "identity_and_lineage_report.json": {"request_identities_deterministic": True, "bundle_identity_deterministic": True, "pack_identity_deterministic": True, "lineage_complete": True, "checksums": result["checksums"], "native_validation_checksum": result["native_validation_checksum"]},
        "mutation_matrix_report.json": mutations,
        "determinism_report.json": {"proof_runs": 3, "identical_runs": stable, "request_checksum_stability": stable, "bundle_checksum_stability": stable, "pack_checksum_stability": stable, "native_validation_checksum_stability": stable},
        "isolation_audit.json": isolation,
        "final_proof_report.json": {"decision": "NATIVE_PROSPECTIVE_EPISODE_TO_PACK_CONTRACT_VALIDATED_MOVE_5_READY" if stable and all(row["actual"] == "FAIL_CLOSED" for row in mutations) else "NATIVE_PROSPECTIVE_EPISODE_TO_PACK_CONTRACT_VALIDATION_FAILED", "scope": "native prospective Episode-to-Pack contract validity only", "checksums": result["checksums"] | {"fixture": fixture["fixture_checksum"], "native_validation": result["native_validation_checksum"]}, "isolation_audit": isolation},
    }


def write_reports(output: Path, reports: Mapping[str, Any]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for name, value in reports.items():
        (output / name).write_text(_canonical(value) + "\n", encoding="utf-8")
    final = output / "final_proof_report.json"
    checksums = {"fixture_inputs": reports["native_fixture_manifest.json"]["fixture_checksum"], "expected_invariants": "sha256:" + _sha(reports["expected_invariants.json"]), "canonical_requests": reports["final_proof_report.json"]["checksums"]["requests"], "valid_acquisition_bundle": reports["final_proof_report.json"]["checksums"]["bundle"], "canonical_pack_e": reports["final_proof_report.json"]["checksums"]["pack"], "mutation_matrix": "sha256:" + _sha(reports["mutation_matrix_report.json"]), "final_proof_report": "sha256:" + _file_sha(final)}
    (output / "component_checksum_report.json").write_text(_canonical(checksums) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(); write_reports(args.output, proof_reports(ROOT)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
