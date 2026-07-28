#!/usr/bin/env python3
"""Create the final rescue-aware Round 1 execution matrix."""
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

from zoneinfo import ZoneInfo

PRIOR_MATRIX_ID = "PPHB-R1-ELIGIBILITY-IMPLEMENTATION-20260728T132849Z-297192188403"
RECONSTRUCTION_DRY_RUN_ID = "PPHB-R1-RECONSTRUCTION-DRY-RUN-20260728T134639Z-b3c9532ef93e"
US_SESSION_JOIN_AUDIT_ID = "PPHB-R1-73-EPISODE-US-SESSION-JOIN-AUDIT-20260728T153350749590Z-5c8af86038c5"
FINAL_RESCUE_AUDIT_ID = "PPHB-R1-REMAINING-65-EVENT-DATE-RESCUE-20260728T155538056417Z-3b8ea248781e"

PRIOR_MATRIX_ROOT = (
    ROOT / "outputs" / "presignal_v21_full_round_1_eligibility_implementation" / PRIOR_MATRIX_ID
)
RECONSTRUCTION_ROOT = (
    ROOT / "outputs" / "presignal_v21_full_round_1_reconstruction_dry_run" / RECONSTRUCTION_DRY_RUN_ID
)
US_SESSION_ROOT = (
    ROOT / "outputs" / "presignal_v21_73_execution_blocked_episode_rescue" / US_SESSION_JOIN_AUDIT_ID
)
FINAL_RESCUE_ROOT = (
    ROOT / "outputs" / "presignal_v21_73_execution_blocked_episode_rescue" / FINAL_RESCUE_AUDIT_ID
)
EPISODE_ROWS_PATH = ROOT / "outputs" / "presignal_v21_episode_builder" / "episode_rows.jsonl"
OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_execution_matrix"

PROMOTABLE_CLASSIFICATIONS = {
    "RECOVERABLE_EXACT",
    "RECOVERABLE_BY_DETERMINISTIC_LINK_REPAIR",
    "RECOVERABLE_BY_DETERMINISTIC_EVENT_DATE_LINK",
}
OPEC_EPISODE_ID = "EP_EVENT_67dc98eaf62822136db2"
TIMEZONE_NAME = "America/New_York"
OUT_OF_SESSION_BLOCKER = "OUT_OF_NORMAL_SESSION_EVENT_LEVEL_ROUTE_PENDING"


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


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def load_prior_matrix_rows() -> list[dict[str, Any]]:
    rows = read_jsonl(PRIOR_MATRIX_ROOT / "expected_arm_ledger.jsonl")
    rows.sort(key=lambda row: (row["release_ts"], row["episode_id"], row["provider"], row["pack_arm"]))
    return rows


def load_episode_rows() -> dict[str, dict[str, Any]]:
    return {row["episode_id"]: row for row in read_jsonl(EPISODE_ROWS_PATH)}


def load_promotion_candidates() -> list[dict[str, Any]]:
    rows = read_jsonl(FINAL_RESCUE_ROOT / "promotion_candidates.jsonl")
    rows.sort(key=lambda row: (row["release_ts_utc"], row["episode_id"]))
    return rows


def to_us_eastern(release_ts_utc: str) -> tuple[str, str, str]:
    release_dt = datetime.fromisoformat(release_ts_utc.replace("Z", "+00:00"))
    local_dt = release_dt.astimezone(ZoneInfo(TIMEZONE_NAME))
    utc_text = release_dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return utc_text, local_dt.isoformat(), local_dt.date().isoformat()


def derive_calendar_day_type(date_text: str) -> str:
    dt = datetime.fromisoformat(date_text)
    return "WEEKEND" if dt.weekday() >= 5 else "WEEKDAY"


def validate_promotion_candidates(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) != 72:
        raise ValueError(f"Expected 72 promotion candidates, found {len(rows)}")
    episode_ids = [row["episode_id"] for row in rows]
    if len(set(episode_ids)) != 72:
        raise ValueError("Promotion candidate Episode IDs are not unique")
    if OPEC_EPISODE_ID in episode_ids:
        raise ValueError("Out-of-session OPEC Episode is present in normal promotion candidates")
    invalid = [row for row in rows if row["final_classification"] not in PROMOTABLE_CLASSIFICATIONS]
    if invalid:
        raise ValueError(f"Promotion candidates include unauthorized classifications: {invalid[:3]}")
    return {
        "candidate_count": len(rows),
        "unique_episode_count": len(set(episode_ids)),
        "classification_counts": dict(sorted(Counter(row["final_classification"] for row in rows).items())),
    }


