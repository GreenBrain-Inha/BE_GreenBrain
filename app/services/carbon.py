"""Carbon calculation service."""

from __future__ import annotations

from ecologits.model_repository import models as ecologits_models
from ecologits.tracers.utils import llm_impacts


_ECOLOGITS_PROVIDER_BY_RUNYOUR_PROVIDER = {
    "openai": "openai",
    "anthropic": "anthropic",
    "gemini": "google_genai",
    "google": "google_genai",
}


def _numeric_value(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        pass

    minimum = getattr(value, "min", None)
    maximum = getattr(value, "max", None)
    if minimum is None or maximum is None:
        return None

    try:
        return (float(minimum) + float(maximum)) / 2.0
    except (TypeError, ValueError):
        return None


def carbon_gco2eq_from_openai_response(response: object) -> float | None:
    impacts = getattr(response, "impacts", None)
    if impacts is None:
        return None

    gwp = getattr(impacts, "gwp", None)
    if gwp is None:
        return None

    gwp_value = getattr(gwp, "value", gwp)
    numeric_value = _numeric_value(gwp_value)
    if numeric_value is None:
        return None

    return numeric_value * 1_000.0


def carbon_gco2eq_from_model_usage(
    *,
    model_id: str,
    output_token_count: int | None,
    request_latency: float,
) -> float | None:
    if output_token_count is None or output_token_count <= 0:
        return None

    provider, separator, model_name = model_id.partition("/")
    if not separator:
        return None

    ecologits_provider = _ECOLOGITS_PROVIDER_BY_RUNYOUR_PROVIDER.get(provider)
    if ecologits_provider is None:
        return None

    try:
        impacts = llm_impacts(
            provider=ecologits_provider,
            model_name=model_name,
            output_token_count=output_token_count,
            request_latency=request_latency,
            electricity_mix_zone=None,
        )
    except Exception:
        return None

    if impacts.has_errors or impacts.gwp is None:
        return None

    numeric_value = _numeric_value(impacts.gwp.value)
    if numeric_value is None:
        return None

    return numeric_value * 1_000.0


def is_carbon_supported_model(model_id: str) -> bool:
    provider, separator, model_name = model_id.partition("/")
    if not separator:
        return False

    ecologits_provider = _ECOLOGITS_PROVIDER_BY_RUNYOUR_PROVIDER.get(provider)
    if ecologits_provider is None:
        return False

    return ecologits_models.find_model(
        provider=ecologits_provider,
        model_name=model_name,
    ) is not None
