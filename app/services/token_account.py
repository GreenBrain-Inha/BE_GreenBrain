"""Token account service — handles both earning and spending of daily tokens."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models import DailyTokenState, TokenTransaction

MAX_DAILY_TOKENS = 150.0
UPLOAD_REWARD_AMOUNT = 20.0
LIKE_REWARD_AMOUNT = 20.0


class TokenExhausted(Exception):
    """Raised when chat usage is attempted without remaining tokens."""


def ensure_chat_tokens_available(state: DailyTokenState) -> None:
    if state.tokens_remaining <= 0:
        raise TokenExhausted


def deduct_chat_usage(
    db: Session,
    *,
    state: DailyTokenState,
    user_id: UUID,
    message_id: UUID,
    carbon_gco2eq: float | None,
) -> bool:
    if carbon_gco2eq is None:
        return state.tokens_remaining <= 0

    deduction = max(carbon_gco2eq, 0.0)
    state.tokens_remaining = max(state.tokens_remaining - deduction, 0.0)
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
    db.add(transaction)
    return state.tokens_remaining <= 0


def grant_upload_reward(
    db: Session,
    *,
    state: DailyTokenState,
    user_id: UUID,
    photo_id: UUID,
) -> float:
    reward_amount = min(
        UPLOAD_REWARD_AMOUNT,
        max(MAX_DAILY_TOKENS - state.tokens_remaining, 0.0),
    )
    state.tokens_remaining = min(state.tokens_remaining + reward_amount, MAX_DAILY_TOKENS)
    state.upload_reward_given += reward_amount
    state.total_reward_given += reward_amount

    transaction = TokenTransaction(
        user_id=user_id,
        daily_state_date=state.date,
        type="upload_reward",
        amount=reward_amount,
        balance_after=state.tokens_remaining,
        source_type="photo",
        source_id=photo_id,
        memo="Challenge photo upload reward",
    )
    db.add(transaction)
    return reward_amount


def grant_like_reward(
    db: Session,
    *,
    state: DailyTokenState,
    user_id: UUID,
    photo_id: UUID,
    milestone: int,
) -> float:
    reward_amount = min(
        LIKE_REWARD_AMOUNT,
        max(MAX_DAILY_TOKENS - state.tokens_remaining, 0.0),
    )
    state.tokens_remaining = min(state.tokens_remaining + reward_amount, MAX_DAILY_TOKENS)
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
    db.add(transaction)
    return reward_amount
