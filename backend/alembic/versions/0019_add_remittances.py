"""Add remittances table for cross-border transfer tracking.

Revision ID: 0019
Revises: 0018
Create Date: 2026-08-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "remittances",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),  # inr_to_usd, usd_to_inr
        sa.Column("source_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("source_currency", sa.String(5), nullable=False),
        sa.Column("target_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("target_currency", sa.String(5), nullable=False),
        sa.Column("exchange_rate", sa.Numeric(10, 4), nullable=False),
        sa.Column("provider", sa.String(50), nullable=True),  # Wise, HDFC, Remitly, etc.
        sa.Column("purpose", sa.String(50), nullable=True),  # investment, savings, expenses
        sa.Column("transfer_date", sa.Date, nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Index("idx_remittances_user", "user_id"),
        sa.Index("idx_remittances_date", "transfer_date"),
    )


def downgrade() -> None:
    op.drop_table("remittances")
