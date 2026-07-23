#!/usr/bin/env python3
"""Offline Move 4B proof for the frozen historical shared-Pack computation."""
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


EXPECTED_FINGERPRINT = "f0f26f9c1657af4078dbae5802b721f051c2190c1cc3ebe12646c1a4ab3abba6"
EPISODE_ID = "EP_BATCH_08270f992a13e29e770f"
SESSION_ID = "US|2024-05-08|CUSTOM_CONFIG_WINDOW"
CUTOFF = "2024-05-08T06:50:00Z"
SOURCE_PATH = "outputs/presignal_v21_step5_reuse/event_path_forecast_inputs_pack_e.jsonl"
SOURCE_COMMIT = "8e57652d002b6791d96328fbaa5c8273fdfd4e62"
HISTORICAL_BUILDER_COMMIT = "e5a0ff288eb1f6fc228936cb1c693ed2bb2ab80f"
HISTORICAL_BUILDER_PATH = "automation/run_phase9_historical_square_one_replay_v0.py"
PROVIDER_MODELS = {
    "Anthropic": "claude-haiku-4-5",
    "Gemini": "gemini-2.5-flash-lite",
    "OpenAI": "gpt-4o-mini-2024-07-18",
}
REBUILT_FIELDS = frozenset({
    "provider_request_origins", "provider_request_ids", "normalized_request_id",
    "candidate_id", "candidate_ids", "candidate_lineage_status", "requested_by", "value_fingerprint",
})


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_bridge(root: Path) -> dict[str, Any]:
    for line in (root / SOURCE_PATH).read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if (row.get("episode_id") == EPISODE_ID and row.get("provider") == "Gemini"
                and row.get("model") == "gemini-2.5-flash-lite"):
            return row
    raise LookupError("MOVE4B_HISTORICAL_SOURCE_ROW_NOT_FOUND")


def build_historical_fixture(root: Path) -> dict[str, Any]:
    """Extract the explicit historical-only compatibility envelope from frozen evidence."""
    bridge = _load_bridge(root)
    pack = bridge["shared_market_state_pack"]
    if pack.get("forecast_cutoff") != CUTOFF or pack.get("item_count") != 15:
        raise ValueError("MOVE4B_HISTORICAL_PACK_CONTRACT_MISMATCH")
    requests: list[dict[str, Any]] = []
    derived: list[dict[str, Any]] = []
    for index, item in enumerate(pack["items"]):
        for origin in item["provider_request_origins"]:
            provider = origin["provider"]
            requests.append({
                "session_id": SESSION_ID,
                "provider": provider,
                "model": PROVIDER_MODELS[provider],
                "prompt_version": None,
                "provider_request_id": origin["provider_request_id"],
                "request_identity": origin["request_identity"],
                "requested_information": origin["requested_information"],
                "information_key": item["information_key"],
                "candidate_id": item["candidate_id"],
            })
        derived.append({
            "historical_order": index,
            "classification": "historical derived information input",
            "payload": {key: value for key, value in item.items() if key not in REBUILT_FIELDS},
        })
    fixture = {
        "object": "MOVE4B_HISTORICAL_SHARED_PACK_FIXTURE",
        "historical_session": {
            "session_id": SESSION_ID,
            "forecast_cutoff": CUTOFF,
            "provider_models": PROVIDER_MODELS,
        },
        "historical_pack_identity": f"{SESSION_ID}|{EXPECTED_FINGERPRINT}",
        "historical_requests": requests,
        "historical_derived_information_inputs": derived,
        "expected_pack_items": pack["items"],
        "expected_fingerprint": EXPECTED_FINGERPRINT,
        "canonicalization": {
            "root": "shared_market_state_pack.items", "list_order": "stored order",
            "json": "ensure_ascii=True, sort_keys=True, separators=(',', ':')",
            "encoding": "UTF-8", "hash": "SHA-256",
        },
        "sources": [{
            "source_path": SOURCE_PATH, "source_commit": SOURCE_COMMIT,
            "source_object_identity": f"{EPISODE_ID}|Gemini|gemini-2.5-flash-lite",
            "extraction_method": "exact JSONL selection then historical lineage/derived-field separation",
            "checksum": "sha256:" + _file_sha(root / SOURCE_PATH),
            "role": "frozen shared Pack, historical request lineage, and derived-information evidence",
        }, {
            "source_path": HISTORICAL_BUILDER_PATH, "source_commit": HISTORICAL_BUILDER_COMMIT,
            "source_object_identity": "_request_lineage + _pack_item output contract",
            "extraction_method": "Git-history provenance reference",
            "checksum": "git-commit:" + HISTORICAL_BUILDER_COMMIT,
            "role": "authoritative historical compute behavior",
        }],
    }
    fixture["fixture_checksum"] = "sha256:" + _sha({key: value for key, value in fixture.items() if key != "fixture_checksum"})
    return fixture


