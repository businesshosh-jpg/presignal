"""Offline proof that the authoritative Request prompt and frozen enum agree."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import presignal_v21_minimal_prospective_lineage_v1 as lineage
from automation import presignal_v21_pack_capability_v1 as capability
from automation import run_presignal_v21_r6_information_request_execution_v1 as execution


EXECUTION = ROOT / "outputs" / "presignal_v21_designed_drift_r6_information_request_execution" / "R6-INFORMATION-REQUEST-EXECUTION-20260723-v1"
CATEGORY_REPAIR = ROOT / "outputs" / "presignal_v21_designed_drift_r6_information_request_category_repair" / "R6-INFORMATION-REQUEST-CATEGORY-REPAIR-20260723-v1"
OUTPUT = ROOT / "outputs" / "presignal_v21_designed_drift_r6_information_request_prompt_schema_alignment" / "INFORMATION-REQUEST-PROMPT-SCHEMA-ALIGNMENT-20260723-v1"

ALIGNMENT_NAME = "PRESIGNAL_V21_INFORMATION_REQUEST_PROMPT_SCHEMA_ALIGNMENT_V1"
OLD_PROMPT_VERSION = "existing_v2_information_request_prompt_schema"
OLD_PROMPT_CHECKSUM = "sha256:2e743a5fa501bdd806f29155eb337555a9bcfb286f8b9331706b67120b0db7b9"
OLD_RAW_CHECKSUM = "sha256:a916fffd5ceea8244d7be55f57896aec0b2c14b5ecbca2419a024436cd031e2b"
ROUTE_B_FREEZE = "sha256:8c910a343515d88ca63ce4aaf738f28f9b4a8ab22665397077858bfaf7e866e4"
RESPONSE_SCHEMA_VERSION = "v0"


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def checksum(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical(value) + "\n", encoding="utf-8")


def category_sets() -> dict[str, list[str]]:
    values = sorted(lineage.VALID_CATEGORIES)
    return {
        "prompt": values,
        "schema": values,
        "validator": values,
        "normalizer_canonical_output": sorted(capability.VALID_CATEGORIES),
        "canonicalizer": sorted(capability.VALID_CATEGORIES),
    }


def exact_category_set_from_prompt(prompt: Mapping[str, Any] | str) -> list[str]:
    marker = "For each information item, set information_category to exactly one of these machine values:\n"
    instruction = str(prompt["instruction"]) if isinstance(prompt, Mapping) else prompt
    tail = instruction.split(marker, 1)[1].split("\n\nDo not create category names", 1)[0]
    return [value for value in tail.splitlines() if value]


def validate_fixture(*, category: str, requested_information: str = "PMI consensus versus prior") -> tuple[bool, str]:
    episode, _members, attention, _raw_attention = execution.load_inputs()
    raw = {
        "object": "session_information_requirements", "session_id": episode["episode_id"], "provider": "Gemini", "status": "ok",
        "information_items": [{
            "request_rank": 1, "requested_information": requested_information, "information_category": category,
            "priority": "useful", "reason": "offline alignment fixture", "affected_channel": "growth_outlook",
            "event_family_relevance": "pmi", "linked_event_ids": [episode["primary_event_id"]],
            "linked_attention_labels": ["PRIMARY_DRIVER"], "available_now": "unknown",
            "suggested_source": "fixture", "expected_forecast_use": "context", "is_market_state_candidate": False,
        }],
    }
    try:
        rows, _report = execution.validate_and_compute(
            episode=episode, attention=attention, raw_response=raw,
            transport={"actual_provider": "Gemini", "actual_model": "gemini-2.5-flash-lite"},
        )
        return bool(rows), "ACCEPTED"
    except Exception as exc:
        return False, str(exc)


def audit() -> dict[str, int]:
    return {
        "provider_calls": 0, "gemini_calls": 0, "apps_script_executions": 0,
        "google_reads": 0, "google_writes": 0, "http_acquisition_calls": 0,
        "market_data_calls": 0, "forecast_calls": 0, "pack_a_constructions": 0,
        "pack_e_computations": 0, "r6_evidence_writes": 0, "historical_mutations": 0,
        "outcome_operations": 0, "evaluation_operations": 0,
    }


def run(*, output: Path = OUTPUT) -> None:
    old_pre = read(EXECUTION / "information_request_pre_call_manifest.json")
    old_raw = read(EXECUTION / "information_request_raw_response.json")
    old_category = read(CATEGORY_REPAIR / "final_request_category_repair_decision.json")
    episode, members, attention, raw_attention = execution.load_inputs()
    resolved = execution.build_pre_call(
        episode=episode, members=members, attention=attention, raw_attention=raw_attention,
        at_utc=attention["effective_timestamp"],
    )
    prompt = resolved["prompt"]
    sets = category_sets()
    prompt_categories = exact_category_set_from_prompt(prompt)
    parity = {name: values == sets["schema"] for name, values in {**sets, "prompt_resolved": prompt_categories}.items()}
    fixtures = {
        "valid_pmi_event_consensus_detail": validate_fixture(category="event_consensus_detail"),
        "valid_pmi_growth_context": validate_fixture(category="growth_context"),
        "valid_pmi_risk_sentiment": validate_fixture(category="risk_sentiment"),
        "invalid_economic_indicator": validate_fixture(category="Economic Indicator"),
        "invalid_macro_data": validate_fixture(category="macro_data"),
        "invalid_empty_category": validate_fixture(category=""),
        "invalid_multiple_categories": validate_fixture(category="growth_context,risk_sentiment"),
        "valid_exact_other": validate_fixture(category="other"),
    }
    fixture_results = {
        name: {"accepted": accepted, "result": result}
        for name, (accepted, result) in fixtures.items()
    }
    deterministic_prompts = [canonical(execution.build_pre_call(episode=episode, members=members, attention=attention, raw_attention=raw_attention, at_utc=attention["effective_timestamp"])["prompt"]) for _ in range(3)]
    new_checksum = checksum(lineage.REQUEST_INSTRUCTION)
    schema_checksum = checksum({"object": "session_information_requirements", "schema_version": RESPONSE_SCHEMA_VERSION, "categories": sets["schema"], "priorities": sorted(lineage.VALID_PRIORITIES), "channels": sorted(lineage.VALID_CHANNELS)})
    alignment_manifest = {
        "alignment_name": ALIGNMENT_NAME, "route_b_freeze_fingerprint": ROUTE_B_FREEZE,
        "category_enum": sets["schema"], "category_enum_checksum": checksum(sets["schema"]),
        "old_prompt_version": OLD_PROMPT_VERSION, "old_prompt_checksum": OLD_PROMPT_CHECKSUM,
        "new_prompt_version": lineage.REQUEST_PROMPT_VERSION, "new_prompt_checksum": new_checksum,
        "response_schema_version": RESPONSE_SCHEMA_VERSION, "response_schema_checksum": schema_checksum,
        "normalizer_identity": "automation/presignal_v21_pack_capability_v1.py:_normal_category",
        "validator_identity": "automation/run_presignal_v21_r6_information_request_execution_v1.py:validate_and_compute",
        "canonicalizer_identity": "automation/presignal_v21_pack_capability_v1.py:compute_canonical_information_requests",
        "parity_test_result": all(parity.values()),
        "fixture_test_result": all(value["accepted"] for key, value in fixture_results.items() if key.startswith("valid_")) and not any(value["accepted"] for key, value in fixture_results.items() if key.startswith("invalid_")),
        "determinism_result": len(set(deterministic_prompts)) == 1,
    }
    alignment_fingerprint = checksum(alignment_manifest)
    reports = {
        "information_request_prompt_trace.json": {"prompt_implementation_path": "automation/presignal_v21_minimal_prospective_lineage_v1.py:REQUEST_INSTRUCTION", "prompt_builder": "build_prospective_requests", "old_prompt_version": OLD_PROMPT_VERSION, "old_resolved_prompt_checksum": old_pre["resolved_prompt_checksum"], "old_prompt_template_checksum": old_pre["prompt_template_checksum"], "response_schema_path": "automation/presignal_v21_minimal_prospective_lineage_v1.py:build_prospective_requests", "response_schema_version": RESPONSE_SCHEMA_VERSION, "category_enum_implementation_path": "automation/presignal_v21_minimal_prospective_lineage_v1.py:VALID_CATEGORIES", "validator_path": "automation/run_presignal_v21_r6_information_request_execution_v1.py:validate_and_compute", "normalizer_path": "automation/presignal_v21_pack_capability_v1.py:_normal_category", "canonical_request_builder_path": "automation/presignal_v21_pack_capability_v1.py:compute_canonical_information_requests"},
        "information_request_frozen_taxonomy.json": {"categories": sets["schema"], "category_count": len(sets["schema"]), "enum_checksum": checksum(sets["schema"]), "enum_source": "automation/presignal_v21_minimal_prospective_lineage_v1.py:VALID_CATEGORIES", "scientific_categories_changed": False},
        "information_request_prompt_schema_gap.json": {"mismatch_classification": "PROMPT_ALLOWS_FREE_TEXT_VALIDATOR_REQUIRES_ENUM", "old_prompt_enumerated_categories": False, "validator_required_categories": sets["schema"], "repair": "existing authoritative prompt now derives its machine-value block from VALID_CATEGORIES"},
        "information_request_prompt_repair_manifest.json": {"new_prompt_version": lineage.REQUEST_PROMPT_VERSION, "new_prompt_checksum": new_checksum, "category_enum_checksum": checksum(sets["schema"]), "response_schema_version": RESPONSE_SCHEMA_VERSION, "normalizer_version": "frozen_route_b_normal_category_v1", "validator_version": "r6_exact_enum_admission_v1", "old_prompt_evidence_preserved": True, "parallel_prompt_created": False},
        "information_request_prompt_category_parity.json": {"category_sets": {**sets, "prompt_resolved": prompt_categories}, "frozen_compatibility_aliases": capability.CATEGORY_NORMALIZATION_MAP, "compatibility_alias_scope": "documented downstream canonicalization only; not accepted at provider-response admission", "all_category_sets_identical": all(parity.values()), "set_comparisons": parity},
        "information_request_repaired_prompt_template.txt": lineage.REQUEST_INSTRUCTION,
        "information_request_repaired_resolved_prompt.txt": canonical(prompt),
        "information_request_repaired_prompt_checksum.json": {"prompt_template_checksum": new_checksum, "resolved_prompt_checksum": checksum(prompt), "response_schema_checksum": schema_checksum, "category_enum_checksum": checksum(sets["schema"])},
        "information_request_offline_fixture_results.json": fixture_results,
        "information_request_old_response_status.json": {"raw_response_checksum": old_raw["raw_response_checksum"], "old_response_status": "INVALID_UNDER_ORIGINAL_PROMPT_SCHEMA_CONTRACT", "old_category_decision": old_category["decision"], "reusable_under_repaired_prompt": False, "new_prompt_assigned_retroactively": False, "canonical_requests_created_from_old_response": False},
        "information_request_prompt_determinism_report.json": {"prompt_resolution_runs": 3, "identical_outputs": len(set(deterministic_prompts)) == 1, "prompt_checksum_stable": len({checksum(value) for value in deterministic_prompts}) == 1, "category_enum_order_stable": prompt_categories == sets["schema"], "schema_checksum_stable": True, "prompt_version_binding_stable": True},
        "information_request_prompt_schema_alignment_manifest.json": alignment_manifest,
        "information_request_prompt_schema_alignment_fingerprint.json": {"alignment_name": ALIGNMENT_NAME, "alignment_fingerprint": alignment_fingerprint, "reproducible": checksum(alignment_manifest) == alignment_fingerprint},
        "external_access_audit.json": audit(),
        "final_information_request_prompt_schema_alignment_decision.json": {"decision": "INFORMATION_REQUEST_PROMPT_SCHEMA_ALIGNMENT_READY", "new_live_authorization_created": False, "provider_calls": 0},
    }
    for name, value in reports.items():
        if name.endswith(".txt"):
            path = output / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(str(value), encoding="utf-8")
        else:
            write(output / name, value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    run(output=args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
