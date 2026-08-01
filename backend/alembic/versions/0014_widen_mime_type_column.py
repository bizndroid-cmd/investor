"""Widen attachments.mime_type from VARCHAR(50) to VARCHAR(100).

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("attachments", "mime_type", type_=sa.String(100), existing_type=sa.String(50))


def downgrade() -> None:
    op.alter_column("attachments", "mime_type", type_=sa.String(50), existing_type=sa.String(100))
