"""Add portfolio_snapshots and portfolio_daily_summary tables.

Revision ID: 0005
Revises: 0004
Create Date: 2025-06-03 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Per-holding daily snapshots
    op.create_table(
        "portfolio_snapshots",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("broker_id", sa.String(20), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("avg_buy_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("current_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("current_value", sa.Numeric(18, 6), nullable=False),
        sa.Column("gain_loss", sa.Numeric(18, 6), nullable=False),
        sa.Column("gain_loss_percent", sa.Numeric(18, 6), nullable=False),
        sa.Column("day_change", sa.Numeric(18, 6), nullable=False, server_default=sa.text("0")),
        sa.Column("day_change_percent", sa.Numeric(18, 6), nullable=False, server_default=sa.text("0")),
        sa.Column("currency", sa.String(10), nullable=False, server_default=sa.text("'INR'")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "snapshot_date", "ticker", name="uq_portfolio_snapshot"),
    )
    op.create_index(
        "idx_portfolio_snapshots_user_date", "portfolio_snapshots", ["user_id", "snapshot_date"]
    )

    # Daily aggregate summary
    op.create_table(
        "portfolio_daily_summary",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("total_value", sa.Numeric(18, 6), nullable=False),
        sa.Column("total_invested", sa.Numeric(18, 6), nullable=False),
        sa.Column("total_gain_loss", sa.Numeric(18, 6), nullable=False),
        sa.Column("total_gain_loss_percent", sa.Numeric(18, 6), nullable=False),
        sa.Column("day_change", sa.Numeric(18, 6), nullable=False, server_default=sa.text("0")),
        sa.Column("day_change_percent", sa.Numeric(18, 6), nullable=False, server_default=sa.text("0")),
        sa.Column("holdings_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "snapshot_date", name="uq_portfolio_daily_summary"),
    )
    op.create_index(
        "idx_portfolio_daily_summary_user_date", "portfolio_daily_summary", ["user_id", "snapshot_date"]
    )


def downgrade() -> None:
    op.drop_table("portfolio_daily_summary")
    op.drop_table("portfolio_snapshots")
