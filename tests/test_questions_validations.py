import pytest

from compilando.modules.questions.services import (
    validar_cuerpo,
    validar_titulo,
)


@pytest.mark.parametrize(
    "titulo",
    [
        "Hola mundo",  # 10 caracteres
        "A" * 150,  # 150 caracteres
        "   Hola mundo   ",  # Espacios exteriores
    ],
)
def test_validar_titulo_valido(titulo):
    assert validar_titulo(titulo) is True


@pytest.mark.parametrize(
    "titulo",
    [
        "Hola",  # Menos de 10 caracteres
        "A" * 151,  # Más de 150 caracteres
        "     ",  # Solo espacios
    ],
)
def test_validar_titulo_invalido(titulo):
    assert validar_titulo(titulo) is False


@pytest.mark.parametrize(
    "cuerpo",
    [
        "Hey",  # 3 caracteres
        "A" * 5000,  # 5000 caracteres
    ],
)
def test_validar_cuerpo_valido(cuerpo):
    assert validar_cuerpo(cuerpo) is True


@pytest.mark.parametrize(
    "cuerpo",
    [
        "Hi",  # Menos de 3 caracteres
        "A" * 5001,  # Más de 5000 caracteres
        "   ",  # Solo espacios
    ],
)
def test_validar_cuerpo_invalido(cuerpo):
    assert validar_cuerpo(cuerpo) is False
