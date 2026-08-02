"""Change etf_holdings unique constraint to include buy_date.

Allows same ticker multiple times with different dates.
Blocks same ticker + same date.

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-01
"""
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_etf_holdings_user_ticker_geo", "etf_holdings", type_="unique")
    op.create_unique_constraint(
        "uq_etf_holdings_user_ticker_geo_date",
        "etf_holdings",
        ["user_id", "ticker", "geo_id", "buy_date"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_etf_holdings_user_ticker_geo_date", "etf_holdings", type_="unique")
    op.create_unique_constraint(
        "uq_etf_holdings_user_ticker_geo",
        "etf_holdings",
        ["user_id", "ticker", "geo_id"],
    )
