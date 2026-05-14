"""KST daily token state service."""

from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import DailyTokenState


DEFAULT_DAILY_TOKENS = 150.0
KST = ZoneInfo("Asia/Seoul")


def today_kst(now: datetime | None = None) -> date:
    current = now or datetime.now(timezone.utc)
    return current.astimezone(KST).date()


def get_or_create_today_state(db: Session, user_id: UUID) -> DailyTokenState:
    current_date = today_kst()
    db.execute(
        insert(DailyTokenState)
        .values(
            user_id=user_id,
            date=current_date,
            tokens_remaining=DEFAULT_DAILY_TOKENS,
            upload_reward_given=0.0,
            like_reward_given=0.0,
            total_reward_given=0.0,
            challenge_count=0,
        )
        .on_conflict_do_nothing()
    )
    return db.get(DailyTokenState, {"user_id": user_id, "date": current_date})
