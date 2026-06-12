import re
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql

import app.models  # noqa: F401 - populate SQLAlchemy metadata
from app.db import Base, SessionLocal, configure_database


EXPECTED_TABLES = {
    "users",
    "user_profiles",
    "chat_sessions",
    "messages",
    "daily_token_state",
    "token_transactions",
    "challenges",
    "challenge_photos",
    "likes",
}

INITIAL_MIGRATION_TABLES = EXPECTED_TABLES - {"chat_sessions"}


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
    assert daily_state.c.tokens_remaining.default.arg == 15_000
    assert daily_state.c.upload_reward_given.default.arg == 0.0
    assert daily_state.c.like_reward_given.default.arg == 0.0
    assert daily_state.c.total_reward_given.default.arg == 0.0
    assert daily_state.c.challenge_count.default.arg == 0


def test_relationship_constraints_and_indexes_are_declared() -> None:
    tables = Base.metadata.tables

    messages = tables["messages"]
    assert "session_id" in messages.c
    assert not messages.c.session_id.nullable
    assert "model_id" in messages.c
    assert messages.c.model_id.nullable

    chat_sessions = tables["chat_sessions"]
    assert "ix_chat_sessions_user_id" in {
        index.name for index in chat_sessions.indexes
    }

    token_transactions = tables["token_transactions"]
    composite_foreign_keys = [
        constraint
        for constraint in token_transactions.foreign_key_constraints
        if {column.name for column in constraint.columns} == {"user_id", "daily_state_date"}
    ]
    assert composite_foreign_keys
    assert {
        element.column.table.name
        for element in composite_foreign_keys[0].elements
    } == {"daily_token_state"}

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
    for table_name in INITIAL_MIGRATION_TABLES:
        assert re.search(rf'op\.create_table\(\s*"{table_name}"', contents)

    assert '["user_id", "daily_state_date"]' in contents
    assert '["daily_token_state.user_id", "daily_token_state.date"]' in contents


def test_chat_session_alembic_migration_adds_session_table_and_message_fk() -> None:
    migration = Path("alembic/versions/20260514_0001_add_chat_sessions.py")

    assert migration.exists()
    contents = migration.read_text()
    assert re.search(r'op\.create_table\(\s*"chat_sessions"', contents)
    assert 'op.add_column("messages"' in contents
    assert '"session_id"' in contents
    assert '"fk_messages_session_id_chat_sessions"' in contents


def test_message_model_id_migration_adds_nullable_model_id() -> None:
    migration = Path("alembic/versions/20260518_0001_add_message_model_id.py")

    assert migration.exists()
    contents = migration.read_text()
    assert 'op.add_column("messages"' in contents
    assert '"model_id"' in contents
    assert "nullable=True" in contents


def test_session_local_is_bound_when_database_is_configured() -> None:
    engine = create_engine("sqlite:///:memory:")
    configure_database(engine=engine)

    with SessionLocal() as session:
        assert session.execute(sa.text("select 1")).scalar_one() == 1
