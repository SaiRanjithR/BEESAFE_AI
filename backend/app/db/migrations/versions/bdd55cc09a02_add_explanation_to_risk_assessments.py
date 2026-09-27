"""add_explanation_to_risk_assessments

Revision ID: bdd55cc09a02
Revises: 9e2d7a4e671a
Create Date: 2026-09-26 16:39:28.020214

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bdd55cc09a02'
down_revision: Union[str, Sequence[str], None] = '9e2d7a4e671a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("risk_assessments", sa.Column("explanation", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("risk_assessments", "explanation")
