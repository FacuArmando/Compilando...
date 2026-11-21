"""Unificar migraciones de administrador y avatar

Revision ID: 0e760e5134af
Revises: ae52e4f97632, 225a4dbb2d53
Create Date: 2026-11-21 13:30:57.805516

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0e760e5134af'
down_revision = ('ae52e4f97632', '225a4dbb2d53')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
