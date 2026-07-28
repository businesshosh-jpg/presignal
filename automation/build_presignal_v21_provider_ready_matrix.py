#!/usr/bin/env python3
"""Apply the validated provider-contract recommendations to the Round 1 execution matrix."""
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
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PRIOR_MATRIX_ID = "PPHB-R1-EXECUTION-MATRIX-RESCUE-FINAL-20260728T163525Z-771789ec7142"
PROVIDER_VALIDATION_ID = "PPHB-R1-PROVIDER-CONTRACT-VALIDATION-20260728T170019660182Z-882230171a68"
CONTRACT_IDENTITY = "presignal_event_path_contract_v1_1"
CONTRACT_SCHEMA_VERSION = "2.1.1"
OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_execution_matrix"
PRIOR_MATRIX_PATH = (
    OUTPUT_ROOT / PRIOR_MATRIX_ID / "final_rescue_aware_execution_matrix.jsonl"
)
PROVIDER_VALIDATION_ROOT = (
    ROOT
    / "outputs"
    / "presignal_v21_full_round_1_provider_contract_validation"
    / PROVIDER_VALIDATION_ID
)
RECOMMENDATION_PATH = PROVIDER_VALIDATION_ROOT / "arm_status_recommendation.jsonl"

EXPECTED_EPISODE_COUNT = 462
EXPECTED_ARM_COUNT = 2772
EXPECTED_RECOMMENDATION_COUNT = 96
EXPECTED_PACK_COUNTS = {"PACK_A": 48, "PACK_E": 48}
ALLOWED_PROVIDER = "Anthropic"
ALLOWED_MODEL = "claude-haiku-4-5"
ALLOWED_PRIOR_STATUS = "BLOCKED_PROVIDER_CONTRACT"
ALLOWED_NEW_STATUS = "READY_FOR_EXECUTION"
CHANGE_REASON = "PROVIDER_TRANSPORT_WRAPPER_REPAIR_VALIDATED"
OPEC_EPISODE_ID = "EP_EVENT_67dc98eaf62822136db2"
OUT_OF_SESSION_BLOCKER = "OUT_OF_NORMAL_SESSION_EVENT_LEVEL_ROUTE_PENDING"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("".join(canonical_json(row) + "\n" for row in rows))
    os.replace(temporary, path)


def path_ref(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def arm_identity(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row["episode_id"]),
        str(row["provider"]),
        str(row.get("model") or row.get("requested_model")),
        str(row.get("pack_arm") or row.get("pack")),
    )


def load_prior_matrix_rows() -> list[dict[str, Any]]:
    rows = read_jsonl(PRIOR_MATRIX_PATH)
    rows.sort(key=lambda row: (row["release_ts"], row["episode_id"], row["provider"], row["pack_arm"]))
    return rows


def load_recommendation_rows() -> list[dict[str, Any]]:
    rows = read_jsonl(RECOMMENDATION_PATH)
    rows.sort(key=lambda row: (row["episode_id"], row["provider"], row["requested_model"], row["pack"]))
    return rows


def validate_recommendation_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) != EXPECTED_RECOMMENDATION_COUNT:
        raise ValueError(f"Expected {EXPECTED_RECOMMENDATION_COUNT} recommendation rows, found {len(rows)}")
    identities = [arm_identity(row) for row in rows]
    if len(set(identities)) != EXPECTED_RECOMMENDATION_COUNT:
        raise ValueError("Recommendation ledger contains duplicate arm identities")
    provider_counts = Counter(row["provider"] for row in rows)
    model_counts = Counter(row["requested_model"] for row in rows)
    pack_counts = Counter(row["pack"] for row in rows)
    prior_status_counts = Counter(row["current_status"] for row in rows)
    new_status_counts = Counter(row["recommended_status"] for row in rows)
    if provider_counts != Counter({ALLOWED_PROVIDER: EXPECTED_RECOMMENDATION_COUNT}):
        raise ValueError(f"Unexpected provider counts: {provider_counts}")
    if model_counts != Counter({ALLOWED_MODEL: EXPECTED_RECOMMENDATION_COUNT}):
        raise ValueError(f"Unexpected model counts: {model_counts}")
    if dict(pack_counts) != EXPECTED_PACK_COUNTS:
        raise ValueError(f"Unexpected pack counts: {pack_counts}")
    if prior_status_counts != Counter({ALLOWED_PRIOR_STATUS: EXPECTED_RECOMMENDATION_COUNT}):
        raise ValueError(f"Unexpected prior-status counts: {prior_status_counts}")
    if new_status_counts != Counter({ALLOWED_NEW_STATUS: EXPECTED_RECOMMENDATION_COUNT}):
        raise ValueError(f"Unexpected recommended-status counts: {new_status_counts}")
    return {
        "recommendation_count": len(rows),
        "unique_arm_count": len(set(identities)),
        "provider_counts": dict(sorted(provider_counts.items())),
        "model_counts": dict(sorted(model_counts.items())),
        "pack_counts": dict(sorted(pack_counts.items())),
        "prior_status_counts": dict(sorted(prior_status_counts.items())),
        "new_status_counts": dict(sorted(new_status_counts.items())),
    }


