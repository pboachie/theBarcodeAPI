"""clean_duplicates_and_add_constraints

Revision ID: 70bfbf5142be
Revises: 1da1e88339c5
Create Date: 2024-11-23 03:52:13.966402

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '70bfbf5142be'
down_revision: Union[str, None] = '1da1e88339c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Drop existing foreign key constraints first
    op.execute('ALTER TABLE active_tokens DROP CONSTRAINT IF EXISTS active_tokens_user_id_fkey')
    op.execute('ALTER TABLE usage DROP CONSTRAINT IF EXISTS usage_user_id_fkey')

    # Create temporary table with unique records
    op.execute("""
        CREATE TEMPORARY TABLE users_dedup AS
        SELECT DISTINCT ON (username) *
        FROM users
        ORDER BY username, last_request DESC NULLS LAST;
    """)

    # Clear original table and repopulate with deduplicated data
    op.execute('TRUNCATE TABLE users')
    op.execute('INSERT INTO users SELECT * FROM users_dedup')
    op.execute('DROP TABLE users_dedup')

    # Add uniqueness constraints
    op.drop_index('ix_users_id', table_name='users')
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=True)
    op.create_unique_constraint('uq_users_id', 'users', ['id'])
    op.create_unique_constraint('uq_users_username', 'users', ['username'])

    # Recreate foreign key constraints
    op.create_foreign_key(
        'active_tokens_user_id_fkey',
        'active_tokens', 'users',
        ['user_id'], ['id']
    )
    op.create_foreign_key(
        'usage_user_id_fkey',
        'usage', 'users',
        ['user_id'], ['id']
    )

def downgrade() -> None:
    # Drop constraints in reverse order
    op.drop_constraint('usage_user_id_fkey', 'usage', type_='foreignkey')
    op.drop_constraint('active_tokens_user_id_fkey', 'active_tokens', type_='foreignkey')
    op.drop_constraint('uq_users_username', 'users', type_='unique')
    op.drop_constraint('uq_users_id', 'users', type_='unique')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.create_index('ix_users_id', 'users', ['id'], unique=False)
    