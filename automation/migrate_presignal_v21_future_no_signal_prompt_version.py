#!/usr/bin/env python3
"""Create the authorized future-only NO_SIGNAL prompt-version migration."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import prepare_presignal_v21_historical_forecast_execution_plan as planning
from automation import run_presignal_v21_single_event_path_pair_v1_1 as step6

OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution"
PLANNING_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_planning"
PACK_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_pack_population"

FORECAST_PLAN_RUN_ID = "PPHB-R1-FORECAST-EXECUTION-PLAN-20260729T123101Z-14d356fb00c1"
BATCH_003_FINAL_DIAGNOSIS_RUN_ID = "PPHB-R1-FORECAST-FINAL-RESULT-DIAGNOSIS-BATCH-003-20260729T234944Z-a65de810bf75"
BATCH_003_CLOSURE_RUN_ID = "PPHB-R1-FORECAST-BATCH-003-CLOSURE-AND-FUTURE-NO-SIGNAL-CLARIFICATION-20260801T103016Z-d79d82f56823"
PACK_CONSTRUCTION_RUN_ID = "PPHB-R1-PACK-POPULATION-CONSTRUCTION-20260729T113217Z-88b9664e9bd2"

EXPECTED_CLOSURE_START_HEAD = "18c20ee3a596bb5eeb86dfb181ddf666099c06ef"
EXPECTED_CLOSURE_FINAL_HEAD = "6f6fbbad15d63b1f24975e8ef50ddc938020b081"
NONEXISTENT_COPIED_HASH = "18c20ee3f7147e18cad7d85f0b64dc7bbfb73672"

COMPLETED_PROMPT_VERSION = "presignal_event_path_contract_v1_1_single_pair_validation"
COMPLETED_PROMPT_FINGERPRINT = "sha256:1c74911301c3c7ddea3dc359044209bbd9685b33fcfa434b504753a77f200ab6"
FUTURE_PROMPT_VERSION = "presignal_event_path_contract_v1_1_single_pair_validation_no_signal_confidence_explicit_v1"
FUTURE_PROMPT_FINGERPRINT = "sha256:2515e6c09742e58507efe8d9196ba58473c01f2d5bb9e8b5405405088d323a77"
ADDED_PROMPT_SENTENCE = "Even when no_signal_flag is true, confidence must be a numeric value from 0 to 1 and must not be null."

RUN_PREFIX = "PPHB-R1-FORECAST-FUTURE-NO-SIGNAL-PROMPT-MIGRATION"
SUPERSEDED_STATUS = "SUPERSEDED_UNEXECUTED_BY_AUTHORIZED_PROMPT_VERSION_MIGRATION"
MIGRATED_STATUS = "AUTHORIZED_MIGRATED_FUTURE_PROMPT_VERSION"


class PromptMigrationError(RuntimeError):
    """The authorized forward-looking migration cannot be proven safe."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_json(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(canonical_json(dict(row)) + "\n" for row in rows))


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def git_branch() -> str:
    return subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT, text=True).strip()


def commit_exists(commit: str) -> bool:
    return subprocess.run(
        ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    ).returncode == 0


def is_descendant_of(commit: str) -> bool:
    return subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, "HEAD"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    ).returncode == 0


def now_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def is_completed_batch(batch_id: str) -> bool:
    return batch_id in {"FCB_PACK_A_001", "FCB_PACK_A_002", "FCB_PACK_A_003"}


def is_future_batch(batch_id: str) -> bool:
    if batch_id.startswith("FCB_PACK_A_"):
        return int(batch_id.rsplit("_", 1)[1]) >= 4
    if batch_id.startswith("FCB_PACK_E_"):
        return int(batch_id.rsplit("_", 1)[1]) >= 1
    return False


def planning_run_dir() -> Path:
    return PLANNING_ROOT / FORECAST_PLAN_RUN_ID


def pack_rows_by_identity() -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for filename in ("pack_a_population.jsonl", "pack_e_population.jsonl"):
        for row in read_jsonl(PACK_ROOT / PACK_CONSTRUCTION_RUN_ID / filename):
            identity = str(row["row_identity"])
            if identity in rows:
                raise PromptMigrationError(f"DUPLICATE_PACK_ROW_IDENTITY:{identity}")
            rows[identity] = row
    return rows


def load_authoritative_plan() -> dict[str, Any]:
    run_dir = planning_run_dir()
    batches = read_jsonl(run_dir / "forecast_batch_manifest.jsonl")
    calls = read_jsonl(run_dir / "authorized_forecast_call_ledger.jsonl")
    prompt_rows = read_jsonl(run_dir / "prompt_payload_manifest.jsonl")
    fingerprint_rows = read_jsonl(run_dir / "prompt_fingerprint_ledger.jsonl")
    if (len(batches), len(calls), len(prompt_rows), len(fingerprint_rows)) != (48, 564, 564, 564):
        raise PromptMigrationError("FROZEN_FORECAST_PLAN_POPULATION_MISMATCH")
    return {
        "batches": batches,
        "calls": calls,
        "prompt_rows": prompt_rows,
        "fingerprint_rows": fingerprint_rows,
    }


