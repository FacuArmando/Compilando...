import json
from datetime import date, timedelta
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

import pytest
from sqlalchemy import event
from werkzeug.security import generate_password_hash

from compilando.extensions import db
from compilando.modules.answers.models import EstadoRespuesta, Respuesta
from compilando.modules.auth.models import Usuario
from compilando.modules.categories.models import Categoria
from compilando.modules.questions.models import Pregunta
from compilando.modules.questions.services import publicar_pregunta
from compilando.modules.tags.models import Tag


class Feed(HTMLParser):
    """Leer los enlaces y controles que recibe el navegador después de integrar el feed."""

    def __init__(self, html):
        super().__init__()
        self.preguntas = []
        self.paginas = {}
        self.numeros = {}
        self.actual = None
        self.conteos = []
        self.busqueda = None
        self.categoria = None
        self.ids = set()
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("data-i18n") in {"{count} respuesta", "{count} respuestas"}:
            self.conteos.append(json.loads(attrs["data-i18n-params"])["count"])
        if "id" in attrs:
            self.ids.add(attrs["id"])
        if "community-page-number" in attrs.get("class", "").split():
            numero = int(attrs["aria-label"].split()[-1])
            if attrs.get("aria-current") == "page":
                self.actual = numero
            elif tag == "a":
                self.numeros[numero] = attrs["href"]
        if tag == "a":
            ruta = urlsplit(attrs.get("href", "")).path
            if ruta.startswith("/questions/") and ruta.removeprefix("/questions/").isdigit():
                self.preguntas.append(int(ruta.removeprefix("/questions/")))
            if attrs.get("rel") in {"prev", "next"}:
                self.paginas[attrs["rel"]] = attrs["href"]
        if tag == "input" and attrs.get("name") == "q":
            self.busqueda = attrs.get("value")
        if tag == "option" and "selected" in attrs:
            self.categoria = attrs["value"]


def cliente_consulta(app, usuario, con_sesion):
    cliente = app.test_client()
    if con_sesion:
        usuario.password_hash = generate_password_hash("clave-prueba")
        db.session.commit()
        response = cliente.post(
            "/auth/login", data={"email": usuario.email, "password": "clave-prueba"}
        )
        assert response.status_code == 303
    return cliente


def test_consultar_preguntas_publicadas(app, usuario):
    publicar_pregunta(
        titulo="¿Cómo funciona Python?",
        cuerpo="Quiero aprender los fundamentos de este lenguaje.",
        categoria_nombre="Programación",
        nombres_tags=["python"],
        usuario=usuario,
    )

    publicar_pregunta(
        titulo="¿Cómo funciona Flask?",
        cuerpo="Quiero aprender a desarrollar aplicaciones web.",
        categoria_nombre="Desarrollo web",
        nombres_tags=["flask"],
        usuario=usuario,
    )

    cliente = app.test_client()
    response = cliente.get("/")

    assert response.status_code == 200
    assert b"Preguntas recientes" in response.data
    assert (
        b"Como funciona Python?" in response.data
        or "¿Cómo funciona Python?".encode() in response.data
    )
    assert "¿Cómo funciona Flask?".encode() in response.data

    posicion_flask = response.data.index("¿Cómo funciona Flask?".encode())
    posicion_python = response.data.index("¿Cómo funciona Python?".encode())

    assert posicion_flask < posicion_python


def test_consultar_preguntas_sin_publicaciones(app):
    cliente = app.test_client()
    response = cliente.get("/")

    assert response.status_code == 200
    assert "Todavía no hay preguntas publicadas.".encode() in response.data


@pytest.mark.parametrize("con_sesion", [False, True])
def test_feed_combina_busqueda_y_categoria_y_conserva_los_controles(app, usuario, con_sesion):
    pregunta = publicar_pregunta(
        "¿Cómo diseño un TAD?",
        "Quiero separar la interfaz y los datos.",
        "Estructuras",
        [],
        usuario,
    )
    publicar_pregunta(
        "¿Cómo diseño una cola?",
        "Quiero organizar sus operaciones.",
        "Estructuras",
        [],
        usuario,
    )
    publicar_pregunta(
        "¿Cómo diseño una interfaz web?",
        "Quiero organizar los botones.",
        "Desarrollo web",
        [],
        usuario,
    )
    cliente = cliente_consulta(app, usuario, con_sesion)
    response = cliente.get("/", query_string={"q": "INTERFAZ", "categoria": pregunta.categoria_id})
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    feed = Feed(html)
    assert feed.preguntas == [pregunta.id]
    assert feed.busqueda == "INTERFAZ"
    assert feed.categoria == str(pregunta.categoria_id)
    assert 'aria-label="1 resultado"' in html
    assert ('id="question-composer"' in html) == con_sesion


