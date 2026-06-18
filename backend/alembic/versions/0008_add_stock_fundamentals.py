"""Add stock_fundamentals table for screener.in data.

Revision ID: 0008
Revises: 0007
Create Date: 2025-06-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stock_fundamentals",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("ticker", sa.String(20), unique=True, nullable=False),
        sa.Column("market_cap", sa.String(50), nullable=True),
        sa.Column("current_price", sa.String(20), nullable=True),
        sa.Column("pe_ratio", sa.String(20), nullable=True),
        sa.Column("book_value", sa.String(20), nullable=True),
        sa.Column("dividend_yield", sa.String(20), nullable=True),
        sa.Column("roce", sa.String(20), nullable=True),
        sa.Column("roe", sa.String(20), nullable=True),
        sa.Column("face_value", sa.String(20), nullable=True),
        sa.Column("high_low", sa.String(50), nullable=True),
        sa.Column("pros", sa.Text(), nullable=True),
        sa.Column("cons", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_stock_fundamentals_ticker", "stock_fundamentals", ["ticker"])


def downgrade() -> None:
    op.drop_table("stock_fundamentals")
