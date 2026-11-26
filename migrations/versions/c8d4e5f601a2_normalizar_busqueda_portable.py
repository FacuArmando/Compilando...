"""Conservar acentos, casefold y ñ al buscar en PostgreSQL.

Revision ID: c8d4e5f601a2
Revises: b7f3c2a19d60
"""

import unicodedata

import sqlalchemy as sa
from alembic import op

revision = "c8d4e5f601a2"
down_revision = "b7f3c2a19d60"
branch_labels = None
depends_on = None


def _normalizar(valor):
    # Copia histórica del algoritmo: no depender de modelos/código futuro.
    texto = unicodedata.normalize("NFC", (valor or "").casefold())
    return "".join(
        c
        if c == "ñ"
        else "".join(p for p in unicodedata.normalize("NFD", c) if unicodedata.category(p) != "Mn")
        for c in texto
    )


def upgrade():
    with op.batch_alter_table("preguntas") as batch:
        batch.add_column(sa.Column("titulo_busqueda", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("cuerpo_busqueda", sa.Text(), nullable=False, server_default=""))
    with op.batch_alter_table("tags") as batch:
        batch.add_column(sa.Column("nombre_busqueda", sa.Text(), nullable=False, server_default=""))
    connection = op.get_bind()
    for tabla, columnas in (
        ("preguntas", {"titulo": "titulo_busqueda", "cuerpo_detallado": "cuerpo_busqueda"}),
        ("tags", {"nombre": "nombre_busqueda"}),
    ):
        source = sa.table(
            tabla,
            sa.column("id"),
            *(sa.column(c) for c in columnas),
            *(sa.column(c) for c in columnas.values()),
        )
        last_id = None
        while True:
            query = sa.select(source.c.id, *(source.c[c] for c in columnas)).order_by(source.c.id)
            if last_id is not None:
                query = query.where(source.c.id > last_id)
            rows = connection.execute(query.limit(200)).mappings().all()
            if not rows:
                break
            for row in rows:
                connection.execute(
                    source.update()
                    .where(source.c.id == row["id"])
                    .values(
                        **{
                            destino: _normalizar(row[origen])
                            for origen, destino in columnas.items()
                        }
                    )
                )
            last_id = rows[-1]["id"]


def downgrade():
    with op.batch_alter_table("tags") as batch:
        batch.drop_column("nombre_busqueda")
    with op.batch_alter_table("preguntas") as batch:
        batch.drop_column("cuerpo_busqueda")
        batch.drop_column("titulo_busqueda")
