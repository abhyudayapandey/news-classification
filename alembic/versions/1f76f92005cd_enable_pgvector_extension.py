"""enable pgvector extension

Revision ID: 1f76f92005cd
Revises: 
Create Date: 2026-08-28 04:04:13.049438

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1f76f92005cd'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enabled now, unused until Phase 2 defines embedding columns (clustering).
    # Both Supabase and Neon free tiers ship this extension pre-installed.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS vector")
