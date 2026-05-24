"""Challenge current/generate/accept service logic."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.exceptions.custom import (
    ChallengeGenerationFailedException as ChallengeGenerationFailed,
    ChallengeNotFoundException as ChallengeNotFound,
    ChallengeNotPendingException as ChallengeNotPending,
    DailyChallengeLimitReachedException as DailyChallengeLimitReached,
    TokenNotExhaustedException as TokenNotExhausted,
)
from app.models import Challenge, UserProfile
from app.services.token_service import TokenService


OPEN_CHALLENGE_STATUSES = ("pending_acceptance", "active")
DAILY_CHALLENGE_LIMIT = 3


@dataclass(frozen=True)
class ChallengeCandidate:
    category: str
    title: str
    description: str
    difficulty: int


class ChallengeService:
    """Handle challenge current/generate/accept use cases."""

    def __init__(self, db: Session):
        self.db = db

    def get_current(self, user_id: UUID) -> Challenge | None:
        return self.db.scalar(
            select(Challenge)
            .where(
                Challenge.user_id == user_id,
                Challenge.status.in_(OPEN_CHALLENGE_STATUSES),
            )
            .order_by(Challenge.created_at.desc())
        )

    def generate(self, user_id: UUID) -> tuple[Challenge, bool]:
        existing = self.get_current(user_id)
        if existing is not None:
            return existing, False

        state = TokenService(self.db).get_or_create_today_state(user_id)
        if state.tokens_remaining > 0:
            raise TokenNotExhausted
        if state.challenge_count >= DAILY_CHALLENGE_LIMIT:
            raise DailyChallengeLimitReached

        profile = self.db.get(UserProfile, user_id)
        candidate = _build_challenge_candidate(
            profile=profile,
            completed_count=self._completed_challenge_count(user_id),
        )
        if not candidate.title or not candidate.description:
            raise ChallengeGenerationFailed

        challenge = Challenge(
            user_id=user_id,
            category=candidate.category,
            title=candidate.title,
            description=candidate.description,
            difficulty=candidate.difficulty,
            status="pending_acceptance",
        )
        state.challenge_count += 1
        self.db.add(challenge)
        self.db.commit()
        self.db.refresh(challenge)
        return challenge, True

    def accept(self, user_id: UUID, challenge_id: UUID) -> Challenge:
        challenge = self.db.scalar(
            select(Challenge).where(
                Challenge.id == challenge_id,
                Challenge.user_id == user_id,
            )
        )
        if challenge is None:
            raise ChallengeNotFound
        if challenge.status != "pending_acceptance":
            raise ChallengeNotPending

        challenge.status = "active"
        self.db.commit()
        self.db.refresh(challenge)
        return challenge

    def _completed_challenge_count(self, user_id: UUID) -> int:
        return self.db.scalar(
            select(sa.func.count())
            .select_from(Challenge)
            .where(Challenge.user_id == user_id, Challenge.status == "completed")
        ) or 0


def _difficulty_for_completed_count(completed_count: int) -> int:
    return min(3, max(1, (completed_count // 3) + 1))


def _build_challenge_candidate(
    *,
    profile: UserProfile | None,
    completed_count: int,
) -> ChallengeCandidate:
    difficulty = _difficulty_for_completed_count(completed_count)
    if profile is None:
        return ChallengeCandidate(
            category="energy",
            title="Standby power off",
            description="Turn off unused lights and unplug idle chargers once today.",
            difficulty=difficulty,
        )

    if profile.transport_mode == "car":
        return ChallengeCandidate(
            category="transport",
            title="Use low-carbon transport once",
            description="Replace one short car trip with walking, transit, or cycling today.",
            difficulty=difficulty,
        )

    if profile.diet_type == "omnivore":
        return ChallengeCandidate(
            category="diet",
            title="Choose one plant-forward meal",
            description="Make one meal today centered on vegetables, grains, or beans.",
            difficulty=difficulty,
        )

    return ChallengeCandidate(
        category="energy",
        title="Reduce home energy for one hour",
        description="Run one hour today with fewer lights or lower heating and cooling demand.",
        difficulty=difficulty,
    )
