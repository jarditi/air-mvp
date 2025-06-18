"""merge token usage and integrations fixes

Revision ID: 9fece6cda12f
Revises: 006_add_token_usage_tracking, fix_integrations_v1
Create Date: 2025-06-16 21:15:51.530579

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9fece6cda12f'
down_revision: Union[str, None] = ('006_add_token_usage_tracking', 'fix_integrations_v1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