def exact_prompt_diff(old_prompt: str, new_prompt: str, context: Mapping[str, Any]) -> dict[str, Any]:
    old_instruction = step6.prompt_instruction_text()
    new_instruction = step6.prompt_instruction_text(
        include_future_no_signal_confidence_clarification=True,
    )
    expected_new_instruction = old_instruction.replace(
        "Confidence is always a number from 0 to 1. ",
        "Confidence is always a number from 0 to 1. " + step6.FUTURE_NO_SIGNAL_CONFIDENCE_SENTENCE,
        1,
    )
    expected_old_prompt = old_instruction + "\n\n" + canonical_json(context)
    expected_new_prompt = new_instruction + "\n\n" + canonical_json(context)
    return {
        "old_prompt_matches_frozen_template": old_prompt == expected_old_prompt,
        "new_prompt_matches_clarified_template": new_prompt == expected_new_prompt,
        "new_instruction_matches_exact_one_sentence_insertion": new_instruction == expected_new_instruction,
        "added_sentence_count": new_instruction.count(ADDED_PROMPT_SENTENCE),
        "zero_deleted_scientific_instructions": new_instruction.replace(
            step6.FUTURE_NO_SIGNAL_CONFIDENCE_SENTENCE,
            "",
            1,
        ) == old_instruction,
        "prompt_context_unchanged": old_prompt.split("\n\n", 1)[1] == new_prompt.split("\n\n", 1)[1],
        "pack_content_changed": False,
        "provider_model_changed": False,
        "horizons_changed": False,
        "schema_changed": False,
    }


def call_manifest_revision_id(call_id: str, prompt_fingerprint: str) -> str:
    return "FMR_CALL_" + hashlib.sha256(
        canonical_json({"forecast_call_id": call_id, "prompt_text_fingerprint": prompt_fingerprint}).encode("utf-8")
    ).hexdigest()[:20]


def batch_manifest_revision_id(batch_id: str, calls: list[Mapping[str, Any]]) -> str:
    return "FMR_BATCH_" + hashlib.sha256(
        canonical_json(
            {
                "batch_id": batch_id,
                "call_revisions": [
                    {"forecast_call_id": row["forecast_call_id"], "revision": row["manifest_revision_id"]}
                    for row in calls
                ],
            }
        ).encode("utf-8")
    ).hexdigest()[:20]


def build_identity_dependency_graph() -> dict[str, Any]:
    return {
        "analysis_method": "exact inspection of prepare_presignal_v21_historical_forecast_execution_plan.call_identity_seed, forecast_call_id, build_batches, and executor resume_key",
        "prompt_change": {
            "directly_affected": [
                "prompt text",
                "prompt text fingerprint",
                "prompt-manifest revision identity",
                "batch-manifest revision fingerprint",
                "migration resume key",
                "evaluation prompt cohort metadata",
            ],
            "indirectly_affected": [
                "future dispatch authorization source",
                "future prompt-version pre-dispatch guard",
            ],
            "unaffected_frozen_identities": [
                "forecast_call_id",
                "episode_id",
                "provider",
                "model",
                "pack_type",
                "pack_row_identity",
                "pack_row_fingerprint",
                "historical_cutoff",
                "batch logical identity",
                "execution_order",
                "forecast contract version",
            ],
        },
        "forecast_call_id_seed_fields": [
            "study_identity",
            "episode_id",
            "source_session_id",
            "provider",
            "model",
            "pack_type",
            "historical_cutoff_identity",
            "pack_row_fingerprint",
            "forecast_contract_version",
            "schema_version",
        ],
        "forecast_call_id_prompt_dependency": False,
        "resume_key_prompt_dependency_before_migration": False,
        "batch_id_prompt_dependency": False,
        "batch_manifest_fingerprint_prompt_dependency": True,
        "forecast_payload_fingerprint_in_established_plan": "No standalone forecast-payload fingerprint field is present in the frozen planning pipeline; the dispatch payload carries prompt text, whose fingerprint is recorded separately.",
        "call_manifest_fingerprint_in_established_plan": "No standalone call-manifest fingerprint field is present; this migration creates versioned call-manifest revision identities append-only.",
    }


