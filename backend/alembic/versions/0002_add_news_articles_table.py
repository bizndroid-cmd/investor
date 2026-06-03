"""Add news_articles table.

Revision ID: 0002
Revises: 0001
Create Date: 2024-01-15 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PGUUID

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "news_articles",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("source_name", sa.String(100), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("published_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("raw_content", sa.Text(), nullable=False),
        sa.Column("summary", sa.String(200), nullable=True),
        sa.Column("sentiment_score", sa.String(10), nullable=True),
        sa.Column("impact_level", sa.String(10), nullable=True),
        sa.Column("related_tickers", ARRAY(sa.String), nullable=True),
        sa.Column(
            "relevance_score", sa.Float(), nullable=False, server_default=sa.text("0.0")
        ),
        sa.Column(
            "is_analyzed", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "is_stub", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("analyzed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "fetched_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )

    # Indexes for common query patterns
    op.create_index("idx_news_articles_user_id", "news_articles", ["user_id"])
    op.create_index(
        "idx_news_articles_published_at", "news_articles", ["published_at"]
    )
    op.create_index(
        "idx_news_articles_sentiment", "news_articles", ["sentiment_score"]
    )
    op.create_index("idx_news_articles_impact", "news_articles", ["impact_level"])
    op.create_index("idx_news_articles_analyzed", "news_articles", ["is_analyzed"])


def downgrade() -> None:
    op.drop_table("news_articles")
