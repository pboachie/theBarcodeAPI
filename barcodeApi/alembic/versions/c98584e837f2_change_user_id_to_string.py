"""change_user_id_to_string

Revision ID: c98584e837f2
Revises: 2f1c039482ee
Create Date: 2024-11-23 02:27:22.838666

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c98584e837f2'
down_revision: Union[str, None] = '2f1c039482ee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Drop foreign key constraints first
    op.drop_constraint('active_tokens_user_id_fkey', 'active_tokens', type_='foreignkey')
    op.drop_constraint('usage_user_id_fkey', 'usage', type_='foreignkey')

    # Change the primary key column type first
    op.alter_column('users', 'id',
               existing_type=sa.INTEGER(),
               type_=sa.String(),
               postgresql_using="id::text",
               existing_nullable=False)

    # Then change the foreign key columns
    op.alter_column('active_tokens', 'user_id',
               existing_type=sa.INTEGER(),
               type_=sa.String(),
               postgresql_using="user_id::text",
               existing_nullable=True)

    op.alter_column('usage', 'user_id',
               existing_type=sa.INTEGER(),
               type_=sa.String(),
               postgresql_using="user_id::text",
               existing_nullable=True)

    # Recreate foreign key constraints
    op.create_foreign_key('active_tokens_user_id_fkey', 'active_tokens', 'users', ['user_id'], ['id'])
    op.create_foreign_key('usage_user_id_fkey', 'usage', 'users', ['user_id'], ['id'])

def downgrade() -> None:
    # Drop foreign key constraints first
    op.drop_constraint('active_tokens_user_id_fkey', 'active_tokens', type_='foreignkey')
    op.drop_constraint('usage_user_id_fkey', 'usage', type_='foreignkey')

    # Change the foreign key columns back first
    op.alter_column('active_tokens', 'user_id',
               existing_type=sa.String(),
               type_=sa.INTEGER(),
               postgresql_using="user_id::integer",
               existing_nullable=True)

    op.alter_column('usage', 'user_id',
               existing_type=sa.String(),
               type_=sa.INTEGER(),
               postgresql_using="user_id::integer",
               existing_nullable=True)

    # Then change the primary key column
    op.alter_column('users', 'id',
               existing_type=sa.String(),
               type_=sa.INTEGER(),
               postgresql_using="id::integer",
               existing_nullable=False)

    # Recreate foreign key constraints
    op.create_foreign_key('active_tokens_user_id_fkey', 'active_tokens', 'users', ['user_id'], ['id'])
    op.create_foreign_key('usage_user_id_fkey', 'usage', 'users', ['user_id'], ['id'])