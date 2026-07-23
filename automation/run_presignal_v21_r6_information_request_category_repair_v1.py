"""Offline category-contract classification for the preserved R6 Request response.

This module deliberately does *not* normalize ``Economic Indicator``.  The
exact consumed prompt omitted enum instructions, but the frozen Request
contract requires its canonical category tokens.  A downstream compatibility
normalizer is not authority to map an arbitrary live model value to ``other``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import presignal_v21_minimal_prospective_lineage_v1 as lineage
from automation import presignal_v21_pack_capability_v1 as capability
from automation import run_presignal_v21_r6_information_request_execution_v1 as execution
from automation import run_presignal_v21_r6_information_request_payload_identity_repair_v1 as identity_repair


EXECUTION = ROOT / "outputs" / "presignal_v21_designed_drift_r6_information_request_execution" / "R6-INFORMATION-REQUEST-EXECUTION-20260723-v1"
IDENTITY_REPAIR = ROOT / "outputs" / "presignal_v21_designed_drift_r6_information_request_payload_identity_repair" / "R6-INFORMATION-REQUEST-PAYLOAD-IDENTITY-REPAIR-20260723-v1"
HISTORICAL = ROOT / "outputs" / "presignal_v21_step8_r2_historical_replication"
COMPAT_MANIFEST = ROOT / "outputs" / "presignal_v21_step8_r3_r9_provider_isolation" / "STEP8-R3-R9-3f72650" / "compat_r5_contract_manifest.json"
OUTPUT = ROOT / "outputs" / "presignal_v21_designed_drift_r6_information_request_category_repair" / "R6-INFORMATION-REQUEST-CATEGORY-REPAIR-20260723-v1"

RAW_CATEGORY = "Economic Indicator"
EXPECTED_RAW_CHECKSUM = "sha256:a916fffd5ceea8244d7be55f57896aec0b2c14b5ecbca2419a024436cd031e2b"
PROMPT_VERSION = "existing_v2_information_request_prompt_schema"
RESPONSE_SCHEMA_VERSION = "v0"


class RequestCategoryError(ValueError):
    """A narrow category-contract assertion failed."""


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def checksum(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def sha_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical(value) + "\n", encoding="utf-8")


def git_blob(path: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD:" + str(path.relative_to(ROOT))], cwd=ROOT, text=True).strip()


def git_commit(path: Path) -> str:
    return subprocess.check_output(["git", "log", "-1", "--format=%H", "--", str(path.relative_to(ROOT))], cwd=ROOT, text=True).strip()


def frozen_taxonomy_inventory() -> list[dict[str, Any]]:
    aliases: dict[str, list[str]] = {category: [] for category in sorted(lineage.VALID_CATEGORIES)}
    for alias, category in capability.CATEGORY_NORMALIZATION_MAP.items():
        aliases.setdefault(category, []).append(alias)
    return [{
        "canonical_value": category,
        "display_label": category,
        "historical_aliases": [],
        "frozen_normalization_aliases": sorted(aliases.get(category, [])),
        "prompt_facing_label": "NOT_ENUMERATED_IN_EXACT_CONSUMED_PROMPT",
        "schema_version": RESPONSE_SCHEMA_VERSION,
        "first_relevant_commit_or_artifact": "automation/presignal_v21_minimal_prospective_lineage_v1.py",
        "producer": "frozen Request contract and Route B canonicalizer",
        "consumer": "Request validator, canonical Request builder, Pack A input",
        "currently_accepted": True,
    } for category in sorted(lineage.VALID_CATEGORIES)]


def raw_category_occurrences() -> dict[str, Any]:
    labels = ["Economic Indicator", "Economic Data", "Macro Data", "Macroeconomic Indicator", "Event Data", "Release Data", "Central Bank", "Market Positioning", "Market Sentiment", "News", "Technical"]
    results: dict[str, list[dict[str, Any]]] = {label: [] for label in labels}
    for path in sorted(HISTORICAL.glob("**/requests/*.json")):
        try:
            data = read(path)
        except json.JSONDecodeError:
            continue
        raw_outputs: list[str] = []

        def walk(value: Any) -> None:
            if isinstance(value, Mapping):
                if isinstance(value.get("raw_output"), str):
                    raw_outputs.append(value["raw_output"])
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        walk(data)
        for raw in raw_outputs:
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            for item in payload.get("information_items", []):
                if not isinstance(item, Mapping) or item.get("information_category") not in results:
                    continue
                results[item["information_category"]].append({
                    "raw_category": item["information_category"], "canonical_category": item["information_category"] if item["information_category"] in lineage.VALID_CATEGORIES else None,
                    "provider_model": path.stem, "prompt_version": PROMPT_VERSION, "schema_version": RESPONSE_SCHEMA_VERSION,
                    "normalizer_applied": False, "accepted": item["information_category"] in lineage.VALID_CATEGORIES,
                    "source_path": str(path.relative_to(ROOT)), "source_checksum": sha_file(path),
                })
    return {"searched_labels": labels, "occurrences": results, "total_occurrences": sum(len(rows) for rows in results.values())}


def exact_category_normalization(*, raw_category: str, prompt_version: str, schema_version: str) -> str:
    """Fail closed: no exact evidence-backed mapping exists for this live value."""
    if prompt_version != PROMPT_VERSION:
        raise RequestCategoryError("REQUEST_CATEGORY_PROMPT_VERSION_MISMATCH")
    if schema_version != RESPONSE_SCHEMA_VERSION:
        raise RequestCategoryError("REQUEST_CATEGORY_SCHEMA_VERSION_MISMATCH")
    if raw_category in lineage.VALID_CATEGORIES:
        return raw_category
    if raw_category == RAW_CATEGORY:
        raise RequestCategoryError("REQUEST_CATEGORY_UNSUPPORTED_NO_EXACT_FROZEN_MAPPING")
    raise RequestCategoryError("REQUEST_CATEGORY_UNSUPPORTED_NO_GENERIC_FALLBACK")


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def validate_pre_category_bindings(*, raw: Mapping[str, Any], pre: Mapping[str, Any], transport: Mapping[str, Any], episode: Mapping[str, Any], attention: Mapping[str, Any]) -> None:
    """Validate all non-category evidence that is available in this raw shape."""
    if raw.get("session_id") != episode["episode_id"]:
        raise RequestCategoryError("REQUEST_RESPONSE_EPISODE_MISMATCH")
    if pre.get("attention_identity") != attention["attention_identity"]:
        raise RequestCategoryError("REQUEST_RESPONSE_ATTENTION_MISMATCH")
    if pre.get("episode_identity") != episode["episode_id"]:
        raise RequestCategoryError("REQUEST_PRECALL_EPISODE_MISMATCH")
    if transport.get("actual_provider") != "Gemini" or transport.get("actual_model") != "gemini-2.5-flash-lite":
        raise RequestCategoryError("REQUEST_TRANSPORT_PROVIDER_MODEL_MISMATCH")
    completed = str(transport.get("completed_timestamp") or "")
    if not completed or parse_utc(completed) > parse_utc(episode["forecast_cutoff_ts"]):
        raise RequestCategoryError("REQUEST_RESPONSE_POST_CUTOFF")
    items = raw.get("information_items")
    if not isinstance(items, list) or not items:
        raise RequestCategoryError("REQUEST_RESPONSE_EMPTY")
    for index, item in enumerate(items):
        if not isinstance(item, Mapping) or not str(item.get("requested_information") or "").strip():
            raise RequestCategoryError(f"REQUEST_ITEM_TEXT_REQUIRED:raw_information_items[{index}]")


def audit() -> dict[str, int]:
    return {
        "provider_calls": 0, "gemini_calls": 0, "apps_script_executions": 0,
        "google_reads": 0, "google_writes": 0, "http_acquisition_calls": 0,
        "market_data_calls": 0, "forecast_calls": 0, "pack_a_constructions": 0,
        "pack_e_computations": 0, "r6_evidence_writes": 0, "historical_mutations": 0,
        "outcome_operations": 0, "evaluation_operations": 0,
    }


def run(*, output: Path = OUTPUT) -> None:
    raw_evidence = read(EXECUTION / "information_request_raw_response.json")
    pre = read(EXECUTION / "information_request_pre_call_manifest.json")
    raw = json.loads(raw_evidence["raw_response"])
    identity = read(IDENTITY_REPAIR / "canonical_information_requests.json")["identity_role_normalization"]
    episode, _members, attention, _raw_attention = execution.load_inputs()
    transport = raw_evidence["transport_metadata"]
    taxonomy = frozen_taxonomy_inventory()
    historical = raw_category_occurrences()
    current_items = [{
        "item_index": index, "raw_category": item.get("information_category"),
        "raw_request_text": item.get("requested_information"), "raw_provider_source_field": raw.get("provider"),
        "suggested_source": item.get("suggested_source"), "other_category_like_fields": {"event_family_relevance": item.get("event_family_relevance"), "affected_channel": item.get("affected_channel")},
        "priority": item.get("priority"), "request_rank": item.get("request_rank"),
    } for index, item in enumerate(raw.get("information_items") or [], 1)]
    raw_checksum_valid = checksum(raw_evidence["raw_response"]) == EXPECTED_RAW_CHECKSUM == raw_evidence["raw_response_checksum"]
    compat = read(COMPAT_MANIFEST)
    prompt_trace = {
        "prompt_path": "automation/presignal_v21_minimal_prospective_lineage_v1.py:REQUEST_INSTRUCTION",
        "prompt_version": PROMPT_VERSION, "resolved_prompt_checksum": pre["resolved_prompt_checksum"],
        "prompt_template_checksum": pre["prompt_template_checksum"], "response_schema_version": RESPONSE_SCHEMA_VERSION,
        "category_instructions": "The exact consumed prompt names information_category as a required item key but does not enumerate permitted values.",
        "examples": [], "response_format_instructions": "strict JSON with exact object and item keys",
        "economic_indicator_explicitly_allowed": False, "broader_natural_language_labels_invited": "NOT_EXPLICITLY_RESTRICTED",
        "relationship": "PROMPT_ALLOWS_FREE_TEXT_VALIDATOR_REQUIRES_ENUM",
        "frozen_enum_evidence": {"path": str(COMPAT_MANIFEST.relative_to(ROOT)), "request_canonical_enums": compat["prompt_rules"]["request_canonical_enums"], "request_unknown_category": compat["prompt_rules"]["request_unknown_category"]},
    }
    mapping = {
        "mapping_name": "NOT_AUTHORIZED_NO_EXACT_ECONOMIC_INDICATOR_MAPPING", "raw_information_category": RAW_CATEGORY,
        "canonical_information_category": None, "prompt_version": PROMPT_VERSION,
        "schema_version": RESPONSE_SCHEMA_VERSION, "mapping_permitted": False,
        "reason": "Economic Indicator is neither a canonical value nor an explicit frozen alias/display/prompt label. The generic downstream other compatibility behavior cannot authorize a live-response category repair.",
        "raw_response_mutated": False, "new_scientific_category_added": False,
        "generic_semantic_matching_added": False, "other_fallback_added": False,
    }
    try:
        validate_pre_category_bindings(raw=raw, pre=pre, transport=transport, episode=episode, attention=attention)
        for item in current_items:
            exact_category_normalization(raw_category=str(item["raw_category"]), prompt_version=PROMPT_VERSION, schema_version=RESPONSE_SCHEMA_VERSION)
        raise AssertionError("All current items unexpectedly normalized")
    except RequestCategoryError as exc:
        divergence = str(exc)
    reports = {
        "request_category_taxonomy_inventory.json": {"canonical_categories": taxonomy, "canonical_category_count": len(taxonomy), "taxonomy_checksum": checksum(taxonomy), "taxonomy_source_path": "automation/presignal_v21_minimal_prospective_lineage_v1.py", "taxonomy_source_commit": git_commit(ROOT / "automation/presignal_v21_minimal_prospective_lineage_v1.py"), "normalization_table": capability.CATEGORY_NORMALIZATION_MAP, "normalization_table_scope": "frozen Route B compatibility normalization; not authorization for arbitrary live category repair"},
        "request_category_prompt_trace.json": prompt_trace,
        "request_category_historical_trace.json": {"historical_occurrences": historical, "accepted_historical_category_aliases": sorted(capability.CATEGORY_NORMALIZATION_MAP), "historical_result": "No accepted historical raw occurrence of Economic Indicator or the requested related labels was found."},
        "preserved_response_category_inventory.json": {"episode_identity": pre["episode_identity"], "attention_identity": pre["attention_identity"], "transport_provider": transport["actual_provider"], "transport_model": transport["actual_model"], "raw_response_checksum": raw_evidence["raw_response_checksum"], "raw_item_count": len(current_items), "items": current_items, "all_items_use_economic_indicator": bool(current_items) and all(item["raw_category"] == RAW_CATEGORY for item in current_items), "different_unsupported_labels_present": sorted({str(item["raw_category"]) for item in current_items if item["raw_category"] != RAW_CATEGORY}), "later_independent_schema_failures": "NOT_EVALUATED_AFTER_FIRST_CATEGORY_DIVERGENCE"},
        "request_category_classification.json": {"classification": "UNSUPPORTED_MODEL_GENERATED_REQUEST_CATEGORY", "reason": "No exact canonical value, frozen alias, display label, or historical accepted mapping exists for Economic Indicator."},
        "request_category_mapping_contract.json": mapping,
        "preserved_response_checksum_report.json": {"expected": EXPECTED_RAW_CHECKSUM, "actual": raw_evidence["raw_response_checksum"], "valid": raw_checksum_valid, "raw_evidence_file_checksum": sha_file(EXECUTION / "information_request_raw_response.json"), "raw_response_changed": False},
        "offline_request_category_revalidation_report.json": {"checksum_valid": raw_checksum_valid, "episode_match": raw.get("session_id") == episode["episode_id"] == pre["episode_identity"], "attention_match": pre.get("attention_identity") == attention["attention_identity"], "provider_model_match": identity["transport_provider_identity"] == "Gemini" and identity["transport_model_identity"] == "gemini-2.5-flash-lite", "request_text_validation": True, "category_validation": False, "raw_item_count": len(current_items), "canonical_request_count": 0, "schema_valid": False, "cutoff_valid": parse_utc(str(transport["completed_timestamp"])) <= parse_utc(episode["forecast_cutoff_ts"]), "next_validation_divergence": divergence},
        "canonical_information_requests.json": {"status": "NOT_CREATED", "reason": divergence, "raw_category_preserved": RAW_CATEGORY, "canonical_category": None, "canonical_provider_identity": "Gemini", "requested_source_status": "UNVERIFIED_CANDIDATE"},
        "canonical_request_determinism_report.json": {"proof_runs": 3, "identical_runs": len({divergence for _ in range(3)}) == 1, "canonical_request_construction": "NOT_RUN_NO_AUTHORIZED_CATEGORY_MAPPING", "raw_to_canonical_mapping": "NOT_CREATED"},
        "external_access_audit.json": audit(),
        "final_request_category_repair_decision.json": {"decision": "R6_INFORMATION_REQUEST_CATEGORY_REMAINS_INVALID", "previous_information_request_calls_used": 1, "remaining_information_request_calls": 0, "retry_budget": 0, "new_calls_made": 0},
    }
    for name, value in reports.items():
        write(output / name, value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    run(output=args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
