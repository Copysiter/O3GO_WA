"""add device to session

Revision ID: 8c4e1f7a2b90
Revises: 420693b7c968
Create Date: 2026-09-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8c4e1f7a2b90'
down_revision = '420693b7c968'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'session', sa.Column('device', sa.String(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('session', 'device')
