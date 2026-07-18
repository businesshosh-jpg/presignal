"""Offline-only freezer for reduced authoritative replay packages."""
from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from automation.local_git_repository_state_v1 import (
    LocalGitRepositoryError,
    authoritative_git_binding,
    normalize_local_git_repository_state,
    read_local_git_repository_state,
    require_expected_local_git_state,
)
from automation.simplified_authoritative_replay_contract_v1 import (
    DIRECTIONS,
    REQUIRED,
    STRENGTHS,
    canonical_event_identity,
    driver_options,
    require_unique_event_identities,
)


ROOT = Path(__file__).resolve().parents[1]
APPS_SCRIPT_DIR = ROOT / "apps_script"
APPS_SCRIPT_CLASP_PATH = APPS_SCRIPT_DIR / ".clasp.json"
SNAPSHOT = Path("/Users/junhoshino/projects/presignal_replay_archives/9-AUTHORITATIVE-HISTORICAL-REPLAY-20260717T094156Z/input_snapshot")

CORE_SNAPSHOT_FILES = (
    "authoritative_sessions.jsonl",
    "authoritative_session_members.jsonl",
    "authoritative_forecast_population.jsonl",
    "authoritative_pack_references.jsonl",
    "authoritative_excluded_sessions.jsonl",
)
PRODUCTION_SOURCE_FILES = CORE_SNAPSHOT_FILES + (
    "authoritative_requests.jsonl",
    "authoritative_component_fingerprints.json",
    "authoritative_provider_model_config.json",
    "authoritative_replay_input_manifest.json",
)
EXPECTED_COUNTS = {
    "sessions": 239,
    "exclusions": 10,
    "identities": 1434,
    "pack_a": 717,
    "pack_e": 717,
    "OpenAI": 478,
    "Gemini": 478,
    "Anthropic": 478,
}


def rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha(value: Any) -> str:
    payload = value if isinstance(value, bytes) else canon(value).encode()
    return hashlib.sha256(payload).hexdigest()


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _local_apps_script_files() -> list[dict[str, str]]:
    files: list[dict[str, str]] = []
    for path in sorted(APPS_SCRIPT_DIR.iterdir(), key=lambda item: item.name):
        if path.name == "appsscript.json":
            files.append({"name": "appsscript", "type": "JSON", "source": path.read_text()})
        elif path.is_file() and path.suffix == ".js":
            files.append({"name": path.name[:-3], "type": "SERVER_JS", "source": path.read_text()})
    return files


