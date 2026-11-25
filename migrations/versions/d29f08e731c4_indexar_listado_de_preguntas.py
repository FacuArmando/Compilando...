"""Indexar el orden del listado y los conteos de respuestas.

Revision ID: d29f08e731c4
Revises: be14a09c9a73
"""

from alembic import op

revision = "d29f08e731c4"
down_revision = "be14a09c9a73"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_preguntas_fecha_id", "preguntas", ["fecha", "id"])
    op.create_index("ix_preguntas_categoria_fecha_id", "preguntas", ["categoria_id", "fecha", "id"])
    op.create_index("ix_respuestas_pregunta_estado", "respuestas", ["pregunta_id", "estado"])


def downgrade():
    op.drop_index("ix_respuestas_pregunta_estado", table_name="respuestas")
    op.drop_index("ix_preguntas_categoria_fecha_id", table_name="preguntas")
    op.drop_index("ix_preguntas_fecha_id", table_name="preguntas")
