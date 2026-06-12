"""탄소 예산(mgCO₂eq) 캘리브레이션 도구.

대표 모델과 응답 토큰 수별 탄소 배출량(mgCO₂eq 차감량)을 출력하고,
하루 기본 예산(DEFAULT_DAILY_TOKENS) 기준 가능 메시지 수를 보여준다.
일일 예산을 조정할 때 근거 자료로 사용한다. (읽기 전용)

실행:
    .venv/bin/python scripts/calibrate_carbon_budget.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.carbon import carbon_gco2eq_from_model_usage
from app.services.token_service import DEFAULT_DAILY_TOKENS, mgco2_from_carbon

MODELS = [
    "openai/gpt-4.1-2025-04-14",
    "openai/gpt-4o-mini",
    "anthropic/claude-sonnet-4-6",
    "gemini/gemini-2.5-pro",
]
OUTPUT_TOKENS = [100, 300, 500, 1000]


def _mg(model_id: str, output_tokens: int) -> int | None:
    carbon = carbon_gco2eq_from_model_usage(
        model_id=model_id,
        output_token_count=output_tokens,
        # latency는 탄소량의 usage 성분에 미미하게 작용하므로 토큰 수 기반 근사값을 쓴다.
        request_latency=output_tokens / 50.0,
    )
    return mgco2_from_carbon(carbon)


def main() -> None:
    header = "model".ljust(34) + "".join(f"{t:>10}" for t in OUTPUT_TOKENS)
    print("=== 메시지당 차감량 (mgCO₂eq) per output tokens ===")
    print(header)
    for model_id in MODELS:
        row = model_id.ljust(34)
        for tokens in OUTPUT_TOKENS:
            mg = _mg(model_id, tokens)
            row += f"{mg:>10}" if mg is not None else f"{'n/a':>10}"
        print(row)

    print()
    print(f"=== 하루 기본 예산 {DEFAULT_DAILY_TOKENS} mgCO₂eq 기준 가능 메시지 수 (300토큰 응답) ===")
    for model_id in MODELS:
        mg = _mg(model_id, 300)
        if mg is None:
            print(f"{model_id:34} n/a")
            continue
        print(f"{model_id:34} {mg:>6} mg/메시지 → {DEFAULT_DAILY_TOKENS // mg}개")


if __name__ == "__main__":
    main()
