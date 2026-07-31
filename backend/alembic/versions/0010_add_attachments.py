"""Add attachments table for Telegram document storage.

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-31
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "attachments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_name", sa.String(200), nullable=False),
        sa.Column("file_id", sa.String(200), nullable=False),  # Telegram file_id
        sa.Column("file_size", sa.Integer, nullable=True),
        sa.Column("mime_type", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), default="pending"),  # pending, processed, failed
        sa.Column("processed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("records_imported", sa.Integer, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("telegram_chat_id", sa.String(30), nullable=True),
        sa.Column("received_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("attachments")
