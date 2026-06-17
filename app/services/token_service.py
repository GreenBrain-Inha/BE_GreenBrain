"""Daily token state and token account service."""

from __future__ import annotations

import math
from datetime import date, datetime, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.common.exceptions.custom import TokenExhaustedException as TokenExhausted
from app.models import DailyTokenState, TokenTransaction


# 잔액·차감·보상 단위는 모두 mgCO₂eq(정수). 별도 토큰 단위 없이 탄소 배출량을 그대로 쓴다.
DEFAULT_DAILY_TOKENS = 15_000  # 하루 기본 15g CO₂eq
LIKE_REWARD_AMOUNT = 2_000     # 좋아요 보상 2g CO₂eq
KST = ZoneInfo("Asia/Seoul")


def today_kst(now: datetime | None = None) -> date:
    """현재 시각을 KST 기준 날짜로 변환한다."""

    current = now or datetime.now(timezone.utc)
    return current.astimezone(KST).date()


def mgco2_from_carbon(carbon_gco2eq: float | None) -> int | None:
    """탄소 배출량(gCO₂eq)을 차감량(mgCO₂eq 정수)으로 변환한다. 올림, 최소 1."""

    if carbon_gco2eq is None:
        return None
    return max(1, math.ceil(carbon_gco2eq * 1000))


class TokenService:
    """일일 토큰 상태 생성, 사용량 차감, 보상 지급을 처리한다."""

    def __init__(self, db: Session):
        self.db = db

    def get_or_create_today_state(self, user_id: UUID) -> DailyTokenState:
        """오늘의 토큰 상태를 조회하고, 없으면 기본 토큰 상태를 생성한다."""

        current_date = today_kst()
        self.db.execute(
            insert(DailyTokenState)
            .values(
                user_id=user_id,
                date=current_date,
                tokens_remaining=DEFAULT_DAILY_TOKENS,
                upload_reward_given=0,
                like_reward_given=0,
                total_reward_given=0,
                challenge_count=0,
            )
            .on_conflict_do_nothing()
        )
        state = self.db.get(DailyTokenState, {"user_id": user_id, "date": current_date})
        if state is None:
            raise RuntimeError("Failed to get or create daily token state")
        return state

    def get_today_state(self, user_id: UUID) -> DailyTokenState:
        """토큰 조회 API에서 사용할 오늘의 토큰 상태를 반환한다."""

        state = self.get_or_create_today_state(user_id)
        self.db.commit()
        self.db.refresh(state)
        return state

    def ensure_chat_tokens_available(self, state: DailyTokenState) -> None:
        """채팅 전송 전에 사용할 수 있는 토큰이 남아 있는지 확인한다."""

        if state.tokens_remaining <= 0:
            raise TokenExhausted

    def deduct_chat_usage(
        self,
        *,
        state: DailyTokenState,
        user_id: UUID,
        message_id: UUID,
        carbon_gco2eq: float | None,
    ) -> tuple[int, bool]:
        """채팅 응답의 탄소 배출량(mgCO₂eq)만큼 차감하고 (차감량, 소진 여부)를 반환한다."""

        deduction = mgco2_from_carbon(carbon_gco2eq)
        if deduction is None:
            return 0, state.tokens_remaining <= 0

        deduction = min(deduction, state.tokens_remaining)
        state.tokens_remaining = state.tokens_remaining - deduction
        transaction = TokenTransaction(
            user_id=user_id,
            daily_state_date=state.date,
            type="chat_usage",
            amount=-deduction,
            balance_after=state.tokens_remaining,
            source_type="message",
            source_id=message_id,
            memo="Chat message carbon usage",
        )
        self.db.add(transaction)
        return deduction, state.tokens_remaining <= 0

    def grant_like_reward(
        self,
        *,
        state: DailyTokenState,
        user_id: UUID,
        photo_id: UUID,
        milestone: int,
    ) -> int:
        """좋아요 milestone 보상을 지급하고 실제 지급량을 반환한다."""

        reward_amount = LIKE_REWARD_AMOUNT
        state.tokens_remaining += reward_amount
        state.like_reward_given += reward_amount
        state.total_reward_given += reward_amount

        transaction = TokenTransaction(
            user_id=user_id,
            daily_state_date=state.date,
            type="like_reward",
            amount=reward_amount,
            balance_after=state.tokens_remaining,
            source_type="photo",
            source_id=photo_id,
            milestone=milestone,
            memo="Challenge photo like milestone reward",
        )
        self.db.add(transaction)
        return reward_amount
