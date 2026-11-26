"""Archivos pequeños persistentes y privados para la demo sin servicios pagos.

Revision ID: d9e5f6a712b3
Revises: c8d4e5f601a2
"""

import sqlalchemy as sa
from alembic import op

revision = "d9e5f6a712b3"
down_revision = "c8d4e5f601a2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "archivos",
        sa.Column("clave", sa.String(160), primary_key=True),
        sa.Column("contenido", sa.LargeBinary(), nullable=False),
        sa.Column("tamanio", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE")),
        sa.Column("pregunta_id", sa.Integer(), sa.ForeignKey("preguntas.id", ondelete="CASCADE")),
        sa.CheckConstraint("tamanio > 0", name=op.f("ck_archivos_tamanio_positivo")),
        sa.CheckConstraint(
            "(usuario_id IS NOT NULL AND pregunta_id IS NULL) OR "
            "(usuario_id IS NULL AND pregunta_id IS NOT NULL)",
            name=op.f("ck_archivos_un_propietario"),
        ),
    )
    op.create_index("ix_archivos_usuario_id", "archivos", ["usuario_id"])
    op.create_index("ix_archivos_pregunta_id", "archivos", ["pregunta_id"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE public.archivos ENABLE ROW LEVEL SECURITY")
        op.execute("REVOKE ALL ON TABLE public.archivos FROM PUBLIC")
        op.execute("""
            DO $$ DECLARE api_role text; BEGIN
                FOR api_role IN SELECT rolname FROM pg_roles
                  WHERE rolname IN ('anon', 'authenticated', 'service_role')
                LOOP
                    EXECUTE format('REVOKE ALL ON TABLE public.archivos FROM %I', api_role);
                END LOOP;
            END $$;
        """)


def downgrade():
    op.drop_table("archivos")
