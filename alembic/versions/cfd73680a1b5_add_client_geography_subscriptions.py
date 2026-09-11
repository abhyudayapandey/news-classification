"""add client geography subscriptions

Revision ID: cfd73680a1b5
Revises: 339a3caf8f23
Create Date: 2026-09-11 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'cfd73680a1b5'
down_revision: Union[str, None] = '339a3caf8f23'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # seat_type already exists as a Postgres enum type (339a3caf8f23) -
    # create_type=False, same convention as social_mentions/system_tags.
    op.create_table(
        'client_geography_subscriptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('state', sa.String(length=64), nullable=False),
        sa.Column('district', sa.String(length=128), nullable=True),
        sa.Column('constituency', sa.String(length=255), nullable=True),
        sa.Column('seat_type', postgresql.ENUM('MP', 'MLA', name='seat_type', create_type=False), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('news_access', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('youtube_access', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('x_access', sa.Boolean(), server_default='false', nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_client_geography_subscriptions_client_id'),
        'client_geography_subscriptions', ['client_id'], unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_client_geography_subscriptions_client_id'), table_name='client_geography_subscriptions')
    op.drop_table('client_geography_subscriptions')
