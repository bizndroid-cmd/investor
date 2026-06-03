"""Add collection_runs table and collection_date to news_articles.

Revision ID: 0003
Revises: 0002
Create Date: 2025-06-02 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PGUUID

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create collection_runs table
    op.create_table(
        "collection_runs",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "started_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'started'"),
        ),
        sa.Column(
            "source",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'scheduled'"),
        ),
        sa.Column(
            "articles_fetched", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "articles_stored", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_collection_runs_status", "collection_runs", ["status"])
    op.create_index(
        "idx_collection_runs_started_at",
        "collection_runs",
        [sa.text("started_at DESC")],
    )

    # 2. Add collection_date column to news_articles (nullable initially for backfill)
    op.add_column(
        "news_articles",
        sa.Column("collection_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "news_articles",
        sa.Column(
            "collection_run_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("collection_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # 3. Backfill collection_date from fetched_at (converted to IST date)
    op.execute(
        "UPDATE news_articles SET collection_date = (fetched_at AT TIME ZONE 'Asia/Kolkata')::date "
        "WHERE collection_date IS NULL"
    )

    # 4. Make collection_date NOT NULL after backfill
    op.alter_column("news_articles", "collection_date", nullable=False)

    # 5. Add new indexes for collection_date queries
    op.create_index("idx_news_collection_date", "news_articles", ["collection_date"])
    op.create_index(
        "idx_news_user_collection_date",
        "news_articles",
        ["user_id", sa.text("collection_date DESC")],
    )
    # GIN index on related_tickers for ticker-based queries
    op.execute(
        "CREATE INDEX idx_news_collection_date_tickers ON news_articles "
        "USING gin(related_tickers) WHERE related_tickers IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_news_collection_date_tickers")
    op.drop_index("idx_news_user_collection_date", table_name="news_articles")
    op.drop_index("idx_news_collection_date", table_name="news_articles")
    op.drop_column("news_articles", "collection_run_id")
    op.drop_column("news_articles", "collection_date")
    op.drop_table("collection_runs")
