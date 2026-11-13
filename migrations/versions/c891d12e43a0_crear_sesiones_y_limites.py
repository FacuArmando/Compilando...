"""Crear sesiones revocables y límites de autenticación.

Revision ID: c891d12e43a0
Revises: bb57280189ce
"""

import sqlalchemy as sa
from alembic import op

revision = "c891d12e43a0"
down_revision = "bb57280189ce"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "sesiones",
        sa.Column("id", sa.String(64), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("fecha_inicio", sa.DateTime(), nullable=False),
        sa.Column("fecha_vencimiento", sa.DateTime(), nullable=False),
        sa.Column("ultimo_acceso", sa.DateTime(), nullable=False),
        sa.Column("activa", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["usuario_id"], ["usuarios.id"], name=op.f("fk_sesiones_usuario_id_usuarios")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sesiones")),
    )
    op.create_index(op.f("ix_sesiones_usuario_id"), "sesiones", ["usuario_id"])
    op.create_index(op.f("ix_sesiones_fecha_vencimiento"), "sesiones", ["fecha_vencimiento"])
    op.create_table(
        "limites_autenticacion",
        sa.Column("clave", sa.String(64), nullable=False),
        sa.Column("inicio_ventana", sa.DateTime(), nullable=False),
        sa.Column("intentos", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("clave", name=op.f("pk_limites_autenticacion")),
    )
    op.create_index(
        op.f("ix_limites_autenticacion_inicio_ventana"), "limites_autenticacion", ["inicio_ventana"]
    )


def downgrade():
    op.drop_index(
        op.f("ix_limites_autenticacion_inicio_ventana"), table_name="limites_autenticacion"
    )
    op.drop_table("limites_autenticacion")
    op.drop_index(op.f("ix_sesiones_fecha_vencimiento"), table_name="sesiones")
    op.drop_index(op.f("ix_sesiones_usuario_id"), table_name="sesiones")
    op.drop_table("sesiones")
