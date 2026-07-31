"""Add trade_history table for storing parsed broker order reports.

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-30

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trade_history",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ticker", sa.String(30), nullable=False),
        sa.Column("isin", sa.String(20), nullable=True),
        sa.Column("trade_type", sa.String(10), nullable=False),  # BUY or SELL
        sa.Column("quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("price", sa.Numeric(18, 6), nullable=False),
        sa.Column("value", sa.Numeric(18, 6), nullable=True),
        sa.Column("exchange", sa.String(10), nullable=True),
        sa.Column("order_id", sa.String(100), nullable=True),
        sa.Column("executed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("broker", sa.String(30), nullable=True),
        sa.Column("source_file", sa.String(100), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Index("idx_trade_history_user_ticker", "user_id", "ticker"),
    )


def downgrade() -> None:
    op.drop_table("trade_history")
