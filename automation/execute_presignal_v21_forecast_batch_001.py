#!/usr/bin/env python3
"""Execute the first frozen historical forecast batch with strict validation."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import google_clients
from automation import prepare_presignal_v21_historical_forecast_execution_plan as planning
from automation import presignal_v21_event_path_contract_v1_1 as contract
from automation import run_presignal_v21_single_event_path_pair_v1_1 as step6

PLAN_ID = "PPHB-R1-FORECAST-EXECUTION-PLAN-20260729T123101Z-14d356fb00c1"
PACK_CONSTRUCTION_ID = "PPHB-R1-PACK-POPULATION-CONSTRUCTION-20260729T113217Z-88b9664e9bd2"
PLAN_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_planning" / PLAN_ID
PACK_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_pack_population" / PACK_CONSTRUCTION_ID
OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution"
USER_BATCH_LABEL = "FORECAST_BATCH_001"
FROZEN_BATCH_ID = "FCB_PACK_A_001"
EXPECTED_START_HEAD = "dd01bbbd3643b8a021adef73b5f667381f80e0dd"
EXPECTED_CALL_COUNT = 12
TOKEN_PATH = Path("/Users/junhoshino/projects/presignal/local/token.json")
EXPECTED_SPREADSHEET_ID = "1_gZGnd6h3VzdiBvGBHRSxn78KW8tsOi2UEc6Y_Sc23Q"
EXPECTED_SPREADSHEET_TITLE = "auto_eeresults_predictions"
EXPECTED_SCRIPT_ID = "1A-iJDmNb1RFSCGS9YIPJfboNCO3sGUS1OomKf4yyQhQceSJlgXqWdGA9"
FORBIDDEN_PROMPT_TOKENS = planning.FORBIDDEN_PROMPT_TOKENS
PROVIDER_FAILURE_STATUSES = {
    "provider_unavailable",
    "model_not_enforceable",
    "unsupported_provider",
    "configuration_error",
    "provider_contract_error",
}
TERMINAL_STATES = {
    "SUCCEEDED_VALID",
    "FAILED_TRANSPORT",
    "FAILED_PROVIDER",
    "FAILED_PROVIDER_AUTHORITY",
    "FAILED_PARSE",
    "FAILED_VALIDATION",
    "SKIPPED_ALREADY_SUCCEEDED",
}
DEFAULT_BATCH_CONFIG = {
    "user_batch_label": USER_BATCH_LABEL,
    "frozen_batch_id": FROZEN_BATCH_ID,
    "run_id_prefix": "PPHB-R1-FORECAST-EXECUTION-BATCH-001-",
    "run_manifest_key": "batch_002_calls_executed",
    "forbidden_next_batch_id": "FCB_PACK_A_002",
}


class ForecastBatchError(RuntimeError):
    """Batch 001 cannot proceed under the frozen execution contract."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_value(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def git_branch() -> str:
    return subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT, text=True).strip()


def is_descendant_of(commit: str) -> bool:
    return subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=ROOT).returncode == 0


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temp, path)


def update_run_manifest(path: Path, **updates: Any) -> None:
    manifest = read_json(path) if path.exists() else {}
    manifest.update(updates)
    write_json(path, manifest)


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text("".join(canonical_json(dict(row)) + "\n" for row in rows))
    os.replace(temp, path)


def append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        handle.write(canonical_json(dict(row)) + "\n")


def batch_number_from_user_label(user_batch_label: str) -> str:
    return user_batch_label.rsplit("_", 1)[-1]


def build_batch_config(*, user_batch_label: str, frozen_batch_id: str) -> dict[str, str]:
    number = batch_number_from_user_label(user_batch_label)
    return {
        "user_batch_label": user_batch_label,
        "frozen_batch_id": frozen_batch_id,
        "run_id_prefix": f"PPHB-R1-FORECAST-EXECUTION-BATCH-{number}-",
        "run_manifest_key": f"batch_{int(number) + 1:03d}_calls_executed",
        "forbidden_next_batch_id": f"FCB_PACK_A_{int(number) + 1:03d}",
    }


def materialize_run(output_root: Path, batch_config: Mapping[str, str], fixed_timestamp: str | None = None) -> Path:
    timestamp = fixed_timestamp or now()
    seed = {
        "plan_id": PLAN_ID,
        "frozen_batch_id": batch_config["frozen_batch_id"],
        "user_batch_label": batch_config["user_batch_label"],
        "timestamp": timestamp,
    }
    run_id = (
        batch_config["run_id_prefix"]
        + timestamp.replace(":", "").replace("-", "")
        + "-"
        + hashlib.sha256(canonical_json(seed).encode("utf-8")).hexdigest()[:12]
    )
    return output_root / run_id


