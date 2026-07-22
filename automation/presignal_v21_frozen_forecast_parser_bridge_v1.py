"""Compatibility bridge from the immutable historical parser to adapter facts."""
from __future__ import annotations

from typing import Any, Mapping

from automation.presignal_v21_provider_adapters_v1 import ParseStatus, ValidationStatus


def adapt_frozen_forecast_parse_result(*, requested_provider: str, requested_model: str,
                                       actual_provider: str | None, actual_model: str | None,
                                       raw_response: Any, frozen_parse_result: Mapping[str, Any] | None,
                                       frozen_parse_error: Exception | str | None = None,
                                       provider_metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Represent a frozen parser outcome without reparsing or revalidating it."""
    parsed = frozen_parse_result is not None and frozen_parse_error is None
    error = None if frozen_parse_error is None else str(frozen_parse_error)
    return {
        "requested_provider": requested_provider, "requested_model": requested_model,
        "actual_provider": actual_provider, "actual_model": actual_model,
        "raw_response": raw_response, "raw_response_reference": None,
        # Deliberately retain the parser object; no JSON round-trip is allowed.
        "canonical_payload": frozen_parse_result if parsed else None,
        "parse_status": ParseStatus.PARSED if parsed else ParseStatus.PARSE_FAILED,
        "validation_status": ValidationStatus.VALID if parsed else ValidationStatus.INVALID,
        "normalization_notes": [{"source_parser": "run_presignal_v21_single_event_path_pair_v1.parse_provider_output"}] + ([{"frozen_parser_error": error}] if error else []),
        "provider_metadata": dict(provider_metadata or {}),
    }