def build_matrix(
    *,
    output_root: Path = OUTPUT_ROOT,
    fixed_timestamp: str | None = None,
) -> dict[str, Any]:
    prior_rows = load_prior_matrix_rows()
    promotion_rows = load_promotion_candidates()
    validation = validate_promotion_candidates(promotion_rows)
    episode_rows = load_episode_rows()
    prior_summary = read_json(PRIOR_MATRIX_ROOT / "arm_executability_summary.json")
    prior_dry_run = read_json(PRIOR_MATRIX_ROOT / "dry_run_summary.json")

    prior_episode_count = len({row["episode_id"] for row in prior_rows})
    prior_arm_count = len(prior_rows)
    if prior_episode_count != 462 or prior_arm_count != 2772:
        raise ValueError(f"Unexpected prior matrix size: episodes={prior_episode_count}, arms={prior_arm_count}")

    promotion_by_episode = {row["episode_id"]: row for row in promotion_rows}

    ts = fixed_timestamp or now()
    seed = {
        "prior_matrix_id": PRIOR_MATRIX_ID,
        "rescue_audit_id": FINAL_RESCUE_AUDIT_ID,
        "timestamp": ts,
        "prior_matrix_fingerprint": fingerprint(prior_rows),
        "promotion_candidate_fingerprint": fingerprint(promotion_rows),
    }
    run_id = (
        "PPHB-R1-EXECUTION-MATRIX-RESCUE-FINAL-"
        + ts.replace(":", "").replace("-", "")
        + "-"
        + hashlib.sha256(canonical_json(seed).encode("utf-8")).hexdigest()[:12]
    )
    run_dir = output_root / run_id

    utc_text, eastern_text, eastern_date = to_us_eastern("2024-06-02T03:00:00Z")
    if utc_text != "2024-06-02T03:00:00Z":
        raise ValueError("Unexpected OPEC UTC normalization")

    promoted_episode_ledger: list[dict[str, Any]] = []
    affected_arm_reclassification: list[dict[str, Any]] = []
    final_rows: list[dict[str, Any]] = []

    for candidate in promotion_rows:
        promoted_episode_ledger.append(
            {
                "episode_id": candidate["episode_id"],
                "episode_type": candidate["episode_type"],
                "release_ts_utc": candidate["release_ts_utc"],
                "release_ts_us_eastern": candidate["release_ts_us_eastern"],
                "derived_us_session_date": candidate["derived_us_session_date"],
                "selected_session_id": candidate["selected_session_id"],
                "promotion_basis": candidate["final_classification"],
                "classification_transition": candidate["classification_transition"],
                "route_complete": candidate["route_complete"],
                "promoted_through_normal_session_route": True,
                "affected_arm_count": 6,
            }
        )

    for prior in prior_rows:
        row = dict(prior)
        episode_id = row["episode_id"]
        route_category = "UNCHANGED"
        route_state = "UNCHANGED"
        event_level_route_status = "NOT_APPLICABLE"
        rescue_source = ""
        rescue_classification = ""
        rescue_scientific_interpretation = ""
        derived_us_session_date = None
        release_ts_us_eastern = None
        calendar_day_type = None

        if episode_id in promotion_by_episode:
            promotion = promotion_by_episode[episode_id]
            route_category = "NORMAL_SESSION_RESCUE_PROMOTED"
            route_state = "NORMAL_SESSION_LINKED"
            rescue_source = promotion["selected_session_id"]
            rescue_classification = promotion["final_classification"]
            rescue_scientific_interpretation = "NORMAL_SESSION_LINEAGE_RESCUED"
            derived_us_session_date = promotion["derived_us_session_date"]
            release_ts_us_eastern = promotion["release_ts_us_eastern"]

            row["attention_status"] = "ATTENTION_RECONSTRUCTABLE"
            row["pack_status"] = "PACK_RECONSTRUCTABLE"
            row["arm_execution_status"] = "BLOCKED_ATTENTION_RECONSTRUCTION"
            row["blocking_reasons"] = [
                "ATTENTION_RECONSTRUCTION_REQUIRED",
                "PACK_RECONSTRUCTION_REQUIRED",
            ]

        elif episode_id == OPEC_EPISODE_ID:
            route_category = "OUT_OF_SESSION_PENDING"
            route_state = "OUT_OF_NORMAL_SESSION"
            event_level_route_status = "NOT_YET_VALIDATED"
            rescue_scientific_interpretation = "VALID_EVENT_EPISODE_OUT_OF_NORMAL_SESSION_PENDING_EVENT_LEVEL_ROUTE"
            derived_us_session_date = eastern_date
            release_ts_us_eastern = eastern_text
            calendar_day_type = derive_calendar_day_type(eastern_date)
            row["blocking_reasons"] = [OUT_OF_SESSION_BLOCKER]

        row["rescue_matrix_category"] = route_category
        row["normal_session_status"] = route_state
        row["normal_session_id"] = rescue_source or None
        row["event_level_route_status"] = event_level_route_status
        row["rescue_recovery_classification"] = rescue_classification or None
        row["rescue_scientific_interpretation"] = rescue_scientific_interpretation or None
        row["derived_us_session_date"] = derived_us_session_date
        row["release_ts_us_eastern"] = release_ts_us_eastern
        row["calendar_day_type"] = calendar_day_type

        final_rows.append(row)

        changed = (
            row["arm_execution_status"] != prior["arm_execution_status"]
            or row["attention_status"] != prior["attention_status"]
            or row["pack_status"] != prior["pack_status"]
            or row["blocking_reasons"] != prior["blocking_reasons"]
            or row["rescue_matrix_category"] != "UNCHANGED"
        )
        if changed:
            affected_arm_reclassification.append(
                {
                    "expected_arm_identity": row["expected_arm_identity"],
                    "episode_id": episode_id,
                    "provider": row["provider"],
                    "pack_arm": row["pack_arm"],
                    "release_ts": row["release_ts"],
                    "prior_arm_execution_status": prior["arm_execution_status"],
                    "final_arm_execution_status": row["arm_execution_status"],
                    "prior_attention_status": prior["attention_status"],
                    "final_attention_status": row["attention_status"],
                    "prior_pack_status": prior["pack_status"],
                    "final_pack_status": row["pack_status"],
                    "prior_blocking_reasons": prior["blocking_reasons"],
                    "final_blocking_reasons": row["blocking_reasons"],
                    "rescue_matrix_category": route_category,
                    "normal_session_status": route_state,
                    "normal_session_id": rescue_source or None,
                    "event_level_route_status": event_level_route_status,
                }
            )

    final_rows.sort(key=lambda row: (row["release_ts"], row["episode_id"], row["provider"], row["pack_arm"]))
    affected_arm_reclassification.sort(key=lambda row: row["expected_arm_identity"])
    promoted_episode_ledger.sort(key=lambda row: (row["release_ts_utc"], row["episode_id"]))

    final_episode_count = len({row["episode_id"] for row in final_rows})
    final_arm_count = len(final_rows)
    if final_episode_count != 462 or final_arm_count != 2772:
        raise ValueError(f"Unexpected final matrix size: episodes={final_episode_count}, arms={final_arm_count}")

    changed_arm_count = len(affected_arm_reclassification)
    unchanged_arm_count = final_arm_count - changed_arm_count
    normal_promotion_changed_count = sum(
        row["rescue_matrix_category"] == "NORMAL_SESSION_RESCUE_PROMOTED" for row in affected_arm_reclassification
    )
    if normal_promotion_changed_count > 432:
        raise ValueError(f"Normal rescue changed too many arms: {normal_promotion_changed_count}")

    prior_status_counts = dict(sorted(Counter(row["arm_execution_status"] for row in prior_rows).items()))
    final_status_counts = dict(sorted(Counter(row["arm_execution_status"] for row in final_rows).items()))
    if len(prior_rows) != len(final_rows):
        raise ValueError("Prior and final matrix row counts differ")
    status_transition_counts = dict(
        sorted(
            Counter(
                f"{prior['arm_execution_status']}->{final['arm_execution_status']}"
                for prior, final in zip(prior_rows, final_rows)
            ).items()
        )
    )

    opec_rows = [row for row in final_rows if row["episode_id"] == OPEC_EPISODE_ID]
    if len(opec_rows) != 6:
        raise ValueError(f"OPEC episode arm count mismatch: {len(opec_rows)}")
    if any(row["normal_session_status"] != "OUT_OF_NORMAL_SESSION" for row in opec_rows):
        raise ValueError("OPEC episode was assigned a normal session status")
    if any(row["event_level_route_status"] != "NOT_YET_VALIDATED" for row in opec_rows):
        raise ValueError("OPEC episode event-level route status is inconsistent")
    if any(row["blocking_reasons"] != [OUT_OF_SESSION_BLOCKER] for row in opec_rows):
        raise ValueError("OPEC episode blocker reason is inconsistent")
    if any(row["arm_execution_status"] == "READY_FOR_EXECUTION" for row in opec_rows):
        raise ValueError("OPEC episode arms became executable")

    opec_episode = episode_rows[OPEC_EPISODE_ID]
    out_of_session_episode_ledger = [
        {
            "episode_id": OPEC_EPISODE_ID,
            "event_name": opec_episode["primary_indicator_name"],
            "release_ts_utc": utc_text,
            "release_ts_us_eastern": eastern_text,
            "derived_us_date": eastern_date,
            "calendar_day_type": derive_calendar_day_type(eastern_date),
            "prior_classification": "NO_RECOVERY_ROUTE",
            "revised_scientific_interpretation": "VALID_EVENT_EPISODE_OUT_OF_NORMAL_SESSION_PENDING_EVENT_LEVEL_ROUTE",
            "normal_session_id": None,
            "normal_session_status": "OUT_OF_NORMAL_SESSION",
            "event_level_route_status": "NOT_YET_VALIDATED",
            "arm_count": 6,
            "arm_execution_statuses": sorted({row["arm_execution_status"] for row in opec_rows}),
            "blocker_reason": OUT_OF_SESSION_BLOCKER,
            "supporting_evidence": {
                "episode_row": path_ref(EPISODE_ROWS_PATH),
                "us_session_join_audit": path_ref(US_SESSION_ROOT / "session_date_join_audit.jsonl"),
                "final_rescue_audit": path_ref(FINAL_RESCUE_ROOT / "final_recovery_classification.jsonl"),
            },
        }
    ]

    prior_matrix_snapshot = {
        "prior_matrix_id": PRIOR_MATRIX_ID,
        "prior_matrix_path": path_ref(PRIOR_MATRIX_ROOT / "expected_arm_ledger.jsonl"),
        "prior_matrix_fingerprint": fingerprint(prior_rows),
        "prior_episode_count": prior_episode_count,
        "prior_arm_count": prior_arm_count,
        "prior_status_counts": prior_status_counts,
        "prior_dry_run_summary_path": path_ref(PRIOR_MATRIX_ROOT / "dry_run_summary.json"),
        "prior_arm_summary_path": path_ref(PRIOR_MATRIX_ROOT / "arm_executability_summary.json"),
        "prior_dry_run_summary": prior_dry_run,
        "prior_arm_executability_summary": prior_summary,
    }

    execution_readiness_summary = {
        "newly_ready_arm_count": sum(
            prior["arm_execution_status"] != "READY_FOR_EXECUTION" and final["arm_execution_status"] == "READY_FOR_EXECUTION"
            for prior, final in zip(prior_rows, final_rows)
        ),
        "newly_attention_reconstructable_arm_count": sum(
            prior["attention_status"] != "ATTENTION_RECONSTRUCTABLE" and final["attention_status"] == "ATTENTION_RECONSTRUCTABLE"
            for prior, final in zip(prior_rows, final_rows)
        ),
        "remaining_provider_contract_blocked_arm_count": final_status_counts.get("BLOCKED_PROVIDER_CONTRACT", 0),
        "remaining_pack_unavailable_arm_count": final_status_counts.get("BLOCKED_PACK_UNAVAILABLE", 0),
        "immutable_result_count": final_status_counts.get("EXISTING_IMMUTABLE_RESULT", 0),
        "ready_for_execution_count": final_status_counts.get("READY_FOR_EXECUTION", 0),
        "blocked_attention_reconstruction_count": final_status_counts.get("BLOCKED_ATTENTION_RECONSTRUCTION", 0),
    }

    matrix_reconciliation = {
        "prior_episode_count": prior_episode_count,
        "final_episode_count": final_episode_count,
        "prior_arm_count": prior_arm_count,
        "final_arm_count": final_arm_count,
        "normal_rescue_promotion_count": len(promotion_rows),
        "out_of_session_pending_count": 1,
        "promoted_episode_count": len(promoted_episode_ledger),
        "out_of_session_episode_id": OPEC_EPISODE_ID,
        "out_of_session_arm_count": len(opec_rows),
        "normal_rescue_maximum_affected_arms": 432,
        "actual_changed_arm_count": changed_arm_count,
        "unchanged_arm_count": unchanged_arm_count,
        "normal_rescue_changed_arm_count": normal_promotion_changed_count,
        "out_of_session_changed_arm_count": len(opec_rows),
        "status_transition_counts": status_transition_counts,
        "prior_status_counts": prior_status_counts,
        "final_status_counts": final_status_counts,
        "scientific_fingerprint": fingerprint(
            {
                "matrix_rows": final_rows,
                "promotion_rows": promoted_episode_ledger,
                "opec_rows": out_of_session_episode_ledger,
            }
        ),
    }

    final_rescue_promotion_contract = {
        "purpose": "Promote normal session-linked rescue Episodes while preserving one out-of-session weekend OPEC Episode.",
        "sole_normal_promotion_source": path_ref(FINAL_RESCUE_ROOT / "promotion_candidates.jsonl"),
        "normal_rescue_promotion_count_required": 72,
        "normal_rescue_maximum_affected_arms": 432,
        "out_of_session_exception_episode_id": OPEC_EPISODE_ID,
        "out_of_session_blocker_reason": OUT_OF_SESSION_BLOCKER,
        "out_of_session_event_level_route_status": "NOT_YET_VALIDATED",
        "counts_must_remain_fixed": {
            "episode_count": 462,
            "arm_count": 2772,
        },
    }

    matrix_decision = {
        "matrix_promotion_status": "FINAL_RESCUE_MATRIX_PROMOTION_COMPLETE",
        "matrix_integrity_decision": "FINAL_VERSIONED_MATRIX_RECONCILED",
        "out_of_session_decision": "OUT_OF_SESSION_EVENT_PRESERVED_PENDING_ROUTE",
        "main_path_decision": "MAIN_341_PATH_UNCHANGED",
        "next_step_decision": "READY_FOR_PROVIDER_CONTRACT_VALIDATION",
    }

    governing_artifact_manifest = {
        "prior_matrix": {
            "id": PRIOR_MATRIX_ID,
            "path": path_ref(PRIOR_MATRIX_ROOT),
        },
        "reconstruction_dry_run": {
            "id": RECONSTRUCTION_DRY_RUN_ID,
            "path": path_ref(RECONSTRUCTION_ROOT),
        },
        "us_session_join_audit": {
            "id": US_SESSION_JOIN_AUDIT_ID,
            "path": path_ref(US_SESSION_ROOT),
        },
        "final_rescue_audit": {
            "id": FINAL_RESCUE_AUDIT_ID,
            "path": path_ref(FINAL_RESCUE_ROOT),
        },
    }

    run_manifest = {
        "run_id": run_id,
        "created_at": ts,
        "source_commit": git_head(),
        "prior_matrix_id": PRIOR_MATRIX_ID,
        "final_matrix_path": path_ref(run_dir / "final_rescue_aware_execution_matrix.jsonl"),
        "promotion_candidate_count": len(promoted_episode_ledger),
        "out_of_session_episode_id": OPEC_EPISODE_ID,
        "scientific_fingerprint": matrix_reconciliation["scientific_fingerprint"],
    }

    write_json(run_dir / "run_manifest.json", run_manifest)
    write_json(run_dir / "governing_artifact_manifest.json", governing_artifact_manifest)
    write_json(run_dir / "final_rescue_promotion_contract.json", final_rescue_promotion_contract)
    write_json(run_dir / "prior_matrix_snapshot.json", prior_matrix_snapshot)
    write_jsonl(run_dir / "promoted_episode_ledger.jsonl", promoted_episode_ledger)
    write_jsonl(run_dir / "out_of_session_episode_ledger.jsonl", out_of_session_episode_ledger)
    write_jsonl(run_dir / "affected_arm_reclassification.jsonl", affected_arm_reclassification)
    write_jsonl(run_dir / "final_rescue_aware_execution_matrix.jsonl", final_rows)
    write_json(run_dir / "matrix_reconciliation.json", matrix_reconciliation)
    write_json(run_dir / "execution_readiness_summary.json", execution_readiness_summary)
    write_json(run_dir / "matrix_decision.json", matrix_decision)

    return {
        "run_id": run_id,
        "run_dir": run_dir,
        "prior_matrix_id": PRIOR_MATRIX_ID,
        "final_episode_count": final_episode_count,
        "final_arm_count": final_arm_count,
        "promotion_candidate_count": len(promoted_episode_ledger),
        "out_of_session_episode_id": OPEC_EPISODE_ID,
        "out_of_session_arm_count": len(opec_rows),
        "actual_changed_arm_count": changed_arm_count,
        "unchanged_arm_count": unchanged_arm_count,
        "prior_status_counts": prior_status_counts,
        "final_status_counts": final_status_counts,
        "status_transition_counts": status_transition_counts,
        "execution_readiness_summary": execution_readiness_summary,
        "matrix_reconciliation": matrix_reconciliation,
        "promotion_validation": validation,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--fixed-timestamp", default=None)
    args = parser.parse_args()
    result = build_matrix(output_root=args.output_root, fixed_timestamp=args.fixed_timestamp)
    print(json.dumps({"run_id": result["run_id"], "run_dir": str(result["run_dir"])}, indent=2))


if __name__ == "__main__":
    main()
