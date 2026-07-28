#!/usr/bin/env python3
"""Implement the frozen Round 1 eligibility/downstream-status separation in dry-run form."""
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

POPULATION_AUDIT_ID = "PPHB-R1-FULL-POPULATION-AUDIT-20260728T125525Z-b25cd178e7d6"
ELIGIBILITY_CONTRACT_ID = "PPHB-R1-ELIGIBILITY-CONTRACT-20260728T132116Z-88a316711419"

AUDIT_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_population_audit" / POPULATION_AUDIT_ID
CONTRACT_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_eligibility_contract" / ELIGIBILITY_CONTRACT_ID
MATRIX_FREEZE = (
    ROOT
    / "outputs"
    / "presignal_v21_pure_prediction_historical_baseline"
    / "PPHB-R1-FULL-MATRIX-FREEZE-20260726T150529Z-97fd30af6719"
)
OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_eligibility_implementation"

PROVIDERS = ("Gemini", "OpenAI", "Anthropic")
PROVIDER_MODELS = {
    "Gemini": "gemini-2.5-flash-lite",
    "OpenAI": "gpt-4o-mini-2024-07-18",
    "Anthropic": "claude-haiku-4-5",
}
PACK_ARMS = ("PACK_A", "PACK_E")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("".join(canonical_json(row) + "\n" for row in rows))
    os.replace(temporary, path)


