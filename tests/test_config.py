"""Testes de configuração (app.config.Settings)."""

from app.config import Settings


def test_normaliza_url_do_railway():
    # Railway/Render injetam "postgresql://"; o app precisa do driver psycopg.
    s = Settings(database_url="postgresql://user:pass@host.internal:5432/railway")
    assert s.database_url == "postgresql+psycopg://user:pass@host.internal:5432/railway"


def test_normaliza_scheme_legado_postgres():
    s = Settings(database_url="postgres://user:pass@host/db")
    assert s.database_url == "postgresql+psycopg://user:pass@host/db"


def test_mantem_psycopg_e_sqlite():
    assert Settings(
        database_url="postgresql+psycopg://u:p@h:5432/db"
    ).database_url == "postgresql+psycopg://u:p@h:5432/db"
    assert Settings(database_url="sqlite:///./dev.db").database_url == "sqlite:///./dev.db"
