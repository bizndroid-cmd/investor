"""Add prediction_records table for LLM accuracy tracking.

Revision ID: 0007
Revises: 0006
Create Date: 2025-06-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "prediction_records",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("prediction_date", sa.Date(), nullable=False),
        sa.Column("market_mood", sa.String(10), nullable=False),
        sa.Column("market_mood_reason", sa.Text(), nullable=True),
        sa.Column("ticker_predictions", sa.Text(), nullable=True),
        sa.Column("suggestions", sa.Text(), nullable=True),
        sa.Column("briefing_text", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("score_computed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("mood_accuracy", sa.Float(), nullable=True),
        sa.Column("ticker_accuracy", sa.Float(), nullable=True),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("model", sa.String(50), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_prediction_records_user_date", "prediction_records", ["user_id", "prediction_date"])


def downgrade() -> None:
    op.drop_table("prediction_records")
