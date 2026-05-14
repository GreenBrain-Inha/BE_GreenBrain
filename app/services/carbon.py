"""Carbon calculation service."""

from __future__ import annotations


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

    return numeric_value * 1000.0
