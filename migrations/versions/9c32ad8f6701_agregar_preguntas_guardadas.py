"""Agregar la colección privada de preguntas guardadas.

Revision ID: 9c32ad8f6701
Revises: 73e2b91a6c04
"""

import sqlalchemy as sa
from alembic import op

revision = "9c32ad8f6701"
down_revision = "73e2b91a6c04"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "preguntas_guardadas",
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("pregunta_id", sa.Integer(), nullable=False),
        sa.Column("fecha", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["pregunta_id"], ["preguntas.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("usuario_id", "pregunta_id"),
    )
    op.create_index(
        "ix_guardadas_usuario_fecha", "preguntas_guardadas", ["usuario_id", "fecha", "pregunta_id"]
    )


def downgrade():
    op.drop_index("ix_guardadas_usuario_fecha", table_name="preguntas_guardadas")
    op.drop_table("preguntas_guardadas")
