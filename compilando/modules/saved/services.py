"""Cambios explícitos e idempotentes; estados personales consultados por lote."""

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from compilando.extensions import db
from compilando.modules.saved.models import PreguntaGuardada


def cambiar_guardado(pregunta_id: int, usuario_id: int, guardar: bool):
    clave = {"usuario_id": usuario_id, "pregunta_id": pregunta_id}
    try:
        if guardar:
            if db.session.get(PreguntaGuardada, clave) is None:
                try:
                    with db.session.begin_nested():
                        db.session.add(PreguntaGuardada(**clave))
                        db.session.flush()
                except IntegrityError:
                    # Otro envío pudo guardar la misma pregunta; no renovar su fecha.
                    if db.session.get(PreguntaGuardada, clave) is None:
                        raise
        else:
            db.session.execute(
                delete(PreguntaGuardada).where(
                    PreguntaGuardada.usuario_id == usuario_id,
                    PreguntaGuardada.pregunta_id == pregunta_id,
                )
            )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def ids_guardadas(pregunta_ids: list[int], usuario_id: int | None) -> set[int]:
    if not pregunta_ids or usuario_id is None:
        return set()
    return set(
        db.session.scalars(
            select(PreguntaGuardada.pregunta_id).where(
                PreguntaGuardada.usuario_id == usuario_id,
                PreguntaGuardada.pregunta_id.in_(pregunta_ids),
            )
        )
    )
