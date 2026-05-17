"""add user profile columns

Revision ID: 20260514_0002
Revises: 20260514_0001
Create Date: 2026-05-14

This migration is intentionally a no-op.

The user profile columns were already included in
20260512_0001_create_core_tables.py:
- users.nickname
- users.profile_image_url
- users.updated_at
- user_profiles.updated_at
"""

revision = "20260514_0002"
down_revision = "20260514_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass