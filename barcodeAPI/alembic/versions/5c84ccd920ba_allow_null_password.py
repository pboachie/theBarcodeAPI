"""allow_null_password

Revision ID: 5c84ccd920ba
Revises: c98584e837f2
Create Date: 2024-11-23 03:05:03.235482

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5c84ccd920ba'
down_revision: Union[str, None] = 'c98584e837f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Allow null hashed_password for unauthenticated users
    op.alter_column('users', 'hashed_password',
               existing_type=sa.String(),
               nullable=True)


def downgrade() -> None:
    # First set any nulls to empty string
    op.execute("UPDATE users SET hashed_password = '' WHERE hashed_password IS NULL")

    # Then make column non-nullable
    op.alter_column('users', 'hashed_password',
               existing_type=sa.String(),
               nullable=False)