def path_ref(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def load_contract_application() -> list[dict[str, Any]]:
    rows = read_jsonl(CONTRACT_ROOT / "full_population_contract_application.jsonl")
    rows.sort(key=lambda row: (row["release_ts"], row["episode_id"]))
    return rows


def load_existing_immutable_arm_index() -> dict[tuple[str, str, str], dict[str, Any]]:
    rows = read_jsonl(MATRIX_FREEZE / "call_ledger.jsonl")
    result: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = (row["episode_id"], row["provider"], row["pack_arm"])
        result[key] = row
    return result


def build_ledgers(
    *,
    output_root: Path = OUTPUT_ROOT,
    fixed_timestamp: str | None = None,
) -> dict[str, Any]:
    episode_rows = load_contract_application()
    immutable_arm_index = load_existing_immutable_arm_index()
    by_episode = {row["episode_id"]: row for row in episode_rows}

    ts = fixed_timestamp or now()
    seed = {
        "audit": POPULATION_AUDIT_ID,
        "contract": ELIGIBILITY_CONTRACT_ID,
        "timestamp": ts,
        "population_fingerprint": fingerprint(episode_rows),
    }
    run_id = f"PPHB-R1-ELIGIBILITY-IMPLEMENTATION-{ts.replace(':', '').replace('-', '')}-{hashlib.sha256(canonical_json(seed).encode()).hexdigest()[:12]}"
    run_dir = output_root / run_id

    episode_admission_ledger: list[dict[str, Any]] = []
    attention_status_ledger: list[dict[str, Any]] = []
    pack_status_ledger: list[dict[str, Any]] = []
    expected_arm_ledger: list[dict[str, Any]] = []

    exact_episode_ids = {row["episode_id"] for row in episode_rows if row["attention_status"] == "ATTENTION_AVAILABLE"}
    existing_47_episode_ids = {episode_id for episode_id in exact_episode_ids if any((episode_id, provider, pack) in immutable_arm_index for provider in ("Gemini", "OpenAI") for pack in PACK_ARMS)}
    outcome_unavailable_exact_episode = "EP_EVENT_757e72165d3ec05306a6"

    for row in episode_rows:
        episode_id = row["episode_id"]
        episode_admission_ledger.append(
            {
                "episode_id": episode_id,
                "release_ts": row["release_ts"],
                "episode_type": row["episode_type"],
                "member_event_count": row["member_event_count"],
                "event_family": row["event_family"],
                "episode_eligibility_status": row["episode_eligibility_status"],
                "admission_preserved": row["episode_eligibility_status"] == "ELIGIBLE",
                "downstream_statuses_do_not_alter_admission": True,
            }
        )
        attention_status_ledger.append(
            {
                "episode_id": episode_id,
                "release_ts": row["release_ts"],
                "attention_status": row["attention_status"],
                "attention_reason": row["attention_reason"],
            }
        )
        pack_status_ledger.append(
            {
                "episode_id": episode_id,
                "release_ts": row["release_ts"],
                "pack_a_status": row["pack_a_status"],
                "pack_a_reason": row["pack_a_reason"],
                "pack_e_status": row["pack_e_status"],
                "pack_e_reason": row["pack_e_reason"],
                "pack_a_input_admissibility": row["pack_a_input_admissibility"],
                "pack_e_input_admissibility": row["pack_e_input_admissibility"],
            }
        )

        for provider in PROVIDERS:
            for pack_arm in PACK_ARMS:
                key = (episode_id, provider, pack_arm)
                immutable = immutable_arm_index.get(key)
                blocking_reasons: list[str] = []
                if row["attention_status"] == "ATTENTION_RECONSTRUCTABLE":
                    blocking_reasons.append("ATTENTION_RECONSTRUCTION_REQUIRED")
                elif row["attention_status"] == "ATTENTION_UNAVAILABLE":
                    blocking_reasons.append("ATTENTION_UNAVAILABLE")

                pack_status = row["pack_a_status"] if pack_arm == "PACK_A" else row["pack_e_status"]
                if pack_status == "PACK_RECONSTRUCTABLE":
                    blocking_reasons.append("PACK_RECONSTRUCTION_REQUIRED")
                elif pack_status == "PACK_UNAVAILABLE":
                    blocking_reasons.append("PACK_UNAVAILABLE")

                if immutable is not None:
                    execution_status = "EXISTING_IMMUTABLE_RESULT"
                elif "PACK_UNAVAILABLE" in blocking_reasons or "ATTENTION_UNAVAILABLE" in blocking_reasons:
                    execution_status = "BLOCKED_PACK_UNAVAILABLE"
                elif "ATTENTION_RECONSTRUCTION_REQUIRED" in blocking_reasons:
                    execution_status = "BLOCKED_ATTENTION_RECONSTRUCTION"
                elif "PACK_RECONSTRUCTION_REQUIRED" in blocking_reasons:
                    execution_status = "BLOCKED_PACK_RECONSTRUCTION"
                elif provider == "Anthropic":
                    execution_status = "BLOCKED_PROVIDER_CONTRACT"
                    blocking_reasons.append("ANTHROPIC_CONTRACT_VALIDATION_PENDING")
                else:
                    execution_status = "READY_FOR_EXECUTION"

                expected_arm_ledger.append(
                    {
                        "episode_id": episode_id,
                        "release_ts": row["release_ts"],
                        "provider": provider,
                        "model": PROVIDER_MODELS[provider],
                        "pack_arm": pack_arm,
                        "expected_arm_identity": f"{episode_id}|{provider}|{pack_arm}",
                        "episode_eligibility_status": row["episode_eligibility_status"],
                        "attention_status": row["attention_status"],
                        "pack_status": pack_status,
                        "outcome_status_t15": row["outcome_status_t15"],
                        "evaluation_status_t15": row["evaluation_status_t15"],
                        "arm_execution_status": execution_status,
                        "blocking_reasons": sorted(set(blocking_reasons)),
                        "runtime_status_if_executed": "STATUS_UNKNOWN",
                        "forecast_status_if_executed": "INCOMPLETE",
                        "references_existing_immutable_result": immutable is not None,
                        "existing_immutable_call_id": None if immutable is None else immutable["call_id"],
                        "existing_cohort_membership": episode_id in existing_47_episode_ids,
                    }
                )

    expected_arm_ledger.sort(key=lambda row: (row["release_ts"], row["episode_id"], row["provider"], row["pack_arm"]))

    counts = {
        "candidate_episode_count": len(episode_rows),
        "admitted_episode_count": sum(row["episode_eligibility_status"] == "ELIGIBLE" for row in episode_rows),
        "excluded_episode_count": sum(row["episode_eligibility_status"] != "ELIGIBLE" for row in episode_rows),
        "exact_attention_count": sum(row["attention_status"] == "ATTENTION_AVAILABLE" for row in episode_rows),
        "reconstructable_attention_count": sum(row["attention_status"] == "ATTENTION_RECONSTRUCTABLE" for row in episode_rows),
        "unavailable_attention_count": sum(row["attention_status"] == "ATTENTION_UNAVAILABLE" for row in episode_rows),
        "exact_pack_a_count": sum(row["pack_a_status"] == "PACK_EXISTING_EXACT" for row in episode_rows),
        "reconstructable_pack_a_count": sum(row["pack_a_status"] == "PACK_RECONSTRUCTABLE" for row in episode_rows),
        "unavailable_pack_a_count": sum(row["pack_a_status"] == "PACK_UNAVAILABLE" for row in episode_rows),
        "exact_pack_e_count": sum(row["pack_e_status"] == "PACK_EXISTING_EXACT" for row in episode_rows),
        "reconstructable_pack_e_count": sum(row["pack_e_status"] == "PACK_RECONSTRUCTABLE" for row in episode_rows),
        "unavailable_pack_e_count": sum(row["pack_e_status"] == "PACK_UNAVAILABLE" for row in episode_rows),
        "expected_gemini_arm_count": sum(row["provider"] == "Gemini" for row in expected_arm_ledger),
        "expected_openai_arm_count": sum(row["provider"] == "OpenAI" for row in expected_arm_ledger),
        "expected_anthropic_arm_count": sum(row["provider"] == "Anthropic" for row in expected_arm_ledger),
        "expected_pack_a_arm_count": sum(row["pack_arm"] == "PACK_A" for row in expected_arm_ledger),
        "expected_pack_e_arm_count": sum(row["pack_arm"] == "PACK_E" for row in expected_arm_ledger),
        "total_expected_arm_count": len(expected_arm_ledger),
        "existing_immutable_gemini_openai_arm_count": sum(
            row["references_existing_immutable_result"] and row["provider"] in {"Gemini", "OpenAI"}
            for row in expected_arm_ledger
        ),
        "missing_anthropic_original_cohort_arm_count": sum(
            row["provider"] == "Anthropic"
            and row["existing_cohort_membership"]
            and not row["references_existing_immutable_result"]
            for row in expected_arm_ledger
        ),
        "blocked_reconstructable_arm_count": sum(
            "ATTENTION_RECONSTRUCTION_REQUIRED" in row["blocking_reasons"]
            or "PACK_RECONSTRUCTION_REQUIRED" in row["blocking_reasons"]
            for row in expected_arm_ledger
        ),
        "blocked_unavailable_arm_count": sum(
            row["arm_execution_status"] == "BLOCKED_PACK_UNAVAILABLE"
            for row in expected_arm_ledger
        ),
        "ready_for_execution_arm_count": sum(row["arm_execution_status"] == "READY_FOR_EXECUTION" for row in expected_arm_ledger),
        "blocked_provider_contract_arm_count": sum(row["arm_execution_status"] == "BLOCKED_PROVIDER_CONTRACT" for row in expected_arm_ledger),
    }

    if counts["candidate_episode_count"] != 462:
        raise RuntimeError("CANDIDATE_COUNT_UNEXPECTED")
    if counts["admitted_episode_count"] != 462 or counts["excluded_episode_count"] != 0:
        raise RuntimeError("ADMISSION_COUNT_UNEXPECTED")
    if counts["total_expected_arm_count"] != 2772:
        raise RuntimeError("TOTAL_EXPECTED_ARMS_UNEXPECTED")
    if counts["expected_pack_a_arm_count"] != 1386 or counts["expected_pack_e_arm_count"] != 1386:
        raise RuntimeError("PACK_ARM_COUNT_UNEXPECTED")
    if counts["expected_gemini_arm_count"] != 924 or counts["expected_openai_arm_count"] != 924 or counts["expected_anthropic_arm_count"] != 924:
        raise RuntimeError("PROVIDER_ARM_COUNT_UNEXPECTED")

    arm_status_counts = Counter(row["arm_execution_status"] for row in expected_arm_ledger)
    population_reconciliation = {
        "candidate_episode_count": counts["candidate_episode_count"],
        "admitted_episode_count": counts["admitted_episode_count"],
        "excluded_episode_count": counts["excluded_episode_count"],
        "expected_provider_count": 3,
        "expected_pack_arm_count_per_provider": 2,
        "expected_arm_count_per_episode": 6,
        "expected_total_arm_count": counts["total_expected_arm_count"],
        "arm_execution_status_counts": dict(sorted(arm_status_counts.items())),
    }

    arm_executability_summary = {
        "arm_execution_status_counts": dict(sorted(arm_status_counts.items())),
        "blocking_reason_counts": dict(
            sorted(
                Counter(reason for row in expected_arm_ledger for reason in row["blocking_reasons"]).items()
            )
        ),
        "existing_immutable_gemini_openai_arm_count": counts["existing_immutable_gemini_openai_arm_count"],
        "missing_anthropic_original_cohort_arm_count": counts["missing_anthropic_original_cohort_arm_count"],
        "ready_for_execution_arm_count": counts["ready_for_execution_arm_count"],
        "blocked_provider_contract_arm_count": counts["blocked_provider_contract_arm_count"],
        "blocked_reconstructable_arm_count": counts["blocked_reconstructable_arm_count"],
        "blocked_unavailable_arm_count": counts["blocked_unavailable_arm_count"],
    }

    existing_47_preservation = {
        "existing_immutable_arm_count": counts["existing_immutable_gemini_openai_arm_count"],
        "existing_immutable_episode_count": len(existing_47_episode_ids),
        "preservation_status": "UNCHANGED_REFERENCED_ONLY",
        "check": "No existing immutable forecast, Pack, Outcome, or evaluation artifact is rewritten by this implementation.",
    }

    outcome_unavailable_case = {
        "episode_id": outcome_unavailable_exact_episode,
        "preserved_in_admitted_population": True,
        "gemini_pack_a": next(row for row in expected_arm_ledger if row["episode_id"] == outcome_unavailable_exact_episode and row["provider"] == "Gemini" and row["pack_arm"] == "PACK_A")["arm_execution_status"],
        "openai_pack_a": next(row for row in expected_arm_ledger if row["episode_id"] == outcome_unavailable_exact_episode and row["provider"] == "OpenAI" and row["pack_arm"] == "PACK_A")["arm_execution_status"],
        "anthropic_pack_a": next(row for row in expected_arm_ledger if row["episode_id"] == outcome_unavailable_exact_episode and row["provider"] == "Anthropic" and row["pack_arm"] == "PACK_A")["arm_execution_status"],
        "outcome_status_t15": by_episode[outcome_unavailable_exact_episode]["outcome_status_t15"],
        "evaluation_status_t15": by_episode[outcome_unavailable_exact_episode]["evaluation_status_t15"],
    }

    superseded_projection_note = {
        "superseded_projection": {
            "eligible_population_assumption": 374,
            "projected_provider_arms_per_provider": 748,
            "projected_total_arms": 2244,
        },
        "replacement_projection": {
            "eligible_population_assumption": 462,
            "projected_provider_arms_per_provider": 924,
            "projected_total_arms": 2772,
        },
        "reason": "The frozen revised eligibility contract separates downstream availability from Episode admission and preserves all 462 admitted Episodes.",
    }

    dry_run_summary = {
        **counts,
        "arm_execution_status_counts": dict(sorted(arm_status_counts.items())),
    }

    implementation_binding = {
        "governing_population_audit_id": POPULATION_AUDIT_ID,
        "governing_eligibility_contract_id": ELIGIBILITY_CONTRACT_ID,
        "binding_mode": "CALL_FREE_DRY_RUN",
        "preserves_existing_pipeline": True,
        "parallel_replay_architecture_created": False,
    }

    implementation_decision = {
        "implementation_status": "NARROW_ELIGIBILITY_IMPLEMENTATION_COMPLETE",
        "admission_decision": "462_EPISODE_ADMISSION_PRESERVED",
        "arm_ledger_decision": "2772_EXPECTED_ARMS_RECONCILED",
        "readiness_status": "READY_WITH_BLOCKED_UNAVAILABLE_EPISODES",
        "external_calls": {"provider": 0, "market_data": 0, "google_writes": 0},
        "implementation_fingerprint": fingerprint(
            {
                "counts": counts,
                "arm_status_counts": arm_status_counts,
                "outcome_unavailable_case": outcome_unavailable_case,
            }
        ),
    }

    run_manifest = {
        "run_id": run_id,
        "generated_at": ts,
        "source_commit": git_head(),
        "governing_population_audit_id": POPULATION_AUDIT_ID,
        "governing_eligibility_contract_id": ELIGIBILITY_CONTRACT_ID,
        "inputs": [
            path_ref(CONTRACT_ROOT / "full_population_contract_application.jsonl"),
            path_ref(MATRIX_FREEZE / "call_ledger.jsonl"),
        ],
        "notes": [
            "No provider calls",
            "No market-data calls",
            "No Google writes",
            "No prior evidence modification",
        ],
    }

    write_json(run_dir / "run_manifest.json", run_manifest)
    write_json(run_dir / "implementation_binding.json", implementation_binding)
    write_jsonl(run_dir / "episode_admission_ledger.jsonl", episode_admission_ledger)
    write_jsonl(run_dir / "attention_status_ledger.jsonl", attention_status_ledger)
    write_jsonl(run_dir / "pack_status_ledger.jsonl", pack_status_ledger)
    write_jsonl(run_dir / "expected_arm_ledger.jsonl", expected_arm_ledger)
    write_json(run_dir / "arm_executability_summary.json", arm_executability_summary)
    write_json(run_dir / "population_reconciliation.json", population_reconciliation)
    write_json(run_dir / "existing_47_preservation_check.json", existing_47_preservation)
    write_json(run_dir / "outcome_unavailable_case_check.json", outcome_unavailable_case)
    write_json(run_dir / "superseded_projection_note.json", superseded_projection_note)
    write_json(run_dir / "dry_run_summary.json", dry_run_summary)
    write_json(run_dir / "implementation_decision.json", implementation_decision)

    return {
        "run_id": run_id,
        "run_dir": path_ref(run_dir),
        "implementation_status": implementation_decision["implementation_status"],
        "admission_decision": implementation_decision["admission_decision"],
        "arm_ledger_decision": implementation_decision["arm_ledger_decision"],
        "readiness_status": implementation_decision["readiness_status"],
        **counts,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()
    result = build_ledgers(output_root=args.output_root)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
