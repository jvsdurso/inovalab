"""Fixtures. Por padrão a suíte roda em SQLite (offline). Para rodar TODA a suíte contra PostgreSQL:

    docker compose up -d db
    SINPIN_TEST_DATABASE_URL=postgresql://sinpin:sinpin@localhost:5432/sinpin pytest

(o schema `public` é limpo antes de cada teste — use um banco de testes, nunca o de dados reais).
"""
import os

import pytest

from sinpin.config import Settings
from sinpin.container import criar_container
from sinpin.identidade import service as ident

URL_PG = os.environ.get("SINPIN_TEST_DATABASE_URL", "")


def _limpar_postgres() -> None:
    import psycopg
    with psycopg.connect(URL_PG, autocommit=True) as conn:
        conn.execute(
            "DO $$ DECLARE r record; BEGIN FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname='public') LOOP "
            "EXECUTE 'DROP TABLE IF EXISTS public.' || quote_ident(r.tablename) || ' CASCADE'; END LOOP; END $$;")


def settings_teste(tmp_path, nome: str = "t", seed_demo: bool = False, **extra) -> Settings:
    base = dict(storage_dir=str(tmp_path / "arq"), seed_demo=seed_demo, **extra)
    if URL_PG:
        _limpar_postgres()
        return Settings(database_url=URL_PG, **base)
    return Settings(db_path=str(tmp_path / f"{nome}.db"), **base)


@pytest.fixture()
def c(tmp_path):
    return criar_container(settings_teste(tmp_path, "t", seed_demo=True))


@pytest.fixture()
def vazio(tmp_path):
    return criar_container(settings_teste(tmp_path, "v", seed_demo=False))


def ctx_de(c, login):
    return ident.contexto_por_login(c.db, login)


def doc_por_titulo(c, ctx, trecho):
    from sinpin.normativo import service as nv
    return next(d for d in nv.listar_documentos(c.db, ctx) if trecho in d["titulo"])