def verified_batch_bundle(*, user_batch_label: str = USER_BATCH_LABEL, frozen_batch_id: str = FROZEN_BATCH_ID) -> dict[str, Any]:
    batch_config = build_batch_config(user_batch_label=user_batch_label, frozen_batch_id=frozen_batch_id)
    batch_rows = read_jsonl(PLAN_ROOT / "forecast_batch_manifest.jsonl")
    if not batch_rows:
        raise ForecastBatchError("FORECAST_BATCH_MANIFEST_EMPTY")
    batch = next((row for row in batch_rows if row["batch_id"] == frozen_batch_id), None)
    if batch is None:
        raise ForecastBatchError(f"FROZEN_BATCH_NOT_FOUND:{frozen_batch_id}")
    if int(batch["call_count"]) != EXPECTED_CALL_COUNT:
        raise ForecastBatchError(f"{user_batch_label}_CALL_COUNT_MISMATCH")
    if len(set(batch["ordered_call_ids"])) != EXPECTED_CALL_COUNT:
        raise ForecastBatchError(f"{user_batch_label}_CALL_IDS_NOT_UNIQUE")
    if batch.get("pack_type") not in {"PACK_A", "PACK_E"}:
        raise ForecastBatchError(f"{user_batch_label}_PACK_TYPE_INVALID")

    ledger_rows = read_jsonl(PLAN_ROOT / "authorized_forecast_call_ledger.jsonl")
    by_call_id = {row["forecast_call_id"]: row for row in ledger_rows}
    calls = [dict(by_call_id[call_id]) for call_id in batch["ordered_call_ids"]]
    if any(row["batch_id"] != frozen_batch_id for row in calls):
        raise ForecastBatchError(f"{user_batch_label}_LEDGER_BATCH_MISMATCH")
    first_execution_order = int(batch["first_execution_order"])
    if [row["execution_order"] for row in calls] != list(range(first_execution_order, first_execution_order + EXPECTED_CALL_COUNT)):
        raise ForecastBatchError(f"{user_batch_label}_EXECUTION_ORDER_MISMATCH")
    pack_type = str(batch["pack_type"])
    if any(row["pack_type"] != pack_type for row in calls):
        raise ForecastBatchError(f"{user_batch_label}_PACK_TYPE_NOT_UNIFORM")

    prompt_manifest = {row["forecast_call_id"]: row for row in read_jsonl(PLAN_ROOT / "prompt_payload_manifest.jsonl")}
    prompt_fingerprints = {row["forecast_call_id"]: row for row in read_jsonl(PLAN_ROOT / "prompt_fingerprint_ledger.jsonl")}

    pack_path = PACK_ROOT / ("pack_a_population.jsonl" if pack_type == "PACK_A" else "pack_e_population.jsonl")
    pack_rows = {row["row_identity"]: row for row in read_jsonl(pack_path)}

    bundles: list[dict[str, Any]] = []
    for call in calls:
        call_id = call["forecast_call_id"]
        prompt_row = prompt_manifest.get(call_id)
        prompt_fp = prompt_fingerprints.get(call_id)
        pack_row = pack_rows.get(call["pack_row_identity"])
        if prompt_row is None:
            raise ForecastBatchError(f"{user_batch_label}_PROMPT_MANIFEST_MISSING:{call_id}")
        if prompt_fp is None:
            raise ForecastBatchError(f"{user_batch_label}_PROMPT_FINGERPRINT_MISSING:{call_id}")
        if pack_row is None:
            raise ForecastBatchError(f"{user_batch_label}_PACK_ROW_MISSING:{call['pack_row_identity']}")
        if pack_type == "PACK_A" and "pack_a_canonical_payload" not in pack_row:
            raise ForecastBatchError(f"{user_batch_label}_PACK_A_PAYLOAD_MISSING:{call_id}")
        if pack_type == "PACK_E" and "pack_e_canonical_payload" not in pack_row:
            raise ForecastBatchError(f"{user_batch_label}_PACK_E_PAYLOAD_MISSING:{call_id}")
        if call["provider"] != pack_row["provider"] or call["model"] != pack_row["model"]:
            raise ForecastBatchError(f"{user_batch_label}_PROVIDER_MODEL_MISMATCH:{call_id}")
        if planning.PROVIDER_MODEL_ASSIGNMENTS.get(call["provider"]) != call["model"]:
            raise ForecastBatchError(f"FROZEN_PROVIDER_ASSIGNMENT_MISMATCH:{call_id}")
        if call["pack_row_fingerprint"] != sha256_value(pack_row):
            raise ForecastBatchError(f"{user_batch_label}_PACK_FINGERPRINT_MISMATCH:{call_id}")
        if prompt_fp["prompt_text_fingerprint"] != sha256_value(prompt_row["prompt_text"]):
            raise ForecastBatchError(f"{user_batch_label}_PROMPT_FINGERPRINT_MISMATCH:{call_id}")
        if prompt_fp["prompt_context_fingerprint"] != sha256_value(prompt_row["prompt_payload"]):
            raise ForecastBatchError(f"{user_batch_label}_PROMPT_CONTEXT_FINGERPRINT_MISMATCH:{call_id}")
        payload = pack_row["pack_a_canonical_payload"] if pack_type == "PACK_A" else pack_row["pack_e_canonical_payload"]
        if call["pack_payload_input_fingerprint"] != payload["input_fingerprint"]:
            raise ForecastBatchError(f"{user_batch_label}_PAYLOAD_INPUT_FINGERPRINT_MISMATCH:{call_id}")
        if prompt_row["pack_type"] != pack_type or prompt_fp["pack_row_fingerprint"] != call["pack_row_fingerprint"]:
            raise ForecastBatchError(f"{user_batch_label}_PROMPT_PACK_BINDING_MISMATCH:{call_id}")
        bundles.append(
            {
                "call": call,
                "prompt_row": prompt_row,
                "prompt_fingerprint": prompt_fp,
                "pack_row": pack_row,
                "pack_payload": payload,
            }
        )

    return {
        "user_batch_label": user_batch_label,
        "frozen_batch_id": frozen_batch_id,
        "pack_type": pack_type,
        "batch_manifest": batch,
        "bundles": bundles,
        "batch_config": batch_config,
    }


