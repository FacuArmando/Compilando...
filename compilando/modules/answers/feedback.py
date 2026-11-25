"""Evaluaciones de utilidad, independientes de la aceptación de respuestas."""

from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError

from compilando.extensions import db
from compilando.modules.answers.models import EvaluacionRespuesta, Respuesta
from compilando.modules.auth.models import Usuario


def evaluar_respuesta(respuesta: Respuesta, usuario: Usuario, util: bool | None) -> None:
    """Guardar una elección explícita; repetir un envío no duplica ni retira el voto."""
    if util is not None and type(util) is not bool:
        raise ValueError("Evaluación inválida.")
    if not respuesta.es_ia and respuesta.usuario_id == usuario.id:
        raise PermissionError("No podés evaluar tu propia respuesta.")

    clave = (respuesta.id, usuario.id)
    try:
        evaluacion = db.session.get(EvaluacionRespuesta, clave)
        if util is None:
            if evaluacion is not None:
                db.session.delete(evaluacion)
        else:
            if evaluacion is None:
                try:
                    with db.session.begin_nested():
                        evaluacion = EvaluacionRespuesta(
                            respuesta_id=respuesta.id, usuario_id=usuario.id, util=util
                        )
                        db.session.add(evaluacion)
                        db.session.flush()
                except IntegrityError:
                    # Otro envío pudo crear la misma evaluación mientras se procesaba este.
                    evaluacion = db.session.get(EvaluacionRespuesta, clave)
                    if evaluacion is None:
                        raise
            evaluacion.util = util
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def resumen_evaluaciones(
    respuestas: list[Respuesta], usuario: Usuario | None
) -> dict[int, tuple[int, bool | None]]:
    """Consultar conteos positivos y elección personal en un máximo de dos consultas."""
    ids = [respuesta.id for respuesta in respuestas]
    if not ids:
        return {}

    conteos = dict(
        db.session.execute(
            select(
                EvaluacionRespuesta.respuesta_id,
                func.sum(case((EvaluacionRespuesta.util.is_(True), 1), else_=0)),
            )
            .where(EvaluacionRespuesta.respuesta_id.in_(ids))
            .group_by(EvaluacionRespuesta.respuesta_id)
        ).all()
    )
    propias = {}
    if usuario is not None:
        propias = dict(
            db.session.execute(
                select(EvaluacionRespuesta.respuesta_id, EvaluacionRespuesta.util).where(
                    EvaluacionRespuesta.respuesta_id.in_(ids),
                    EvaluacionRespuesta.usuario_id == usuario.id,
                )
            ).all()
        )
    return {id_: (int(conteos.get(id_, 0)), propias.get(id_)) for id_ in ids}