def build_migration_population() -> dict[str, Any]:
    plan = load_authoritative_plan()
    packs = pack_rows_by_identity()
    batch_by_id = {row["batch_id"]: row for row in plan["batches"]}
    prompt_by_call = {row["forecast_call_id"]: row for row in plan["prompt_rows"]}
    fingerprint_by_call = {row["forecast_call_id"]: row for row in plan["fingerprint_rows"]}
    future_batches = [row for row in plan["batches"] if is_future_batch(str(row["batch_id"]))]
    completed_batches = [row for row in plan["batches"] if is_completed_batch(str(row["batch_id"]))]
    if len(future_batches) != 45 or len(completed_batches) != 3:
        raise PromptMigrationError("FUTURE_BATCH_BOUNDARY_MISMATCH")
    future_batch_ids = {str(row["batch_id"]) for row in future_batches}
    future_calls = [row for row in plan["calls"] if str(row["batch_id"]) in future_batch_ids]
    if len(future_calls) != 528:
        raise PromptMigrationError(f"FUTURE_CALL_COUNT_MISMATCH:{len(future_calls)}")
    if sum(row["pack_type"] == "PACK_A" for row in future_calls) != 246:
        raise PromptMigrationError("FUTURE_PACK_A_COUNT_MISMATCH")
    if sum(row["pack_type"] == "PACK_E" for row in future_calls) != 282:
        raise PromptMigrationError("FUTURE_PACK_E_COUNT_MISMATCH")

    migrated_calls: list[dict[str, Any]] = []
    old_to_new_calls: list[dict[str, Any]] = []
    superseded: list[dict[str, Any]] = []
    prompt_diffs: list[dict[str, Any]] = []
    for call in future_calls:
        call_id = str(call["forecast_call_id"])
        prompt_row = prompt_by_call.get(call_id)
        old_fingerprint = fingerprint_by_call.get(call_id)
        pack_row = packs.get(str(call["pack_row_identity"]))
        if prompt_row is None or old_fingerprint is None or pack_row is None:
            raise PromptMigrationError(f"MIGRATION_SOURCE_MISSING:{call_id}")
        if old_fingerprint["prompt_text_fingerprint"] != sha256_json(str(prompt_row["prompt_text"])):
            raise PromptMigrationError(f"FROZEN_PROMPT_TEXT_FINGERPRINT_MISMATCH:{call_id}")
        if old_fingerprint["prompt_context_fingerprint"] != sha256_json(prompt_row["prompt_payload"]):
            raise PromptMigrationError(f"FROZEN_PROMPT_CONTEXT_FINGERPRINT_MISMATCH:{call_id}")
        recomputed_id = planning.forecast_call_id(pack_row, str(call["pack_type"]), str(call["pack_row_fingerprint"]))
        if recomputed_id != call_id:
            raise PromptMigrationError(f"FORECAST_CALL_IDENTITY_RECOMPUTATION_MISMATCH:{call_id}")
        new_prompt = step6.future_prompt_text(prompt_row["prompt_payload"])
        prompt_diff = exact_prompt_diff(str(prompt_row["prompt_text"]), new_prompt, prompt_row["prompt_payload"])
        if not all(
            prompt_diff[key]
            for key in (
                "old_prompt_matches_frozen_template",
                "new_prompt_matches_clarified_template",
                "new_instruction_matches_exact_one_sentence_insertion",
                "zero_deleted_scientific_instructions",
                "prompt_context_unchanged",
            )
        ) or prompt_diff["added_sentence_count"] != 1:
            raise PromptMigrationError(f"UNAUTHORIZED_PROMPT_DIFFERENCE:{call_id}")
        new_prompt_fingerprint = sha256_json(new_prompt)
        revision_id = call_manifest_revision_id(call_id, new_prompt_fingerprint)
        migration_resume_key = {
            "forecast_call_id": call_id,
            "manifest_revision_id": revision_id,
            "prompt_version": FUTURE_PROMPT_VERSION,
            "prompt_text_fingerprint": new_prompt_fingerprint,
            "pack_type": call["pack_type"],
            "episode_id": call["episode_id"],
            "provider": call["provider"],
            "model": call["model"],
            "pack_row_fingerprint": call["pack_row_fingerprint"],
            "forecast_contract_version": call["resume_key"]["forecast_contract_version"],
        }
        migrated = {
            **call,
            "logical_prior_batch_id": call["batch_id"],
            "prior_forecast_call_id": call_id,
            "forecast_call_id": call_id,
            "call_identity_preserved": True,
            "manifest_revision_id": revision_id,
            "prior_prompt_version": COMPLETED_PROMPT_VERSION,
            "prompt_version": FUTURE_PROMPT_VERSION,
            "prior_prompt_instruction_fingerprint": COMPLETED_PROMPT_FINGERPRINT,
            "prompt_instruction_fingerprint": FUTURE_PROMPT_FINGERPRINT,
            "prior_prompt_text_fingerprint": old_fingerprint["prompt_text_fingerprint"],
            "prompt_text_fingerprint": new_prompt_fingerprint,
            "prompt_context_fingerprint": old_fingerprint["prompt_context_fingerprint"],
            "prompt_payload": prompt_row["prompt_payload"],
            "prompt_text": new_prompt,
            "migration_status": MIGRATED_STATUS,
            "prior_authorization_state": call["authorization_state"],
            "authorization_state": MIGRATED_STATUS,
            "migration_resume_key": migration_resume_key,
            "prior_attempt_count": 0,
            "new_manifest_revision_attempt_count": 0,
        }
        migrated_calls.append(migrated)
        old_to_new_calls.append(
            {
                "old_forecast_call_id": call_id,
                "new_forecast_call_id": call_id,
                "call_identity_preserved": True,
                "old_manifest_revision": "FROZEN_ORIGINAL_FORECAST_PLAN",
                "new_manifest_revision": revision_id,
                "old_prompt_version": COMPLETED_PROMPT_VERSION,
                "new_prompt_version": FUTURE_PROMPT_VERSION,
                "old_prompt_text_fingerprint": old_fingerprint["prompt_text_fingerprint"],
                "new_prompt_text_fingerprint": new_prompt_fingerprint,
                "batch_id": call["batch_id"],
                "episode_id": call["episode_id"],
                "provider": call["provider"],
                "model": call["model"],
                "pack_type": call["pack_type"],
                "lineage_status": "PROMPT_MANIFEST_REVISED_CALL_ID_STABLE",
            }
        )
        superseded.append(
            {
                "identity_type": "UNEXECUTED_PROMPT_MANIFEST_REVISION",
                "forecast_call_id": call_id,
                "superseded_identity": f"{FORECAST_PLAN_RUN_ID}:{call_id}:{old_fingerprint['prompt_text_fingerprint']}",
                "replacement_identity": f"{revision_id}:{new_prompt_fingerprint}",
                "status": SUPERSEDED_STATUS,
                "dispatch_prohibited": True,
                "reason": "Authorized future prompt clarification changes the prompt fingerprint while forecast_call_id remains scientifically stable and prompt-independent.",
            }
        )
        prompt_diffs.append({"forecast_call_id": call_id, **prompt_diff})

    if len({row["forecast_call_id"] for row in migrated_calls}) != 528:
        raise PromptMigrationError("MIGRATED_CALL_ID_DUPLICATE")
    if len({row["old_forecast_call_id"] for row in old_to_new_calls}) != 528:
        raise PromptMigrationError("OLD_CALL_LINEAGE_DUPLICATE")
    if len({row["new_forecast_call_id"] for row in old_to_new_calls}) != 528:
        raise PromptMigrationError("NEW_CALL_LINEAGE_DUPLICATE")

    migrated_by_batch: dict[str, list[dict[str, Any]]] = {}
    for row in migrated_calls:
        migrated_by_batch.setdefault(str(row["batch_id"]), []).append(row)
    migrated_batches: list[dict[str, Any]] = []
    old_to_new_batches: list[dict[str, Any]] = []
    for prior_batch in future_batches:
        batch_id = str(prior_batch["batch_id"])
        batch_calls = sorted(migrated_by_batch.get(batch_id, []), key=lambda row: int(row["execution_order"]))
        if [row["forecast_call_id"] for row in batch_calls] != prior_batch["ordered_call_ids"]:
            raise PromptMigrationError(f"BATCH_ORDER_OR_MEMBERSHIP_CHANGED:{batch_id}")
        revision_id = batch_manifest_revision_id(batch_id, batch_calls)
        prior_fingerprint = sha256_json(prior_batch)
        new_batch = {
            **prior_batch,
            "logical_prior_batch_id": batch_id,
            "batch_id": batch_id,
            "batch_identity_preserved": True,
            "manifest_revision_id": revision_id,
            "prior_batch_manifest_fingerprint": prior_fingerprint,
            "prior_prompt_version": COMPLETED_PROMPT_VERSION,
            "prompt_version": FUTURE_PROMPT_VERSION,
            "prior_prompt_instruction_fingerprint": COMPLETED_PROMPT_FINGERPRINT,
            "prompt_instruction_fingerprint": FUTURE_PROMPT_FINGERPRINT,
            "call_manifest_revision_ids": [row["manifest_revision_id"] for row in batch_calls],
            "call_prompt_text_fingerprints": [row["prompt_text_fingerprint"] for row in batch_calls],
            "migration_status": MIGRATED_STATUS,
            "original_manifest_dispatch_prohibited": True,
        }
        new_batch["batch_manifest_fingerprint"] = sha256_json(
            {key: value for key, value in new_batch.items() if key != "batch_manifest_fingerprint"}
        )
        migrated_batches.append(new_batch)
        old_to_new_batches.append(
            {
                "old_batch_id": batch_id,
                "new_batch_id": batch_id,
                "batch_identity_preserved": True,
                "old_manifest_revision": "FROZEN_ORIGINAL_FORECAST_PLAN",
                "new_manifest_revision": revision_id,
                "old_batch_manifest_fingerprint": prior_fingerprint,
                "new_batch_manifest_fingerprint": new_batch["batch_manifest_fingerprint"],
                "old_prompt_version": COMPLETED_PROMPT_VERSION,
                "new_prompt_version": FUTURE_PROMPT_VERSION,
                "call_count": len(batch_calls),
                "lineage_status": "PROMPT_MANIFEST_REVISED_BATCH_ID_STABLE",
            }
        )

    if len(migrated_batches) != 45 or sum(row["call_count"] for row in migrated_batches) != 528:
        raise PromptMigrationError("MIGRATED_BATCH_RECONCILIATION_MISMATCH")
    return {
        "future_batches": future_batches,
        "completed_batches": completed_batches,
        "migrated_calls": migrated_calls,
        "migrated_batches": migrated_batches,
        "old_to_new_calls": old_to_new_calls,
        "old_to_new_batches": old_to_new_batches,
        "superseded": superseded,
        "prompt_diffs": prompt_diffs,
        "identity_dependency_graph": build_identity_dependency_graph(),
    }