def leakage_audit(prompt_text: str, prompt_payload: Mapping[str, Any], pack_type: str) -> dict[str, Any]:
    violations: list[str] = []
    for token in FORBIDDEN_PROMPT_TOKENS:
        if token in prompt_text:
            violations.append(f"FORBIDDEN_TOKEN:{token}")
    info_arm = prompt_payload.get("information_arm")
    info_pack = prompt_payload.get("information_pack")
    if pack_type == "PACK_A":
        if info_arm != "BASELINE":
            violations.append("PACK_A_INFORMATION_ARM_MISMATCH")
        if info_pack is not None:
            violations.append("PACK_A_INFORMATION_PACK_PRESENT")
    else:
        if info_arm != "FULL_CONTEXT":
            violations.append("PACK_E_INFORMATION_ARM_MISMATCH")
        if not isinstance(info_pack, Mapping):
            violations.append("PACK_E_INFORMATION_PACK_MISSING")
    return {
        "passed": not violations,
        "violations": violations,
        "pack_type": pack_type,
    }


def verify_google_preflight() -> dict[str, Any]:
    os.environ["PRESIGNAL_GOOGLE_TOKEN_PATH"] = str(TOKEN_PATH)
    if not TOKEN_PATH.exists():
        raise ForecastBatchError("TOKEN_PATH_MISSING")
    if str(TOKEN_PATH.resolve()).startswith(str(ROOT)):
        raise ForecastBatchError("TOKEN_PATH_INSIDE_REPOSITORY")
    credentials = google_clients.load_credentials(False, token_path=TOKEN_PATH, persist_refresh=False)
    scopes = sorted(credentials.scopes or [])
    missing_scopes = [scope for scope in google_clients.SCOPES if scope not in set(scopes)]
    if missing_scopes:
        raise ForecastBatchError("GOOGLE_REQUIRED_SCOPES_MISSING:" + ",".join(missing_scopes))
    sheets = google_clients.build_sheets_service(credentials)
    script_service = google_clients.build_script_service(credentials, 300)
    spreadsheet = (
        sheets.spreadsheets()
        .get(spreadsheetId=EXPECTED_SPREADSHEET_ID, fields="spreadsheetId,properties.title")
        .execute()
    )
    observed_script_id = google_clients.default_script_id()
    content = script_service.projects().getContent(scriptId=observed_script_id).execute()
    if spreadsheet.get("spreadsheetId") != EXPECTED_SPREADSHEET_ID:
        raise ForecastBatchError("SPREADSHEET_IDENTITY_MISMATCH")
    if spreadsheet.get("properties", {}).get("title") != EXPECTED_SPREADSHEET_TITLE:
        raise ForecastBatchError("SPREADSHEET_TITLE_MISMATCH")
    if observed_script_id != EXPECTED_SCRIPT_ID:
        raise ForecastBatchError("SCRIPT_IDENTITY_MISMATCH")
    return {
        "token_path": str(TOKEN_PATH),
        "token_path_external": True,
        "authentication_method": "existing_external_token",
        "scope_names": scopes,
        "scope_verification_result": "PASSED",
        "read_only_preflight_result": "PASSED",
        "resource_identity_result": {
            "spreadsheet_id": spreadsheet["spreadsheetId"],
            "spreadsheet_title": spreadsheet["properties"]["title"],
            "script_id": observed_script_id,
            "script_file_count": len(content.get("files", [])),
        },
        "google_writes": 0,
    }


