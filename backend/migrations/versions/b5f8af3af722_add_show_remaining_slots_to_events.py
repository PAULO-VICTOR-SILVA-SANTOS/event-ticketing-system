"""add show_remaining_slots to events

Revision ID: b5f8af3af722
Revises: 7060cf053fdf
Create Date: 2026-09-07 13:25:30.643763

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b5f8af3af722'
down_revision: Union[str, Sequence[str], None] = '7060cf053fdf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'show_remaining_slots',
                sa.Boolean(),
                nullable=False,
                server_default='true',
            )
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.drop_column('show_remaining_slots')