def build_matrix(
    *,
    output_root: Path = OUTPUT_ROOT,
    fixed_timestamp: str | None = None,
) -> dict[str, Any]:
    prior_rows = load_prior_matrix_rows()
    recommendation_rows = load_recommendation_rows()
    recommendation_validation = validate_recommendation_rows(recommendation_rows)
    prior_episode_count = len({row["episode_id"] for row in prior_rows})
    if prior_episode_count != EXPECTED_EPISODE_COUNT or len(prior_rows) != EXPECTED_ARM_COUNT:
        raise ValueError(
            f"Unexpected prior matrix size: episodes={prior_episode_count}, arms={len(prior_rows)}"
        )

    ts = fixed_timestamp or now()
    seed = {
        "prior_matrix_id": PRIOR_MATRIX_ID,
        "provider_validation_id": PROVIDER_VALIDATION_ID,
        "timestamp": ts,
        "prior_matrix_fingerprint": fingerprint(prior_rows),
        "recommendation_fingerprint": fingerprint(recommendation_rows),
    }
    run_id = (
        "PPHB-R1-EXECUTION-MATRIX-PROVIDER-READY-"
        + ts.replace(":", "").replace("-", "")
        + "-"
        + hashlib.sha256(canonical_json(seed).encode("utf-8")).hexdigest()[:12]
    )
    run_dir = output_root / run_id

    recommendation_by_arm = {arm_identity(row): row for row in recommendation_rows}

    changed_rows: list[dict[str, Any]] = []
    final_rows: list[dict[str, Any]] = []
    status_transition_counts: Counter[str] = Counter()
    provider_transition_counts: Counter[str] = Counter()
    model_transition_counts: Counter[str] = Counter()
    pack_transition_counts: Counter[str] = Counter()

    for prior in prior_rows:
        row = dict(prior)
        identity = arm_identity(row)
        if identity in recommendation_by_arm:
            recommendation = recommendation_by_arm[identity]
            if row["arm_execution_status"] != ALLOWED_PRIOR_STATUS:
                raise ValueError(f"Prior status mismatch for {identity}: {row['arm_execution_status']}")
            row["arm_execution_status"] = ALLOWED_NEW_STATUS
            row["blocking_reasons"] = []
            row["provider_contract_validation_identity"] = PROVIDER_VALIDATION_ID
            row["provider_contract_change_reason"] = CHANGE_REASON
            row["provider_contract_recommendation_reason"] = recommendation["recommendation_reason"]
            changed_rows.append(
                {
                    "episode_id": row["episode_id"],
                    "provider": row["provider"],
                    "model": row["model"],
                    "pack": row["pack_arm"],
                    "prior_status": prior["arm_execution_status"],
                    "prior_blocker": prior["blocking_reasons"],
                    "new_status": row["arm_execution_status"],
                    "new_blocker": row["blocking_reasons"],
                    "change_reason": CHANGE_REASON,
                    "provider_validation_identity": PROVIDER_VALIDATION_ID,
                    "contract_identity": CONTRACT_IDENTITY,
                }
            )
        final_rows.append(row)
        status_transition = f"{prior['arm_execution_status']}->{row['arm_execution_status']}"
        status_transition_counts[status_transition] += 1
        if prior["arm_execution_status"] != row["arm_execution_status"]:
            provider_transition_counts[f"{row['provider']}:{status_transition}"] += 1
            model_transition_counts[f"{row['model']}:{status_transition}"] += 1
            pack_transition_counts[f"{row['pack_arm']}:{status_transition}"] += 1

    final_rows.sort(key=lambda row: (row["release_ts"], row["episode_id"], row["provider"], row["pack_arm"]))
    changed_rows.sort(key=lambda row: (row["episode_id"], row["provider"], row["pack"]))

    changed_arm_count = len(changed_rows)
    unchanged_arm_count = len(final_rows) - changed_arm_count
    if changed_arm_count != EXPECTED_RECOMMENDATION_COUNT:
        raise ValueError(f"Expected {EXPECTED_RECOMMENDATION_COUNT} changed arms, found {changed_arm_count}")
    if unchanged_arm_count != 2676:
        raise ValueError(f"Expected 2676 unchanged arms, found {unchanged_arm_count}")

    final_status_counts = Counter(row["arm_execution_status"] for row in final_rows)
    expected_final_counts = {
        "EXISTING_IMMUTABLE_RESULT": 170,
        "READY_FOR_EXECUTION": 118,
        "BLOCKED_PROVIDER_CONTRACT": 0,
        "BLOCKED_ATTENTION_RECONSTRUCTION": 2478,
        "BLOCKED_PACK_UNAVAILABLE": 6,
    }
    actual_final_counts = {status: final_status_counts.get(status, 0) for status in expected_final_counts}
    if actual_final_counts != expected_final_counts:
        raise ValueError(f"Unexpected final status counts: {actual_final_counts}")

    opec_rows = [row for row in final_rows if row["episode_id"] == OPEC_EPISODE_ID]
    if len(opec_rows) != 6:
        raise ValueError(f"Expected 6 OPEC rows, found {len(opec_rows)}")
    if any(row["arm_execution_status"] != "BLOCKED_PACK_UNAVAILABLE" for row in opec_rows):
        raise ValueError("OPEC arms changed unexpectedly")
    if any(row["blocking_reasons"] != [OUT_OF_SESSION_BLOCKER] for row in opec_rows):
        raise ValueError("OPEC blocker reasons changed unexpectedly")

    immutable_count = sum(row["arm_execution_status"] == "EXISTING_IMMUTABLE_RESULT" for row in final_rows)
    attention_blocked_count = sum(row["arm_execution_status"] == "BLOCKED_ATTENTION_RECONSTRUCTION" for row in final_rows)
    provider_blocked_count = sum(row["arm_execution_status"] == "BLOCKED_PROVIDER_CONTRACT" for row in final_rows)
    ready_count = sum(row["arm_execution_status"] == "READY_FOR_EXECUTION" for row in final_rows)
    pack_unavailable_count = sum(row["arm_execution_status"] == "BLOCKED_PACK_UNAVAILABLE" for row in final_rows)

    prior_status_counts = dict(sorted(Counter(row["arm_execution_status"] for row in prior_rows).items()))
    final_status_counts_dict = dict(sorted(actual_final_counts.items()))
    matrix_reconciliation = {
        "prior_matrix_identity": PRIOR_MATRIX_ID,
        "new_matrix_identity": run_id,
        "prior_episode_count": prior_episode_count,
        "new_episode_count": len({row["episode_id"] for row in final_rows}),
        "prior_arm_count": len(prior_rows),
        "new_arm_count": len(final_rows),
        "changed_arm_count": changed_arm_count,
        "unchanged_arm_count": unchanged_arm_count,
        "prior_status_counts": prior_status_counts,
        "new_status_counts": final_status_counts_dict,
        "status_transition_counts": dict(sorted(status_transition_counts.items())),
        "per_provider_transitions": dict(sorted(provider_transition_counts.items())),
        "per_model_transitions": dict(sorted(model_transition_counts.items())),
        "per_pack_transitions": dict(sorted(pack_transition_counts.items())),
        "unexpected_differences": [],
        "scientific_fingerprint": fingerprint(
            {
                "recommendation_rows": recommendation_rows,
                "status_transition_counts": dict(sorted(status_transition_counts.items())),
                "final_status_counts": final_status_counts_dict,
                "changed_rows": changed_rows,
            }
        ),
    }

    execution_readiness_summary = {
        "episode_count": len({row["episode_id"] for row in final_rows}),
        "arm_count": len(final_rows),
        "existing_immutable_result_count": immutable_count,
        "ready_for_execution_count": ready_count,
        "blocked_provider_contract_count": provider_blocked_count,
        "blocked_attention_reconstruction_count": attention_blocked_count,
        "blocked_pack_unavailable_count": pack_unavailable_count,
        "provider_ready_update_applied": True,
    }

    provider_matrix_update_contract = {
        "prior_matrix_identity": PRIOR_MATRIX_ID,
        "provider_validation_identity": PROVIDER_VALIDATION_ID,
        "recommendation_artifact_path": path_ref(RECOMMENDATION_PATH),
        "recommendation_artifact_fingerprint": fingerprint(recommendation_rows),
        "allowed_provider": ALLOWED_PROVIDER,
        "allowed_model": ALLOWED_MODEL,
        "allowed_prior_status": ALLOWED_PRIOR_STATUS,
        "allowed_new_status": ALLOWED_NEW_STATUS,
        "expected_recommendation_count": EXPECTED_RECOMMENDATION_COUNT,
        "expected_pack_counts": EXPECTED_PACK_COUNTS,
        "immutability_rules": [
            "Do not modify the prior rescue-final matrix in place",
            "Do not change immutable-result rows",
            "Do not change Attention-reconstruction rows",
            "Do not change OPEC out-of-session rows",
        ],
        "fail_closed_rules": [
            "Abort if recommendation count is not exactly 96",
            "Abort if any recommended arm is not Anthropic / claude-haiku-4-5",
            "Abort if any recommended transition is not BLOCKED_PROVIDER_CONTRACT -> READY_FOR_EXECUTION",
            "Abort if pack counts are not 48 / 48",
            "Abort if unrelated rows change",
        ],
    }

    prior_matrix_snapshot = {
        "matrix_identity": PRIOR_MATRIX_ID,
        "matrix_path": path_ref(PRIOR_MATRIX_PATH),
        "matrix_fingerprint": fingerprint(prior_rows),
        "episode_count": prior_episode_count,
        "arm_count": len(prior_rows),
        "status_counts": prior_status_counts,
    }

    matrix_decision = {
        "matrix_update_status": "PROVIDER_MATRIX_UPDATE_COMPLETE",
        "matrix_integrity_decision": "PROVIDER_READY_MATRIX_RECONCILED",
        "main_path_decision": "MAIN_RECONSTRUCTION_PATH_UNCHANGED",
        "next_step_decision": "READY_FOR_ATTENTION_EXECUTION_PLANNING",
        "reason": "Exactly 96 validated Anthropic provider-contract blockers were reclassified to READY_FOR_EXECUTION with no population or non-provider status changes.",
    }

    run_manifest = {
        "run_id": run_id,
        "generated_at": ts,
        "git_head": git_head(),
        "provider_calls": 0,
        "research_ai_calls": 0,
        "market_data_calls": 0,
        "web_calls": 0,
        "google_writes": 0,
        "forecast_execution_calls": 0,
        "prior_matrix_identity": PRIOR_MATRIX_ID,
        "provider_validation_identity": PROVIDER_VALIDATION_ID,
    }

    governing_artifact_manifest = {
        "prior_matrix_path": path_ref(PRIOR_MATRIX_PATH),
        "provider_validation_root": path_ref(PROVIDER_VALIDATION_ROOT),
        "recommendation_path": path_ref(RECOMMENDATION_PATH),
        "contract_identity": CONTRACT_IDENTITY,
        "contract_schema_version": CONTRACT_SCHEMA_VERSION,
    }

    write_json(run_dir / "run_manifest.json", run_manifest)
    write_json(run_dir / "governing_artifact_manifest.json", governing_artifact_manifest)
    write_json(run_dir / "provider_matrix_update_contract.json", provider_matrix_update_contract)
    write_json(run_dir / "prior_matrix_snapshot.json", prior_matrix_snapshot)
    write_jsonl(run_dir / "provider_arm_reclassification.jsonl", changed_rows)
    write_jsonl(run_dir / "provider_ready_execution_matrix.jsonl", final_rows)
    write_json(run_dir / "matrix_reconciliation.json", matrix_reconciliation)
    write_json(run_dir / "execution_readiness_summary.json", execution_readiness_summary)
    write_json(run_dir / "matrix_decision.json", matrix_decision)

    return {
        "run_id": run_id,
        "run_dir": run_dir,
        "recommendation_validation": recommendation_validation,
        "prior_status_counts": prior_status_counts,
        "final_status_counts": final_status_counts_dict,
        "status_transition_counts": dict(sorted(status_transition_counts.items())),
        "per_provider_transitions": dict(sorted(provider_transition_counts.items())),
        "per_model_transitions": dict(sorted(model_transition_counts.items())),
        "per_pack_transitions": dict(sorted(pack_transition_counts.items())),
        "changed_arm_count": changed_arm_count,
        "unchanged_arm_count": unchanged_arm_count,
        "ready_count": ready_count,
        "provider_blocked_count": provider_blocked_count,
        "immutable_count": immutable_count,
        "attention_blocked_count": attention_blocked_count,
        "pack_unavailable_count": pack_unavailable_count,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--fixed-timestamp")
    args = parser.parse_args(argv)
    result = build_matrix(output_root=args.output_root, fixed_timestamp=args.fixed_timestamp)
    print(
        json.dumps(
            {
                "run_id": result["run_id"],
                "changed_arm_count": result["changed_arm_count"],
                "ready_count": result["ready_count"],
                "provider_blocked_count": result["provider_blocked_count"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