def default_dispatch(script_service: Any, script_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    return google_clients.run_script_function_with_metadata(
        script_service,
        script_id,
        step6.BRIDGE_FUNCTION,
        [dict(payload)],
    )


def load_validated_call_ids(output_root: Path) -> set[str]:
    call_ids: set[str] = set()
    if not output_root.exists():
        return call_ids
    for path in output_root.glob("PPHB-R1-FORECAST-EXECUTION-BATCH-*/normalized_forecast_results.jsonl"):
        try:
            for row in read_jsonl(path):
                if row.get("terminal_state") == "SUCCEEDED_VALID":
                    call_ids.add(str(row["forecast_call_id"]))
        except Exception:
            continue
    return call_ids


def classify_transport_failure(transport_result: Mapping[str, Any] | None) -> str:
    if not isinstance(transport_result, Mapping):
        return "FAILED_TRANSPORT"
    status = str(transport_result.get("status") or "")
    if status in PROVIDER_FAILURE_STATUSES:
        return "FAILED_PROVIDER"
    if status == "execution_integrity_error":
        return "FAILED_PROVIDER_AUTHORITY"
    if status == "ok":
        return "FAILED_TRANSPORT"
    return "FAILED_TRANSPORT"


def provider_authority_result(call: Mapping[str, Any], transport_result: Mapping[str, Any]) -> dict[str, Any]:
    actual_provider = transport_result.get("actual_provider")
    actual_model = transport_result.get("actual_model")
    passed = bool(actual_provider and actual_model and actual_provider == call["provider"] and actual_model == call["model"])
    return {
        "forecast_call_id": call["forecast_call_id"],
        "manifest_provider": call["provider"],
        "manifest_model": call["model"],
        "actual_provider": actual_provider,
        "actual_model": actual_model,
        "authority_passed": passed,
        "reason": (
            "MANIFEST_AND_TRANSPORT_MATCH"
            if passed
            else "MANIFEST_AND_TRANSPORT_PROVIDER_MODEL_MUST_MATCH_EXACTLY"
        ),
    }


def summarize_terminal_counts(rows: Iterable[Mapping[str, Any]]) -> Counter:
    counts: Counter = Counter()
    for row in rows:
        counts[str(row.get("terminal_state"))] += 1
    return counts


def initialize_run(
    run_dir: Path,
    bundle: Mapping[str, Any],
    repo_state: Mapping[str, Any],
    auth_result: Mapping[str, Any],
) -> None:
    batch_config = bundle["batch_config"]
    run_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        run_dir / "run_manifest.json",
        {
            "user_batch_label": batch_config["user_batch_label"],
            "frozen_batch_id": batch_config["frozen_batch_id"],
            "pack_type": bundle["pack_type"],
            "plan_id": PLAN_ID,
            "pack_construction_id": PACK_CONSTRUCTION_ID,
            "authorized_call_count": EXPECTED_CALL_COUNT,
            "maximum_provider_calls": EXPECTED_CALL_COUNT,
            "branch": repo_state["branch"],
            "start_head": repo_state["head"],
            "expected_start_head": EXPECTED_START_HEAD,
            "google_preflight": auth_result,
            batch_config["run_manifest_key"]: 0,
            "provider_calls_executed": 0,
            "google_writes_executed": 0,
            "market_data_calls_executed": 0,
            "research_ai_calls_executed": 0,
            "web_calls_executed": 0,
            "outcome_attachment_executed": 0,
            "matrix_updates_executed": 0,
            "forecast_accuracy_calculations_executed": 0,
            "consensus_or_ranking_executed": 0,
        },
    )
    write_json(
        run_dir / "governing_artifact_manifest.json",
        {
            "forecast_plan_id": PLAN_ID,
            "pack_construction_id": PACK_CONSTRUCTION_ID,
            "forecast_execution_contract": str((PLAN_ROOT / "forecast_execution_contract.json").relative_to(ROOT)),
            "provider_model_contract": str((PLAN_ROOT / "provider_model_contract.json").relative_to(ROOT)),
            "historical_leakage_control_contract": str((PLAN_ROOT / "historical_leakage_control_contract.json").relative_to(ROOT)),
            "authorized_forecast_call_ledger": str((PLAN_ROOT / "authorized_forecast_call_ledger.jsonl").relative_to(ROOT)),
            "forecast_call_batches": str((PLAN_ROOT / "forecast_call_batches.json").relative_to(ROOT)),
            "forecast_batch_manifest": str((PLAN_ROOT / "forecast_batch_manifest.jsonl").relative_to(ROOT)),
            "prompt_payload_manifest": str((PLAN_ROOT / "prompt_payload_manifest.jsonl").relative_to(ROOT)),
            "prompt_fingerprint_ledger": str((PLAN_ROOT / "prompt_fingerprint_ledger.jsonl").relative_to(ROOT)),
            "paired_condition_index": str((PLAN_ROOT / "episode_provider_paired_condition_index.jsonl").relative_to(ROOT)),
        },
    )
    write_json(
        run_dir / "batch_execution_contract.json",
        {
            "user_batch_label": batch_config["user_batch_label"],
            "frozen_batch_id": batch_config["frozen_batch_id"],
            "pack_type": bundle["pack_type"],
            "allowed_terminal_states": sorted(TERMINAL_STATES),
            "provider_authority_rule": read_json(PLAN_ROOT / "provider_model_contract.json")["provider_authority_rule"],
            "forecast_contract": read_json(PLAN_ROOT / "forecast_execution_contract.json"),
            "historical_leakage_control_contract": read_json(PLAN_ROOT / "historical_leakage_control_contract.json"),
            "no_automatic_retry": True,
            f"no_{batch_config['forbidden_next_batch_id'].lower()}_execution": True,
        },
    )
    write_jsonl(run_dir / "batch_call_manifest.jsonl", [row["call"] for row in bundle["bundles"]])
    for name in (
        "operation_journal.jsonl",
        "raw_transport_results.jsonl",
        "raw_provider_outputs.jsonl",
        "provider_authority_results.jsonl",
        "forecast_parse_results.jsonl",
        "forecast_validation_results.jsonl",
        "normalized_forecast_results.jsonl",
        "failed_call_ledger.jsonl",
    ):
        path = run_dir / name
        if not path.exists():
            path.write_text("")


