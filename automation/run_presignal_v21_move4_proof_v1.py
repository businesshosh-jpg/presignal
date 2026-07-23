#!/usr/bin/env python3
"""Offline Move 4 fixture admissibility and canonicalization proof.

This diagnostic is deliberately return-only.  It reads frozen local evidence,
performs no Route B computation when the fixture is not admissible, and never
contacts a provider, Google, Apps Script, HTTP endpoint, or writer.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from automation import presignal_v21_event_path_contract_v1 as episode_contract


EXPECTED_FINGERPRINT = "f0f26f9c1657af4078dbae5802b721f051c2190c1cc3ebe12646c1a4ab3abba6"
EPISODE_ID = "EP_BATCH_08270f992a13e29e770f"
EPISODE_SOURCE = "outputs/presignal_v21_episode_builder/episode_rows.jsonl"
PACK_SOURCE = "outputs/presignal_v21_step5_reuse/event_path_forecast_inputs_pack_e.jsonl"


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _jsonl_identity(path: Path, identity: str) -> Mapping[str, Any]:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            if row.get("episode_id") == identity:
                return row
    raise ValueError("AUTHORITATIVE_OBJECT_NOT_FOUND:" + identity)


def run_offline_move4_fixture_admissibility(repo_root: Path) -> dict[str, Any]:
    """Return deterministic Move 4 evidence; never writes or dispatches work."""
    episode_path, pack_path = repo_root / EPISODE_SOURCE, repo_root / PACK_SOURCE
    episode = _jsonl_identity(episode_path, EPISODE_ID)
    input_row = _jsonl_identity(pack_path, EPISODE_ID)
    pack = input_row["shared_market_state_pack"]
    historical_hash = sha256(pack["items"])
    episode_contract.validate_episode(episode)
    provider_origins = sorted({
        origin["provider"] for item in pack["items"] for origin in item.get("provider_request_origins", [])
    })
    mismatch = episode["forecast_cutoff_ts"] != input_row["forecast_cutoff_ts"]
    return {
        "object": "MOVE4_OFFLINE_PROOF_RESULT",
        "status": "FIXTURE_INPUT_MISMATCH" if mismatch else "FIXTURE_ADMISSIBLE",
        "episode_id": EPISODE_ID,
        "expected_fingerprint": EXPECTED_FINGERPRINT,
        "historical_items_fingerprint": historical_hash,
        "historical_fingerprint_matches_expected": historical_hash == EXPECTED_FINGERPRINT,
        "canonicalization": {
            "included_root_object": "shared_market_state_pack.items",
            "included_fields": "all item fields",
            "excluded_non_scientific_fields": "outer pack envelope only",
            "field_ordering_rule": "JSON object keys sorted lexicographically",
            "list_ordering_rule": "stored item order preserved",
            "null_handling": "JSON null",
            "boolean_handling": "JSON true/false",
            "number_formatting": "Python json.dumps default numeric representation",
            "timestamp_formatting": "stored strings unchanged",
            "unicode_handling": "ensure_ascii=True",
            "json_separators": ", and : without whitespace",
            "encoding": "UTF-8",
            "hash_algorithm": "SHA-256 lowercase hex",
        },
        "fixture_components": {
            "episode": {"source_path": EPISODE_SOURCE, "source_file_sha256": file_sha256(episode_path), "forecast_cutoff_ts": episode["forecast_cutoff_ts"], "episode_contract_valid": True},
            "pack_input": {"source_path": PACK_SOURCE, "source_file_sha256": file_sha256(pack_path), "forecast_cutoff_ts": input_row["forecast_cutoff_ts"], "pack_item_count": len(pack["items"]), "provider_origins": provider_origins, "provider_episode_selection": input_row.get("provider_episode_selection", "")},
        },
        "first_divergence": {
            "classification": "FIXTURE_INPUT_MISMATCH" if mismatch else "NONE",
            "object": "forecast_cutoff_ts",
            "expected_value": input_row["forecast_cutoff_ts"],
            "actual_value": episode["forecast_cutoff_ts"],
            "expected_source": PACK_SOURCE + ": event-path Pack E input row",
            "actual_source": EPISODE_SOURCE + ": canonical Episode row",
            "scientific_meaning_differs": mismatch,
            "representational_only": False,
            "recommended_minimal_action": "Provide an authoritative canonical Episode and complete shared Request/acquisition fixture at the same frozen cutoff; do not alter either existing artifact.",
        },
        "external_access_counts": {"provider_calls": 0, "google_calls": 0, "apps_script_calls": 0, "http_calls": 0, "market_data_calls": 0, "production_writes": 0, "historical_mutations": 0, "forecast_calls": 0, "outcome_operations": 0, "evaluation_operations": 0},
    }