def build_execution_guard() -> dict[str, Any]:
    return {
        "guard_name": "presignal_future_prompt_version_execution_guard_v1",
        "completed_batch_rules": {
            "batch_ids": ["FCB_PACK_A_001", "FCB_PACK_A_002", "FCB_PACK_A_003"],
            "required_prompt_version": COMPLETED_PROMPT_VERSION,
            "required_prompt_instruction_fingerprint": COMPLETED_PROMPT_FINGERPRINT,
            "new_prompt_version_rejected": True,
        },
        "future_batch_rules": {
            "batch_ids": "FCB_PACK_A_004 through FCB_PACK_A_024; FCB_PACK_E_001 through FCB_PACK_E_024",
            "required_prompt_version": FUTURE_PROMPT_VERSION,
            "required_prompt_instruction_fingerprint": FUTURE_PROMPT_FINGERPRINT,
            "old_prompt_fingerprint_rejected": True,
            "missing_prompt_version_lineage_rejected": True,
            "original_frozen_manifest_dispatch_prohibited": True,
        },
        "execution_source_rule": "Future batches must load their prompt rows only from a completed append-only future prompt migration run, not from the original frozen prompt manifest.",
        "resume_rule": "The migrated manifest revision resume key includes the unchanged forecast_call_id plus manifest_revision_id, prompt version, and prompt text fingerprint; its prior attempt count must be zero before dispatch.",
    }


