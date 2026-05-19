from __future__ import annotations

from types import SimpleNamespace

from app.services.carbon import carbon_gco2eq_from_model_usage, carbon_gco2eq_from_openai_response


def test_carbon_gco2eq_from_scalar_kgco2eq_value() -> None:
    response = SimpleNamespace(
        impacts=SimpleNamespace(gwp=SimpleNamespace(value=0.0012))
    )

    assert carbon_gco2eq_from_openai_response(response) == 1.2


def test_carbon_gco2eq_from_ecologits_range_kgco2eq_value() -> None:
    response = SimpleNamespace(
        impacts=SimpleNamespace(
            gwp=SimpleNamespace(value=SimpleNamespace(min=0.001, max=0.003))
        )
    )

    assert carbon_gco2eq_from_openai_response(response) == 2.0


def test_carbon_gco2eq_returns_none_without_impacts() -> None:
    assert carbon_gco2eq_from_openai_response(object()) is None


def test_carbon_gco2eq_from_model_usage_supports_openai_anthropic_google() -> None:
    for model_id in [
        "openai/gpt-5.2",
        "anthropic/claude-sonnet-4-6",
        "gemini/gemini-2.5-pro",
        "google/gemini-2.5-pro",
    ]:
        carbon = carbon_gco2eq_from_model_usage(
            model_id=model_id,
            output_token_count=10,
            request_latency=1.0,
        )

        assert carbon is not None
        assert carbon > 0


def test_carbon_gco2eq_from_model_usage_returns_none_for_unknown_model() -> None:
    assert (
        carbon_gco2eq_from_model_usage(
            model_id="openai/not-registered",
            output_token_count=10,
            request_latency=1.0,
        )
        is None
    )
