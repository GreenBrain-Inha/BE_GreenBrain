"""create core tables

Revision ID: 20260512_0001
Revises:
Create Date: 2026-05-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260512_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=False)

    op.create_table(
        "user_profiles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transport_mode", sa.String(), nullable=False),
        sa.Column("diet_type", sa.String(), nullable=False),
        sa.Column("housing_type", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("carbon_gco2eq", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_messages_user_id"), "messages", ["user_id"], unique=False)

    op.create_table(
        "daily_token_state",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("tokens_remaining", sa.Float(), server_default=sa.text("150.0"), nullable=False),
        sa.Column("upload_reward_given", sa.Float(), server_default=sa.text("0.0"), nullable=False),
        sa.Column("like_reward_given", sa.Float(), server_default=sa.text("0.0"), nullable=False),
        sa.Column("total_reward_given", sa.Float(), server_default=sa.text("0.0"), nullable=False),
        sa.Column("challenge_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "date"),
    )

    op.create_table(
        "token_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("daily_state_date", sa.Date(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("balance_after", sa.Float(), nullable=False),
        sa.Column("source_type", sa.String(), nullable=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("milestone", sa.Integer(), nullable=True),
        sa.Column("memo", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_token_transactions_user_id"), "token_transactions", ["user_id"], unique=False)
    op.create_index(
        "uq_token_transactions_like_reward_milestone",
        "token_transactions",
        ["source_type", "source_id", "milestone"],
        unique=True,
        postgresql_where=sa.text("type = 'like_reward'"),
    )

    op.create_table(
        "challenges",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("difficulty", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_challenges_user_id"), "challenges", ["user_id"], unique=False)
    op.create_index(
        "uq_challenges_one_open_per_user",
        "challenges",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending_acceptance', 'active')"),
    )

    op.create_table(
        "challenge_photos",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("challenge_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_path", sa.String(), nullable=False),
        sa.Column("upload_rewarded", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["challenge_id"], ["challenges.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("challenge_id"),
    )
    op.create_index(op.f("ix_challenge_photos_user_id"), "challenge_photos", ["user_id"], unique=False)

    op.create_table(
        "likes",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("photo_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("liker_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["liker_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["photo_id"], ["challenge_photos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("photo_id", "liker_user_id", name="uq_likes_photo_id_liker_user_id"),
    )
    op.create_index(op.f("ix_likes_liker_user_id"), "likes", ["liker_user_id"], unique=False)
    op.create_index(op.f("ix_likes_photo_id"), "likes", ["photo_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_likes_photo_id"), table_name="likes")
    op.drop_index(op.f("ix_likes_liker_user_id"), table_name="likes")
    op.drop_table("likes")
    op.drop_index(op.f("ix_challenge_photos_user_id"), table_name="challenge_photos")
    op.drop_table("challenge_photos")
    op.drop_index("uq_challenges_one_open_per_user", table_name="challenges")
    op.drop_index(op.f("ix_challenges_user_id"), table_name="challenges")
    op.drop_table("challenges")
    op.drop_index("uq_token_transactions_like_reward_milestone", table_name="token_transactions")
    op.drop_index(op.f("ix_token_transactions_user_id"), table_name="token_transactions")
    op.drop_table("token_transactions")
    op.drop_table("daily_token_state")
    op.drop_index(op.f("ix_messages_user_id"), table_name="messages")
    op.drop_table("messages")
    op.drop_table("user_profiles")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