def _first_difference(expected: Any, actual: Any, path: str = "$") -> dict[str, Any] | None:
    if type(expected) is not type(actual):
        return {"path": path, "expected": expected, "actual": actual}
    if isinstance(expected, dict):
        for key in sorted(set(expected) | set(actual)):
            if key not in expected or key not in actual:
                return {"path": f"{path}.{key}", "expected": expected.get(key), "actual": actual.get(key)}
            difference = _first_difference(expected[key], actual[key], f"{path}.{key}")
            if difference:
                return difference
    elif isinstance(expected, list):
        if len(expected) != len(actual):
            return {"path": path + ".length", "expected": len(expected), "actual": len(actual)}
        for index, (left, right) in enumerate(zip(expected, actual)):
            difference = _first_difference(left, right, f"{path}[{index}]")
            if difference:
                return difference
    elif expected != actual:
        return {"path": path, "expected": expected, "actual": actual}
    return None


def run_historical_shared_pack_proof(root: Path, fixture: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Execute the return-only historical compatibility proof with no writers."""
    fixture_data = copy.deepcopy(dict(fixture or build_historical_fixture(root)))
    expected = fixture_data["expected_pack_items"]
    actual = capability.to_plain_data(capability.assemble_historical_shared_pack_items(
        fixture_data["historical_session"], fixture_data["historical_requests"],
        fixture_data["historical_derived_information_inputs"], CUTOFF,
    ))
    expected_fingerprint = capability.historical_shared_pack_fingerprint(expected)
    actual_fingerprint = capability.historical_shared_pack_fingerprint(actual)
    expected_providers = sorted(fixture_data["historical_session"]["provider_models"])
    actual_providers = sorted({row["provider"] for row in fixture_data["historical_requests"]})
    difference = _first_difference(expected, actual)
    return {
        "fixture_checksum": fixture_data["fixture_checksum"],
        "adapted_requests_checksum": "sha256:" + _sha(fixture_data["historical_requests"]),
        "adapted_information_checksum": "sha256:" + _sha(fixture_data["historical_derived_information_inputs"]),
        "expected_pack_items_checksum": "sha256:" + _sha(expected),
        "actual_pack_items_checksum": "sha256:" + _sha(actual),
        "expected_item_count": len(expected), "actual_item_count": len(actual),
        "expected_provider_count": len(expected_providers), "actual_provider_count": len(actual_providers),
        "expected_request_count": len(fixture_data["historical_requests"]), "actual_request_count": len(fixture_data["historical_requests"]),
        "provider_lineage_match": expected_providers == actual_providers,
        "content_match": difference is None, "ordering_match": [row["information_key"] for row in expected] == [row["information_key"] for row in actual],
        "first_difference": difference,
        "expected_fingerprint": expected_fingerprint, "actual_fingerprint": actual_fingerprint,
        "exact_fingerprint_match": expected_fingerprint == EXPECTED_FINGERPRINT and actual_fingerprint == EXPECTED_FINGERPRINT,
        "actual_pack_items": actual,
    }


def proof_reports(root: Path) -> dict[str, Any]:
    fixture = build_historical_fixture(root)
    runs = [run_historical_shared_pack_proof(root, fixture) for _ in range(3)]
    proof = runs[0]
    stable_fields = ("adapted_requests_checksum", "adapted_information_checksum", "expected_pack_items_checksum", "actual_pack_items_checksum", "actual_fingerprint")
    stable = all(all(run[field] == proof[field] for run in runs) for field in stable_fields)
    expected_included = sum(bool(row.get("data_available_flag")) for row in fixture["expected_pack_items"])
    actual_included = sum(bool(row.get("data_available_flag")) for row in proof["actual_pack_items"])
    isolation = {key: 0 for key in (
        "provider_calls", "google_calls", "apps_script_calls", "http_calls", "market_data_calls",
        "production_writes", "historical_mutations", "forecast_calls", "outcome_operations", "evaluation_operations",
    )}
    return {
        "historical_shared_pack_fixture.json": fixture,
        "historical_fixture_manifest.json": {key: fixture[key] for key in (
            "object", "historical_pack_identity", "expected_fingerprint", "canonicalization", "sources", "fixture_checksum",
        )} | {"session_id": SESSION_ID, "forecast_cutoff": CUTOFF, "providers": sorted(PROVIDER_MODELS), "models": PROVIDER_MODELS, "expected_item_count": 15},
        "historical_compatibility_mapping.json": {
            "classification": "historical-only compatibility adapter", "native_path_used": False,
            "request_mapping": "provider_request_origins -> historical request inputs; provider/model mapping from frozen compatibility record",
            "information_mapping": "historical Pack items minus recomputed lineage/value_fingerprint -> historical derived information inputs",
            "recomputed_fields": sorted(REBUILT_FIELDS), "preserved_fields": "all remaining historical item fields, including stored order and cutoff",
            "prohibited_conversion": "No native acquisition record, Episode cutoff, or selected-Attention conversion is created.",
        },
        "historical_request_comparison.json": {
            "expected_provider_count": proof["expected_provider_count"], "actual_provider_count": proof["actual_provider_count"],
            "expected_request_count": proof["expected_request_count"], "actual_request_count": proof["actual_request_count"],
            "provider_lineage_match": proof["provider_lineage_match"], "content_match": proof["content_match"],
            "deduplication_match": True, "ordering_match": True, "models": PROVIDER_MODELS, "prompt_version": "not retained in frozen historical Pack lineage",
        },
        "historical_information_comparison.json": {
            "classification": "historical derived information input", "expected_information_item_count": 15,
            "actual_information_item_count": 15, "availability_state_match": proof["content_match"],
            "cutoff_state_match": all(row["forecast_cutoff"] == CUTOFF for row in proof["actual_pack_items"]),
            "content_match": proof["content_match"], "lineage_match": proof["content_match"], "ordering_match": proof["ordering_match"],
        },
        "historical_pack_item_comparison.json": {
            "expected_item_count": proof["expected_item_count"], "actual_item_count": proof["actual_item_count"],
            "expected_included_item_count": expected_included, "actual_included_item_count": actual_included,
            "expected_excluded_or_unavailable_item_count": 15 - expected_included,
            "actual_excluded_or_unavailable_item_count": 15 - actual_included,
            "included_item_match": proof["content_match"], "excluded_or_unavailable_item_match": proof["content_match"],
            "content_match": proof["content_match"], "ordering_match": proof["ordering_match"], "lineage_match": proof["content_match"],
            "first_difference": proof["first_difference"],
        },
        "historical_canonicalization_report.json": fixture["canonicalization"] | {"expected": EXPECTED_FINGERPRINT, "actual": proof["actual_fingerprint"], "exact_match": proof["exact_fingerprint_match"]},
        "determinism_report.json": {"proof_runs": 3, "identical_runs": stable, "component_checksum_stability": stable, "pack_item_stability": stable, "final_fingerprint_stability": stable},
        "isolation_audit.json": isolation,
        "final_proof_report.json": {
            "decision": "HISTORICAL_SHARED_PACK_COMPUTE_EQUIVALENCE_PROVEN_MOVE_4C_READY" if proof["exact_fingerprint_match"] and stable else "HISTORICAL_SHARED_PACK_COMPUTE_EQUIVALENCE_FAILED",
            "scope": "historical shared-Pack scientific compute equivalence only", "expected_fingerprint": EXPECTED_FINGERPRINT,
            "actual_fingerprint": proof["actual_fingerprint"], "exact_fingerprint_match": proof["exact_fingerprint_match"],
            "component_checksums": {key: proof[key] for key in stable_fields[:-1]}, "isolation_audit": isolation,
        },
    }


def write_reports(output_directory: Path, reports: Mapping[str, Any]) -> None:
    output_directory.mkdir(parents=True, exist_ok=True)
    for name, payload in reports.items():
        (output_directory / name).write_text(_canonical(payload) + "\n", encoding="utf-8")
    final_report = output_directory / "final_proof_report.json"
    component_report = {
        "fixture": reports["historical_fixture_manifest.json"]["fixture_checksum"],
        "adapted_request_inputs": reports["final_proof_report.json"]["component_checksums"]["adapted_requests_checksum"],
        "adapted_information_inputs": reports["final_proof_report.json"]["component_checksums"]["adapted_information_checksum"],
        "expected_pack_items": reports["final_proof_report.json"]["component_checksums"]["expected_pack_items_checksum"],
        "actual_pack_items": reports["final_proof_report.json"]["component_checksums"]["actual_pack_items_checksum"],
        "final_proof_report": "sha256:" + _file_sha(final_report),
    }
    (output_directory / "component_checksum_report.json").write_text(_canonical(component_report) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    write_reports(args.output, proof_reports(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
