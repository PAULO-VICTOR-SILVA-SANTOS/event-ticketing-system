"""make participant cpf nullable

Revision ID: 45742fc8d1a7
Revises: 3ddff0464a74
Create Date: 2026-09-03 21:50:51.068704

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '45742fc8d1a7'
down_revision: Union[str, Sequence[str], None] = '3ddff0464a74'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('participants') as batch_op:
        batch_op.alter_column(
            'cpf',
            existing_type=sa.VARCHAR(length=14),
            nullable=True,
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('participants') as batch_op:
        batch_op.alter_column(
            'cpf',
            existing_type=sa.VARCHAR(length=14),
            nullable=False,
        )
