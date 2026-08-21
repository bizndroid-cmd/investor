"""Add analytics_events table for click/page tracking.

Revision ID: 0018
Revises: 0017
Create Date: 2026-08-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analytics_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(20), nullable=False),  # page_view, click, session_end
        sa.Column("page", sa.String(50), nullable=True),
        sa.Column("target", sa.String(100), nullable=True),  # button label or element
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("extra_data", sa.Text, nullable=True),  # JSON extra data
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Index("idx_analytics_user", "user_id"),
        sa.Index("idx_analytics_type", "event_type"),
        sa.Index("idx_analytics_created", "created_at"),
    )


def downgrade() -> None:
    op.drop_table("analytics_events")
