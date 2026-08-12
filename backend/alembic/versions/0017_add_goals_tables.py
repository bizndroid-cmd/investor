"""Add goals and wealth_entries tables.

Revision ID: 0017
Revises: 0016
Create Date: 2026-08-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "goals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("target_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("target_currency", sa.String(5), nullable=False),
        sa.Column("deadline", sa.Date, nullable=True),
        sa.Column("icon", sa.String(20), default="target"),
        sa.Column("color", sa.String(20), default="blue"),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Index("idx_goals_user", "user_id"),
    )

    op.create_table(
        "wealth_entries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("goal_id", UUID(as_uuid=True), sa.ForeignKey("goals.id", ondelete="CASCADE"), nullable=True),
        sa.Column("category", sa.String(30), nullable=False),  # savings, fd, real_estate, crypto, gold_physical, other
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(5), nullable=False),
        sa.Column("entry_date", sa.Date, nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Index("idx_wealth_entries_user", "user_id"),
        sa.Index("idx_wealth_entries_goal", "goal_id"),
    )


def downgrade() -> None:
    op.drop_table("wealth_entries")
    op.drop_table("goals")
