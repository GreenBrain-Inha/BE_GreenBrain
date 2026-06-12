"""greenbrain integer tokens

Revision ID: 20260611_0001
Revises: 20260518_0001
Create Date: 2026-06-11
"""

from alembic import op
import sqlalchemy as sa


revision = "20260611_0001"
down_revision = "20260518_0001"
branch_labels = None
depends_on = None


_DAILY_STATE_COLUMNS = {
    "tokens_remaining": "150000",
    "upload_reward_given": "0",
    "like_reward_given": "0",
    "total_reward_given": "0",
}
_TRANSACTION_COLUMNS = ("amount", "balance_after")


def upgrade() -> None:
    for column, default in _DAILY_STATE_COLUMNS.items():
        op.alter_column(
            "daily_token_state",
            column,
            type_=sa.Integer(),
            existing_type=sa.Float(),
            postgresql_using=f"round({column})::integer",
            server_default=sa.text(default),
        )

    for column in _TRANSACTION_COLUMNS:
        op.alter_column(
            "token_transactions",
            column,
            type_=sa.Integer(),
            existing_type=sa.Float(),
            postgresql_using=f"round({column})::integer",
        )


def downgrade() -> None:
    for column in _TRANSACTION_COLUMNS:
        op.alter_column(
            "token_transactions",
            column,
            type_=sa.Float(),
            existing_type=sa.Integer(),
        )

    for column, default in _DAILY_STATE_COLUMNS.items():
        op.alter_column(
            "daily_token_state",
            column,
            type_=sa.Float(),
            existing_type=sa.Integer(),
            server_default=sa.text(f"{default}.0"),
        )