@pytest.mark.parametrize("con_sesion", [False, True])
def test_feed_pagina_sin_perder_busqueda_ni_categoria(app, usuario, con_sesion):
    ids = []
    for numero in range(22):
        pregunta = publicar_pregunta(
            f"Pila de prueba {numero:02d}",
            "Quiero organizar sus operaciones.",
            "Estructuras",
            [],
            usuario,
        )
        ids.append(pregunta.id)
    categoria_id = db.session.scalar(
        db.select(Categoria.id).where(Categoria.nombre == "Estructuras")
    )
    publicar_pregunta(
        "Pila de otra categoría",
        "Una pregunta de desarrollo web.",
        "Desarrollo web",
        [],
        usuario,
    )
    cliente = cliente_consulta(app, usuario, con_sesion)
    primera = cliente.get("/", query_string={"q": "Pila", "categoria": categoria_id})
    assert primera.status_code == 200
    html = primera.get_data(as_text=True)
    feed = Feed(html)
    assert feed.preguntas == list(reversed(ids))[:20]
    assert 'aria-label="22 resultados"' in html
    assert "prev" not in feed.paginas
    enlace = urlsplit(feed.paginas["next"])
    assert enlace.fragment == "preguntas"
    assert parse_qs(enlace.query) == {
        "page": ["2"],
        "q": ["Pila"],
        "categoria": [str(categoria_id)],
    }
    segunda = cliente.get(f"{enlace.path}?{enlace.query}")
    assert segunda.status_code == 200
    feed_segunda = Feed(segunda.get_data(as_text=True))
    assert feed_segunda.preguntas == list(reversed(ids))[20:]
    assert "next" not in feed_segunda.paginas
    assert parse_qs(urlsplit(feed_segunda.paginas["prev"]).query)["page"] == ["1"]


@pytest.mark.parametrize("con_sesion", [False, True])
def test_feed_sin_coincidencias_conserva_y_escapa_la_busqueda(app, usuario, con_sesion):
    cliente = cliente_consulta(app, usuario, con_sesion)
    busqueda = '"><script>alert(1)</script>'
    response = cliente.get("/", query_string={"q": busqueda})
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "No encontramos preguntas" in html
    assert "<script>alert(1)</script>" not in html
    assert Feed(html).busqueda == busqueda
    assert Feed(html).preguntas == []


def test_busqueda_y_formulario_desplegable_no_comparten_identificadores(app, usuario):
    cliente = cliente_consulta(app, usuario, con_sesion=True)
    inicio = cliente.get("/")
    formulario = cliente.get("/questions/publish")
    assert inicio.status_code == formulario.status_code == 200
    ids_inicio = Feed(inicio.get_data(as_text=True)).ids
    ids_formulario = Feed(formulario.get_data(as_text=True)).ids
    # Al insertar el formulario en el inicio, cada label debe seguir apuntando a su campo.
    assert ids_inicio.isdisjoint(ids_formulario)


def crear_listado(usuario, cantidad):
    """Datos aislados con fechas repetidas y distintas del orden de inserción."""
    categoria = Categoria(nombre="Estructuras", descripcion="Categoría de prueba")
    etiqueta = Tag(nombre="java")
    db.session.add_all([categoria, etiqueta])
    db.session.flush()
    preguntas = [
        Pregunta(
            titulo=f"Pregunta de prueba {numero:03d}",
            cuerpo_detallado="Cómo separar una interfaz de su implementación.",
            fecha=date(2026, 1, 1) + timedelta(days=numero % 4),
            usuario_id=usuario.id,
            categoria_id=categoria.id,
            tags=[etiqueta],
        )
        for numero in range(cantidad)
    ]
    db.session.add_all(preguntas)
    db.session.commit()
    ids = [p.id for p in sorted(preguntas, key=lambda p: (p.fecha, p.id), reverse=True)]
    return categoria.id, ids


