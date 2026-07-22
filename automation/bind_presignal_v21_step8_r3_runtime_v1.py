"""Manifest-bound runtime adapter for R3 historical verification contracts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from automation import presignal_v21_historical_verification_r3_contract_v1 as r3
from automation import presignal_v21_historical_verification_r3_compat_r1_contract_v1 as compat_r1
from automation import presignal_v21_historical_verification_r3_compat_r2_contract_v1 as compat_r2
from automation import presignal_v21_historical_verification_r3_compat_r3_contract_v1 as compat_r3
from automation import presignal_v21_historical_verification_r3_compat_r4_contract_v1 as compat_r4
from automation import presignal_v21_historical_verification_r3_compat_r5_contract_v1 as compat_r5
from automation import presignal_v21_minimal_prospective_lineage_v1 as lineage
from automation import presignal_v21_prospective_flat_contract_v1 as parent
from automation import presignal_v21_provider_adapters_v1 as provider_adapters

ROOT = Path(__file__).resolve().parents[1]
PREP = ROOT / "outputs/presignal_v21_step8_r3_repair/STEP8-R3-REPAIR-df9c25e/fresh_verification_manifest.json"

CONTRACTS = {
    r3.CONTRACT_VERSION: r3,
    compat_r1.CONTRACT_VERSION: compat_r1,
    compat_r2.CONTRACT_VERSION: compat_r2,
    compat_r3.CONTRACT_VERSION: compat_r3,
    compat_r4.CONTRACT_VERSION: compat_r4,
    compat_r5.CONTRACT_VERSION: compat_r5,
}


class BindingError(RuntimeError):
    pass


def fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def contract_module(spec: Mapping[str, Any]):
    module = CONTRACTS.get(str(spec.get("contract_version") or ""))
    if module is None:
        raise BindingError("R3_CONTRACT_REQUIRED")
    return module


def load_manifest(path: Path = PREP) -> dict[str, Any]:
    manifest = json.loads(path.read_text())
    spec = manifest.get("contract", {})
    module = contract_module(spec)
    if spec != module.spec():
        raise BindingError("R3_CONTRACT_FINGERPRINT_DRIFT")
    return manifest


def attention_instruction(spec: Mapping[str, Any], provider: str) -> str:
    module = contract_module(spec)
    if provider == "Anthropic" and module.CONTRACT_VERSION in (compat_r1.CONTRACT_VERSION, compat_r2.CONTRACT_VERSION, compat_r3.CONTRACT_VERSION, compat_r4.CONTRACT_VERSION, compat_r5.CONTRACT_VERSION):
        return lineage.ATTENTION_INSTRUCTION + "\n\n" + compat_r1.ANTHROPIC_ATTENTION_RULE
    return lineage.ATTENTION_INSTRUCTION


def request_instruction(spec: Mapping[str, Any], provider: str) -> str:
    module = contract_module(spec)
    if module.CONTRACT_VERSION == compat_r1.CONTRACT_VERSION:
        return lineage.REQUEST_INSTRUCTION + "\n\n" + compat_r1.REQUEST_ENUM_RULE
    if module.CONTRACT_VERSION == compat_r2.CONTRACT_VERSION:
        return lineage.REQUEST_INSTRUCTION + "\n\n" + compat_r2.REQUEST_ENUM_RULE + "\n\n" + compat_r2.REQUEST_PRIORITY_RULE + "\n\n" + compat_r2.OTHER_CHANNEL_RULE
    if module.CONTRACT_VERSION == compat_r3.CONTRACT_VERSION:
        return lineage.REQUEST_INSTRUCTION + "\n\n" + compat_r2.REQUEST_ENUM_RULE + "\n\n" + compat_r2.REQUEST_PRIORITY_RULE + "\n\n" + compat_r2.OTHER_CHANNEL_RULE + "\n\n" + compat_r3.REQUEST_CATEGORY_RULE
    if module.CONTRACT_VERSION in (compat_r4.CONTRACT_VERSION, compat_r5.CONTRACT_VERSION):
        return lineage.REQUEST_INSTRUCTION + "\n\n" + compat_r2.REQUEST_ENUM_RULE + "\n\n" + compat_r2.REQUEST_PRIORITY_RULE + "\n\n" + compat_r2.OTHER_CHANNEL_RULE + "\n\n" + compat_r3.REQUEST_CATEGORY_RULE + "\n\n" + compat_r4.REQUEST_HOUSING_RULE
    return lineage.REQUEST_INSTRUCTION


def attention_parser(provider: str, raw: Any, spec: Mapping[str, Any] | None = None) -> dict[str, Any]:
    module = contract_module(spec or r3.spec())
    adapted = provider_adapters.normalize_provider_response(stage="ATTENTION", requested_provider=provider, requested_model="", transport_result={"raw_output": raw}, contract_version=module.CONTRACT_VERSION)
    if adapted["parse_status"] != provider_adapters.ParseStatus.PARSED:
        reason = adapted["normalization_notes"][-1]["reason"]
        if reason == "ANTHROPIC_EMITTED_RUNTIME_IDENTITY_CONTRADICTION":
            raise BindingError(reason)
        raise ValueError(reason)
    return adapted["canonical_payload"]


def generation_settings(spec: Mapping[str, Any], provider: str, stage: str) -> dict[str, Any]:
    module = contract_module(spec)
    if module.CONTRACT_VERSION in (compat_r2.CONTRACT_VERSION, compat_r3.CONTRACT_VERSION, compat_r4.CONTRACT_VERSION, compat_r5.CONTRACT_VERSION) and provider == "Anthropic" and stage == "ATTENTION":
        return {"max_output_tokens": compat_r2.ANTHROPIC_ATTENTION_MAX_TOKENS, "preserve_raw_before_parse": True}
    return {}


def normalize_request_item(item: Mapping[str, Any], spec: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    module = contract_module(spec)
    return provider_adapters.normalize_information_request_item(item, module.CONTRACT_VERSION)


def validate_attention_rank(rows: list[Mapping[str, Any]], spec: Mapping[str, Any]) -> None:
    """Reject malformed ordering metadata before a provider path reaches Requests."""
    module = contract_module(spec)
    if module.CONTRACT_VERSION != compat_r5.CONTRACT_VERSION:
        return
    rule = compat_r5.ATTENTION_RANK_RULE
    for row in rows:
        rank = row.get("attention_rank")
        if isinstance(rank, bool) or not isinstance(rank, int) or rank < rule["minimum"]:
            raise BindingError(rule["error"])


def forecast_prompt(input_row: Mapping[str, Any], provider: str, spec: Mapping[str, Any] | None = None) -> str:
    if provider not in ("Gemini", "OpenAI", "Anthropic"):
        raise BindingError("EXACT_PROVIDER_REQUIRED")
    module = contract_module(spec or r3.spec())
    base = parent.prospective_prompt_text(parent.prospective_context(input_row, parent.PROSPECTIVE_CONTRACT_VERSION), parent.PROSPECTIVE_CONTRACT_VERSION)
    provider_rule = module.PROMPT_RULES["gemini_pips"] if provider == "Gemini" else module.PROMPT_RULES["openai_reversal"] if provider == "OpenAI" else module.PROMPT_RULES["anthropic_json"]
    rule = (module.PROMPT_RULES["pip_representation"] + "\n" + provider_rule) if module.CONTRACT_VERSION in (compat_r3.CONTRACT_VERSION, compat_r4.CONTRACT_VERSION, compat_r5.CONTRACT_VERSION) else provider_rule
    return base + "\n\nR3 historical-verification compatibility rule: " + rule


def missingness(records: list[Mapping[str, Any]]) -> dict[str, Any]:
    forecast = [row for row in records if row.get("selection") == "FORECAST"]
    complete = [row for row in forecast if row.get("completion") == "COMPLETE_PAIRED"]
    difference = sum(int(row["pack_a_evaluation"]["direction_15m_ok"] is True) - int(row["pack_e_evaluation"]["direction_15m_ok"] is True) for row in complete)
    a_missing = sum(row.get("completion") == "INCOMPLETE_PACK_A" for row in forecast)
    e_missing = sum(row.get("completion") == "INCOMPLETE_PACK_E" for row in forecast)
    denominator = len(forecast)
    return {"estimand": "FORECAST_SELECTED_PAIRS", "denominator": denominator, "complete_case_difference": difference / len(complete) if complete else None, "worst_pack_a": (difference - a_missing - e_missing) / denominator if denominator else None, "worst_pack_e": (difference + a_missing + e_missing) / denominator if denominator else None, "incomplete_both": "excluded_symmetrically"}


def gate(manifest_path: Path = PREP) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    return {"status": "R3_RUNTIME_BINDING_VALIDATED", "manifest_path": str(manifest_path), "manifest_fingerprint": fingerprint(manifest), "contract": manifest["contract"], "provider_routes": manifest["providers"], "provider_calls": 0, "execution_enabled": False}
