"""Update ActiveToken model

Revision ID: 2f1c039482ee
Revises: 09b041f3e341
Create Date: 2024-10-06 22:44:34.066320

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2f1c039482ee'
down_revision: Union[str, None] = '09b041f3e341'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('users', sa.Column('requests_today', sa.Integer(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('users', 'requests_today')
    # ### end Alembic commands ###
