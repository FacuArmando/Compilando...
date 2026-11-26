"""Arranque de producción sin fallback local ni confianza en proxies arbitrarios."""

import pytest
from flask import request

from compilando import create_app
from compilando.config import load_config


def test_produccion_rechaza_sqlite():
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        create_app(
            {
                "APP_ENV": "production",
                "TESTING": False,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            }
        )


def test_produccion_rechaza_archivos_locales():
    with pytest.raises(RuntimeError, match="almacenamiento persistente"):
        create_app(
            {
                "APP_ENV": "production",
                "TESTING": False,
                "SQLALCHEMY_DATABASE_URI": "postgresql://u:p@host.invalid/db",
                "STORAGE_BACKEND": "local",
            }
        )


def test_vercel_exige_produccion_y_permite_solo_hosts_concretos(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("TRUSTED_HOSTS", raising=False)
    monkeypatch.setenv("VERCEL_URL", "compilando-preview.vercel.app")
    monkeypatch.setenv("VERCEL_PROJECT_PRODUCTION_URL", "compilando.vercel.app")
    config = load_config()
    assert config["APP_ENV"] == "production"
    assert config["SESSION_COOKIE_SECURE"]
    assert config["TRUSTED_HOSTS"] == ["compilando-preview.vercel.app", "compilando.vercel.app"]
    monkeypatch.setenv("APP_ENV", "development")
    with pytest.raises(RuntimeError, match="APP_ENV=production"):
        load_config()


@pytest.mark.parametrize("vercel", [False, True])
def test_proxy_solo_se_confia_en_vercel(monkeypatch, vercel):
    monkeypatch.setenv("VERCEL", "1" if vercel else "0")
    monkeypatch.setenv("APP_ENV", "production" if vercel else "development")
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "clave-larga-solo-para-pruebas-123456",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "TRUSTED_HOSTS": ["localhost"],
        }
    )

    @app.get("/__proxy_probe")
    def probe():
        return {"secure": request.is_secure, "ip": request.remote_addr}

    result = app.test_client().get(
        "/__proxy_probe",
        headers={
            "X-Forwarded-Proto": "https",
            "X-Forwarded-For": "203.0.113.5",
        },
    )
    assert result.status_code == 200
    assert result.json["secure"] is vercel
    assert result.json["ip"] == ("203.0.113.5" if vercel else "127.0.0.1")
