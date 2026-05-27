"""add paper_questions snapshot columns

Revision ID: add_snapshot_cols
Revises: 8d986edf6147
Create Date: 2026-05-26 17:49:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_snapshot_cols'
down_revision: Union[str, Sequence[str], None] = '8d986edf6147'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add snapshot columns to paper_questions table."""
    # Check if columns exist before adding
    op.add_column('paper_questions', sa.Column('course_outcome_snapshot', sa.String(length=10), nullable=True))
    op.add_column('paper_questions', sa.Column('bloom_level_snapshot', sa.String(length=10), nullable=True))
    op.add_column('paper_questions', sa.Column('module_number_snapshot', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Remove snapshot columns from paper_questions table."""
    op.drop_column('paper_questions', 'module_number_snapshot')
    op.drop_column('paper_questions', 'bloom_level_snapshot')
    op.drop_column('paper_questions', 'course_outcome_snapshot')
