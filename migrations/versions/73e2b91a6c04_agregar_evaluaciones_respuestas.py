"""Agregar evaluaciones de utilidad por lector y respuesta.

Revision ID: 73e2b91a6c04
Revises: f681d3b207ac
"""

import sqlalchemy as sa
from alembic import op

revision = "73e2b91a6c04"
down_revision = "f681d3b207ac"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "evaluaciones_respuestas",
        sa.Column("respuesta_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("util", sa.Boolean(), nullable=False),
        sa.Column("fecha", sa.DateTime(), nullable=False),
        sa.Column("fecha_actualizacion", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["respuesta_id"], ["respuestas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("respuesta_id", "usuario_id"),
    )
    op.create_index(
        "ix_evaluaciones_respuesta_util", "evaluaciones_respuestas", ["respuesta_id", "util"]
    )


def downgrade():
    op.drop_index("ix_evaluaciones_respuesta_util", table_name="evaluaciones_respuestas")
    op.drop_table("evaluaciones_respuestas")
