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
        "대기전력 끄기",
        "오늘 한 번 사용하지 않는 조명과 충전기의 전원을 꺼 보세요.",
    ),
    (
        "energy",
        "조명 사용 1시간 줄이기",
        "오늘 1시간 동안 자연광을 활용하거나 필요한 공간의 조명만 켜 보세요.",
    ),
    (
        "lifestyle",
        "샤워 시간 줄이기",
        "오늘 샤워 시간을 한 번 짧게 줄여 따뜻한 물과 에너지를 아껴 보세요.",
    ),
)
CAR_TRANSPORT_OPTIONS = (
    (
        "transport",
        "가까운 거리는 도보나 자전거 이용하기",
        "오늘 가까운 거리 이동 한 번을 자동차 대신 걷기나 자전거로 바꿔 보세요.",
    ),
    (
        "transport",
        "짧은 차량 이동 1회 줄이기",
        "오늘 짧은 차량 이동 한 번을 줄이고 가까운 선택지나 묶음 이동을 활용해 보세요.",
    ),
    (
        "transport",
        "대중교통 또는 도보로 한 번 이동하기",
        "오늘 이동 한 번은 자동차 대신 대중교통, 도보, 자전거 중 하나를 선택해 보세요.",
    ),
)
LOW_CARBON_TRANSPORT_OPTIONS = (
    (
        "transport",
        "저탄소 이동 한 번 실천하기",
        "오늘 한 번은 대중교통, 걷기, 자전거처럼 탄소 배출이 적은 방식으로 이동해 보세요.",
    ),
    (
        "transport",
        "이동 동선 효율화하기",
        "오늘 가까운 볼일을 한 번에 묶어 불필요한 이동을 줄여 보세요.",
    ),
)
OMNIVORE_DIET_OPTIONS = (
    (
        "diet",
        "채식 중심 한 끼 먹기",
        "오늘 한 끼는 채소, 곡물, 콩류를 중심으로 구성해 보세요.",
    ),
    (
        "diet",
        "육류 없는 식사 한 번 하기",
        "오늘 한 끼는 육류를 제외하고 탄소 배출이 적은 단백질을 선택해 보세요.",
    ),
    (
        "diet",
        "제철 채소 활용하기",
        "오늘 한 끼에 제철 채소를 활용해 식사를 준비하거나 선택해 보세요.",
    ),
)
LOW_CARBON_DIET_OPTIONS = (
    (
        "diet",
        "음식물 쓰레기 줄이기",
        "오늘 한 끼는 먹을 수 있는 음식이 버려지지 않도록 식사량을 계획해 보세요.",
    ),
    (
        "diet",
        "남은 재료 활용하기",
        "오늘 남은 재료를 활용해 한 끼나 간식을 만들어 보세요.",
    ),
    (
        "diet",
        "포장 적은 식사 선택하기",
        "오늘 한 번은 일회용 포장이 적은 식사나 간식을 선택해 보세요.",
    ),
)
HOME_ENERGY_OPTIONS = (
    (
        "energy",
        "대기전력 차단하기",
        "오늘 사용하지 않는 전자기기 플러그나 충전기를 한 번 뽑아 보세요.",
    ),
    (
        "energy",
        "냉난방 사용 1시간 줄이기",
        "오늘 1시간 동안 냉난방 사용을 줄이고 실내 온도를 조절해 보세요.",
    ),
    (
        "lifestyle",
        "물 사용 줄이기",
        "오늘 샤워, 세탁, 설거지 중 한 가지에서 물 사용량을 줄여 보세요.",
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
