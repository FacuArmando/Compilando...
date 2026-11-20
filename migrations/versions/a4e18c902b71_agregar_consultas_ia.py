"""Registrar solicitudes IA y separar al solicitante del autor de la respuesta.

Revision ID: a4e18c902b71
Revises: 86c41e902ab7
"""

import sqlalchemy as sa
from alembic import op

revision = "a4e18c902b71"
down_revision = "86c41e902ab7"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("respuestas") as batch:
        batch.alter_column("usuario_id", existing_type=sa.Integer(), nullable=True)
        batch.add_column(sa.Column("proveedor_ia", sa.String(32), nullable=True))
    op.create_table(
        "solicitudes_ia",
        sa.Column("pregunta_id", sa.Integer(), sa.ForeignKey("preguntas.id"), primary_key=True),
        sa.Column("solicitante_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("respuesta_id", sa.Integer(), sa.ForeignKey("respuestas.id"), unique=True),
        sa.Column("token", sa.String(32), nullable=False),
        sa.Column("estado", sa.String(20), nullable=False),
        sa.Column("vence", sa.DateTime(), nullable=False),
    )


def downgrade():
    # El esquema previo exigía un usuario incluso para IA. Preservar las respuestas
    # asociándolas al solicitante; es_ia/modelo_ia conservan la identificación visible.
    op.execute(
        sa.text("""
        UPDATE respuestas SET usuario_id = COALESCE(
            (SELECT solicitante_id FROM solicitudes_ia WHERE respuesta_id = respuestas.id),
            (SELECT usuario_id FROM preguntas WHERE id = respuestas.pregunta_id)
        ) WHERE usuario_id IS NULL
    """)
    )
    op.drop_table("solicitudes_ia")
    with op.batch_alter_table("respuestas") as batch:
        batch.drop_column("proveedor_ia")
        batch.alter_column("usuario_id", existing_type=sa.Integer(), nullable=False)
