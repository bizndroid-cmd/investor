"""Add user_preferences table for geography settings.

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_preferences",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("geography", sa.String(5), server_default="IN", nullable=False),
        sa.Column("default_broker", sa.String(20), nullable=True),
        sa.Column("timezone", sa.String(50), nullable=True),
        sa.Column("currency_code", sa.String(5), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", name="uq_user_preferences_user"),
    )


def downgrade() -> None:
    op.drop_table("user_preferences")
