"""Add is_approved column to users table.

Existing users default to True (approved). New registrations set False.

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Default True so existing users remain approved
    op.add_column(
        "users",
        sa.Column("is_approved", sa.Boolean, nullable=False, server_default=sa.text("true")),
    )


def downgrade() -> None:
    op.drop_column("users", "is_approved")
