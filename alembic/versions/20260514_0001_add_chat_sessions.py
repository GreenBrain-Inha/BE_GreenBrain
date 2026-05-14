"""add chat sessions

Revision ID: 20260514_0001
Revises: 20260512_0001
Create Date: 2026-05-14
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260514_0001"
down_revision = "20260512_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_chat_sessions_user_id"), "chat_sessions", ["user_id"], unique=False)

    op.add_column("messages", sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True))

    op.execute(
        """
        INSERT INTO chat_sessions (id, user_id, title, created_at, updated_at)
        SELECT gen_random_uuid(), messages.user_id, NULL, MIN(messages.created_at), MAX(messages.created_at)
        FROM messages
        GROUP BY messages.user_id
        """
    )
    op.execute(
        """
        UPDATE messages
        SET session_id = chat_sessions.id
        FROM chat_sessions
        WHERE messages.user_id = chat_sessions.user_id
          AND messages.session_id IS NULL
        """
    )

    op.alter_column("messages", "session_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)
    op.create_index(op.f("ix_messages_session_id"), "messages", ["session_id"], unique=False)
    op.create_foreign_key(
        op.f("fk_messages_session_id_chat_sessions"),
        "messages",
        "chat_sessions",
        ["session_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("fk_messages_session_id_chat_sessions"), "messages", type_="foreignkey")
    op.drop_index(op.f("ix_messages_session_id"), table_name="messages")
    op.drop_column("messages", "session_id")
    op.drop_index(op.f("ix_chat_sessions_user_id"), table_name="chat_sessions")
    op.drop_table("chat_sessions")
