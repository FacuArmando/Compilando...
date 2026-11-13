"""Crear usuarios

Revision ID: bb57280189ce
Revises:
Create Date: 2026-11-12 18:24:42.611394

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "bb57280189ce"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Crear la tabla de usuarios con sus restricciones de unicidad."""
    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_usuarios")),
        sa.UniqueConstraint("email", name=op.f("uq_usuarios_email")),
        sa.UniqueConstraint("username", name=op.f("uq_usuarios_username")),
    )


def downgrade():
    """Eliminar la tabla de usuarios al revertir esta revisión."""
    op.drop_table("usuarios")
