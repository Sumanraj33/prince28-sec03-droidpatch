"""add typed bulletin month column

Revision ID: d03_bulletin_month
Revises: 65bfe7089f16
Create Date: 2026-11-18

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d03_bulletin_month"
down_revision: str | Sequence[str] | None = "65bfe7089f16"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add and backfill the typed bulletin month column."""
    op.add_column("documents", sa.Column("bulletin_month", sa.String(length=7), nullable=True))
    op.execute(
        sa.text(
            "UPDATE documents "
            "SET bulletin_month = metadata ->> 'bulletin_month' "
            "WHERE metadata ? 'bulletin_month'"
        )
    )
    op.create_index("ix_documents_bulletin_month", "documents", ["bulletin_month"])


def downgrade() -> None:
    """Remove the typed bulletin month column."""
    op.drop_index("ix_documents_bulletin_month", table_name="documents")
    op.drop_column("documents", "bulletin_month")
