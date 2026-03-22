"""add filter_mode to jobs

Revision ID: 2a9c4f6c9b7b
Revises: 845baf25f302
Create Date: 2026-03-17 09:45:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2a9c4f6c9b7b'
down_revision: Union[str, None] = '845baf25f302'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'jobs',
        sa.Column('filter_mode', sa.String(), server_default='smart', nullable=False)
    )


def downgrade() -> None:
    op.drop_column('jobs', 'filter_mode')