@pytest.mark.parametrize("cantidad", [0, 19, 20, 21, 40, 41])
def test_limites_del_listado_y_ultima_pagina(app, usuario, cantidad):
    _, ids = crear_listado(usuario, cantidad)
    cliente = app.test_client()
    respuesta = cliente.get("/", query_string={"per_page": 10000})
    assert respuesta.status_code == 200
    html = respuesta.get_data(as_text=True)
    feed = Feed(html)
    assert feed.preguntas == ids[:20]
    assert ("next" in feed.paginas) == (cantidad > 20)
    assert "prev" not in feed.paginas
    assert ('class="community-pagination-controls"' in html) == (cantidad > 20)

    if cantidad:
        assert f"Mostrando 1–{min(20, cantidad)} de {cantidad} preguntas" in html
    if cantidad > 20:
        ultima = (cantidad + 19) // 20
        html_ultima = cliente.get(f"/?page={ultima}").get_data(as_text=True)
        feed_ultima = Feed(html_ultima)
        assert feed_ultima.preguntas == ids[(ultima - 1) * 20 :]
        assert feed_ultima.actual == ultima
        assert "next" not in feed_ultima.paginas
        assert "prev" in feed_ultima.paginas


@pytest.mark.parametrize("filtro", ["categoria", "busqueda", "ambos"])
def test_orden_estable_en_todas_las_paginas_con_filtros(app, usuario, filtro):
    categoria_id, ids = crear_listado(usuario, 41)
    parametros = {}
    if filtro in {"categoria", "ambos"}:
        parametros["categoria"] = categoria_id
    if filtro in {"busqueda", "ambos"}:
        parametros["q"] = "interfaz"
    encontrados = []
    for pagina in (1, 2, 3):
        respuesta = app.test_client().get("/", query_string={**parametros, "page": pagina})
        assert respuesta.status_code == 200
        encontrados.extend(Feed(respuesta.get_data(as_text=True)).preguntas)
    assert encontrados == ids


@pytest.mark.parametrize("pagina", ["0", "-1", "abc", "", "1.5", "999", "9" * 50])
def test_pagina_invalida_vuelve_al_inicio_con_los_filtros(app, usuario, pagina):
    categoria_id, _ = crear_listado(usuario, 1)
    respuesta = app.test_client().get(
        "/", query_string={"page": pagina, "q": "interfaz", "categoria": categoria_id}
    )
    assert respuesta.status_code == 302
    destino = urlsplit(respuesta.location)
    assert destino.path == "/"
    assert destino.fragment == "preguntas"
    assert parse_qs(destino.query) == {"q": ["interfaz"], "categoria": [str(categoria_id)]}


def test_pagina_dos_sin_publicaciones_vuelve_a_la_primera(app):
    respuesta = app.test_client().get("/?page=2", follow_redirects=True)
    assert len(respuesta.history) == 1
    assert respuesta.status_code == 200
    assert Feed(respuesta.get_data(as_text=True)).preguntas == []


@pytest.mark.parametrize("idioma", ["es", "en"])
@pytest.mark.parametrize("con_sesion", [False, True])
def test_navegacion_numerada_y_resumen_en_ambos_idiomas(app, usuario, idioma, con_sesion):
    categoria_id, _ = crear_listado(usuario, 300)
    cliente = cliente_consulta(app, usuario, con_sesion)
    cliente.set_cookie("compilando-language", idioma)
    respuesta = cliente.get(
        "/", query_string={"page": 8, "q": "interfaz", "categoria": categoria_id}
    )
    assert respuesta.status_code == 200
    html = respuesta.get_data(as_text=True)
    feed = Feed(html)
    assert feed.actual == 8
    assert set(feed.numeros) == {1, 7, 9, 15}
    assert html.count('class="community-page-gap"') == 2
    for numero, href in feed.numeros.items():
        enlace = urlsplit(href)
        assert enlace.fragment == "preguntas"
        assert parse_qs(enlace.query) == {
            "page": [str(numero)],
            "q": ["interfaz"],
            "categoria": [str(categoria_id)],
        }
    resumen = (
        "Showing 141–160 of 300 questions"
        if idioma == "en"
        else ("Mostrando 141–160 de 300 preguntas")
    )
    assert resumen in html
    assert ('id="question-composer"' in html) == con_sesion
    # El formulario GET de filtros no arrastra la página anterior.
    assert 'name="page"' not in html


