"""Guardar los metadatos de los archivos adjuntos a preguntas.

Revision ID: 86c41e902ab7
Revises: 4b2e88c7eeba
"""

import sqlalchemy as sa
from alembic import op

revision = "86c41e902ab7"
down_revision = "4b2e88c7eeba"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "adjuntos_pregunta",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("pregunta_id", sa.Integer(), sa.ForeignKey("preguntas.id"), nullable=False),
        sa.Column("nombre_original", sa.String(120), nullable=False),
        sa.Column("tamanio", sa.Integer(), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False),
    )
    op.create_index("ix_adjuntos_pregunta_pregunta_id", "adjuntos_pregunta", ["pregunta_id"])


def downgrade():
    op.drop_index("ix_adjuntos_pregunta_pregunta_id", table_name="adjuntos_pregunta")
    op.drop_table("adjuntos_pregunta")
