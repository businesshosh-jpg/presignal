"""Versioned, prospective-only FLAT stage prompt contract.

This module deliberately does not replace the frozen v1 validator, parser, or
historical prompt.  It makes one provider-visible rule explicit for new runs
and exposes a fail-closed version selector for future runners.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import presignal_v21_event_path_contract_v1 as frozen
from automation import run_presignal_v21_single_event_path_pair_v1 as single

CONTRACT_PATH = ROOT / "contracts" / "presignal_v21_event_path" / "prospective_flat_path_contract_v1.json"
FIXTURE_PATH = ROOT / "contracts" / "presignal_v21_event_path" / "prospective_flat_path_fixtures_v1.json"
PROSPECTIVE_CONTRACT_VERSION = "presignal_event_path_contract_v1_flat_stage_prospective_v1"
PARENT_CONTRACT_VERSION = frozen.CONTRACT_VERSION
PROMPT_RULE = (
    "Prospective path-stage FLAT rule: FLAT means zero directional pip movement for that stage. "
    "For FLAT, expected_pips_min must be 0 and expected_pips_max must be 0. "
    "Do not use a non-zero range around zero for FLAT; express uncertainty or low volatility in "
    "stage_confidence or stage_reason. Valid FLAT example: "
    '{"horizon_min":30,"expected_direction":"FLAT","expected_pips_min":0,"expected_pips_max":0}.'
)


class ProspectiveFlatContractError(RuntimeError):
    """A prospective contract selection or integrity invariant failed."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _file_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def fingerprints() -> dict[str, str]:
    """Stable identities for the inherited implementation and new prompt clause."""
    schema = json.loads((ROOT / "contracts" / "presignal_v21_event_path" / "prediction_path_contract_v1.json").read_text())
    return {
        "prompt_template_fingerprint": sha256(PROMPT_RULE),
        "schema_fingerprint": sha256(schema),
        "validator_fingerprint": sha256(inspect.getsource(frozen.validate_prediction_path)),
        "parser_fingerprint": sha256(inspect.getsource(single.parse_provider_output)),
    }


def expected_contract_fingerprint(spec: Mapping[str, Any]) -> str:
    value = dict(spec)
    value["contract_fingerprint"] = ""
    return sha256(value)


def contract_spec() -> dict[str, Any]:
    spec = _file_json(CONTRACT_PATH)
    required = {
        "contract_version", "parent_contract_version", "prospective_only", "effective_scope",
        "contract_fingerprint", "prompt_template_fingerprint", "schema_fingerprint",
        "validator_fingerprint", "parser_fingerprint", "created_from_commit",
    }
    missing = sorted(required - set(spec))
    if missing:
        raise ProspectiveFlatContractError("PROSPECTIVE_CONTRACT_FIELDS:" + ",".join(missing))
    if spec["contract_version"] != PROSPECTIVE_CONTRACT_VERSION or spec["parent_contract_version"] != PARENT_CONTRACT_VERSION:
        raise ProspectiveFlatContractError("PROSPECTIVE_CONTRACT_LINEAGE")
    if spec["prospective_only"] is not True:
        raise ProspectiveFlatContractError("PROSPECTIVE_SCOPE_REQUIRED")
    expected = fingerprints()
    for field, value in expected.items():
        if spec[field] != value:
            raise ProspectiveFlatContractError("PROSPECTIVE_FINGERPRINT_DRIFT:" + field)
    if spec["contract_fingerprint"] != expected_contract_fingerprint(spec):
        raise ProspectiveFlatContractError("PROSPECTIVE_CONTRACT_FINGERPRINT_DRIFT")
    return spec


def resolve_contract(contract_version: str | None, *, prospective: bool) -> dict[str, Any]:
    if not contract_version:
        raise ProspectiveFlatContractError("MISSING_CONTRACT_VERSION")
    if contract_version == PARENT_CONTRACT_VERSION:
        if prospective:
            raise ProspectiveFlatContractError("HISTORICAL_CONTRACT_NOT_PERMITTED_FOR_NEW_PROSPECTIVE_RUN")
        return {"contract_version": PARENT_CONTRACT_VERSION, "prospective_only": False}
    if contract_version == PROSPECTIVE_CONTRACT_VERSION:
        if not prospective:
            raise ProspectiveFlatContractError("PROSPECTIVE_CONTRACT_NOT_PERMITTED_FOR_HISTORICAL_RECONSTRUCTION")
        return contract_spec()
    raise ProspectiveFlatContractError("UNSUPPORTED_CONTRACT_VERSION:" + contract_version)


def verify_resume_contract(stored_contract_version: str | None, requested_contract_version: str | None) -> None:
    if not stored_contract_version or not requested_contract_version:
        raise ProspectiveFlatContractError("MISSING_CONTRACT_VERSION")
    if stored_contract_version != requested_contract_version:
        raise ProspectiveFlatContractError("CONTRACT_SUBSTITUTION_DURING_RESUME")


def prospective_context(input_row: Mapping[str, Any], contract_version: str | None) -> dict[str, Any]:
    spec = resolve_contract(contract_version, prospective=True)
    context = single.arm_context(input_row)
    context["object"] = "presignal_event_path_prospective_forecast_request"
    context["contract_version"] = spec["contract_version"]
    context["response_contract_version"] = spec["contract_version"]
    return context


def prospective_prompt_text(context: Mapping[str, Any], contract_version: str | None) -> str:
    resolve_contract(contract_version, prospective=True)
    return single.prompt_text(context) + "\n\n" + PROMPT_RULE


def prospective_request(input_row: Mapping[str, Any], *, run_id: str, contract_version: str | None) -> dict[str, Any]:
    context = prospective_context(input_row, contract_version)
    prompt = prospective_prompt_text(context, contract_version)
    arm = "BASELINE" if input_row["information_arm"] == "PACK_A" else "FULL_CONTEXT"
    payload = single.bridge_payload(input_row, prompt, run_id=run_id, arm=arm)
    return {"contract": contract_spec(), "context": context, "prompt": prompt, "payload": payload}


def fixture_spec() -> dict[str, Any]:
    return _file_json(FIXTURE_PATH)
