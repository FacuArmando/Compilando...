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


@pytest.mark.parametrize(
    "busqueda", ["herencia java", "java herencia", "  JAVA   herencia JAVA  ", "java\therencia"]
)
def test_busqueda_por_terminos_distribuidos_y_sin_orden(client, usuario, busqueda):
    esperada = publicar_pregunta(
        "Clases y contratos en Java", "Un ejemplo de herencia.", "Java", [], usuario
    )
    publicar_pregunta("Contratos en Java", "Un ejemplo de interfaces.", "Java", [], usuario)
    publicar_pregunta("Herencia en Python", "Un ejemplo de clases.", "Python", [], usuario)
    response = client.get("/", query_string={"q": busqueda})
    assert response.status_code == 200
    feed = Feed(response.text)
    assert feed.preguntas == [esperada.id]
    assert feed.busqueda == busqueda.strip()


@pytest.mark.parametrize("tecnologia", ["C++", "C#", ".NET"])
def test_busqueda_conserva_simbolos_de_tecnologias(client, usuario, tecnologia):
    esperadas = {}
    for nombre in ["C++", "C#", ".NET", "dotnet"]:
        esperadas[nombre] = publicar_pregunta(
            f"Ejemplos para {nombre}", "Una explicación específica.", "Programación", [], usuario
        ).id
    assert Feed(client.get("/", query_string={"q": tecnologia}).text).preguntas == [
        esperadas[tecnologia]
    ]


@pytest.mark.parametrize(
    "literal, alternativa",
    [("100%", "100X"), ("mi_variable", "miXvariable"), (r"C:\ejemplos", "C:ejemplos")],
)
def test_busqueda_trata_comodines_y_barra_como_texto(client, usuario, literal, alternativa):
    esperada = publicar_pregunta(
        f"Ejemplo de {literal}", "Contenido específico.", "Java", [], usuario
    )
    publicar_pregunta(f"Ejemplo de {alternativa}", "Otro contenido.", "Java", [], usuario)
    assert Feed(client.get("/", query_string={"q": literal}).text).preguntas == [esperada.id]


def test_varios_terminos_conservan_categoria_y_paginacion(client, usuario):
    categoria = Categoria(nombre="Java", descripcion="Ejemplos")
    preguntas = [
        Pregunta(
            titulo=f"Contratos Java {n}",
            cuerpo_detallado="Ejemplo de herencia.",
            usuario=usuario,
            categoria=categoria,
        )
        for n in range(21)
    ]
    db.session.add_all(preguntas)
    db.session.commit()
    parametros = {"q": "herencia Java", "categoria": categoria.id}
    primera = Feed(client.get("/", query_string=parametros).text)
    assert primera.preguntas == [p.id for p in reversed(preguntas)][0:20]
    siguiente = primera.paginas["next"]
    query = parse_qs(urlsplit(siguiente).query)
    assert query["q"] == [parametros["q"]]
    assert query["categoria"] == [str(categoria.id)]
    assert Feed(client.get(siguiente).text).preguntas == [preguntas[0].id]
    otra = publicar_pregunta(
        "Java y sus contratos", "Ejemplo de herencia.", "Otra categoría", [], usuario
    )
    assert otra.id not in Feed(client.get("/", query_string=parametros).text).preguntas


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


def test_busqueda_usa_aceptadas_para_desempatar_y_sin_busqueda_sigue_reciente(app, usuario):
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
        ({"q": "interfaz"}, [ids[-1], *ids[:-1]]),
        ({"q": "interfaz", "categoria": categoria_id}, [ids[-1], *ids[:-1]]),
    ]:
        html = cliente.get("/", query_string=parametros).get_data(as_text=True)
        assert Feed(html).preguntas == orden[:20]
        assert ('data-i18n="Más relevantes"' in html) == ("q" in parametros)


@pytest.mark.parametrize("con_categoria", [False, True])
def test_relevancia_prioriza_titulo_etiquetas_cuerpo_antes_de_aceptacion(
    client, usuario, con_categoria
):
    titulo = publicar_pregunta("Herencia en Java", "Ejemplo concreto.", "Java", [], usuario)
    etiquetas = publicar_pregunta(
        "Clases y contratos", "Ejemplo concreto.", "Java", ["java", "java-basics"], usuario
    )
    cuerpo = publicar_pregunta("Ejemplos de contratos", "Un ejemplo de Java.", "Java", [], usuario)
    titulo.fecha = date(2020, 1, 1)
    db.session.add(
        Respuesta(
            cuerpo="Solución aceptada pero menos relacionada.",
            pregunta=cuerpo,
            usuario=usuario,
            estado=EstadoRespuesta.ACEPTADA.value,
        )
    )
    db.session.commit()
    parametros = {"q": "java"}
    if con_categoria:
        parametros["categoria"] = titulo.categoria_id
    for consulta in ["java", "JAVA java JAVA"]:
        html = client.get("/", query_string={**parametros, "q": consulta}).text
        assert Feed(html).preguntas == [titulo.id, etiquetas.id, cuerpo.id]
        assert 'data-i18n="Más relevantes"' in html
    client.set_cookie("compilando-language", "en")
    assert "Most relevant" in client.get("/", query_string=parametros).text


