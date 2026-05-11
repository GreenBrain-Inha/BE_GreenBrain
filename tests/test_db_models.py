import re
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

import app.models  # noqa: F401 - populate SQLAlchemy metadata
from app.db import Base


EXPECTED_TABLES = {
    "users",
    "user_profiles",
    "messages",
    "daily_token_state",
    "token_transactions",
    "challenges",
    "challenge_photos",
    "likes",
}


def test_architecture_tables_are_declared() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_users_table_matches_auth_requirements() -> None:
    users = Base.metadata.tables["users"]

    assert isinstance(users.c.id.type, postgresql.UUID)
    assert users.c.id.primary_key
    assert users.c.email.unique
    assert not users.c.email.nullable
    assert not users.c.password_hash.nullable
    assert not users.c.created_at.nullable


def test_daily_token_state_has_composite_primary_key() -> None:
    daily_state = Base.metadata.tables["daily_token_state"]

    assert [column.name for column in daily_state.primary_key.columns] == [
        "user_id",
        "date",
    ]
    assert daily_state.c.tokens_remaining.default.arg == 150.0
    assert daily_state.c.upload_reward_given.default.arg == 0.0
    assert daily_state.c.like_reward_given.default.arg == 0.0
    assert daily_state.c.total_reward_given.default.arg == 0.0
    assert daily_state.c.challenge_count.default.arg == 0


def test_relationship_constraints_and_indexes_are_declared() -> None:
    tables = Base.metadata.tables

    challenge_photos = tables["challenge_photos"]
    assert challenge_photos.c.challenge_id.unique

    likes = tables["likes"]
    unique_constraints = [
        constraint
        for constraint in likes.constraints
        if isinstance(constraint, sa.UniqueConstraint)
    ]
    assert {"photo_id", "liker_user_id"} in [
        {column.name for column in constraint.columns}
        for constraint in unique_constraints
    ]

    token_transactions = tables["token_transactions"]
    assert "uq_token_transactions_like_reward_milestone" in {
        index.name for index in token_transactions.indexes
    }

    challenges = tables["challenges"]
    assert "uq_challenges_one_open_per_user" in {
        index.name for index in challenges.indexes
    }


def test_initial_alembic_migration_creates_all_architecture_tables() -> None:
    migration = Path("alembic/versions/20260512_0001_create_core_tables.py")

    assert migration.exists()
    contents = migration.read_text()
    for table_name in EXPECTED_TABLES:
        assert re.search(rf'op\.create_table\(\s*"{table_name}"', contents)
