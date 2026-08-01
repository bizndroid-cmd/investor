"""Add etf_holdings table.

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "etf_holdings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("buy_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("buy_date", sa.Date, nullable=True),
        sa.Column("geo_id", sa.String(5), nullable=False),
        sa.Column("currency", sa.String(5), nullable=False),
        sa.Column("portfolio_id", UUID(as_uuid=True), sa.ForeignKey("portfolios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Index("idx_etf_holdings_user", "user_id"),
        sa.UniqueConstraint("user_id", "ticker", "geo_id", name="uq_etf_holdings_user_ticker_geo"),
    )


def downgrade() -> None:
    op.drop_table("etf_holdings")