def test_terminos_entre_titulo_y_etiquetas(client, usuario):
    esperada = publicar_pregunta(
        "Herencia entre objetos", "Una explicación con ejemplos.", "Java", ["java"], usuario
    )
    publicar_pregunta(
        "Contratos entre objetos", "Una explicación con ejemplos.", "Java", ["java"], usuario
    )
    publicar_pregunta(
        "Herencia entre clases", "Una explicación con ejemplos.", "Python", ["python"], usuario
    )
    assert Feed(client.get("/", query_string={"q": "java herencia"}).text).preguntas == [
        esperada.id
    ]


def test_etiquetas_multiples_no_duplican_resultados_ni_paginas(client, usuario):
    categoria = Categoria(nombre="Java", descripcion="Ejemplos")
    etiquetas = [Tag(nombre="java"), Tag(nombre="java-basics")]
    preguntas = [
        Pregunta(
            titulo=f"Pregunta sobre contratos {n}",
            cuerpo_detallado="Ejemplo de interfaces.",
            usuario=usuario,
            categoria=categoria,
            tags=etiquetas,
        )
        for n in range(21)
    ]
    db.session.add_all(preguntas)
    db.session.commit()
    primera = client.get("/", query_string={"q": "java contratos"})
    feed = Feed(primera.text)
    assert 'aria-label="21 resultados"' in primera.text
    ids = feed.preguntas + Feed(client.get(feed.paginas["next"]).text).preguntas
    assert ids == [p.id for p in reversed(preguntas)]
    assert len(set(ids)) == 21


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
    assert len(lecturas) <= 7  # Incluye una consulta agrupada de destacados, sin crecer por autor.
    assert any("LIMIT ? OFFSET ?" in sql and valores[-2:] == (20, 0) for sql, valores in lecturas)
    respuestas = [(sql, valores) for sql, valores in lecturas if "FROM respuestas" in sql]
    assert len(respuestas) == 1
    sql, valores = respuestas[0]
    assert "count(respuestas.id)" in sql
    assert "respuestas.cuerpo" not in sql
    assert set(valores) == set(ids[:20])


def test_eliminar_pregunta_autor_exitosa(app, usuario, tmp_path):
    from io import BytesIO

    from werkzeug.datastructures import FileStorage

    from compilando.modules.answers.services import publicar_respuesta
    from compilando.modules.questions.attachments import ruta_adjunto
    from compilando.modules.questions.models import AdjuntoPregunta, Pregunta
    from compilando.modules.questions.services import eliminar_pregunta, publicar_pregunta

    app.config["ATTACHMENTS_FOLDER"] = str(tmp_path)
    archivo = FileStorage(
        stream=BytesIO(b"print('hola')\n"),
        filename="ejemplo.py",
        content_type="text/x-python",
    )

    pregunta = publicar_pregunta(
        titulo="¿Cómo borrar una pregunta?",
        cuerpo="Probando eliminación completa con adjunto y respuesta.",
        categoria_nombre="Python",
        nombres_tags=["pytest"],
        usuario=usuario,
        archivos=[archivo],
    )
    adjunto_id = pregunta.adjuntos[0].id
    ruta_archivo = ruta_adjunto(adjunto_id)
    assert ruta_archivo.is_file()

    publicar_respuesta(
        pregunta_id=pregunta.id,
        cuerpo="Esta respuesta debe eliminarse en cascada.",
        usuario=usuario,
    )

    eliminar_pregunta(pregunta_id=pregunta.id, usuario=usuario)

    assert db.session.get(Pregunta, pregunta.id) is None
    assert db.session.get(AdjuntoPregunta, adjunto_id) is None
    assert not ruta_archivo.exists()


def test_eliminar_pregunta_otro_usuario_falla(app, usuario):
    from compilando.modules.auth.models import Usuario
    from compilando.modules.questions.services import eliminar_pregunta, publicar_pregunta

    intruso = Usuario(
        username="intruso_preg",
        email="intruso_preg@test.com",
        password_hash="hash_intruso",
    )
    db.session.add(intruso)
    db.session.commit()

    pregunta = publicar_pregunta(
        titulo="¿Puede otro usuario borrar mi pregunta?",
        cuerpo="Solo el autor debería poder eliminarla.",
        categoria_nombre="Seguridad",
        nombres_tags=["permisos"],
        usuario=usuario,
    )

    with pytest.raises(PermissionError, match="Solo el autor"):
        eliminar_pregunta(pregunta_id=pregunta.id, usuario=intruso)


def test_ruta_eliminar_pregunta(app, usuario, client, cliente_autenticado):
    from compilando.modules.questions.models import Pregunta
    from compilando.modules.questions.services import publicar_pregunta

    pregunta = publicar_pregunta(
        titulo="¿Ruta POST para eliminar pregunta?",
        cuerpo="Probando endpoint HTTP de eliminación.",
        categoria_nombre="Flask",
        nombres_tags=["rutas"],
        usuario=usuario,
    )

    # Sin sesión devuelve 401
    resp_anon = client.post(f"/questions/{pregunta.id}/delete")
    assert resp_anon.status_code == 401

    # Con sesión del autor elimina y redirige
    auth_client = cliente_autenticado(usuario)
    resp_ok = auth_client.post(f"/questions/{pregunta.id}/delete", follow_redirects=False)
    assert resp_ok.status_code == 302
    assert db.session.get(Pregunta, pregunta.id) is None