def build_evaluation_prompt_cohort_metadata() -> dict[str, Any]:
    return {
        "completed_call_prompt_cohort": {
            "batch_ids": ["FCB_PACK_A_001", "FCB_PACK_A_002", "FCB_PACK_A_003"],
            "prompt_version": COMPLETED_PROMPT_VERSION,
            "prompt_instruction_fingerprint": COMPLETED_PROMPT_FINGERPRINT,
            "frozen_call_count": 36,
            "authoritative_valid_results": 35,
            "terminal_batch_003_schema_failure": "FCL_27720b8b23236b173b96fdee",
        },
        "clarified_prompt_cohort": {
            "first_affected_batch": "FCB_PACK_A_004",
            "batch_count": 45,
            "unexecuted_call_count": 528,
            "prompt_version": FUTURE_PROMPT_VERSION,
            "prompt_instruction_fingerprint": FUTURE_PROMPT_FINGERPRINT,
            "cohort_comparability_note": "Prompt version and fingerprint must be retained for later plan-aligned interpretation; this migration does not decide statistical pooling.",
        },
    }


def load_migrated_manifest_source(migration_run_dir: Path, batch_id: str) -> dict[str, Any]:
    """Load and strictly validate the only permitted future execution source."""
    if not is_future_batch(batch_id):
        raise PromptMigrationError(f"MIGRATION_SOURCE_FOR_NON_FUTURE_BATCH_FORBIDDEN:{batch_id}")
    decision = read_json(migration_run_dir / "migration_decision.json")
    if decision.get("prompt_migration_decision") != "FUTURE_NO_SIGNAL_PROMPT_MIGRATION_COMPLETE":
        raise PromptMigrationError("MIGRATION_NOT_COMPLETE")
    guard = read_json(migration_run_dir / "prompt_version_execution_guard.json")
    if guard.get("future_batch_rules", {}).get("required_prompt_version") != FUTURE_PROMPT_VERSION:
        raise PromptMigrationError("MIGRATION_GUARD_PROMPT_VERSION_MISMATCH")
    if guard.get("future_batch_rules", {}).get("required_prompt_instruction_fingerprint") != FUTURE_PROMPT_FINGERPRINT:
        raise PromptMigrationError("MIGRATION_GUARD_PROMPT_FINGERPRINT_MISMATCH")
    batch_rows = read_jsonl(migration_run_dir / "migrated_batch_manifest.jsonl")
    batch = next((row for row in batch_rows if row.get("batch_id") == batch_id), None)
    if batch is None:
        raise PromptMigrationError(f"MIGRATED_BATCH_NOT_FOUND:{batch_id}")
    if batch.get("prompt_version") != FUTURE_PROMPT_VERSION:
        raise PromptMigrationError(f"MIGRATED_BATCH_OLD_PROMPT_REJECTED:{batch_id}")
    calls_by_id = {row["forecast_call_id"]: row for row in read_jsonl(migration_run_dir / "migrated_call_manifest.jsonl")}
    calls = [calls_by_id.get(call_id) for call_id in batch["ordered_call_ids"]]
    if any(row is None for row in calls):
        raise PromptMigrationError(f"MIGRATED_CALL_MISSING:{batch_id}")
    typed_calls = [dict(row) for row in calls if row is not None]
    for row in typed_calls:
        if row.get("prompt_version") != FUTURE_PROMPT_VERSION:
            raise PromptMigrationError(f"MIGRATED_CALL_OLD_PROMPT_REJECTED:{row['forecast_call_id']}")
        if row.get("prompt_instruction_fingerprint") != FUTURE_PROMPT_FINGERPRINT:
            raise PromptMigrationError(f"MIGRATED_CALL_PROMPT_LINEAGE_MISSING:{row['forecast_call_id']}")
        if row.get("migration_status") != MIGRATED_STATUS:
            raise PromptMigrationError(f"MIGRATED_CALL_STATUS_INVALID:{row['forecast_call_id']}")
        if row.get("new_manifest_revision_attempt_count") != 0:
            raise PromptMigrationError(f"MIGRATED_CALL_PRIOR_ATTEMPT_PRESENT:{row['forecast_call_id']}")
        if sha256_json(str(row.get("prompt_text"))) != row.get("prompt_text_fingerprint"):
            raise PromptMigrationError(f"MIGRATED_CALL_PROMPT_FINGERPRINT_MISMATCH:{row['forecast_call_id']}")
        if ADDED_PROMPT_SENTENCE not in str(row.get("prompt_text")):
            raise PromptMigrationError(f"MIGRATED_CALL_CLARIFICATION_MISSING:{row['forecast_call_id']}")
    return {
        "batch_rows": batch_rows,
        "ledger_rows": typed_calls,
        "prompt_rows": [
            {
                "forecast_call_id": row["forecast_call_id"],
                "pack_type": row["pack_type"],
                "episode_id": row["episode_id"],
                "provider": row["provider"],
                "model": row["model"],
                "historical_cutoff": row["historical_cutoff"],
                "prompt_payload": row["prompt_payload"],
                "prompt_text": row["prompt_text"],
            }
            for row in typed_calls
        ],
        "fingerprint_rows": [
            {
                "forecast_call_id": row["forecast_call_id"],
                "pack_type": row["pack_type"],
                "episode_id": row["episode_id"],
                "provider": row["provider"],
                "model": row["model"],
                "pack_row_fingerprint": row["pack_row_fingerprint"],
                "prompt_context_fingerprint": row["prompt_context_fingerprint"],
                "prompt_text_fingerprint": row["prompt_text_fingerprint"],
                "pack_payload_input_fingerprint": row["pack_payload_input_fingerprint"],
                "prompt_version": row["prompt_version"],
                "prompt_instruction_fingerprint": row["prompt_instruction_fingerprint"],
                "manifest_revision_id": row["manifest_revision_id"],
            }
            for row in typed_calls
        ],
        "manifest_source": {
            "kind": "AUTHORIZED_FUTURE_PROMPT_MIGRATION",
            "migration_run_dir": str(migration_run_dir),
            "migration_run_id": migration_run_dir.name,
            "prompt_version": FUTURE_PROMPT_VERSION,
            "prompt_instruction_fingerprint": FUTURE_PROMPT_FINGERPRINT,
        },
    }


