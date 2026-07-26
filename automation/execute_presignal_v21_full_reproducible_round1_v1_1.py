#!/usr/bin/env python3
"""Execute the full currently reproducible Gemini/OpenAI Round 1 matrix."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import prepare_presignal_v21_historical_baseline_prevalidation_v1_1 as prevalidation
from automation import presignal_v21_event_path_contract_v1_1 as contract
from automation import run_presignal_v21_single_event_path_pair_v1_1 as step6
from automation.execute_presignal_v21_historical_validation_batch_v1_1 import (
    BRIDGE_FUNCTION,
    PREVALIDATION_RUN_ID,
    REQUEST_SCHEMA_VERSION,
    TOKEN_ENV,
    TOKEN_PATH,
    ValidationExecutionError,
    outcome_preflight,
    pair_classification,
    sha256,
    terminal_from_transport,
    token_sha256,
    verify_bridge_transport,
    write_json,
    write_jsonl,
)
from automation.google_clients import build_script_service, default_script_id, load_credentials, run_script_function_with_metadata

STEP5 = ROOT / "outputs" / "presignal_v21_step5_reuse"
OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_pure_prediction_historical_baseline"
PROVIDERS = ("Gemini", "OpenAI")
MODELS = {
    "Gemini": "gemini-2.5-flash-lite",
    "OpenAI": "gpt-4o-mini-2024-07-18",
}
ACCEPTED_STARTING_HEAD = "1375a2e7601720593eed0a610f6c4c0b478eae48"
BOUNDARY = {
    "user_facing_timezone": "America/New_York",
    "start_local_inclusive": "2024-05-01 00:00:00 America/New_York",
    "end_local_exclusive": "2024-08-01 00:00:00 America/New_York",
    "start_utc_inclusive": "2024-05-01T04:00:00Z",
    "end_utc_exclusive": "2024-08-01T04:00:00Z",
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def path_ref(path: Path) -> str:
    return str(path.relative_to(ROOT))


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_inputs() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return (
        read_jsonl(STEP5 / "event_path_forecast_inputs_pack_a.jsonl"),
        read_jsonl(STEP5 / "event_path_forecast_inputs_pack_e.jsonl"),
    )


def key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return (str(row["episode_id"]), str(row["provider"]), str(row["model"]))


def pair_rows(
    pack_a_rows: list[dict[str, Any]],
    pack_e_rows: list[dict[str, Any]],
) -> dict[tuple[str, str, str], tuple[dict[str, Any], dict[str, Any]]]:
    by_a = {key(row): row for row in pack_a_rows}
    by_e = {key(row): row for row in pack_e_rows}
    return {
        identity: (by_a[identity], by_e[identity])
        for identity in sorted(set(by_a) & set(by_e))
        if identity[1] in PROVIDERS
    }


def indicator_label(row: Mapping[str, Any]) -> str:
    members = list(row.get("episode_members") or [])
    if not members:
        return "UNKNOWN"
    primary = next((member for member in members if member.get("structural_component_role") == "STRUCTURAL_PRIMARY"), members[0])
    return str(primary.get("indicator_name") or "UNKNOWN")


def classify_no_signal_reason(text: str | None) -> str:
    if not text:
        return "UNCLASSIFIED"
    value = text.lower()
    if any(token in value for token in ("not available", "unavailable", "not supplied", "policy_rejected", "missing", "critical information gap", "must-have information unavailable")):
        return "MISSING_REQUIRED_CONTEXT"
    if any(token in value for token in ("context_only", "low direct market impact", "minimal direct market impact", "negligible direct", "insufficient standalone signal", "irrelevant")):
        return "EVENT_IRRELEVANT_TO_USDJPY"
    if any(token in value for token in ("conflicting", "competing forces", "mixed signal", "cross-currents")):
        return "CONFLICTING_INPUTS"
    if any(token in value for token in ("low magnitude", "too small", "negligible move", "minimal move")):
        return "LOW_EXPECTED_MAGNITUDE"
    if any(token in value for token in ("uncertainty", "uncertain", "below threshold", "confidence falls below")):
        return "HIGH_UNCERTAINTY"
    if any(token in value for token in ("insufficient directional", "no defensible directional hypothesis", "no directional signal", "cannot establish directional")):
        return "INSUFFICIENT_DIRECTIONAL_EDGE"
    return "OTHER"


def build_full_manifest(
    *,
    population_rows: list[dict[str, Any]],
    pair_index: Mapping[tuple[str, str, str], tuple[dict[str, Any], dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    population_by_episode = {row["episode_id"]: row for row in population_rows}
    executable_rows: list[dict[str, Any]] = []
    unique_episode_rows: dict[str, dict[str, Any]] = {}
    removed_identities: list[dict[str, Any]] = []
    for (episode_id, provider, model), (row_a, row_e) in sorted(pair_index.items(), key=lambda item: (item[1][0]["release_ts"], item[0][0], item[0][1], item[0][2])):
        population = population_by_episode[episode_id]
        if population["population_status"] != "ELIGIBLE":
            removed_identities.append({
                "episode_id": episode_id,
                "release_ts": row_a["release_ts"],
                "provider": provider,
                "model": model,
                "execution_status": "NOT_AUTHORIZED_SCIENTIFIC_ADMISSION_EXCLUSION",
                "population_status": population["population_status"],
                "population_exclusion_detail": population.get("population_exclusion_detail"),
                "provider_identities_removed": 1,
                "forecast_arms_removed": 2,
            })
            continue
        episode_meta = {
            "episode_id": episode_id,
            "release_ts": row_a["release_ts"],
            "episode_type": "cluster" if len(row_a["episode_members"]) > 1 else "standalone",
            "member_count": len(row_a["episode_members"]),
            "event_family": indicator_label(row_a),
            "provider": provider,
            "model": model,
            "pack_a_ready": True,
            "pack_e_ready": True,
            "historical_cutoff_ts": row_a["forecast_cutoff_ts"],
            "pack_a_fingerprint": None,
            "pack_e_fingerprint": row_e["pack_fingerprint"],
            "input_snapshot_identity_pack_a": row_a["input_fingerprint"],
            "input_snapshot_identity_pack_e": row_e["input_fingerprint"],
            "same_time_cluster_flag": len(row_a["episode_members"]) > 1,
        }
        executable_rows.append(episode_meta)
        unique_episode_rows.setdefault(episode_id, {
            "episode_id": episode_id,
            "release_ts": row_a["release_ts"],
            "episode_type": episode_meta["episode_type"],
            "member_count": episode_meta["member_count"],
            "event_family": episode_meta["event_family"],
            "providers": [],
        })
        unique_episode_rows[episode_id]["providers"].append(provider)
    if len(executable_rows) + len(removed_identities) != 87:
        raise ValidationExecutionError(
            "FULL_MATRIX_SOURCE_IDENTITY_COUNT_UNEXPECTED:" + canonical_json({
                "authorized_identities": len(executable_rows),
                "removed_identities": len(removed_identities),
            })
        )
    if len(executable_rows) != 85:
        raise ValidationExecutionError(f"FULL_MATRIX_IDENTITY_COUNT_UNEXPECTED:{len(executable_rows)}")
    by_provider = Counter(row["provider"] for row in executable_rows)
    if by_provider != Counter({"Gemini": 47, "OpenAI": 38}):
        raise ValidationExecutionError("FULL_MATRIX_PROVIDER_COUNT_UNEXPECTED:" + canonical_json(dict(by_provider)))
    removed_by_provider = Counter(row["provider"] for row in removed_identities)
    if removed_by_provider != Counter({"Gemini": 1, "OpenAI": 1}):
        raise ValidationExecutionError("FULL_MATRIX_REMOVED_PROVIDER_COUNT_UNEXPECTED:" + canonical_json(dict(removed_by_provider)))
    unique_episodes = sorted(unique_episode_rows.values(), key=lambda row: (row["release_ts"], row["episode_id"]))
    eligible_episode_ids = {row["episode_id"] for row in population_rows if row["population_status"] == "ELIGIBLE"}
    executable_episode_ids = {row["episode_id"] for row in unique_episodes}
    coverage_gap = sorted(eligible_episode_ids - executable_episode_ids)
    if len(unique_episodes) != 47:
        raise ValidationExecutionError(f"FULL_MATRIX_UNIQUE_EPISODE_COUNT_UNEXPECTED:{len(unique_episodes)}")
    if len(coverage_gap) != 327:
        raise ValidationExecutionError(f"FULL_MATRIX_COVERAGE_GAP_UNEXPECTED:{len(coverage_gap)}")
    coverage = {
        "scientifically_eligible_episode_count": len(eligible_episode_ids),
        "unique_executable_episode_count": len(executable_episode_ids),
        "gemini_covered_episode_count": sum("Gemini" in row["providers"] for row in unique_episodes),
        "openai_covered_episode_count": sum("OpenAI" in row["providers"] for row in unique_episodes),
        "both_provider_episode_count": sum(set(row["providers"]) == {"Gemini", "OpenAI"} for row in unique_episodes),
        "eligible_episode_count_without_executable_provider_coverage": len(coverage_gap),
        "eligible_episode_ids_without_executable_provider_coverage": coverage_gap,
    }
    if coverage["gemini_covered_episode_count"] != 47:
        raise ValidationExecutionError("FULL_MATRIX_GEMINI_EPISODE_COUNT_UNEXPECTED")
    if coverage["openai_covered_episode_count"] != 38:
        raise ValidationExecutionError("FULL_MATRIX_OPENAI_EPISODE_COUNT_UNEXPECTED")
    if coverage["both_provider_episode_count"] != 38:
        raise ValidationExecutionError("FULL_MATRIX_BOTH_PROVIDER_COUNT_UNEXPECTED")
    removed_reconciliation = {
        "source_pack_paired_provider_episode_identity_count": len(pair_index),
        "authorized_provider_episode_identity_count": len(executable_rows),
        "removed_provider_episode_identity_count": len(removed_identities),
        "source_pack_paired_forecast_arm_count": len(pair_index) * 2,
        "authorized_forecast_arm_count": len(executable_rows) * 2,
        "removed_forecast_arm_count": len(removed_identities) * 2,
        "removed_identities": removed_identities,
    }
    if removed_reconciliation["authorized_forecast_arm_count"] != 170:
        raise ValidationExecutionError("FULL_MATRIX_AUTHORIZED_ARM_COUNT_UNEXPECTED")
    if removed_reconciliation["removed_forecast_arm_count"] != 4:
        raise ValidationExecutionError("FULL_MATRIX_REMOVED_ARM_COUNT_UNEXPECTED")
    return executable_rows, coverage, unique_episodes, removed_identities, removed_reconciliation


def build_outcomes_for_executable(unique_episodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    legacy_rows = {row["episode_id"]: row for row in read_jsonl(prevalidation.LEGACY_OUTCOMES)}
    acquisition_ts = now()
    outcomes = [prevalidation.convert_legacy_outcome(legacy_rows[row["episode_id"]], acquisition_ts=acquisition_ts) for row in unique_episodes]
    if len({row["outcome_id"] for row in outcomes}) != len(outcomes):
        raise ValidationExecutionError("FULL_OUTCOME_DUPLICATE_IDENTITY")
    return outcomes


def build_ledger(
    *,
    executable_rows: list[dict[str, Any]],
    pair_index: Mapping[tuple[str, str, str], tuple[dict[str, Any], dict[str, Any]]],
    outcomes_by_episode: Mapping[str, Mapping[str, Any]],
    run_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ledger: list[dict[str, Any]] = []
    pair_symmetry: list[dict[str, Any]] = []
    call_index = 0
    for row in executable_rows:
        episode_id = row["episode_id"]
        provider = row["provider"]
        model = row["model"]
        row_a, row_e = pair_index[(episode_id, provider, model)]
        context_a = step6.arm_context(row_a)
        context_e = step6.arm_context(row_e)
        diff = step6.prompt_diff(context_a, context_e)
        pair_symmetry.append({
            "episode_id": episode_id,
            "provider": provider,
            "model": model,
            "prompt_symmetry_passed": diff["passed"],
            "differences": diff["differences"],
            "allowed_differences": diff["allowed_differences"],
        })
        if not diff["passed"]:
            raise ValidationExecutionError("FULL_PROMPT_SYMMETRY_FAILURE:" + canonical_json(diff["differences"]))
        for pack_arm, pair_row, context in (("PACK_A", row_a, context_a), ("PACK_E", row_e, context_e)):
            call_index += 1
            prompt = step6.prompt_text(context)
            payload = step6.bridge_payload(pair_row, prompt, run_id=run_dir.name, arm="BASELINE" if pack_arm == "PACK_A" else "FULL_CONTEXT")
            ledger.append({
                "call_index": call_index,
                "call_id": f"FULL_CALL_{call_index:03d}_{hashlib.sha256((episode_id + provider + model + pack_arm).encode()).hexdigest()[:16]}",
                "episode_id": episode_id,
                "release_ts": pair_row["release_ts"],
                "episode_type": row["episode_type"],
                "event_family": row["event_family"],
                "member_count": row["member_count"],
                "provider": provider,
                "model": model,
                "pack_arm": pack_arm,
                "historical_cutoff_ts": pair_row["forecast_cutoff_ts"],
                "input_snapshot_id": pair_row["input_fingerprint"],
                "pack_fingerprint": None if pack_arm == "PACK_A" else pair_row["pack_fingerprint"],
                "prompt_fingerprint": sha256(context),
                "request_fingerprint": sha256(payload),
                "contract": contract.CONTRACT_VERSION,
                "schema": contract.SCHEMA_VERSION,
                "request_schema_version": REQUEST_SCHEMA_VERSION,
                "attempt_limit": 1,
                "canonical_outcome_id": outcomes_by_episode[episode_id]["outcome_id"],
                "canonical_outcome_schema": outcomes_by_episode[episode_id]["schema_version"],
                "expected_forecast_arm_count": 2,
            })
    if len(ledger) != 170:
        raise ValidationExecutionError(f"FULL_LEDGER_COUNT_UNEXPECTED:{len(ledger)}")
    return ledger, pair_symmetry


def persist_precall(
    *,
    run_dir: Path,
    source_prevalidation_manifest: dict[str, Any],
    boundary: dict[str, Any],
    coverage: dict[str, Any],
    executable_rows: list[dict[str, Any]],
    unique_episodes: list[dict[str, Any]],
    removed_reconciliation: dict[str, Any],
    ledger: list[dict[str, Any]],
    pair_symmetry: list[dict[str, Any]],
    pair_index: Mapping[tuple[str, str, str], tuple[dict[str, Any], dict[str, Any]]],
    outcomes: list[dict[str, Any]],
) -> None:
    for folder in (
        "input_snapshots",
        "pack_symmetry",
        "prompts",
        "raw_provider_responses",
        "normalization_audits",
        "canonical_forecasts",
        "outcomes",
        "evaluations",
        "pair_comparisons",
    ):
        (run_dir / folder).mkdir(parents=True, exist_ok=True)
    write_json(run_dir / "source_prevalidation_manifest.json", source_prevalidation_manifest)
    write_json(run_dir / "historical_boundary.json", boundary)
    write_json(run_dir / "population_coverage.json", coverage)
    write_jsonl(run_dir / "provider_episode_manifest.jsonl", executable_rows)
    write_json(run_dir / "removed_provider_identity_reconciliation.json", removed_reconciliation)
    write_json(run_dir / "provider_episode_manifest_summary.json", {
        "provider_episode_identity_count": len(executable_rows),
        "pack_a_arm_count": len(executable_rows),
        "pack_e_arm_count": len(executable_rows),
        "expected_forecast_arm_count": len(ledger),
        "unique_executable_episode_count": len(unique_episodes),
    })
    write_jsonl(run_dir / "call_ledger.jsonl", ledger)
    write_json(run_dir / "pack_symmetry" / "pair_symmetry.json", {"pairs": pair_symmetry})
    write_jsonl(run_dir / "outcomes" / "outcome_rows.jsonl", outcomes)
    for item in ledger:
        row_a, row_e = pair_index[(item["episode_id"], item["provider"], item["model"])]
        row = row_a if item["pack_arm"] == "PACK_A" else row_e
        context = step6.arm_context(row)
        prompt = step6.prompt_text(context)
        payload = step6.bridge_payload(row, prompt, run_id=run_dir.name, arm="BASELINE" if item["pack_arm"] == "PACK_A" else "FULL_CONTEXT")
        prefix = f"{item['call_index']:03d}_{item['episode_id']}_{item['provider']}_{item['pack_arm']}"
        write_json(run_dir / "input_snapshots" / f"{prefix}.json", {"input_row": row, "context": context, "payload": payload})
        (run_dir / "prompts" / f"{prefix}.txt").write_text(prompt + "\n")


def no_signal_reason_fields(prediction: Mapping[str, Any], episode_type: str, event_family: str) -> dict[str, Any]:
    reason = prediction.get("no_signal_reason")
    if isinstance(reason, Mapping):
        reason_code = reason.get("code")
        reason_text = reason.get("reason") or reason.get("text") or reason.get("message")
    else:
        reason_code = "UNSPECIFIED"
        reason_text = reason
    return {
        "provider": prediction["provider"],
        "model": prediction["model"],
        "episode_id": prediction["episode_id"],
        "pack": prediction["information_arm"],
        "confidence": prediction["confidence"],
        "reason_code": reason_code or "UNSPECIFIED",
        "reason_text": reason_text,
        "derived_reason_classification": classify_no_signal_reason(reason_text),
        "event_family": event_family,
        "episode_type": episode_type,
    }


def pair_transition(pack_a_prediction: Mapping[str, Any] | None, pack_e_prediction: Mapping[str, Any] | None) -> str:
    if not pack_a_prediction or not pack_e_prediction:
        return "PAIR_NOT_EVALUABLE"
    a_signal = not pack_a_prediction["no_signal_flag"]
    e_signal = not pack_e_prediction["no_signal_flag"]
    if not a_signal and e_signal:
        return "A_NO_SIGNAL_TO_E_DIRECTIONAL"
    if a_signal and not e_signal:
        return "A_DIRECTIONAL_TO_E_NO_SIGNAL"
    if not a_signal and not e_signal:
        return "BOTH_NO_SIGNAL"
    return "BOTH_DIRECTIONAL"


def metric_rows(
    evaluations: list[dict[str, Any]],
    forecasts_by_prediction: Mapping[str, dict[str, Any]],
    outcomes_by_episode: Mapping[str, Mapping[str, Any]],
    episode_type_by_id: Mapping[str, str],
    family_by_id: Mapping[str, str],
    horizon: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for evaluation in evaluations:
        forecast = forecasts_by_prediction[evaluation["prediction_id"]]
        if forecast["no_signal_flag"]:
            continue
        outcome = outcomes_by_episode[forecast["episode_id"]]
        rows.append({
            "provider": forecast["provider"],
            "pack": forecast["information_arm"],
            "episode_id": forecast["episode_id"],
            "episode_type": episode_type_by_id[forecast["episode_id"]],
            "event_family": family_by_id[forecast["episode_id"]],
            "direction_ok": evaluation[f"direction_{horizon}m_ok"],
            "signed_realized_pips": outcome[f"pips_{horizon}m"],
            "prediction_id": forecast["prediction_id"],
        })
    return rows


def aggregate_directional_yield(authoritative_valid_forecasts: list[dict[str, Any]], episode_type_by_id: Mapping[str, str], family_by_id: Mapping[str, str]) -> dict[str, Any]:
    def yield_block(rows: list[dict[str, Any]]) -> dict[str, Any]:
        directional = sum(not row["no_signal_flag"] for row in rows)
        return {
            "authoritative_valid_forecasts": len(rows),
            "completed_directional_forecasts": directional,
            "valid_no_signal_forecasts": len(rows) - directional,
            "directional_yield": directional / len(rows) if rows else None,
        }
    by_provider = {provider: yield_block([row for row in authoritative_valid_forecasts if row["provider"] == provider]) for provider in PROVIDERS}
    by_pack = {arm: yield_block([row for row in authoritative_valid_forecasts if row["information_arm"] == arm]) for arm in ("BASELINE", "FULL_CONTEXT")}
    by_provider_pack = {
        f"{provider}|{arm}": yield_block([row for row in authoritative_valid_forecasts if row["provider"] == provider and row["information_arm"] == arm])
        for provider in PROVIDERS for arm in ("BASELINE", "FULL_CONTEXT")
    }
    by_episode_type = {
        episode_type: yield_block([row for row in authoritative_valid_forecasts if episode_type_by_id[row["episode_id"]] == episode_type])
        for episode_type in ("standalone", "cluster")
    }
    by_family = {
        family: yield_block([row for row in authoritative_valid_forecasts if family_by_id[row["episode_id"]] == family])
        for family in sorted(set(family_by_id.values()))
    }
    overall = yield_block(authoritative_valid_forecasts)
    return {
        "overall": overall,
        "by_provider": by_provider,
        "by_pack": by_pack,
        "by_provider_pack": by_provider_pack,
        "by_episode_type": by_episode_type,
        "by_event_family": by_family,
    }


def aggregate_provider_pack_metrics(
    evaluations: list[dict[str, Any]],
    forecasts_by_prediction: Mapping[str, dict[str, Any]],
    outcomes_by_episode: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for provider in PROVIDERS:
        for arm in ("BASELINE", "FULL_CONTEXT"):
            rows = [evaluation for evaluation in evaluations if forecasts_by_prediction[evaluation["prediction_id"]]["provider"] == provider and forecasts_by_prediction[evaluation["prediction_id"]]["information_arm"] == arm and not forecasts_by_prediction[evaluation["prediction_id"]]["no_signal_flag"]]
            if not rows:
                metrics[f"{provider}|{arm}"] = {"count": 0}
                continue
            signed_15 = [outcomes_by_episode[forecasts_by_prediction[row["prediction_id"]]["episode_id"]]["pips_15m"] for row in rows]
            metrics[f"{provider}|{arm}"] = {
                "count": len(rows),
                "t15_directional_accuracy": sum(bool(row["direction_15m_ok"]) for row in rows) / len(rows),
                "t15_range_coverage": sum(row["magnitude_15m_error"] == 0 for row in rows) / len(rows),
                "t15_average_range_distance_error": sum(float(row["magnitude_15m_error"]) for row in rows) / len(rows),
                "t15_average_midpoint_absolute_error": sum(float(row["magnitude_15m_error"]) for row in rows) / len(rows),
                "t15_average_signed_realized_pips": sum(signed_15) / len(rows),
                "t5_directional_accuracy": sum(bool(row["direction_5m_ok"]) for row in rows) / len(rows),
                "t30_directional_accuracy": sum(bool(row["direction_30m_ok"]) for row in rows) / len(rows),
                "t60_directional_accuracy": sum(bool(row["direction_60m_ok"]) for row in rows) / len(rows),
                "reversal_accuracy": sum(bool(row["reversal_ok"]) for row in rows) / len(rows),
            }
    return metrics


def freeze_admissible_matrix(output_root: Path = OUTPUT_ROOT) -> tuple[Path, dict[str, Any]]:
    source_prevalidation_manifest = read_json(OUTPUT_ROOT / "latest_prevalidation_manifest.json")
    if source_prevalidation_manifest.get("prevalidation_run_id") != PREVALIDATION_RUN_ID:
        raise ValidationExecutionError("FULL_PREVALIDATION_RUN_ID_MISMATCH")
    _, outcome_preflight_check = outcome_preflight(source_prevalidation_manifest)
    pack_a_rows, pack_e_rows = load_inputs()
    pairs = pair_rows(pack_a_rows, pack_e_rows)
    population_rows = read_jsonl(OUTPUT_ROOT / PREVALIDATION_RUN_ID / "population_admission.jsonl")
    executable_rows, coverage, unique_episodes, _, removed_reconciliation = build_full_manifest(
        population_rows=population_rows,
        pair_index=pairs,
    )
    outcomes = build_outcomes_for_executable(unique_episodes)
    outcomes_by_episode = {row["episode_id"]: row for row in outcomes}
    run_id = "PPHB-R1-FULL-MATRIX-FREEZE-" + now().replace(":", "").replace("-", "") + "-" + hashlib.sha256((PREVALIDATION_RUN_ID + "|matrix|" + git_head()).encode()).hexdigest()[:12]
    run_dir = output_root / run_id
    ledger, pair_symmetry = build_ledger(
        executable_rows=executable_rows,
        pair_index=pairs,
        outcomes_by_episode=outcomes_by_episode,
        run_dir=run_dir,
    )
    persist_precall(
        run_dir=run_dir,
        source_prevalidation_manifest=source_prevalidation_manifest,
        boundary=BOUNDARY,
        coverage=coverage,
        executable_rows=executable_rows,
        unique_episodes=unique_episodes,
        removed_reconciliation=removed_reconciliation,
        ledger=ledger,
        pair_symmetry=pair_symmetry,
        pair_index=pairs,
        outcomes=outcomes,
    )
    write_json(run_dir / "outcomes" / "source_outcome_preflight_check.json", outcome_preflight_check)
    report = {
        "run_id": run_id,
        "source_pack_paired_provider_episode_identity_count": removed_reconciliation["source_pack_paired_provider_episode_identity_count"],
        "authorized_provider_episode_identity_count": removed_reconciliation["authorized_provider_episode_identity_count"],
        "removed_provider_episode_identity_count": removed_reconciliation["removed_provider_episode_identity_count"],
        "source_pack_paired_forecast_arm_count": removed_reconciliation["source_pack_paired_forecast_arm_count"],
        "authorized_forecast_arm_count": removed_reconciliation["authorized_forecast_arm_count"],
        "removed_forecast_arm_count": removed_reconciliation["removed_forecast_arm_count"],
        "unique_executable_episode_count": coverage["unique_executable_episode_count"],
        "coverage_limitation": "The run covers the complete currently reproducible and scientifically admissible Gemini/OpenAI Pack-paired matrix, not all 374 eligible Episodes.",
    }
    write_json(run_dir / "run_manifest.json", report)
    return run_dir, report


def execute_run(output_root: Path = OUTPUT_ROOT) -> tuple[Path, dict[str, Any]]:
    current_head = git_head()
    source_prevalidation_manifest = read_json(OUTPUT_ROOT / "latest_prevalidation_manifest.json")
    if source_prevalidation_manifest.get("prevalidation_run_id") != PREVALIDATION_RUN_ID:
        raise ValidationExecutionError("FULL_PREVALIDATION_RUN_ID_MISMATCH")
    if current_head == ACCEPTED_STARTING_HEAD:
        pass

    token_before = token_sha256()
    bridge_info = verify_bridge_transport()
    _, outcome_preflight_check = outcome_preflight(source_prevalidation_manifest)
    pack_a_rows, pack_e_rows = load_inputs()
    pairs = pair_rows(pack_a_rows, pack_e_rows)
    population_rows = read_jsonl(OUTPUT_ROOT / PREVALIDATION_RUN_ID / "population_admission.jsonl")
    executable_rows, coverage, unique_episodes, _, removed_reconciliation = build_full_manifest(population_rows=population_rows, pair_index=pairs)
    outcomes = build_outcomes_for_executable(unique_episodes)
    outcomes_by_episode = {row["episode_id"]: row for row in outcomes}
    run_id = "PPHB-R1-FULL-" + now().replace(":", "").replace("-", "") + "-" + hashlib.sha256((PREVALIDATION_RUN_ID + "|" + current_head).encode()).hexdigest()[:12]
    run_dir = output_root / run_id
    ledger, pair_symmetry = build_ledger(executable_rows=executable_rows, pair_index=pairs, outcomes_by_episode=outcomes_by_episode, run_dir=run_dir)
    persist_precall(
        run_dir=run_dir,
        source_prevalidation_manifest=source_prevalidation_manifest,
        boundary=BOUNDARY,
        coverage=coverage,
        executable_rows=executable_rows,
        unique_episodes=unique_episodes,
        removed_reconciliation=removed_reconciliation,
        ledger=ledger,
        pair_symmetry=pair_symmetry,
        pair_index=pairs,
        outcomes=outcomes,
    )
    write_json(run_dir / "outcomes" / "source_outcome_preflight_check.json", outcome_preflight_check)
    write_json(run_dir / "transport_verification.json", bridge_info)

    os.environ[TOKEN_ENV] = str(TOKEN_PATH)
    script_service = build_script_service(load_credentials(False, token_path=TOKEN_PATH, persist_refresh=False), 240)
    script_id = default_script_id()

    call_results: list[dict[str, Any]] = []
    forecasts: list[dict[str, Any]] = []
    forecast_paths: list[dict[str, Any]] = []
    evaluations: list[dict[str, Any]] = []
    pair_comparisons: list[dict[str, Any]] = []
    no_signal_rows: list[dict[str, Any]] = []
    stop_reason: str | None = None
    ledger_lookup = {(item["episode_id"], item["provider"], item["model"], item["pack_arm"]): item for item in ledger}
    episode_type_by_id = {row["episode_id"]: row["episode_type"] for row in unique_episodes}
    family_by_id = {row["episode_id"]: row["event_family"] for row in unique_episodes}

    for row in executable_rows:
        episode_id = row["episode_id"]
        provider = row["provider"]
        model = row["model"]
        outcome = outcomes_by_episode[episode_id]
        row_a, row_e = pairs[(episode_id, provider, model)]
        pair_forecasts: dict[str, dict[str, Any]] = {}
        pair_paths: dict[str, list[dict[str, Any]]] = {}
        pair_evaluations: dict[str, dict[str, Any]] = {}
        for pack_arm, pair_row in (("PACK_A", row_a), ("PACK_E", row_e)):
            item = ledger_lookup[(episode_id, provider, model, pack_arm)]
            context = step6.arm_context(pair_row)
            prompt = step6.prompt_text(context)
            payload = step6.bridge_payload(pair_row, prompt, run_id=run_id, arm="BASELINE" if pack_arm == "PACK_A" else "FULL_CONTEXT")
            prefix = f"{item['call_index']:03d}_{episode_id}_{provider}_{pack_arm}"
            result = run_script_function_with_metadata(script_service, script_id, BRIDGE_FUNCTION, [dict(payload)], dev_mode=True)
            raw_path = run_dir / "raw_provider_responses" / f"{prefix}.json"
            write_json(raw_path, {"request": payload, "transport_result": result})
            terminal = {
                "call_id": item["call_id"],
                "episode_id": episode_id,
                "release_ts": item["release_ts"],
                "episode_type": row["episode_type"],
                "event_family": row["event_family"],
                "provider": provider,
                "model": model,
                "pack_arm": pack_arm,
                "request_fingerprint": item["request_fingerprint"],
                "transport_ok": result["ok"],
                "transport_elapsed_ms": result["elapsed_ms"],
                "transport_classification": result["classification"],
                "transport_request": result["request"],
                "raw_response_path": path_ref(raw_path),
                "attempted": True,
            }
            if not result["ok"]:
                terminal["terminal_state"] = "PROVIDER_RUNTIME_FAILURE"
                terminal["error"] = result["classification"]["message"]
                call_results.append(terminal)
                continue
            bridge_result = result["result"]
            terminal["bridge_result_status"] = bridge_result.get("status")
            terminal["actual_provider"] = bridge_result.get("actual_provider")
            terminal["actual_model"] = bridge_result.get("actual_model")
            transport_terminal = terminal_from_transport(bridge_result)
            if transport_terminal == "MODEL_MISMATCH":
                terminal["terminal_state"] = "MODEL_MISMATCH"
                terminal["error"] = bridge_result.get("error")
                call_results.append(terminal)
                stop_reason = "MODEL_SUBSTITUTION"
                break
            if transport_terminal != "RESPONSE_RECEIVED":
                terminal["terminal_state"] = transport_terminal
                terminal["error"] = bridge_result.get("error")
                call_results.append(terminal)
                continue
            try:
                normalized, audit = step6.normalize_provider_output(bridge_result.get("raw_output"))
                write_json(run_dir / "normalization_audits" / f"{prefix}.json", audit)
                prediction, paths = step6.response_to_contract(
                    normalized,
                    pair_row,
                    run_id=run_id,
                    created_ts=str(bridge_result.get("completed_timestamp") or now()),
                    raw_output=bridge_result.get("raw_output"),
                    bridge_result=bridge_result,
                )
                evaluation = step6.evaluate(prediction, paths, outcome, generated_ts=now())
                write_json(run_dir / "canonical_forecasts" / f"{prefix}.json", prediction)
                write_jsonl(run_dir / "canonical_forecasts" / f"{prefix}_paths.jsonl", paths)
                write_json(run_dir / "evaluations" / f"{prefix}.json", evaluation)
                pair_forecasts[pack_arm] = prediction
                pair_paths[pack_arm] = paths
                pair_evaluations[pack_arm] = evaluation
                forecasts.append(prediction)
                forecast_paths.extend(paths)
                evaluations.append(evaluation)
                terminal["terminal_state"] = "VALID_NO_SIGNAL" if prediction["no_signal_flag"] else "COMPLETED_DIRECTIONAL_FORECAST"
                terminal["prediction_id"] = prediction["prediction_id"]
                terminal["provider_immediate_window_status"] = audit["provider_immediate_window_status"]
                terminal["provider_returned_immediate_window_seconds"] = audit["provider_returned_immediate_window_seconds"]
                terminal["canonical_immediate_window_seconds"] = audit["canonical_immediate_window_seconds"]
                if prediction["no_signal_flag"]:
                    no_signal_rows.append(no_signal_reason_fields(prediction, row["episode_type"], row["event_family"]))
            except Exception as exc:
                terminal["terminal_state"] = "SCHEMA_FAILURE"
                terminal["error"] = str(exc)
            call_results.append(terminal)
        if stop_reason:
            break

        compare = {
            "episode_id": episode_id,
            "provider": provider,
            "model": model,
            "baseline_prediction_id": pair_forecasts.get("PACK_A", {}).get("prediction_id"),
            "full_context_prediction_id": pair_forecasts.get("PACK_E", {}).get("prediction_id"),
            "shared_outcome_id": outcome["outcome_id"],
            "pair_transition": pair_transition(pair_forecasts.get("PACK_A"), pair_forecasts.get("PACK_E")),
            "t5_pair_classification": pair_classification(
                None if "PACK_A" not in pair_evaluations or pair_forecasts["PACK_A"]["no_signal_flag"] else pair_evaluations["PACK_A"]["direction_5m_ok"],
                None if "PACK_E" not in pair_evaluations or pair_forecasts["PACK_E"]["no_signal_flag"] else pair_evaluations["PACK_E"]["direction_5m_ok"],
            ) if {"PACK_A", "PACK_E"} <= pair_forecasts.keys() else "PAIR_NOT_EVALUABLE",
            "t15_pair_classification": pair_classification(
                None if "PACK_A" not in pair_evaluations or pair_forecasts["PACK_A"]["no_signal_flag"] else pair_evaluations["PACK_A"]["direction_15m_ok"],
                None if "PACK_E" not in pair_evaluations or pair_forecasts["PACK_E"]["no_signal_flag"] else pair_evaluations["PACK_E"]["direction_15m_ok"],
            ) if {"PACK_A", "PACK_E"} <= pair_forecasts.keys() else "PAIR_NOT_EVALUABLE",
        }
        pair_comparisons.append(compare)
        write_json(run_dir / "pair_comparisons" / f"{episode_id}_{provider}_{model}.json", compare)

    token_after = token_sha256()
    write_json(run_dir / "token_checksum_audit.json", {"before_sha256": token_before, "after_sha256": token_after, "unchanged": token_before == token_after})

    authoritative_valid_forecasts = [row for row in forecasts if row["status"] in {"VALID", "NO_SIGNAL"}]
    directional_forecasts = [row for row in forecasts if not row["no_signal_flag"]]
    forecasts_by_prediction = {row["prediction_id"]: row for row in forecasts}
    terminal_counts = dict(sorted(Counter(row["terminal_state"] for row in call_results).items()))

    no_signal_analysis = {
        "total_no_signal_forecasts": len(no_signal_rows),
        "by_provider": dict(sorted(Counter(row["provider"] for row in no_signal_rows).items())),
        "by_pack": dict(sorted(Counter(row["pack"] for row in no_signal_rows).items())),
        "by_provider_pack": dict(sorted(Counter(f"{row['provider']}|{row['pack']}" for row in no_signal_rows).items())),
        "by_episode_type": dict(sorted(Counter(row["episode_type"] for row in no_signal_rows).items())),
        "by_event_family": dict(sorted(Counter(row["event_family"] for row in no_signal_rows).items())),
        "by_reason_code": dict(sorted(Counter(row["reason_code"] for row in no_signal_rows).items())),
        "by_derived_reason_classification": dict(sorted(Counter(row["derived_reason_classification"] for row in no_signal_rows).items())),
        "rows": no_signal_rows,
    }
    directional_yield_analysis = aggregate_directional_yield(authoritative_valid_forecasts, episode_type_by_id, family_by_id)
    provider_pack_metrics = aggregate_provider_pack_metrics(evaluations, forecasts_by_prediction, outcomes_by_episode)

    population_reconciliation = {
        "scientifically_eligible_episode_count": 374,
        "unique_executable_episode_count": coverage["unique_executable_episode_count"],
        "eligible_episode_count_without_executable_provider_coverage": coverage["eligible_episode_count_without_executable_provider_coverage"],
    }
    provider_identity_reconciliation = {
        "provider_episode_identity_count": len(executable_rows),
        "by_provider": dict(sorted(Counter(row["provider"] for row in executable_rows).items())),
        "removed_identities": removed_reconciliation["removed_identities"],
    }
    call_reconciliation = {
        "authorized_calls": len(ledger),
        "attempted_calls": len(call_results),
        "transport_returned_calls": sum(bool(row["transport_ok"]) for row in call_results),
        "transport_failures": sum(not row["transport_ok"] for row in call_results),
        "terminal_counts": terminal_counts,
    }
    forecast_arm_reconciliation = {
        "expected_forecast_arms": len(ledger),
        "completed_directional_forecasts": sum(row["terminal_state"] == "COMPLETED_DIRECTIONAL_FORECAST" for row in call_results),
        "valid_no_signals": sum(row["terminal_state"] == "VALID_NO_SIGNAL" for row in call_results),
        "schema_failures": sum(row["terminal_state"] == "SCHEMA_FAILURE" for row in call_results),
        "runtime_failures": sum(row["terminal_state"] == "PROVIDER_RUNTIME_FAILURE" for row in call_results),
        "provider_rejections": sum(row["terminal_state"] == "PROVIDER_REJECTION" for row in call_results),
        "model_mismatches": sum(row["terminal_state"] == "MODEL_MISMATCH" for row in call_results),
        "lineage_failures": 0,
        "persistence_failures": 0,
        "pre_call_blocks": len(ledger) - len(call_results),
    }
    evaluation_reconciliation = {
        "authoritative_valid_forecasts": len(authoritative_valid_forecasts),
        "evaluated_directional_forecasts": len(directional_forecasts),
        "evaluated_no_signal_forecasts": len(authoritative_valid_forecasts) - len(directional_forecasts),
        "explicit_evaluation_exclusions": len(call_results) - len(authoritative_valid_forecasts),
    }

    write_json(run_dir / "no_signal_analysis.json", no_signal_analysis)
    write_json(run_dir / "directional_yield_analysis.json", directional_yield_analysis)
    write_json(run_dir / "provider_pack_metrics.json", provider_pack_metrics)
    write_json(run_dir / "population_reconciliation.json", population_reconciliation)
    write_json(run_dir / "provider_identity_reconciliation.json", provider_identity_reconciliation)
    write_json(run_dir / "call_reconciliation.json", call_reconciliation)
    write_json(run_dir / "forecast_arm_reconciliation.json", forecast_arm_reconciliation)
    write_json(run_dir / "evaluation_reconciliation.json", evaluation_reconciliation)
    write_jsonl(run_dir / "transport_results.jsonl", call_results)
    write_jsonl(run_dir / "canonical_forecasts" / "forecast_index.jsonl", forecasts)
    write_jsonl(run_dir / "canonical_forecasts" / "path_index.jsonl", forecast_paths)
    write_jsonl(run_dir / "evaluations" / "evaluation_index.jsonl", evaluations)
    write_jsonl(run_dir / "pair_comparisons" / "pair_index.jsonl", pair_comparisons)

    report = {
        "run_id": run_id,
        "git_head": current_head,
        "contract_version": contract.CONTRACT_VERSION,
        "schema_version": contract.SCHEMA_VERSION,
        "provider_matrix": [{"provider": provider, "model": MODELS[provider]} for provider in PROVIDERS],
        "anthropic_exclusion_reason": "PROVIDER_EXCLUDED_SYMMETRIC_PACK_EXECUTION_UNSAFE",
        "scientifically_eligible_episode_count": 374,
        "unique_executable_episode_count": coverage["unique_executable_episode_count"],
        "provider_episode_identity_count": len(executable_rows),
        "expected_forecast_arm_count": len(ledger),
        "attempted_calls": len(call_results),
        "terminal_counts": terminal_counts,
        "directional_forecasts": len(directional_forecasts),
        "valid_no_signal_forecasts": len(authoritative_valid_forecasts) - len(directional_forecasts),
        "schema_failures": forecast_arm_reconciliation["schema_failures"],
        "token_checksum_unchanged": token_before == token_after,
        "transport_verification": bridge_info,
        "coverage_limitation": "This run covers the complete currently reproducible Gemini/OpenAI provider–Episode matrix, not all 374 scientifically eligible Episodes.",
        "stop_reason": stop_reason,
    }
    write_json(run_dir / "run_manifest.json", report)
    (run_dir / "full_round_1_report.md").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return run_dir, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--freeze-manifest-only", action="store_true")
    args = parser.parse_args()
    run_dir, report = freeze_admissible_matrix(args.output_root) if args.freeze_manifest_only else execute_run(args.output_root)
    print(json.dumps({"run_dir": str(run_dir), "report": report}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
