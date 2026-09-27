"""add_enrichment_columns_to_threat_indicators

Revision ID: 9e2d7a4e671a
Revises: 35b5fb6bfaf9
Create Date: 2026-09-26 16:18:08.917047

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9e2d7a4e671a'
down_revision: Union[str, Sequence[str], None] = '35b5fb6bfaf9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("threat_indicators", sa.Column("known_bad", sa.Boolean(), nullable=True))
    op.add_column("threat_indicators", sa.Column("domain_age_days", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("threat_indicators", "domain_age_days")
    op.drop_column("threat_indicators", "known_bad")
