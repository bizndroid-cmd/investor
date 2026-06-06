"""Add source_type column to news_articles.

Revision ID: 0006
Revises: 0005
Create Date: 2025-06-04
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "news_articles",
        sa.Column("source_type", sa.String(20), nullable=False, server_default=sa.text("'rss'")),
    )
    op.create_index("idx_news_source_type", "news_articles", ["source_type"])


def downgrade() -> None:
    op.drop_index("idx_news_source_type", table_name="news_articles")
    op.drop_column("news_articles", "source_type")
