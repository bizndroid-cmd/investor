"""Add portfolios table and portfolio_id to related tables.

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create portfolios table
    op.create_table(
        "portfolios",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("geo_id", sa.String(5), nullable=False, server_default="IN"),
        sa.Column("broker_id", sa.String(20), nullable=True),
        sa.Column("is_default", sa.Boolean, server_default="true", nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Index("idx_portfolios_user", "user_id"),
    )

    # Add portfolio_id to portfolio_snapshots (nullable for backward compat)
    op.add_column("portfolio_snapshots", sa.Column("portfolio_id", UUID(as_uuid=True), nullable=True))

    # Add portfolio_id to portfolio_daily_summary (nullable for backward compat)
    op.add_column("portfolio_daily_summary", sa.Column("portfolio_id", UUID(as_uuid=True), nullable=True))

    # Add portfolio_id to trade_history (nullable for backward compat)
    op.add_column("trade_history", sa.Column("portfolio_id", UUID(as_uuid=True), nullable=True))


def downgrade() -> None:
    op.drop_column("trade_history", "portfolio_id")
    op.drop_column("portfolio_daily_summary", "portfolio_id")
    op.drop_column("portfolio_snapshots", "portfolio_id")
    op.drop_table("portfolios")
