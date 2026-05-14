"""Token account service — handles both earning and spending of daily tokens."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models import DailyTokenState, TokenTransaction


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
