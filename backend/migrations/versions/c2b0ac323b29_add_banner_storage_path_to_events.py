"""add banner_storage_path to events

Revision ID: c2b0ac323b29
Revises: b5f8af3af722
Create Date: 2026-09-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c2b0ac323b29'
down_revision: Union[str, Sequence[str], None] = 'b5f8af3af722'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.add_column(sa.Column('banner_storage_path', sa.String(length=500), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.drop_column('banner_storage_path')
