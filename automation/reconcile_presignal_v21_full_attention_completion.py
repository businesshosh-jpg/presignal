#!/usr/bin/env python3
"""Reconcile authoritative final Attention results across all 204 planned calls."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import execute_presignal_v21_attention_batch_004 as batch004

PLAN_ID = batch004.PLAN_ID
PLAN_ROOT = batch004.PLAN_ROOT
OUTPUT_ROOT = batch004.OUTPUT_ROOT

AUTHORITATIVE_BATCH_RUNS = {
    "ATTN_BATCH_001": {
        "run_id": "PPHB-R1-ATTENTION-BATCH-001-CLOSED-20260729T035345Z-e3bc0c2909ca",
        "kind": "closure",
        "prior_evidence_runs": [
            "PPHB-R1-ATTENTION-BATCH-001-FINALIZATION-20260729T023607Z-eb4bd2a9277c",
            "PPHB-R1-ATTENTION-BATCH-001-ANTHROPIC-FAILURE-AUDIT-20260729T032157Z-a5ae0ae86b0f",
            "PPHB-R1-ATTENTION-BATCH-001-CORRECTED-FINALIZATION-20260729T033528Z-66166de58345",
            "PPHB-R1-ATTENTION-ANTHROPIC-SHADOW-ALIAS-AUDIT-20260729T035345Z-e3bc0c2909ca",
        ],
    },
    "ATTN_BATCH_002": {
        "run_id": "PPHB-R1-ATTENTION-BATCH-002-CLOSED-20260729T044448Z-97d9ec4cf579",
        "kind": "closure",
        "prior_evidence_runs": [
            "PPHB-R1-ATTENTION-EXECUTION-BATCH-002-20260729T040014Z-e270ec415b79",
            "PPHB-R1-ATTENTION-CONTRACT-REPAIR-BATCH-002-20260729T042144Z-22ef2d6080ef",
            "PPHB-R1-ATTENTION-PROVIDER-AUTHORITY-AUDIT-20260729T044448Z-97d9ec4cf579",
        ],
    },
    "ATTN_BATCH_003": {
        "run_id": "PPHB-R1-ATTENTION-BATCH-003-COMPLETENESS-RETRY-20260729T053347Z-3bbe67af1930",
        "kind": "completeness_retry",
        "prior_evidence_runs": [
            "PPHB-R1-ATTENTION-EXECUTION-BATCH-003-20260729T045507Z-64f3c4f5fc50",
            "PPHB-R1-ATTENTION-ROW-STATUS-AUDIT-BATCH-003-20260729T051700Z-e377782d7d25",
        ],
    },
    "ATTN_BATCH_004": {"run_id": "PPHB-R1-ATTENTION-EXECUTION-BATCH-004-20260729T060007Z-2b28132d61f4", "kind": "execution", "prior_evidence_runs": []},
    "ATTN_BATCH_005": {"run_id": "PPHB-R1-ATTENTION-EXECUTION-BATCH-005-20260729T062307Z-a8d4e499fc50", "kind": "execution", "prior_evidence_runs": []},
    "ATTN_BATCH_006": {"run_id": "PPHB-R1-ATTENTION-EXECUTION-BATCH-006-20260729T063514Z-a9329b56342b", "kind": "execution", "prior_evidence_runs": []},
    "ATTN_BATCH_007": {"run_id": "PPHB-R1-ATTENTION-EXECUTION-BATCH-007-20260729T065113Z-dfd5c326249f", "kind": "execution", "prior_evidence_runs": []},
    "ATTN_BATCH_008": {"run_id": "PPHB-R1-ATTENTION-EXECUTION-BATCH-008-20260729T070157Z-9a7f35ddf62d", "kind": "execution", "prior_evidence_runs": []},
    "ATTN_BATCH_009": {"run_id": "PPHB-R1-ATTENTION-EXECUTION-BATCH-009-20260729T071942Z-6f918ad51b93", "kind": "execution", "prior_evidence_runs": []},
    "ATTN_BATCH_010": {"run_id": "PPHB-R1-ATTENTION-EXECUTION-BATCH-010-20260729T072954Z-a6226ec669a9", "kind": "execution", "prior_evidence_runs": []},
    "ATTN_BATCH_011": {"run_id": "PPHB-R1-ATTENTION-EXECUTION-BATCH-011-20260729T081001Z-a52246208ecd", "kind": "execution", "prior_evidence_runs": []},
    "ATTN_BATCH_012": {"run_id": "PPHB-R1-ATTENTION-EXECUTION-BATCH-012-20260729T081445Z-6b95a2de5cac", "kind": "execution", "prior_evidence_runs": []},
    "ATTN_BATCH_013": {"run_id": "PPHB-R1-ATTENTION-EXECUTION-BATCH-013-20260729T082604Z-f9f471494171", "kind": "execution", "prior_evidence_runs": []},
    "ATTN_BATCH_014": {"run_id": "PPHB-R1-ATTENTION-EXECUTION-BATCH-014-20260729T082854Z-a906012f07c8", "kind": "execution", "prior_evidence_runs": []},
    "ATTN_BATCH_015": {
        "run_id": "PPHB-R1-ATTENTION-EXECUTION-BATCH-015-20260729T093506Z-9cbf6043b4aa",
        "kind": "execution_after_auth_recovery",
        "prior_evidence_runs": [
            "PPHB-R1-ATTENTION-EXECUTION-BATCH-015-20260729T090319Z-a624a4386240",
            "PPHB-R1-ATTENTION-EXECUTION-BATCHES-015-016-20260729T090318Z-9e64f5d6f733",
            "PPHB-R1-ATTENTION-AUTH-RECOVERY-AND-BATCHES-015-016-20260729T093506Z-c17b34484144",
        ],
    },
    "ATTN_BATCH_016": {
        "run_id": "PPHB-R1-ATTENTION-EXECUTION-BATCH-016-20260729T093902Z-d591d2f9d944",
        "kind": "execution_after_auth_recovery",
        "prior_evidence_runs": [
            "PPHB-R1-ATTENTION-AUTH-RECOVERY-AND-BATCHES-015-016-20260729T093506Z-c17b34484144",
        ],
    },
}


def canonical_json(value: Any) -> str:
    return batch004.canonical_json(value)


def now() -> str:
    return batch004.now()


def write_json(path: Path, value: Any) -> None:
    batch004.write_json(path, value)


def write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    batch004.write_jsonl(path, rows)


def materialize_run(output_root: Path, final_batch_017_run_id: str, fixed_timestamp: str | None = None) -> Path:
    ts = fixed_timestamp or now()
    seed = {"plan_id": PLAN_ID, "timestamp": ts, "final_batch_017_run_id": final_batch_017_run_id, "move": "FULL_ATTENTION_COMPLETION"}
    run_id = (
        "PPHB-R1-ATTENTION-EXECUTION-FULL-COMPLETION-"
        + ts.replace(":", "").replace("-", "")
        + "-"
        + hashlib.sha256(canonical_json(seed).encode("utf-8")).hexdigest()[:12]
    )
    return output_root / run_id


def load_plan_batch_ids() -> list[str]:
    batch_data = batch004.read_json(PLAN_ROOT / "attention_call_batches.json")
    if isinstance(batch_data.get("batches"), list):
        return [str(row["batch_id"]) for row in batch_data["batches"] if str(row.get("batch_id", "")).startswith("ATTN_BATCH_")]
    batch_ids = sorted(batch_data.keys())
    return [batch_id for batch_id in batch_ids if str(batch_id).startswith("ATTN_BATCH_")]


def plan_calls_by_batch() -> dict[str, list[dict[str, Any]]]:
    return {batch_id: batch004.base.load_batch_calls(batch_id) for batch_id in load_plan_batch_ids()}


def build_authoritative_batch_runs(final_batch_017_run_id: str) -> dict[str, dict[str, Any]]:
    return {
        **AUTHORITATIVE_BATCH_RUNS,
        "ATTN_BATCH_017": {
            "run_id": final_batch_017_run_id,
            "kind": "execution",
            "prior_evidence_runs": [],
        },
    }


def first_existing_path(run_dir: Path, candidates: list[str]) -> Path:
    for candidate in candidates:
        path = run_dir / candidate
        if path.exists():
            return path
    raise FileNotFoundError(f"No expected artifact found in {run_dir} for candidates={candidates!r}")


def execute_reconciliation(
    *,
    final_batch_017_run_dir: Path,
    output_root: Path = OUTPUT_ROOT,
    fixed_timestamp: str | None = None,
) -> dict[str, Any]:
    final_batch_017_run_id = final_batch_017_run_dir.name
    authoritative_runs = build_authoritative_batch_runs(final_batch_017_run_id)
    batch_calls = plan_calls_by_batch()
    run_dir = materialize_run(output_root=output_root, final_batch_017_run_id=final_batch_017_run_id, fixed_timestamp=fixed_timestamp)
    run_dir.mkdir(parents=True, exist_ok=True)

    write_json(
        run_dir / "run_manifest.json",
        {
            "plan_id": PLAN_ID,
            "move": "FULL_ATTENTION_COMPLETION",
            "authoritative_batch_count": len(authoritative_runs),
            "final_batch_017_run_id": final_batch_017_run_id,
        },
    )
    write_json(
        run_dir / "governing_artifact_manifest.json",
        {
            "plan_id": PLAN_ID,
            "authoritative_batch_runs": authoritative_runs,
            "blocked_runs_not_counted_as_valid": [
                "PPHB-R1-ATTENTION-EXECUTION-BATCHES-015-016-20260729T090318Z-9e64f5d6f733",
                "PPHB-R1-ATTENTION-EXECUTION-BATCH-015-20260729T090319Z-a624a4386240",
            ],
        },
    )

    frozen_inventory: list[dict[str, Any]] = []
    for batch_id, calls in batch_calls.items():
        for row in calls:
            frozen_inventory.append(
                {
                    "batch_id": batch_id,
                    "call_id": row["call_id"],
                    "provider": row["provider"],
                    "model": row["model"],
                    "source_session_id": row["source_session_id"],
                    "episode_ids": list(row["episode_ids"]),
                }
            )
    write_jsonl(run_dir / "frozen_call_inventory.jsonl", frozen_inventory)

    authoritative_inventory: list[dict[str, Any]] = []
    call_rows: list[dict[str, Any]] = []
    by_provider_model: Counter[str] = Counter()
    by_batch: Counter[str] = Counter()
    sessions: set[str] = set()
    episode_ids: set[str] = set()
    mapping_count = 0
    duplicates: list[dict[str, Any]] = []
    seen_call_ids: dict[str, dict[str, Any]] = {}

    for batch_id in load_plan_batch_ids():
        run_id = authoritative_runs[batch_id]["run_id"]
        batch_run_dir = output_root / run_id
        normalized_rows = batch004.read_jsonl(
            first_existing_path(
                batch_run_dir,
                [
                    "normalized_attention_results.jsonl",
                    "final_normalized_attention_results.jsonl",
                ],
            )
        )
        batch_summary = batch004.read_json(
            first_existing_path(
                batch_run_dir,
                [
                    "batch_summary.json",
                    "batch_001_summary.json",
                    "batch_002_summary.json",
                    "batch_003_summary.json",
                ],
            )
        )
        batch_decision = batch004.read_json(
            first_existing_path(
                batch_run_dir,
                [
                    "batch_decision.json",
                    "batch_001_decision.json",
                    "batch_002_decision.json",
                    "batch_003_decision.json",
                ],
            )
        )
        successful_valid_calls = int(
            batch_summary.get(
                "successful_valid_calls",
                batch_summary.get("final_validated_results", len(normalized_rows)),
            )
        )
        normalized_result_count = int(batch_summary.get("normalized_result_count", len(normalized_rows)))
        authoritative_inventory.append(
            {
                "batch_id": batch_id,
                "run_id": run_id,
                "run_dir": str(batch_run_dir),
                "kind": authoritative_runs[batch_id]["kind"],
                "successful_valid_calls": successful_valid_calls,
                "normalized_result_count": normalized_result_count,
                "decision": batch_decision,
                "prior_evidence_runs": authoritative_runs[batch_id]["prior_evidence_runs"],
            }
        )
        for row in normalized_rows:
            call_id = row["call_id"]
            result_fingerprint = row.get("result_fingerprint") or batch004.base.sha256_text(row)
            if call_id in seen_call_ids:
                duplicates.append(
                    {
                        "call_id": call_id,
                        "first_run_id": seen_call_ids[call_id]["run_id"],
                        "duplicate_run_id": run_id,
                        "first_result_fingerprint": seen_call_ids[call_id]["result_fingerprint"],
                        "duplicate_result_fingerprint": result_fingerprint,
                    }
                )
            seen_call_ids[call_id] = {"run_id": run_id, "result_fingerprint": result_fingerprint}
            by_provider_model[f"{row['provider']}|{row['model']}"] += 1
            by_batch[batch_id] += 1
            sessions.add(row["source_session_id"])
            call_rows.append(
                {
                    "call_id": call_id,
                    "batch_id": batch_id,
                    "authoritative_run_id": run_id,
                    "authoritative_run_dir": str(batch_run_dir),
                    "provider": row["provider"],
                    "model": row["model"],
                    "source_session_id": row["source_session_id"],
                    "result_fingerprint": result_fingerprint,
                    "non_authoritative_evidence_runs": authoritative_runs[batch_id]["prior_evidence_runs"],
                }
            )
        mapping_rows = batch004.read_jsonl(
            first_existing_path(
                batch_run_dir,
                [
                    "episode_attention_result_map.jsonl",
                    "final_episode_attention_result_map.jsonl",
                ],
            )
        )
        mapping_count += len(mapping_rows)
        for row in mapping_rows:
            episode_ids.add(row["episode_id"])

    write_jsonl(run_dir / "authoritative_batch_result_inventory.jsonl", authoritative_inventory)

    frozen_call_ids = {row["call_id"] for row in frozen_inventory}
    authoritative_call_ids = {row["call_id"] for row in call_rows}
    missing_call_ids = sorted(frozen_call_ids - authoritative_call_ids)
    unexpected_call_ids = sorted(authoritative_call_ids - frozen_call_ids)

    reconciliation_rows: list[dict[str, Any]] = []
    by_call = {row["call_id"]: row for row in call_rows}
    for frozen_row in frozen_inventory:
        authoritative = by_call.get(frozen_row["call_id"])
        reconciliation_rows.append(
            {
                **frozen_row,
                "completion_status": "VALIDATED" if authoritative else "MISSING",
                "authoritative_run_id": authoritative["authoritative_run_id"] if authoritative else None,
                "authoritative_result_fingerprint": authoritative["result_fingerprint"] if authoritative else None,
                "non_authoritative_evidence_runs": authoritative["non_authoritative_evidence_runs"] if authoritative else [],
            }
        )
    write_jsonl(run_dir / "call_completion_reconciliation.jsonl", reconciliation_rows)
    write_jsonl(run_dir / "duplicate_call_audit.jsonl", duplicates)
    write_jsonl(
        run_dir / "remaining_failed_calls.jsonl",
        [{"call_id": call_id, "reason": "MISSING_AUTHORITATIVE_VALIDATED_RESULT"} for call_id in missing_call_ids],
    )

    write_json(
        run_dir / "provider_model_reconciliation.json",
        {
            "validated_calls_by_provider_model": dict(sorted(by_provider_model.items())),
            "unexpected_call_ids": unexpected_call_ids,
            "duplicate_authoritative_result_ids": [row["call_id"] for row in duplicates],
        },
    )
    write_json(
        run_dir / "session_coverage_reconciliation.json",
        {
            "total_sessions_represented": len(sessions),
            "session_ids": sorted(sessions),
            "validated_calls_by_batch": dict(sorted(by_batch.items())),
        },
    )
    write_json(
        run_dir / "episode_mapping_reconciliation.json",
        {
            "total_episode_ids_mapped": len(episode_ids),
            "total_episode_provider_mappings": mapping_count,
        },
    )

    summary = {
        "frozen_planned_call_count": len(frozen_inventory),
        "unique_frozen_call_id_count": len(frozen_call_ids),
        "authoritative_validated_call_result_count": len(call_rows),
        "missing_call_ids": missing_call_ids,
        "duplicate_authoritative_result_ids": sorted({row["call_id"] for row in duplicates}),
        "unexpected_call_ids": unexpected_call_ids,
        "validated_calls_by_batch": dict(sorted(by_batch.items())),
        "validated_calls_by_provider_model": dict(sorted(by_provider_model.items())),
        "total_sessions_represented": len(sessions),
        "total_episodes_mapped": len(episode_ids),
        "total_episode_provider_mappings": mapping_count,
        "remaining_failed_call_count": len(missing_call_ids),
        "blocked_runs_counted_as_valid": 0,
        "repaired_or_retried_calls_double_counted": len(duplicates),
    }
    write_json(run_dir / "full_attention_summary.json", summary)

    if len(frozen_inventory) == 204 and len(frozen_call_ids) == 204 and len(call_rows) == 204 and not missing_call_ids and not duplicates and not unexpected_call_ids:
        decision = {
            "full_attention_completion_decision": "FULL_ATTENTION_204_CALL_POPULATION_COMPLETE",
            "next_phase_decision": "READY_FOR_ATTENTION_RESULT_CONSOLIDATION",
        }
    elif missing_call_ids or duplicates or unexpected_call_ids:
        decision = {
            "full_attention_completion_decision": "FULL_ATTENTION_POPULATION_INCOMPLETE",
            "next_phase_decision": "RECONCILIATION_REPAIR_REQUIRED" if duplicates or unexpected_call_ids else "REPAIR_REMAINING_ATTENTION_CALLS",
        }
    else:
        decision = {
            "full_attention_completion_decision": "FULL_ATTENTION_RECONCILIATION_BLOCKED",
            "next_phase_decision": "RECONCILIATION_REPAIR_REQUIRED",
        }
    write_json(run_dir / "full_attention_decision.json", decision)

    return {
        "run_dir": run_dir,
        "summary": summary,
        "decision": decision,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-017-run-dir", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--fixed-timestamp")
    args = parser.parse_args(argv)
    result = execute_reconciliation(
        final_batch_017_run_dir=args.batch_017_run_dir,
        output_root=args.output_root,
        fixed_timestamp=args.fixed_timestamp,
    )
    print(
        json.dumps(
            {
                "run_dir": str(result["run_dir"]),
                "full_attention_completion_decision": result["decision"]["full_attention_completion_decision"],
                "authoritative_validated_call_result_count": result["summary"]["authoritative_validated_call_result_count"],
                "remaining_failed_call_count": result["summary"]["remaining_failed_call_count"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