def apps_script_project_fingerprint(files: Sequence[Mapping[str, Any]]) -> str:
    normalized = sorted(
        ({"name": str(item["name"]), "type": str(item["type"]), "source": str(item["source"])} for item in files),
        key=lambda item: (item["name"], item["type"]),
    )
    payload = json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def apps_script_source_binding() -> dict[str, Any]:
    files = _local_apps_script_files()
    by_name = {item["name"]: item for item in files}
    project_id = str(json.loads(APPS_SCRIPT_CLASP_PATH.read_text()).get("scriptId") or "")
    return {
        "apps_script_project_id": project_id,
        "project_fingerprint": apps_script_project_fingerprint(files),
        "bridge_sha256": hashlib.sha256(by_name["authoritative_provider_bridge"]["source"].encode("utf-8")).hexdigest(),
        "prediction_runner_sha256": hashlib.sha256(by_name["prediction_runner"]["source"].encode("utf-8")).hexdigest(),
        "file_count": len(files),
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def write_jsonl(path: Path, records: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(canon(record) + "\n" for record in records))


def _snapshot_file_sha(snapshot: Path, names: Sequence[str]) -> dict[str, str]:
    return {name: file_sha(snapshot / name) for name in names if (snapshot / name).exists()}


def _load_core_snapshot(snapshot: Path) -> dict[str, list[dict[str, Any]]]:
    missing = [name for name in CORE_SNAPSHOT_FILES if not (snapshot / name).exists()]
    if missing:
        raise ValueError("SCIENTIFIC_SNAPSHOT_FILE_MISSING:" + missing[0])
    return {
        "sessions": rows(snapshot / "authoritative_sessions.jsonl"),
        "members": rows(snapshot / "authoritative_session_members.jsonl"),
        "population": rows(snapshot / "authoritative_forecast_population.jsonl"),
        "packs": rows(snapshot / "authoritative_pack_references.jsonl"),
        "excluded": rows(snapshot / "authoritative_excluded_sessions.jsonl"),
    }


def _correct_member_event_ids(members: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    counts: dict[str, int] = {}
    for member in members:
        event_id = str(member.get("event_id") or "")
        counts[event_id] = counts.get(event_id, 0) + 1

    corrected: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    for member in members:
        original = str(member.get("event_id") or "")
        corrected_event_id = canonical_event_identity(member) if counts.get(original, 0) > 1 else original
        row = dict(member)
        row["event_id"] = corrected_event_id
        corrected.append(row)
        audit.append({
            "session_id": str(member.get("session_id") or ""),
            "member_order": member.get("member_order"),
            "indicator_name": str(member.get("indicator_name") or ""),
            "original_event_id": original,
            "corrected_event_id": corrected_event_id,
            "correction_applied": corrected_event_id != original,
        })
    require_unique_event_identities(corrected)
    return corrected, audit


def _sessions_with_corrected_member_ids(
    sessions: Sequence[Mapping[str, Any]],
    members: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    by_session: dict[str, list[Mapping[str, Any]]] = {}
    for member in members:
        by_session.setdefault(str(member["session_id"]), []).append(member)

    normalized: list[dict[str, Any]] = []
    for session in sessions:
        sid = str(session["session_id"])
        member_ids = [
            str(member["event_id"])
            for member in sorted(by_session.get(sid, []), key=lambda item: int(item.get("member_order") or 0))
        ]
        row = dict(session)
        row["member_event_count"] = len(member_ids)
        row["member_event_ids"] = "|".join(member_ids)
        normalized.append(row)
    return normalized


def _group_members_by_session(members: Sequence[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_session: dict[str, list[dict[str, Any]]] = {}
    for member in members:
        by_session.setdefault(str(member["session_id"]), []).append(dict(member))
    return by_session


def _build_token_records(members: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, list[dict[str, str]]]]:
    by_session = _group_members_by_session(members)
    session_tokens: list[dict[str, Any]] = []
    mappings: list[dict[str, Any]] = []
    audit_by_session: dict[str, list[dict[str, str]]] = {}

    for session_id in sorted(by_session):
        member_ids = {str(member["event_id"]) for member in by_session[session_id]}
        options = driver_options(by_session[session_id])
        tokens_seen: dict[str, str] = {}
        audit_by_session[session_id] = []
        for option in options:
            token = str(option.get("token") or "")
            event_id = str(option.get("event_id") or "")
            if not token:
                raise ValueError("DRIVER_TOKEN_MISSING")
            if token in tokens_seen:
                raise ValueError("DRIVER_TOKEN_DUPLICATED_WITHIN_SESSION")
            tokens_seen[token] = event_id
            matches = [member for member in by_session[session_id] if str(member["event_id"]) == event_id]
            if len(matches) == 0:
                raise ValueError("TOKEN_RESOLVES_ZERO_MEMBERS")
            if len(matches) > 1:
                raise ValueError("TOKEN_RESOLVES_MULTIPLE_MEMBERS")
            if event_id not in member_ids:
                raise ValueError("TOKEN_RESOLVES_OUTSIDE_SESSION")
            record = {
                "session_id": session_id,
                "token": token,
                "event_id": event_id,
                "indicator_name": str(matches[0].get("indicator_name") or option.get("label") or ""),
            }
            session_tokens.append(record)
            mappings.append({"session_id": session_id, "token": token, "event_id": event_id})
            audit_by_session[session_id].append({"token": token, "event_id": event_id, "label": record["indicator_name"]})
    return session_tokens, mappings, audit_by_session


def _count_population(population: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = {
        "identities": len(population),
        "pack_a": sum(str(row.get("arm") or "") == "A" for row in population),
        "pack_e": sum(str(row.get("arm") or "") == "E" for row in population),
        "OpenAI": sum(str(row.get("provider") or "") == "OpenAI" for row in population),
        "Gemini": sum(str(row.get("provider") or "") == "Gemini" for row in population),
        "Anthropic": sum(str(row.get("provider") or "") == "Anthropic" for row in population),
    }
    return counts


def _validate_scientific_counts(snapshot: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, int]:
    population_counts = _count_population(snapshot["population"])
    counts = {
        "sessions": len(snapshot["sessions"]),
        "exclusions": len(snapshot["excluded"]),
        **population_counts,
    }
    mismatches = {key: (counts.get(key), expected) for key, expected in EXPECTED_COUNTS.items() if counts.get(key) != expected}
    if mismatches:
        raise ValueError("SCIENTIFIC_COUNTS_MISMATCH:" + canon(mismatches))
    return counts


def _validate_population_routes(population: Sequence[Mapping[str, Any]], session_ids: set[str]) -> None:
    forecast_ids: set[str] = set()
    for row in population:
        forecast_id = str(row.get("forecast_identity") or "")
        if not forecast_id or forecast_id in forecast_ids:
            raise ValueError("FORECAST_IDENTITY_DUPLICATED_OR_MISSING")
        forecast_ids.add(forecast_id)
        if str(row.get("session_id") or "") not in session_ids:
            raise ValueError("IDENTITY_SESSION_MISSING")
        if str(row.get("arm") or "") not in {"A", "E"}:
            raise ValueError("IDENTITY_PACK_ASSIGNMENT_MISSING")
        if not str(row.get("provider") or "") or not str(row.get("model") or ""):
            raise ValueError("IDENTITY_PROVIDER_MODEL_ROUTE_MISSING")


def _validate_production_inputs(
    immutable_apps_script_version: int,
    apps_script_project_id: str,
    execution_deployment_id: str,
    execution_deployment_version: int,
    project_fingerprint: str,
    fingerprints: Mapping[str, str],
    outcome_enabled: bool,
    evaluation_enabled: bool,
    native_v2_prediction_path_required: bool,
) -> None:
    if isinstance(immutable_apps_script_version, bool) or not isinstance(immutable_apps_script_version, int) or immutable_apps_script_version <= 0:
        raise ValueError("IMMUTABLE_APPS_SCRIPT_VERSION_MISSING_OR_MUTABLE")
    if not isinstance(execution_deployment_id, str) or not execution_deployment_id.strip():
        raise ValueError("EXECUTION_DEPLOYMENT_ID_MISSING")
    if isinstance(execution_deployment_version, bool) or not isinstance(execution_deployment_version, int) or execution_deployment_version <= 0:
        raise ValueError("EXECUTION_DEPLOYMENT_VERSION_MISSING")
    if execution_deployment_version != immutable_apps_script_version:
        raise ValueError("EXECUTION_DEPLOYMENT_VERSION_MISMATCH")
    missing = [key for key, value in fingerprints.items() if not isinstance(value, str) or not value.strip()]
    if missing:
        raise ValueError("IMPLEMENTATION_FINGERPRINT_MISSING:" + missing[0])
    if not isinstance(project_fingerprint, str) or not project_fingerprint.strip():
        raise ValueError("IMPLEMENTATION_FINGERPRINT_MISSING:project_fingerprint")
    local_binding = apps_script_source_binding()
    if apps_script_project_id != local_binding["apps_script_project_id"]:
        raise ValueError("APPS_SCRIPT_PROJECT_ID_MISMATCH")
    if project_fingerprint != local_binding["project_fingerprint"]:
        raise ValueError("APPS_SCRIPT_PROJECT_FINGERPRINT_MISMATCH")
    if fingerprints["bridge_source_fingerprint"] != local_binding["bridge_sha256"]:
        raise ValueError("BRIDGE_SOURCE_FINGERPRINT_MISMATCH")
    if fingerprints["prediction_runner_fingerprint"] != local_binding["prediction_runner_sha256"]:
        raise ValueError("PREDICTION_RUNNER_FINGERPRINT_MISMATCH")
    if outcome_enabled or evaluation_enabled:
        raise ValueError("OUTCOME_OR_EVALUATION_ENABLED")
    if native_v2_prediction_path_required:
        raise ValueError("NATIVE_V2_PREDICTION_PATH_REQUIRED")


def _provider_model_counts(population: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in population:
        key = f"{row.get('provider')}|{row.get('model')}"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _write_production_package(
    package_dir: Path,
    package_id: str,
    scientific_snapshot_path: Path,
    snapshot: Mapping[str, list[dict[str, Any]]],
    deployment_binding: Mapping[str, Any],
    local_git_provenance: Mapping[str, Any],
    fingerprints: Mapping[str, str],
    counts: Mapping[str, int],
) -> None:
    corrected_members, event_id_audit = _correct_member_event_ids(snapshot["members"])
    normalized_sessions = _sessions_with_corrected_member_ids(snapshot["sessions"], corrected_members)
    session_tokens, token_mappings, token_audit = _build_token_records(corrected_members)
    session_ids = {str(session["session_id"]) for session in normalized_sessions}
    _validate_population_routes(snapshot["population"], session_ids)

    provider_models = _provider_model_counts(snapshot["population"])
    population_audit = {
        "counts": dict(counts),
        "expected_counts": dict(EXPECTED_COUNTS),
        "scientific_counts_match": True,
        "source_snapshot": str(scientific_snapshot_path),
    }
    identity_audit = {
        "forecast_identity_count": len(snapshot["population"]),
        "unique_forecast_identity_count": len({str(row["forecast_identity"]) for row in snapshot["population"]}),
        "event_member_count": len(corrected_members),
        "unique_corrected_event_id_count": len({str(row["event_id"]) for row in corrected_members}),
        "corrected_event_id_count": sum(1 for row in event_id_audit if row["correction_applied"]),
    }
    provider_model_audit = {
        "provider_counts": {name: counts[name] for name in ("OpenAI", "Gemini", "Anthropic")},
        "provider_model_counts": provider_models,
        "provider_model_routes_present": True,
    }
    token_summary = {
        "sessions": len(token_audit),
        "tokens": len(token_mappings),
        "session_scoped_uniqueness": "PASS",
        "token_to_event_resolution": "PASS",
    }

    write_jsonl(package_dir / "snapshot" / "authoritative_sessions.jsonl", normalized_sessions)
    write_jsonl(package_dir / "snapshot" / "authoritative_session_members.jsonl", corrected_members)
    write_jsonl(package_dir / "snapshot" / "authoritative_forecast_population.jsonl", snapshot["population"])
    write_jsonl(package_dir / "snapshot" / "authoritative_pack_references.jsonl", snapshot["packs"])
    write_jsonl(package_dir / "snapshot" / "authoritative_excluded_sessions.jsonl", snapshot["excluded"])
    for name in PRODUCTION_SOURCE_FILES:
        source = scientific_snapshot_path / name
        if source.exists() and not (package_dir / "snapshot" / name).exists():
            shutil.copyfile(source, package_dir / "snapshot" / name)

    write_jsonl(
        package_dir / "identity" / "forecast_identities.jsonl",
        ({
            "forecast_identity": row["forecast_identity"],
            "session_id": row["session_id"],
            "pack_arm": row["arm"],
            "provider": row["provider"],
            "model": row["model"],
        } for row in snapshot["population"]),
    )
    write_jsonl(package_dir / "identity" / "corrected_event_ids.jsonl", event_id_audit)
    write_jsonl(package_dir / "identity" / "session_scoped_driver_tokens.jsonl", session_tokens)
    write_jsonl(package_dir / "identity" / "token_to_event_mappings.jsonl", token_mappings)
    write_json(package_dir / "identity" / "token_mapping_audit.json", token_audit)

    write_jsonl(
        package_dir / "assignments" / "pack_assignments.jsonl",
        ({
            "forecast_identity": row["forecast_identity"],
            "session_id": row["session_id"],
            "pack_arm": row["arm"],
            "pack_fingerprint": row.get("pack_fingerprint", ""),
            "stage4a_contract_fingerprint": row.get("stage4a_contract_fingerprint", ""),
        } for row in snapshot["population"]),
    )
    write_jsonl(
        package_dir / "assignments" / "provider_model_assignments.jsonl",
        ({
            "forecast_identity": row["forecast_identity"],
            "session_id": row["session_id"],
            "provider": row["provider"],
            "model": row["model"],
            "parser_fingerprint": row.get("parser_fingerprint", ""),
            "prompt_fingerprint": row.get("prompt_fingerprint", ""),
            "storage_fingerprint": row.get("storage_fingerprint", ""),
        } for row in snapshot["population"]),
    )

    source_manifest = scientific_snapshot_path / "authoritative_replay_input_manifest.json"
    source_components = scientific_snapshot_path / "authoritative_component_fingerprints.json"
    historical_reference = {
        "source_snapshot": str(scientific_snapshot_path),
        "source_file_sha256": _snapshot_file_sha(scientific_snapshot_path, PRODUCTION_SOURCE_FILES),
        "replay_input_manifest": json.loads(source_manifest.read_text()) if source_manifest.exists() else {},
        "component_fingerprints": json.loads(source_components.read_text()) if source_components.exists() else {},
    }
    write_json(package_dir / "references" / "historical_environment_references.json", historical_reference)
    write_json(package_dir / "references" / "pack_references_index.json", {
        "pack_reference_count": len(snapshot["packs"]),
        "pack_reference_file": "snapshot/authoritative_pack_references.jsonl",
        "pack_reference_sha256": file_sha(package_dir / "snapshot" / "authoritative_pack_references.jsonl"),
    })
    write_json(package_dir / "schema" / "reduced_provider_schema_reference.json", {
        "schema_source": "automation/simplified_authoritative_replay_contract_v1.py",
        "required_fields": sorted(REQUIRED),
        "directions": sorted(DIRECTIONS),
        "reaction_strengths": sorted(STRENGTHS),
        "strict_unknown_field_rejection": True,
        "driver_tokens_are_session_scoped": True,
    })
    write_json(package_dir / "binding" / "immutable_deployment_binding.json", {
        # An immutable version can exist without the active API deployment pointing to it.
        **dict(deployment_binding),
        "apps_script_version": deployment_binding["immutable_version_number"],
        "version_is_immutable": True,
        "deployment_performed": False,
        "binding_source": "operator_supplied_execution_deployment_and_immutable_version",
    })
    write_json(
        package_dir / "binding" / "local_git_repository_binding.json",
        authoritative_git_binding(local_git_provenance),
    )
    write_json(
        package_dir / "provenance" / "local_git_repository.json",
        dict(local_git_provenance),
    )
    write_json(package_dir / "fingerprints" / "implementation_fingerprints.json", {
        **dict(fingerprints),
        "all_required_fingerprints_present": True,
    })
    write_json(package_dir / "audit" / "identity_audit.json", identity_audit)
    write_json(package_dir / "audit" / "token_audit.json", token_summary)
    write_json(package_dir / "audit" / "population_audit.json", population_audit)
    write_json(package_dir / "audit" / "provider_model_audit.json", provider_model_audit)


def _manifest_file_map(package_dir: Path) -> dict[str, str]:
    excluded = {"package_manifest.json", "whole_package_sha256.txt"}
    files: dict[str, str] = {}
    for path in sorted(package_dir.rglob("*")):
        if path.is_file():
            rel = path.relative_to(package_dir).as_posix()
            if rel not in excluded:
                files[rel] = file_sha(path)
    return files


def _whole_package_sha256(package_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(package_dir.rglob("*")):
        if path.is_file():
            rel = path.relative_to(package_dir).as_posix()
            if rel == "whole_package_sha256.txt":
                continue
            digest.update(rel.encode())
            digest.update(b"\0")
            digest.update(file_sha(path).encode())
            digest.update(b"\0")
    return digest.hexdigest()


def _write_manifest(
    package_dir: Path,
    package_id: str,
    counts: Mapping[str, int],
    provider_models: Mapping[str, int],
    local_git_provenance: Mapping[str, Any],
) -> dict[str, Any]:
    manifest = {
        "package_id": package_id,
        "package_mode": "production_freeze",
        "offline_only": True,
        "provider_calls_enabled": False,
        "outcome_enabled": False,
        "evaluation_enabled": False,
        "native_v2_prediction_path_required": False,
        "local_git_repository_binding": authoritative_git_binding(local_git_provenance),
        "local_git_repository_provenance": dict(local_git_provenance),
        "counts": dict(counts),
        "provider_models": dict(provider_models),
        "files": _manifest_file_map(package_dir),
    }
    manifest["manifest_sha256_without_self"] = sha(manifest)
    write_json(package_dir / "package_manifest.json", manifest)
    return manifest


def verify_package_manifest(package_dir: Path) -> bool:
    manifest = json.loads((package_dir / "package_manifest.json").read_text())
    for rel, expected in manifest.get("files", {}).items():
        path = package_dir / rel
        if not path.exists() or file_sha(path) != expected:
            raise ValueError("PACKAGE_MANIFEST_VERIFICATION_FAILED:" + rel)
    current = _manifest_file_map(package_dir)
    if current != manifest.get("files", {}):
        raise ValueError("PACKAGE_MANIFEST_FILE_SET_MISMATCH")
    if manifest.get("local_git_repository_binding") is not None:
        git_binding = json.loads((package_dir / "binding" / "local_git_repository_binding.json").read_text())
        git_provenance = json.loads((package_dir / "provenance" / "local_git_repository.json").read_text())
        if manifest.get("local_git_repository_binding") != git_binding:
            raise ValueError("PACKAGE_GIT_BINDING_MANIFEST_MISMATCH")
        if manifest.get("local_git_repository_provenance") != git_provenance:
            raise ValueError("PACKAGE_GIT_PROVENANCE_MANIFEST_MISMATCH")
        if authoritative_git_binding(git_provenance) != git_binding:
            raise ValueError("PACKAGE_GIT_BINDING_PROVENANCE_MISMATCH")
    return True


def verify_whole_package_fingerprint(package_dir: Path) -> bool:
    expected = (package_dir / "whole_package_sha256.txt").read_text().strip()
    actual = _whole_package_sha256(package_dir)
    if actual != expected:
        raise ValueError("WHOLE_PACKAGE_FINGERPRINT_MISMATCH")
    return True


def freeze(destination: Path, package_id: str = "SIMPLIFIED-REPLAY-DRY-RUN-V1"):
    if destination.exists():
        raise ValueError("DESTINATION_EXISTS")
    snapshot = _load_core_snapshot(SNAPSHOT)
    sessions = snapshot["sessions"]
    members = snapshot["members"]
    population = snapshot["population"]
    packs = snapshot["packs"]
    excluded = snapshot["excluded"]
    if (
        len(sessions),
        len(excluded),
        len(population),
        sum(row["arm"] == "A" for row in population),
        sum(row["arm"] == "E" for row in population),
        len(packs),
    ) != (239, 10, 1434, 717, 717, 239):
        raise ValueError("POPULATION_MISMATCH")

    members, _ = _correct_member_event_ids(members)
    by_session = _group_members_by_session(members)
    token_audit = {session_id: driver_options(rows) for session_id, rows in by_session.items()}
    if any(len({row["token"] for row in value}) != len(value) or len({row["event_id"] for row in value}) != len(value) for value in token_audit.values()):
        raise ValueError("TOKEN_AUDIT_FAILED")
    if any(row["session_id"] not in by_session for row in population):
        raise ValueError("IDENTITY_SESSION_MISSING")
    providers: dict[tuple[str, str], int] = {}
    for row in population:
        providers[(row["provider"], row["model"])] = providers.get((row["provider"], row["model"]), 0) + 1

    destination.mkdir(parents=True)
    snap = destination / "snapshot"
    snap.mkdir()
    for name in CORE_SNAPSHOT_FILES:
        if name == "authoritative_session_members.jsonl":
            write_jsonl(snap / name, members)
        else:
            shutil.copyfile(SNAPSHOT / name, snap / name)
    write_json(destination / "token_mapping_audit.json", token_audit)
    manifest = {
        "package_id": package_id,
        "offline_only": True,
        "outcome_evaluation_enabled": False,
        "counts": {"sessions": 239, "excluded": 10, "identities": 1434, "pack_a": 717, "pack_e": 717},
        "provider_models": {f"{provider}|{model}": count for (provider, model), count in providers.items()},
        "scientific_snapshot_equality": "PASS",
        "source_snapshot": str(SNAPSHOT),
        "components": {name: file_sha(snap / name) for name in CORE_SNAPSHOT_FILES},
        "token_audit_sha256": file_sha(destination / "token_mapping_audit.json"),
    }
    manifest["package_fingerprint"] = sha(manifest)
    write_json(destination / "package_manifest.json", manifest)
    return manifest


def freeze_production_package(
    *,
    scientific_snapshot_path: Path | str,
    durable_output_root: Path | str,
    package_id: str,
    apps_script_project_id: str,
    execution_deployment_id: str,
    execution_deployment_version: int,
    immutable_apps_script_version: int,
    project_fingerprint: str,
    bridge_source_fingerprint: str,
    prediction_runner_fingerprint: str,
    contract_fingerprint: str,
    executor_fingerprint: str,
    expected_git_commit: str,
    repository_path: Path | str = ROOT,
    repository_state_reader=None,
    outcome_enabled: bool = False,
    evaluation_enabled: bool = False,
    native_v2_prediction_path_required: bool = False,
) -> dict[str, Any]:
    if not package_id or Path(package_id).name != package_id:
        raise ValueError("PACKAGE_ID_INVALID")
    snapshot_path = Path(scientific_snapshot_path)
    output_root = Path(durable_output_root)
    final_dir = output_root / package_id
    if final_dir.exists():
        raise ValueError("EXISTING_FINAL_PACKAGE_ID")

    reader = repository_state_reader or read_local_git_repository_state
    try:
        observed_git_state = reader(Path(repository_path))
        local_git_provenance = normalize_local_git_repository_state(observed_git_state, repository_path)
        local_git_provenance = require_expected_local_git_state(local_git_provenance, expected_git_commit)
    except LocalGitRepositoryError as error:
        raise ValueError(str(error)) from error
    except Exception as error:
        raise ValueError("LOCAL_GIT_REPOSITORY_UNREADABLE") from error

    fingerprints = {
        "bridge_source_fingerprint": bridge_source_fingerprint,
        "prediction_runner_fingerprint": prediction_runner_fingerprint,
        "contract_fingerprint": contract_fingerprint,
        "executor_fingerprint": executor_fingerprint,
    }
    _validate_production_inputs(
        immutable_apps_script_version,
        apps_script_project_id,
        execution_deployment_id,
        execution_deployment_version,
        project_fingerprint,
        fingerprints,
        outcome_enabled,
        evaluation_enabled,
        native_v2_prediction_path_required,
    )
    deployment_binding = {
        "apps_script_project_id": apps_script_project_id,
        "execution_deployment_id": execution_deployment_id,
        "execution_deployment_version": execution_deployment_version,
        "immutable_version_number": immutable_apps_script_version,
        "project_fingerprint": project_fingerprint,
        "bridge_sha256": bridge_source_fingerprint,
        "prediction_runner_sha256": prediction_runner_fingerprint,
    }
    snapshot = _load_core_snapshot(snapshot_path)
    counts = _validate_scientific_counts(snapshot)
    provider_models = _provider_model_counts(snapshot["population"])

    output_root.mkdir(parents=True, exist_ok=True)
    temp_dir = output_root / f".{package_id}.tmp-{uuid.uuid4().hex}"
    try:
        temp_dir.mkdir()
        _write_production_package(
            temp_dir,
            package_id,
            snapshot_path,
            snapshot,
            deployment_binding,
            local_git_provenance,
            fingerprints,
            counts,
        )
        manifest = _write_manifest(temp_dir, package_id, counts, provider_models, local_git_provenance)
        (temp_dir / "whole_package_sha256.txt").write_text(_whole_package_sha256(temp_dir) + "\n")
        verify_package_manifest(temp_dir)
        verify_whole_package_fingerprint(temp_dir)
        temp_dir.rename(final_dir)
        return {
            **manifest,
            "package_dir": str(final_dir),
            "whole_package_sha256": (final_dir / "whole_package_sha256.txt").read_text().strip(),
        }
    except Exception:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        raise
