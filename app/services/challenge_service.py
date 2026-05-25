"""Challenge current/generate/accept service logic."""

from __future__ import annotations

import random
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
)
from app.models import Challenge, UserProfile
from app.services.token_service import TokenService


OPEN_CHALLENGE_STATUSES = ("pending_acceptance", "active")
DAILY_CHALLENGE_LIMIT = 3
DEFAULT_CHALLENGE_OPTIONS = (
    (
        "energy",
        "Standby power off",
        "Turn off unused lights and unplug idle chargers once today.",
    ),
    (
        "energy",
        "Reduce lighting for one hour",
        "Use less lighting for one hour today by relying on daylight or fewer rooms.",
    ),
    (
        "lifestyle",
        "Take one shorter shower",
        "Reduce shower time once today to save warm water and energy.",
    ),
)
CAR_TRANSPORT_OPTIONS = (
    (
        "transport",
        "Walk or cycle one nearby trip",
        "Replace one nearby car trip with walking or cycling today.",
    ),
    (
        "transport",
        "Skip one short car ride",
        "Avoid one short vehicle trip by combining errands or choosing a closer option.",
    ),
    (
        "transport",
        "Use transit or walking once",
        "Choose public transit, walking, or cycling for one trip instead of driving.",
    ),
)
LOW_CARBON_TRANSPORT_OPTIONS = (
    (
        "transport",
        "Keep one low-carbon trip",
        "Make one trip today by transit, walking, cycling, or another low-carbon option.",
    ),
    (
        "transport",
        "Plan one efficient route",
        "Group nearby errands into one route to reduce unnecessary travel.",
    ),
)
OMNIVORE_DIET_OPTIONS = (
    (
        "diet",
        "Choose one plant-forward meal",
        "Make one meal today centered on vegetables, grains, or beans.",
    ),
    (
        "diet",
        "Eat one meat-free meal",
        "Have one meal today without meat and choose a lower-carbon protein.",
    ),
    (
        "diet",
        "Use seasonal vegetables once",
        "Prepare or choose one meal using seasonal vegetables today.",
    ),
)
LOW_CARBON_DIET_OPTIONS = (
    (
        "diet",
        "Reduce food waste once",
        "Plan one meal today to avoid throwing away edible food.",
    ),
    (
        "diet",
        "Use leftover ingredients",
        "Use leftover ingredients for one meal or snack today.",
    ),
    (
        "diet",
        "Choose less packaging",
        "Pick one meal or snack with less disposable packaging today.",
    ),
)
HOME_ENERGY_OPTIONS = (
    (
        "energy",
        "Cut standby power",
        "Turn off unused lights and unplug idle chargers once today.",
    ),
    (
        "energy",
        "Reduce heating or cooling for one hour",
        "Run one hour today with lower heating or cooling demand.",
    ),
    (
        "lifestyle",
        "Save water once",
        "Use less water during one shower, wash, or cleaning task today.",
    ),
)


@dataclass(frozen=True)
class ChallengeCandidate:
    category: str
    title: str
    description: str
    difficulty: int


class ChallengeService:
    """Handle the challenge current, generate, and accept use cases.

    The challenges router calls this service for the core challenge lifecycle endpoints.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_current(self, user_id: UUID) -> Challenge | None:
        """Return the user's latest open challenge for the current endpoint."""

        return self.db.scalar(
            select(Challenge)
            .where(
                Challenge.user_id == user_id,
                Challenge.status.in_(OPEN_CHALLENGE_STATUSES),
            )
            .order_by(Challenge.created_at.desc())
        )

    def generate(self, user_id: UUID) -> tuple[Challenge, bool]:
        """열린 챌린지가 있으면 반환하고, 없으면 토큰 잔량과 관계없이 새 챌린지를 생성한다."""

        existing = self.get_current(user_id)
        if existing is not None:
            return existing, False

        state = TokenService(self.db).get_or_create_today_state(user_id)
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
        """Accept a pending challenge owned by the user."""

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
    """온보딩 값을 기반으로 후보를 구성하고 그중 하나를 선택한다."""

    difficulty = _difficulty_for_completed_count(completed_count)
    if profile is None:
        return random.choice(_build_candidates(DEFAULT_CHALLENGE_OPTIONS, difficulty))

    options: list[tuple[str, str, str]] = []
    if profile.transport_mode == "car":
        options.extend(CAR_TRANSPORT_OPTIONS)
    elif profile.transport_mode in {"transit", "walk", "bike", "mixed"}:
        options.extend(LOW_CARBON_TRANSPORT_OPTIONS)

    if profile.diet_type == "omnivore":
        options.extend(OMNIVORE_DIET_OPTIONS)
    elif profile.diet_type in {"vegetarian", "vegan", "flexitarian"}:
        options.extend(LOW_CARBON_DIET_OPTIONS)

    if profile.housing_type in {"apartment", "house", "studio", "dorm", "other"}:
        options.extend(HOME_ENERGY_OPTIONS)

    if not options:
        options.extend(DEFAULT_CHALLENGE_OPTIONS)

    return random.choice(_build_candidates(tuple(options), difficulty))


def _build_candidates(
    options: tuple[tuple[str, str, str], ...],
    difficulty: int,
) -> list[ChallengeCandidate]:
    """후보 정의에 현재 난이도를 적용해 ChallengeCandidate 목록을 만든다."""

    return [
        ChallengeCandidate(
            category=category,
            title=title,
            description=description,
            difficulty=difficulty,
        )
        for category, title, description in options
    ]
