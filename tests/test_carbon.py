from __future__ import annotations

from types import SimpleNamespace

from app.services.carbon import carbon_gco2eq_from_openai_response


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
