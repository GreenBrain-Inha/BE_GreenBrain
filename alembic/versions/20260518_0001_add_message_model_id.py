"""add message model id

Revision ID: 20260518_0001
Revises: 20260514_0002
Create Date: 2026-05-18
"""

from alembic import op
import sqlalchemy as sa


revision = "20260518_0001"
down_revision = "20260514_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("model_id", sa.String(length=160), nullable=True))


def downgrade() -> None:
    op.drop_column("messages", "model_id")