def construct_migration(
    output_root: Path = OUTPUT_ROOT,
    fixed_timestamp: str | None = None,
    *,
    enforce_head: bool = True,
) -> dict[str, Any]:
    if git_branch() != "codex/immediate-impulse-outcome-recovery-r1":
        raise PromptMigrationError("BRANCH_MISMATCH")
    if enforce_head and git_head() != EXPECTED_CLOSURE_FINAL_HEAD:
        raise PromptMigrationError("EXPECTED_START_HEAD_MISMATCH")
    if step6.PROMPT_VERSION != COMPLETED_PROMPT_VERSION:
        raise PromptMigrationError("COMPLETED_PROMPT_VERSION_MISMATCH")
    if step6.FUTURE_NO_SIGNAL_PROMPT_VERSION != FUTURE_PROMPT_VERSION:
        raise PromptMigrationError("FUTURE_PROMPT_VERSION_MISMATCH")
    if step6.prompt_instruction_fingerprint() != COMPLETED_PROMPT_FINGERPRINT:
        raise PromptMigrationError("COMPLETED_PROMPT_FINGERPRINT_MISMATCH")
    if step6.prompt_instruction_fingerprint(include_future_no_signal_confidence_clarification=True) != FUTURE_PROMPT_FINGERPRINT:
        raise PromptMigrationError("FUTURE_PROMPT_FINGERPRINT_MISMATCH")

    timestamp = fixed_timestamp or now_timestamp()
    seed = {
        "forecast_plan_run_id": FORECAST_PLAN_RUN_ID,
        "closure_run_id": BATCH_003_CLOSURE_RUN_ID,
        "timestamp": timestamp,
        "future_prompt_version": FUTURE_PROMPT_VERSION,
    }
    run_id = RUN_PREFIX + "-" + timestamp + "-" + sha256_json(seed)[7:19]
    run_dir = output_root / run_id
    if run_dir.exists():
        raise PromptMigrationError(f"RUN_ALREADY_EXISTS:{run_id}")
    run_dir.mkdir(parents=True, exist_ok=False)

    population = build_migration_population()
    all_prompt_diffs_passed = all(
        row["old_prompt_matches_frozen_template"]
        and row["new_prompt_matches_clarified_template"]
        and row["new_instruction_matches_exact_one_sentence_insertion"]
        and row["added_sentence_count"] == 1
        and row["zero_deleted_scientific_instructions"]
        and row["prompt_context_unchanged"]
        for row in population["prompt_diffs"]
    )
    if not all_prompt_diffs_passed:
        raise PromptMigrationError("PROMPT_DIFF_VALIDATION_FAILED")

    migration_reconciliation = {
        "future_batch_count": len(population["migrated_batches"]),
        "migrated_call_count": len(population["migrated_calls"]),
        "migrated_pack_a_call_count": sum(row["pack_type"] == "PACK_A" for row in population["migrated_calls"]),
        "migrated_pack_e_call_count": sum(row["pack_type"] == "PACK_E" for row in population["migrated_calls"]),
        "completed_batches_excluded": [row["batch_id"] for row in population["completed_batches"]],
        "completed_batch_count": len(population["completed_batches"]),
        "old_to_new_call_lineage_count": len(population["old_to_new_calls"]),
        "old_to_new_batch_lineage_count": len(population["old_to_new_batches"]),
        "superseded_unexecuted_prompt_manifest_identity_count": len(population["superseded"]),
        "duplicate_old_call_lineage_count": len(population["old_to_new_calls"]) - len({row["old_forecast_call_id"] for row in population["old_to_new_calls"]}),
        "duplicate_new_call_lineage_count": len(population["old_to_new_calls"]) - len({row["new_forecast_call_id"] for row in population["old_to_new_calls"]}),
        "call_ids_preserved": True,
        "batch_ids_preserved": True,
        "prompt_diff_only_authorized_sentence": True,
        "pack_rows_unchanged": True,
        "provider_model_assignments_unchanged": True,
        "historical_cutoffs_unchanged": True,
        "prior_attempts_for_migrated_revisions": 0,
        "completed_call_identities_remain_closed": True,
        "original_future_manifest_dispatch_prohibited": True,
        "no_provider_calls": True,
        "no_google_writes": True,
        "no_outcome_attachment": True,
        "no_forecast_accuracy_calculation": True,
        "prior_evidence_immutable": True,
    }
    if (
        migration_reconciliation["future_batch_count"],
        migration_reconciliation["migrated_call_count"],
        migration_reconciliation["migrated_pack_a_call_count"],
        migration_reconciliation["migrated_pack_e_call_count"],
    ) != (45, 528, 246, 282):
        raise PromptMigrationError("MIGRATION_COUNTS_NOT_RECONCILED")

    decision = {
        "prompt_migration_decision": "FUTURE_NO_SIGNAL_PROMPT_MIGRATION_COMPLETE",
        "call_identity_decision": "FORECAST_CALL_IDENTITIES_PRESERVED_WITH_VERSIONED_MANIFESTS",
        "batch_identity_decision": "BATCH_IDENTITIES_PRESERVED_WITH_NEW_REVISIONS",
        "prompt_diff_decision": "ONLY_AUTHORIZED_NO_SIGNAL_SENTENCE_ADDED",
        "execution_readiness_decision": "READY_TO_EXECUTE_FORECAST_BATCH_004",
    }
    repository_history_binding = {
        "actual_closure_start_head": EXPECTED_CLOSURE_START_HEAD,
        "closure_final_head": EXPECTED_CLOSURE_FINAL_HEAD,
        "current_migration_start_head": git_head(),
        "closure_final_head_is_ancestor_of_migration_start": is_descendant_of(EXPECTED_CLOSURE_FINAL_HEAD),
        "copied_expected_hash": NONEXISTENT_COPIED_HASH,
        "copied_expected_hash_exists_locally": commit_exists(NONEXISTENT_COPIED_HASH),
        "copied_expected_hash_classification": "NONEXISTENT_COPIED_HASH_TRANSCRIPTION_DISCREPANCY",
        "history_rewritten": False,
    }
    prompt_version_contract = {
        "completed_prompt": {
            "version": COMPLETED_PROMPT_VERSION,
            "instruction_fingerprint": COMPLETED_PROMPT_FINGERPRINT,
            "frozen_batch_ids": migration_reconciliation["completed_batches_excluded"],
        },
        "future_prompt": {
            "version": FUTURE_PROMPT_VERSION,
            "instruction_fingerprint": FUTURE_PROMPT_FINGERPRINT,
            "exact_added_sentence": ADDED_PROMPT_SENTENCE,
            "migrated_batch_count": 45,
            "migrated_call_count": 528,
        },
        "schema_changed": False,
        "provider_specific_scientific_wording": False,
    }
    exact_prompt_diff_artifact = {
        "authorized_added_sentence": ADDED_PROMPT_SENTENCE,
        "per_call_diff_count": len(population["prompt_diffs"]),
        "all_diffs_passed": all_prompt_diffs_passed,
        "one_added_sentence": True,
        "zero_deleted_scientific_instructions": True,
        "zero_modified_scientific_instructions": True,
        "zero_pack_content_changes": True,
        "zero_provider_model_changes": True,
        "zero_horizon_changes": True,
        "zero_schema_changes": True,
        "sample_diffs": population["prompt_diffs"][:12],
    }
    summary = {
        **decision,
        "migration_run_id": run_id,
        "future_batches": 45,
        "migrated_calls": 528,
        "pack_a_calls": 246,
        "pack_e_calls": 282,
        "completed_batches_excluded": migration_reconciliation["completed_batches_excluded"],
        "call_identity_dependency": "prompt-independent",
        "batch_identity_dependency": "prompt-independent logical batch IDs; prompt-dependent manifest revision fingerprints",
    }

    write_json(
        run_dir / "run_manifest.json",
        {
            "run_id": run_id,
            "object": "presignal_future_no_signal_prompt_version_migration_run",
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "repository": str(ROOT),
            "branch": git_branch(),
            "start_head": git_head(),
            "expected_start_head": EXPECTED_CLOSURE_FINAL_HEAD,
            "provider_calls_executed": 0,
            "google_writes_executed": 0,
            "outcome_attachment_executed": 0,
            "forecast_accuracy_calculations_executed": 0,
            "batch_004_executed": False,
        },
    )
    write_json(
        run_dir / "governing_artifact_manifest.json",
        {
            "forecast_plan_run_id": FORECAST_PLAN_RUN_ID,
            "batch_003_final_diagnosis_run_id": BATCH_003_FINAL_DIAGNOSIS_RUN_ID,
            "batch_003_closure_run_id": BATCH_003_CLOSURE_RUN_ID,
            "forecast_plan_authorized_call_ledger": str(planning_run_dir() / "authorized_forecast_call_ledger.jsonl"),
            "forecast_plan_batch_manifest": str(planning_run_dir() / "forecast_batch_manifest.jsonl"),
            "forecast_plan_prompt_payload_manifest": str(planning_run_dir() / "prompt_payload_manifest.jsonl"),
            "forecast_plan_prompt_fingerprint_ledger": str(planning_run_dir() / "prompt_fingerprint_ledger.jsonl"),
        },
    )
    write_json(
        run_dir / "migration_authorization.json",
        {
            "authorization": "USER_AUTHORIZED_FORWARD_LOOKING_NO_SIGNAL_PROMPT_VERSION_MIGRATION",
            "authorized_prompt_version": FUTURE_PROMPT_VERSION,
            "authorized_prompt_instruction_fingerprint": FUTURE_PROMPT_FINGERPRINT,
            "exact_added_sentence": ADDED_PROMPT_SENTENCE,
            "scope": "unexecuted forecast calls only",
            "provider_calls_authorized": 0,
            "completed_batches_modified": False,
        },
    )
    write_json(run_dir / "repository_history_binding.json", repository_history_binding)
    write_json(run_dir / "prompt_version_contract.json", prompt_version_contract)
    write_json(run_dir / "exact_prompt_diff.json", exact_prompt_diff_artifact)
    write_json(run_dir / "identity_dependency_graph.json", population["identity_dependency_graph"])
    write_json(
        run_dir / "forecast_call_identity_decision.json",
        {
            "decision": decision["call_identity_decision"],
            "evidence": "planning.call_identity_seed contains no prompt text, prompt version, prompt fingerprint, or prompt payload fingerprint.",
            "forecast_call_id_regenerated": False,
        },
    )
    write_json(
        run_dir / "batch_identity_decision.json",
        {
            "decision": decision["batch_identity_decision"],
            "evidence": "planning.batch_id uses pack type and batch number only; new batch-manifest fingerprints are prompt-version dependent.",
            "batch_id_regenerated": False,
        },
    )
    write_jsonl(run_dir / "unexecuted_call_inventory.jsonl", population["migrated_calls"])
    write_jsonl(run_dir / "old_to_new_call_lineage.jsonl", population["old_to_new_calls"])
    write_jsonl(run_dir / "old_to_new_batch_lineage.jsonl", population["old_to_new_batches"])
    write_jsonl(run_dir / "superseded_identity_ledger.jsonl", population["superseded"])
    write_jsonl(run_dir / "migrated_call_manifest.jsonl", population["migrated_calls"])
    write_jsonl(run_dir / "migrated_batch_manifest.jsonl", population["migrated_batches"])
    write_json(run_dir / "prompt_version_execution_guard.json", build_execution_guard())
    write_json(
        run_dir / "resume_protection_migration.json",
        {
            "call_identity_preserved": True,
            "migrated_manifest_revision_attempt_count": 0,
            "superseded_original_unexecuted_manifest_dispatch_prohibited": True,
            "completed_call_identities_closed": True,
            "old_and_new_prompt_manifest_revisions_cannot_both_dispatch": True,
            "future_dispatch_requires_migration_resume_key": True,
        },
    )
    write_json(run_dir / "evaluation_prompt_cohort_metadata.json", build_evaluation_prompt_cohort_metadata())
    write_json(run_dir / "migration_reconciliation.json", migration_reconciliation)
    write_json(run_dir / "migration_summary.json", summary)
    write_json(run_dir / "migration_decision.json", decision)
    return {"run_dir": run_dir, "run_id": run_id, "summary": summary, "decision": decision}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--fixed-timestamp", default=None)
    args = parser.parse_args(argv)
    result = construct_migration(args.output_root, args.fixed_timestamp)
    print(json.dumps({"run_dir": str(result["run_dir"]), **result["decision"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