def test_300_preguntas_se_recorren_sin_repeticiones_ni_omisiones(app, usuario):
    _, ids = crear_listado(usuario, 300)
    encontrados = []
    cliente = app.test_client()
    for pagina in range(1, 16):
        respuesta = cliente.get(f"/?page={pagina}")
        assert respuesta.status_code == 200
        feed = Feed(respuesta.get_data(as_text=True))
        assert len(feed.preguntas) == 20
        encontrados.extend(feed.preguntas)
    assert encontrados == ids
    assert len(set(encontrados)) == 300


def test_etiquetas_multiples_no_duplican_total_ni_recortan_la_pagina(app, usuario):
    _, ids = crear_listado(usuario, 22)
    etiquetas = [Tag(nombre=f"extra{n}") for n in range(8)]
    db.session.add_all(etiquetas)
    for pregunta in db.session.scalars(db.select(Pregunta)):
        pregunta.tags = etiquetas if pregunta.id % 2 else []
    db.session.commit()
    db.session.remove()

    cliente = app.test_client()
    for pagina, esperados in [(1, ids[:20]), (2, ids[20:])]:
        respuesta = cliente.get(f"/?page={pagina}")
        html = respuesta.get_data(as_text=True)
        assert respuesta.status_code == 200
        assert Feed(html).preguntas == esperados
        assert 'aria-label="22 resultados"' in html


def test_busqueda_combinada_conserva_prioridad_de_aceptadas(app, usuario):
    categoria_id, ids = crear_listado(usuario, 21)
    db.session.add(
        Respuesta(
            cuerpo="Respuesta de prueba",
            pregunta_id=ids[-1],
            usuario_id=usuario.id,
            estado=EstadoRespuesta.ACEPTADA.value,
        )
    )
    db.session.commit()
    cliente = app.test_client()
    for parametros, orden in [
        ({"categoria": categoria_id}, ids),
        ({"q": "interfaz"}, ids),
        ({"q": "interfaz", "categoria": categoria_id}, [ids[-1], *ids[:-1]]),
    ]:
        html = cliente.get("/", query_string=parametros).get_data(as_text=True)
        assert Feed(html).preguntas == orden[:20]
        assert ('data-i18n="Aceptadas primero"' in html) == (len(parametros) == 2)


def test_consultas_acotadas_y_conteos_sin_cargar_respuestas(app, usuario):
    _, ids = crear_listado(usuario, 41)
    autores = [
        Usuario(username=f"autor{n}", email=f"autor{n}@example.com", password_hash="prueba")
        for n in range(20)
    ]
    db.session.add_all(autores)
    db.session.flush()
    for pregunta_id, autor in zip(ids[:20], autores, strict=True):
        db.session.get(Pregunta, pregunta_id).usuario_id = autor.id
        db.session.add_all(
            Respuesta(cuerpo="No cargar este cuerpo", pregunta_id=pregunta_id, usuario_id=autor.id)
            for _ in range(3)
        )
    db.session.commit()
    db.session.remove()  # No aprovechar relaciones que ya estén en memoria.
    consultas = []

    def registrar(conn, cursor, statement, parameters, context, executemany):
        consultas.append((statement, parameters))

    engine = db.engine
    event.listen(engine, "before_cursor_execute", registrar)
    try:
        html = app.test_client().get("/").get_data(as_text=True)
    finally:
        event.remove(engine, "before_cursor_execute", registrar)

    feed = Feed(html)
    assert feed.preguntas == ids[:20]
    assert feed.conteos == [3] * 20
    lecturas = [
        (sql, valores) for sql, valores in consultas if sql.lstrip().upper().startswith("SELECT")
    ]
    assert len(lecturas) <= 2  # Preguntas con total/etiquetas + categorías.
    assert any("LIMIT ? OFFSET ?" in sql and valores[-2:] == (20, 0) for sql, valores in lecturas)
    respuestas = [(sql, valores) for sql, valores in lecturas if "FROM respuestas" in sql]
    assert len(respuestas) == 1
    sql, valores = respuestas[0]
    assert "count(respuestas.id)" in sql
    assert "respuestas.cuerpo" not in sql
    assert "respuestas.pregunta_id = preguntas.id" in sql
    assert valores[-2:] == (20, 0)
    assert "count(*) OVER ()" in sql
