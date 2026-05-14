"""add user profile columns

Revision ID: 20260514_0002
Revises: 20260514_0001
Create Date: 2026-05-14
"""

from alembic import op
import sqlalchemy as sa


revision = "20260514_0002"
down_revision = "20260514_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("nickname", sa.String(), nullable=True))
    op.add_column("users", sa.Column("profile_image_url", sa.String(), nullable=True))
    op.add_column(
        "users",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.add_column(
        "user_profiles",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("user_profiles", "updated_at")
    op.drop_column("users", "updated_at")
    op.drop_column("users", "profile_image_url")
    op.drop_column("users", "nickname")
