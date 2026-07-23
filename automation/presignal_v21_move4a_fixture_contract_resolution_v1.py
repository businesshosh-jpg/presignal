"""Read-only evidence resolver for the Designed Drift 2 Move 4A contract.

This module deliberately has no network, credential, provider, Google, or write
dependencies.  It classifies the frozen historical Pack fingerprint without
converting its derived items into native prospective acquisition records.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


EXPECTED_FINGERPRINT = "f0f26f9c1657af4078dbae5802b721f051c2190c1cc3ebe12646c1a4ab3abba6"
EPISODE_ID = "EP_BATCH_08270f992a13e29e770f"
HISTORICAL_CUTOFF = "2024-05-08T06:50:00Z"
EPISODE_CUTOFF = "2024-05-08T11:00:00Z"
STEP5_PATH = "outputs/presignal_v21_step5_reuse/event_path_forecast_inputs_pack_e.jsonl"
EPISODE_PATH = "outputs/presignal_v21_episode_builder/episode_rows.jsonl"


def _json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")


def sha256(value: Any) -> str:
    return hashlib.sha256(_json_bytes(value)).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _row(path: Path, predicate: Any) -> dict[str, Any]:
    for line in path.read_text(encoding="utf-8").splitlines():
        candidate = json.loads(line)
        if predicate(candidate):
            return candidate
    raise LookupError(f"No matching record in {path}")


def resolve(repository_root: Path) -> dict[str, Any]:
    """Return the audited Move 4A evidence; never writes or invokes I/O adapters."""
    episode_file = repository_root / EPISODE_PATH
    step5_file = repository_root / STEP5_PATH
    episode = _row(episode_file, lambda value: value.get("episode_id") == EPISODE_ID)
    bridge = _row(
        step5_file,
        lambda value: value.get("episode_id") == EPISODE_ID
        and value.get("provider") == "Gemini"
        and value.get("model") == "gemini-2.5-flash-lite",
    )
    pack = bridge["shared_market_state_pack"]
    items = pack["items"]
    actual_fingerprint = sha256(items)
    origins = {
        origin["provider"]
        for item in items
        for origin in item.get("provider_request_origins", [])
    }
    supplied = [item for item in items if item.get("data_available_flag")]
    source_record_fields = {
        "originating Request identity": all(bool(item.get("normalized_request_id")) for item in items),
        "source identity": all(bool(item.get("source_identity")) for item in supplied),
        "source URL or source key": False,
        "retrieval timestamp": False,
        "as-of timestamp": all(bool(item.get("historical_availability_timestamp")) for item in supplied),
        "cutoff decision": all(item.get("forecast_cutoff") == HISTORICAL_CUTOFF for item in items),
        "raw acquired content": False,
        "normalized acquired content": False,
        "unavailable classification": all(bool(item.get("final_status")) for item in items),
        "acquisition method": all(bool(item.get("acquisition_method")) for item in items),
    }
    return {
        "source_checksums": {
            EPISODE_PATH: f"sha256:{file_sha256(episode_file)}",
            STEP5_PATH: f"sha256:{file_sha256(step5_file)}",
        },
        "episode": episode,
        "bridge": bridge,
        "pack": pack,
        "fingerprint": actual_fingerprint,
        "fingerprint_matches_frozen": actual_fingerprint == EXPECTED_FINGERPRINT,
        "provider_origins": sorted(origins),
        "source_record_fields": source_record_fields,
        "supplied_item_count": len(supplied),
        "excluded_or_unavailable_item_count": len(items) - len(supplied),
    }


def reports(repository_root: Path) -> dict[str, Any]:
    """Build deterministic report payloads used by the committed evidence package."""
    evidence = resolve(repository_root)
    episode = evidence["episode"]
    bridge = evidence["bridge"]
    pack = evidence["pack"]
    items = pack["items"]
    sources = evidence["source_checksums"]
    historical_compatible = {
        "episode_cutoff_matches_pack_cutoff": episode["forecast_cutoff_ts"] == pack["forecast_cutoff"],
        "attention_is_selected": bridge["provider_episode_selection"] in {
            "SELECTED",
            "SELECTED_FOR_INFORMATION_REQUESTS",
        },
        "complete_shared_request_lineage": len(evidence["provider_origins"]) == 3,
        "source_level_acquisition_records": all(evidence["source_record_fields"].values()),
        "canonical_pack_present": True,
        "authoritative_expected_fingerprint": evidence["fingerprint_matches_frozen"],
    }
    inventory = {
        "schema_version": "presignal_v21_move4a_fixture_inventory_v1",
        "read_only": True,
        "sources": sources,
        "candidates": [
            {
                "artifact_path": STEP5_PATH,
                "source_commit": "8e57652d002b6791d96328fbaa5c8273fdfd4e62",
                "episode_identity": EPISODE_ID,
                "attention_state": bridge["provider_episode_selection"],
                "provider_model": "Gemini/gemini-2.5-flash-lite",
                "request_provider_count": len(evidence["provider_origins"]),
                "pack_cutoff": pack["forecast_cutoff"],
                "episode_cutoff": episode["forecast_cutoff_ts"],
                "acquisition_record_availability": "DERIVED_PACK_ITEMS_ONLY",
                "pack_item_count": len(pack["items"]),
                "expected_checksum": EXPECTED_FINGERPRINT,
                "compatibility": "PARTIAL_HISTORICAL_COMPUTE_ONLY",
                "rejection_reason": "WATCH is not selected; cutoffs differ; Pack is a three-provider shared union; only derived Pack items are retained.",
            },
            {
                "artifact_path": "outputs/presignal_v21_step8_r2_historical_replication/STEP8-R2-e057ba70c884e0e618cf/sessions/US|2024-05-08|CUSTOM_CONFIG_WINDOW",
                "source_commit": "local frozen output",
                "episode_identity": None,
                "attention_state": "historical per-provider attention artifacts",
                "provider_model": "Anthropic/Gemini/OpenAI",
                "request_provider_count": 3,
                "pack_cutoff": HISTORICAL_CUTOFF,
                "episode_cutoff": None,
                "acquisition_record_availability": "DERIVED_PACK_ITEMS_ONLY",
                "pack_item_count": None,
                "expected_checksum": None,
                "compatibility": "PARTIAL_HISTORICAL_CONTEXT_ONLY",
                "rejection_reason": "No canonical Episode identity or source-level acquisition records in one native lineage.",
            },
            {
                "artifact_path": "outputs/presignal_v21_post_step9_r2_return_only_wrappers",
                "source_commit": "local frozen output",
                "episode_identity": None,
                "attention_state": None,
                "provider_model": None,
                "request_provider_count": 0,
                "pack_cutoff": None,
                "episode_cutoff": None,
                "acquisition_record_availability": "INSUFFICIENT_LINEAGE",
                "pack_item_count": None,
                "expected_checksum": None,
                "compatibility": "REJECTED",
                "rejection_reason": "Return-only wrapper contracts are explicitly not implemented and contain no frozen proof inputs.",
            },
            {
                "artifact_path": "outputs/presignal_v21_prospective_shadow_preparation",
                "source_commit": "local frozen output",
                "episode_identity": None,
                "attention_state": None,
                "provider_model": None,
                "request_provider_count": 0,
                "pack_cutoff": None,
                "episode_cutoff": None,
                "acquisition_record_availability": "INSUFFICIENT_LINEAGE",
                "pack_item_count": None,
                "expected_checksum": None,
                "compatibility": "REJECTED",
                "rejection_reason": "Preparation contracts contain no completed native Episode-to-Pack fixture.",
            },
        ],
    }
    return {
        "candidate_fixture_inventory.json": inventory,
        "candidate_fixture_compatibility_matrix.json": {
            "schema_version": "presignal_v21_move4a_compatibility_matrix_v1",
            "required_native_lineage": historical_compatible,
            "fully_compatible_fixture_count": 0,
            "partially_compatible_fixture_count": 2,
            "rejected_fixture_count": 2,
            "result": "NO_NATIVE_FIXTURE; historical fixture is sufficient only for a separate historical-compute proof envelope.",
        },
        "historical_fingerprint_scope.json": {
            "fingerprint": EXPECTED_FINGERPRINT,
            "classification": "HISTORICAL_SHARED_PACK_FINGERPRINT",
            "root_hashed_object": "shared_market_state_pack.items",
            "source_artifact": STEP5_PATH,
            "source_commit": "8e57652d002b6791d96328fbaa5c8273fdfd4e62",
            "provider_lineage": evidence["provider_origins"],
            "cutoff_source": "shared_market_state_pack.forecast_cutoff",
            "information_item_source": "historical Phase 9 repaired derived Pack items",
            "pack_item_count": len(pack["items"]),
            "canonicalization": {
                "key_order": "lexicographic sort_keys=True",
                "list_order": "stored item order",
                "null_boolean_number": "Python json default representation",
                "timestamps": "stored strings unchanged",
                "unicode": "ensure_ascii=True",
                "separators": ", and :",
                "encoding": "UTF-8",
                "hash_algorithm": "SHA-256",
            },
            "independent_reproduction": evidence["fingerprint_matches_frozen"],
        },
        "attention_contract_resolution.json": {
            "historical_state": bridge["provider_episode_selection"],
            "historical_source": f"{STEP5_PATH}:provider_episode_selection",
            "historical_meaning": "Historical adapter result from member attention classifications; it is not an accepted selected-Attention object.",
            "native_required_state": ["SELECTED", "SELECTED_FOR_INFORMATION_REQUESTS"],
            "native_source": "automation/presignal_v21_pack_capability_v1.py:_validate_selected_attention",
            "equivalence_classification": "SCIENTIFICALLY_DIFFERENT",
            "conversion_permitted": False,
        },
        "cutoff_contract_resolution.json": {
            "historical_0650z": {
                "field": "shared_market_state_pack.forecast_cutoff",
                "source": STEP5_PATH,
                "value": HISTORICAL_CUTOFF,
                "timezone": "UTC",
                "meaning": "historical session forecast issuance and Pack eligibility cutoff, before the session events",
            },
            "episode_1100z": {
                "field": "forecast_cutoff_ts",
                "source": EPISODE_PATH,
                "value": EPISODE_CUTOFF,
                "timezone": "UTC",
                "meaning": "canonical unselected Episode release-time upper availability boundary",
            },
            "same_scientific_boundary": False,
            "mapping_defect_found": True,
            "mapping_defect": "The legacy event-path adapter maps session.forecast_cutoff into its input rather than the canonical Episode forecast_cutoff_ts; neither frozen source value is changed.",
        },
        "request_lineage_resolution.json": {
            "historical_aggregation_rule": "session-level shared union of captured Requests from Anthropic, Gemini, and OpenAI; deduplicated by normalized information key for Pack construction",
            "historical_source": "e5a0ff288eb1f6fc228936cb1c693ed2bb2ab80f:automation/run_phase9_historical_square_one_replay_v0.py",
            "native_prospective_aggregation_rule": "shared union of canonical Requests from all accepted selected providers supplied to Pack assembly",
            "native_source": "automation/presignal_v21_pack_capability_v1.py:assemble_canonical_pack_e",
            "rules_match": True,
            "adapter_sufficient": True,
            "one_provider_fixture_sufficient": False,
        },
        "acquisition_evidence_resolution.json": {
            "classification": "DERIVED_PACK_ITEMS_ONLY",
            "source_level_records_present": False,
            "lossless_native_adaptation_possible": False,
            "item_count": len(items),
            "supplied_item_count": evidence["supplied_item_count"],
            "unavailable_or_excluded_item_count": evidence["excluded_or_unavailable_item_count"],
            "field_availability": evidence["source_record_fields"],
            "missing_fields": [
                "source URL or immutable source key",
                "retrieval/acquisition timestamp",
                "raw acquired content",
                "normalized acquired content independent of final Pack item",
            ],
            "rule": "Final Pack text and derived values are not reverse-engineered into authoritative source-level acquisition records.",
        },
        "final_fixture_contract_decision.json": {
            "decision": "HISTORICAL_AND_PROSPECTIVE_PROOF_CONTRACTS_MUST_BE_SEPARATED",
            "reason": "The f0 fingerprint reproducibly covers a historical three-provider shared Pack item list, while the available canonical Episode is unselected at a distinct release boundary and no source-level acquisition record set exists.",
            "proof_1_historical_scientific_compute_equivalence": "historical canonical Request/derived-information envelope -> migrated pure compute -> historical shared Pack items -> f0 fingerprint",
            "proof_2_native_prospective_contract_validation": "canonical Event Episode + accepted selected Attention + complete shared Requests + supplied source-level acquisition records + forecast cutoff -> deterministic canonical Pack E; validate invariants, lineage, cutoff safety, isolation, and determinism without assigning f0.",
            "proof_method_correction_not_scientific_redesign": True,
            "next_move_authorization": "No Move 4 rerun is authorized by this report; freeze a native fixture only from future authorized prospective evidence.",
        },
    }
