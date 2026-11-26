"""Restringir las tablas de Flask al acceso SQL privado en PostgreSQL.

Revision ID: b7f3c2a19d60
Revises: 9c32ad8f6701
"""

import sqlalchemy as sa
from alembic import op

revision = "b7f3c2a19d60"
down_revision = "9c32ad8f6701"
branch_labels = None
depends_on = None

# Lista histórica fija: no importar modelos que pueden cambiar en el futuro.
TABLAS = (
    "usuarios",
    "sesiones",
    "limites_autenticacion",
    "preguntas",
    "categorias",
    "tags",
    "pregunta_tags",
    "respuestas",
    "adjuntos_pregunta",
    "solicitudes_ia",
    "evaluaciones_respuestas",
    "preguntas_guardadas",
    "alembic_version",
)


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        return

    # Las tablas viven en public, pero solo Flask las consulta mediante SQL.
    # RLS sin políticas deniega filas a roles normales; postgres mantiene acceso.
    for tabla in TABLAS:
        op.execute(sa.text(f'ALTER TABLE public."{tabla}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'REVOKE ALL ON TABLE public."{tabla}" FROM PUBLIC'))
        # Supabase define estos roles. En PostgreSQL genérico pueden no existir.
        op.execute(
            sa.text(f"""
            DO $$
            DECLARE
                api_role text;
                sequence_name text;
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = '{tabla}'
                      AND column_name = 'id'
                ) THEN
                    sequence_name := pg_get_serial_sequence('public.{tabla}', 'id');
                END IF;
                IF sequence_name IS NOT NULL THEN
                    EXECUTE format('REVOKE ALL ON SEQUENCE %s FROM PUBLIC', sequence_name);
                END IF;
                FOR api_role IN
                    SELECT rolname FROM pg_roles
                    WHERE rolname IN ('anon', 'authenticated', 'service_role')
                LOOP
                    EXECUTE format('REVOKE ALL ON TABLE public.%I FROM %I',
                                   '{tabla}', api_role);
                    IF sequence_name IS NOT NULL THEN
                        EXECUTE format('REVOKE ALL ON SEQUENCE %s FROM %I',
                                       sequence_name, api_role);
                    END IF;
                END LOOP;
            END $$;
            """)
        )


def downgrade():
    # No restaurar grants desconocidos ni abrir datos al bajar una versión.
    # RLS y las revocaciones se conservan intencionalmente.
    pass
