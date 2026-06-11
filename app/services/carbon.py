"""Carbon calculation service."""

from __future__ import annotations

from dataclasses import dataclass

from ecologits.model_repository import models as ecologits_models
from ecologits.tracers.utils import llm_impacts


_ECOLOGITS_PROVIDER_BY_RUNYOUR_PROVIDER = {
    "openai": "openai",
    "anthropic": "anthropic",
    "gemini": "google_genai",
    "google": "google_genai",
}

# 1인 연간 기준값 (NF) — 정규화에 사용
# gwp/adpe/pe/wcf: EF 3.1 (JRC130796, Table 10, 기준년도 2010)
# energy: IEA World Energy Statistics 2022
_NF = {
    "gwp":    7.55e3,   # kgCO₂eq
    "adpe":   6.36e-2,  # kgSbeq
    "pe":     6.50e4,   # MJ
    "energy": 3.50e3,   # kWh
    "wcf":    1.15e4,   # m³
}


@dataclass
class GreenBrainScore:
    score_npy: float    # GreenBrain Score (nPY)
    gwp: float          # kgCO₂eq
    adpe: float         # kgSbeq
    pe: float           # MJ
    energy: float       # kWh
    wcf: float          # L


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


def calc_greenbrain_score(
    gwp: float,
    adpe: float,
    pe: float,
    energy: float,
    wcf: float,
) -> float:
    """5개 EcoLogits 지표로 GreenBrain Score(nPY)를 계산한다."""
    wcf_m3 = wcf / 1000
    score_raw = (1 / 5) * (
        gwp    / _NF["gwp"]    +
        adpe   / _NF["adpe"]   +
        pe     / _NF["pe"]     +
        energy / _NF["energy"] +
        wcf_m3 / _NF["wcf"]
    )
    return score_raw * 1e9


def greenbrain_score_from_model_usage(
    *,
    model_id: str,
    output_token_count: int | None,
    request_latency: float,
) -> GreenBrainScore | None:
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

    if impacts.has_errors:
        return None

    gwp    = _numeric_value(getattr(getattr(impacts, "gwp",    None), "value", None))
    adpe   = _numeric_value(getattr(getattr(impacts, "adpe",   None), "value", None))
    pe     = _numeric_value(getattr(getattr(impacts, "pe",     None), "value", None))
    energy = _numeric_value(getattr(getattr(impacts, "energy", None), "value", None))
    wcf    = _numeric_value(getattr(getattr(impacts, "wcf",    None), "value", None))

    if any(v is None for v in (gwp, adpe, pe, energy, wcf)):
        return None

    return GreenBrainScore(
        score_npy=calc_greenbrain_score(gwp, adpe, pe, energy, wcf),
        gwp=gwp,
        adpe=adpe,
        pe=pe,
        energy=energy,
        wcf=wcf,
    )