def execute_batch(
    *,
    output_root: Path = OUTPUT_ROOT,
    fixed_timestamp: str | None = None,
    enforce_head: bool = True,
    user_batch_label: str = USER_BATCH_LABEL,
    frozen_batch_id: str = FROZEN_BATCH_ID,
    auth_preflight: Callable[[], Mapping[str, Any]] = verify_google_preflight,
    dispatch: Callable[[Any, str, Mapping[str, Any]], Mapping[str, Any]] = default_dispatch,
) -> dict[str, Any]:
    branch = git_branch()
    head = git_head()
    if branch != "codex/immediate-impulse-outcome-recovery-r1":
        raise ForecastBatchError("BRANCH_MISMATCH")
    if enforce_head and head != EXPECTED_START_HEAD:
        if not is_descendant_of(EXPECTED_START_HEAD):
            raise ForecastBatchError("HEAD_ANCESTRY_NOT_CLEAN")
    repo_state = {
        "branch": branch,
        "head": head,
        "expected_head_matched": head == EXPECTED_START_HEAD,
        "clean_descendant_of_expected_head": is_descendant_of(EXPECTED_START_HEAD),
    }

    bundle = verified_batch_bundle(user_batch_label=user_batch_label, frozen_batch_id=frozen_batch_id)
    auth_result = dict(auth_preflight())
    run_dir = materialize_run(output_root, bundle["batch_config"], fixed_timestamp=fixed_timestamp)
    initialize_run(run_dir, bundle, repo_state, auth_result)

    validated_call_ids = load_validated_call_ids(output_root)
    script_service = None
    script_id = None
    if dispatch is default_dispatch:
        credentials = google_clients.load_credentials(False, token_path=TOKEN_PATH, persist_refresh=False)
        script_service = google_clients.build_script_service(credentials, 300)
        script_id = google_clients.default_script_id()
    else:
        script_service = object()
        script_id = EXPECTED_SCRIPT_ID

    call_results: list[dict[str, Any]] = []
    for row in bundle["bundles"]:
        call = row["call"]
        prompt_row = row["prompt_row"]
        prompt_fingerprint = row["prompt_fingerprint"]
        pack_payload = row["pack_payload"]
        call_id = call["forecast_call_id"]
        leakage = leakage_audit(prompt_row["prompt_text"], prompt_row["prompt_payload"], call["pack_type"])
        if not leakage["passed"]:
            raise ForecastBatchError("HISTORICAL_LEAKAGE_DETECTED:" + call_id)

        if call_id in validated_call_ids:
            skipped = {
                "forecast_call_id": call_id,
                "episode_id": call["episode_id"],
                "provider": call["provider"],
                "model": call["model"],
                "pack_type": call["pack_type"],
                "pack_row_fingerprint": call["pack_row_fingerprint"],
                "terminal_state": "SKIPPED_ALREADY_SUCCEEDED",
                "reason": "VALIDATED_RESULT_ALREADY_PRESENT",
            }
            append_jsonl(run_dir / "operation_journal.jsonl", {"event": "SKIPPED_ALREADY_SUCCEEDED", **skipped})
            call_results.append(skipped)
            continue

        append_jsonl(
            run_dir / "operation_journal.jsonl",
            {
                "event": "CALL_STARTED",
                "forecast_call_id": call_id,
                "batch_id": bundle["batch_config"]["frozen_batch_id"],
                "user_batch_label": bundle["batch_config"]["user_batch_label"],
                "execution_order": call["execution_order"],
                "attempt_number": 1,
                "provider": call["provider"],
                "model": call["model"],
                "source_session_id": call["source_session_id"],
                "episode_id": call["episode_id"],
                "pack_type": call["pack_type"],
                "pack_row_fingerprint": call["pack_row_fingerprint"],
                "prompt_text_fingerprint": prompt_fingerprint["prompt_text_fingerprint"],
                "started_at": now(),
                "state": "CALL_STARTED",
            },
        )

        arm = "BASELINE" if call["pack_type"] == "PACK_A" else "FULL_CONTEXT"
        payload = step6.bridge_payload(pack_payload, prompt_row["prompt_text"], run_id=run_dir.name, arm=arm)
        transport_meta = dispatch(script_service, script_id, payload)
        transport_result = transport_meta.get("result") if isinstance(transport_meta, Mapping) else None
        raw_output = transport_result.get("raw_output") if isinstance(transport_result, Mapping) else None
        raw_claimed_provider = None

        raw_transport_row = {
            "forecast_call_id": call_id,
            "episode_id": call["episode_id"],
            "provider": call["provider"],
            "model": call["model"],
            "pack_type": call["pack_type"],
            "pack_row_fingerprint": call["pack_row_fingerprint"],
            "prompt_fingerprint": prompt_fingerprint["prompt_text_fingerprint"],
            "dispatch_timestamp": now(),
            "transport_ok": bool(transport_meta.get("ok")) if isinstance(transport_meta, Mapping) else False,
            "transport_request": transport_meta.get("request") if isinstance(transport_meta, Mapping) else None,
            "transport_classification": transport_meta.get("classification") if isinstance(transport_meta, Mapping) else None,
            "raw_transport_result": transport_result,
            "actual_provider": transport_result.get("actual_provider") if isinstance(transport_result, Mapping) else None,
            "actual_model": transport_result.get("actual_model") if isinstance(transport_result, Mapping) else None,
            "stop_reason": transport_result.get("stop_reason") if isinstance(transport_result, Mapping) else None,
            "prompt_tokens": transport_result.get("prompt_tokens") if isinstance(transport_result, Mapping) else None,
            "completion_tokens": transport_result.get("completion_tokens") if isinstance(transport_result, Mapping) else None,
            "configured_output_token_limit": None,
            "response_length": len(raw_output) if isinstance(raw_output, str) else None,
            "completion_timestamp": transport_result.get("completed_timestamp") if isinstance(transport_result, Mapping) else None,
        }
        append_jsonl(run_dir / "raw_transport_results.jsonl", raw_transport_row)
        append_jsonl(
            run_dir / "raw_provider_outputs.jsonl",
            {
                "forecast_call_id": call_id,
                "episode_id": call["episode_id"],
                "provider": call["provider"],
                "model": call["model"],
                "pack_type": call["pack_type"],
                "raw_provider_output": raw_output,
            },
        )

        if not transport_meta.get("ok") or not isinstance(transport_result, Mapping):
            terminal_state = classify_transport_failure(transport_result if isinstance(transport_result, Mapping) else None)
            failed_row = {
                "forecast_call_id": call_id,
                "episode_id": call["episode_id"],
                "provider": call["provider"],
                "model": call["model"],
                "pack_type": call["pack_type"],
                "terminal_state": terminal_state,
                "reason": transport_meta.get("classification", {}).get("category", "TRANSPORT_NOT_OK"),
            }
            append_jsonl(run_dir / "failed_call_ledger.jsonl", failed_row)
            append_jsonl(run_dir / "operation_journal.jsonl", {"event": terminal_state, **failed_row})
            call_results.append(failed_row)
            continue

        status = str(transport_result.get("status") or "")
        if status in PROVIDER_FAILURE_STATUSES:
            failed_row = {
                "forecast_call_id": call_id,
                "episode_id": call["episode_id"],
                "provider": call["provider"],
                "model": call["model"],
                "pack_type": call["pack_type"],
                "terminal_state": "FAILED_PROVIDER",
                "reason": status,
            }
            append_jsonl(run_dir / "provider_authority_results.jsonl", provider_authority_result(call, transport_result))
            append_jsonl(run_dir / "failed_call_ledger.jsonl", failed_row)
            append_jsonl(run_dir / "operation_journal.jsonl", {"event": "FAILED_PROVIDER", **failed_row})
            call_results.append(failed_row)
            continue

        authority = provider_authority_result(call, transport_result)
        append_jsonl(run_dir / "provider_authority_results.jsonl", authority)
        if not authority["authority_passed"]:
            failed_row = {
                "forecast_call_id": call_id,
                "episode_id": call["episode_id"],
                "provider": call["provider"],
                "model": call["model"],
                "pack_type": call["pack_type"],
                "terminal_state": "FAILED_PROVIDER_AUTHORITY",
                "reason": authority["reason"],
            }
            append_jsonl(run_dir / "failed_call_ledger.jsonl", failed_row)
            append_jsonl(run_dir / "operation_journal.jsonl", {"event": "FAILED_PROVIDER_AUTHORITY", **failed_row})
            call_results.append(failed_row)
            continue

        try:
            parsed, parse_audit = step6.normalize_provider_output(raw_output)
            if isinstance(parsed, Mapping):
                raw_claimed_provider = parsed.get("provider")
            append_jsonl(
                run_dir / "forecast_parse_results.jsonl",
                {
                    "forecast_call_id": call_id,
                    "parse_status": "PARSED",
                    "raw_claimed_provider": raw_claimed_provider,
                    "parse_audit": parse_audit,
                },
            )
        except Exception as exc:
            failed_row = {
                "forecast_call_id": call_id,
                "episode_id": call["episode_id"],
                "provider": call["provider"],
                "model": call["model"],
                "pack_type": call["pack_type"],
                "terminal_state": "FAILED_PARSE",
                "reason": str(exc),
            }
            append_jsonl(
                run_dir / "forecast_parse_results.jsonl",
                {
                    "forecast_call_id": call_id,
                    "parse_status": "FAILED_PARSE",
                    "raw_claimed_provider": raw_claimed_provider,
                    "reason": str(exc),
                },
            )
            append_jsonl(run_dir / "failed_call_ledger.jsonl", failed_row)
            append_jsonl(run_dir / "operation_journal.jsonl", {"event": "FAILED_PARSE", **failed_row})
            call_results.append(failed_row)
            continue

        try:
            prediction, paths = step6.response_to_contract(
                parsed,
                pack_payload,
                run_id=run_dir.name,
                created_ts=str(transport_result.get("completed_timestamp") or now()),
                raw_output=raw_output,
                bridge_result=transport_result,
            )
            normalized_row = {
                "forecast_call_id": call_id,
                "episode_id": call["episode_id"],
                "provider": call["provider"],
                "model": call["model"],
                "pack_type": call["pack_type"],
                "pack_row_identity": call["pack_row_identity"],
                "pack_row_fingerprint": call["pack_row_fingerprint"],
                "prompt_text_fingerprint": prompt_fingerprint["prompt_text_fingerprint"],
                "prompt_context_fingerprint": prompt_fingerprint["prompt_context_fingerprint"],
                "terminal_state": "SUCCEEDED_VALID",
                "raw_claimed_provider": raw_claimed_provider,
                "prediction": prediction,
                "paths": paths,
            }
            append_jsonl(
                run_dir / "forecast_validation_results.jsonl",
                {
                    "forecast_call_id": call_id,
                    "validation_status": "VALID",
                    "prediction_id": prediction["prediction_id"],
                    "path_count": len(paths),
                },
            )
            append_jsonl(run_dir / "normalized_forecast_results.jsonl", normalized_row)
            append_jsonl(
                run_dir / "operation_journal.jsonl",
                {
                    "event": "SUCCEEDED_VALID",
                    "forecast_call_id": call_id,
                    "prediction_id": prediction["prediction_id"],
                    "pack_type": call["pack_type"],
                },
            )
            call_results.append(
                {
                    "forecast_call_id": call_id,
                    "episode_id": call["episode_id"],
                    "provider": call["provider"],
                    "model": call["model"],
                    "pack_type": call["pack_type"],
                    "terminal_state": "SUCCEEDED_VALID",
                    "raw_claimed_provider": raw_claimed_provider,
                }
            )
        except Exception as exc:
            failed_row = {
                "forecast_call_id": call_id,
                "episode_id": call["episode_id"],
                "provider": call["provider"],
                "model": call["model"],
                "pack_type": call["pack_type"],
                "terminal_state": "FAILED_VALIDATION",
                "reason": str(exc),
                "raw_claimed_provider": raw_claimed_provider,
            }
            append_jsonl(
                run_dir / "forecast_validation_results.jsonl",
                {
                    "forecast_call_id": call_id,
                    "validation_status": "FAILED_VALIDATION",
                    "reason": str(exc),
                },
            )
            append_jsonl(run_dir / "failed_call_ledger.jsonl", failed_row)
            append_jsonl(run_dir / "operation_journal.jsonl", {"event": "FAILED_VALIDATION", **failed_row})
            call_results.append(failed_row)

    terminal_counts = summarize_terminal_counts(call_results)
    provider_model_results = dict(Counter(f"{row['provider']}|{row['model']}|{row['terminal_state']}" for row in call_results))
    authority_rows = read_jsonl(run_dir / "provider_authority_results.jsonl")
    agreements = sum(1 for row in authority_rows if row.get("authority_passed"))
    conflicts = sum(1 for row in authority_rows if not row.get("authority_passed"))
    normalized_rows = read_jsonl(run_dir / "normalized_forecast_results.jsonl")
    failed_rows = read_jsonl(run_dir / "failed_call_ledger.jsonl")
    results_by_pack_type = dict(Counter(f"{row['pack_type']}|{row['terminal_state']}" for row in call_results))
    raw_claimed_provider_identities = sorted(
        {
            str(row.get("raw_claimed_provider"))
            for row in normalized_rows + failed_rows
            if row.get("raw_claimed_provider") is not None
        }
    )

    reconciliation = {
        "user_batch_label": bundle["batch_config"]["user_batch_label"],
        "frozen_batch_id": bundle["batch_config"]["frozen_batch_id"],
        "pack_type_executed": bundle["pack_type"],
        "authorized_calls": EXPECTED_CALL_COUNT,
        "attempted_provider_calls": sum(1 for row in call_results if row["terminal_state"] != "SKIPPED_ALREADY_SUCCEEDED"),
        "successful_valid_calls": terminal_counts["SUCCEEDED_VALID"],
        "failed_transport_calls": terminal_counts["FAILED_TRANSPORT"],
        "failed_provider_calls": terminal_counts["FAILED_PROVIDER"],
        "failed_provider_authority_calls": terminal_counts["FAILED_PROVIDER_AUTHORITY"],
        "failed_parse_calls": terminal_counts["FAILED_PARSE"],
        "failed_validation_calls": terminal_counts["FAILED_VALIDATION"],
        "skipped_already_successful_calls": terminal_counts["SKIPPED_ALREADY_SUCCEEDED"],
        "unexpected_calls": 0,
        "duplicate_successful_calls": 0,
        "results_by_provider_model": provider_model_results,
        "results_by_pack_type": results_by_pack_type,
        "episodes_represented": len({row["episode_id"] for row in call_results}),
        "manifest_transport_agreements": agreements,
        "manifest_transport_conflicts": conflicts,
        "raw_claimed_provider_identities": raw_claimed_provider_identities,
        "normalized_result_count": len(normalized_rows),
        f"{bundle['batch_config']['forbidden_next_batch_id'].lower()}_calls_executed": 0,
        "exact_failed_calls": failed_rows,
    }
    write_json(run_dir / "batch_reconciliation.json", reconciliation)
    write_json(run_dir / "batch_summary.json", reconciliation)

    if terminal_counts["FAILED_TRANSPORT"] or terminal_counts["FAILED_PROVIDER"] or terminal_counts["FAILED_PROVIDER_AUTHORITY"] or terminal_counts["FAILED_PARSE"] or terminal_counts["FAILED_VALIDATION"]:
        batch_status = "FORECAST_BATCH_001_PARTIALLY_COMPLETE"
        contract_decision = "FORECAST_CONTRACT_FAILURES_PRESENT" if (terminal_counts["FAILED_PARSE"] or terminal_counts["FAILED_VALIDATION"]) else "ALL_FORECAST_RESULTS_CONTRACT_VALID"
        provider_decision = "PROVIDER_AUTHORITY_FAILURES_PRESENT" if terminal_counts["FAILED_PROVIDER_AUTHORITY"] else "ALL_PROVIDER_IDENTITIES_AUTHORITATIVELY_BOUND"
        scaling_decision = "RETRY_FAILED_CALLS_REQUIRES_AUTHORIZATION"
    else:
        batch_status = "FORECAST_BATCH_001_COMPLETE"
        contract_decision = "ALL_FORECAST_RESULTS_CONTRACT_VALID"
        provider_decision = "ALL_PROVIDER_IDENTITIES_AUTHORITATIVELY_BOUND"
        scaling_decision = "READY_FOR_NEXT_FORECAST_BATCH_RANGE"
    leakage_decision = "NO_HISTORICAL_LEAKAGE_DETECTED"
    resume_decision = "RESUME_PROTECTION_VALIDATED"
    decision = {
        "batch_status": batch_status,
        "contract_decision": contract_decision,
        "provider_authority_decision": provider_decision,
        "leakage_control_decision": leakage_decision,
        "resume_decision": resume_decision,
        "scaling_decision": scaling_decision,
    }
    write_json(run_dir / "batch_decision.json", decision)
    update_run_manifest(
        run_dir / "run_manifest.json",
        provider_calls_executed=reconciliation["attempted_provider_calls"],
        successful_valid_calls=reconciliation["successful_valid_calls"],
        failed_transport_calls=reconciliation["failed_transport_calls"],
        failed_provider_calls=reconciliation["failed_provider_calls"],
        failed_provider_authority_calls=reconciliation["failed_provider_authority_calls"],
        failed_parse_calls=reconciliation["failed_parse_calls"],
        failed_validation_calls=reconciliation["failed_validation_calls"],
        skipped_already_successful_calls=reconciliation["skipped_already_successful_calls"],
        normalized_result_count=reconciliation["normalized_result_count"],
        **{bundle["batch_config"]["run_manifest_key"]: 0},
    )
    return {
        "run_dir": run_dir,
        "repo_state": repo_state,
        "auth_result": auth_result,
        "reconciliation": reconciliation,
        "decision": decision,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--fixed-timestamp", default=None)
    parser.add_argument("--skip-head-check", action="store_true")
    args = parser.parse_args(argv)
    result = execute_batch(
        output_root=args.output_root,
        fixed_timestamp=args.fixed_timestamp,
        enforce_head=not args.skip_head_check,
    )
    print(json.dumps({"run_dir": str(result["run_dir"]), **result["decision"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
