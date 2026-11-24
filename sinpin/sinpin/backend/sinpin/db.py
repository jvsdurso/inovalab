"""Acesso ao banco.

Banco principal: **PostgreSQL** (driver psycopg 3). SQLite existe apenas para testes/execução offline
(`SINPIN_DATABASE_URL=sqlite:///caminho.db`); a suíte completa pode rodar nos dois (ver tests/conftest.py).

Toda a persistência passa por aqui. O SQL do domínio usa o subconjunto comum aos dois dialetos, com placeholders `?`
(traduzidos para `%s` no PostgreSQL) e as poucas diferenças tratadas em `traduzir_sql`.
"""
from __future__ import annotations

import contextlib
import re
import sqlite3
import threading
from pathlib import Path
from typing import Any

MIGRACOES = Path(__file__).resolve().parent / "migrations"
_TRAVA_MIGRACAO = 727274  # pg_advisory_lock: evita duas instâncias migrando ao mesmo tempo


def traduzir_sql(sql: str, com_params: bool = True) -> str:
    """SQL do domínio (`?`, INSERT OR IGNORE) -> PostgreSQL (`%s`, ON CONFLICT DO NOTHING)."""
    ignora = re.match(r"\s*INSERT\s+OR\s+IGNORE\s+INTO", sql, re.I) is not None
    if ignora:
        sql = re.sub(r"INSERT\s+OR\s+IGNORE\s+INTO", "INSERT INTO", sql, count=1, flags=re.I)
        sql = sql.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
    if com_params:
        sql = sql.replace("%", "%%").replace("?", "%s")
    return sql


def separar_comandos(script: str) -> list[str]:
    """Divide um script de migração em comandos. Remove comentários `--` (inclusive no fim de linha) respeitando
    aspas simples. Só DDL simples: sem funções, DO blocks nem `$$`."""
    saida, atual, aspas, i, n = [], [], False, 0, len(script)
    while i < n:
        ch = script[i]
        if aspas:
            atual.append(ch)
            if ch == "'":
                aspas = False
        elif ch == "'":
            aspas = True
            atual.append(ch)
        elif ch == "-" and script.startswith("--", i):
            while i < n and script[i] != "\n":
                i += 1
            continue
        elif ch == ";":
            cmd = "".join(atual).strip()
            if cmd:
                saida.append(cmd)
            atual = []
        else:
            atual.append(ch)
        i += 1
    cmd = "".join(atual).strip()
    if cmd:
        saida.append(cmd)
    return saida


class Database:
    """Base: conexão por thread + transações aninháveis. Subclasses definem o driver."""
    dialeto = "?"
    suporta_vetor = False

    def __init__(self) -> None:
        self._local = threading.local()

    # -- driver
    def _abrir(self) -> Any:  # pragma: no cover - abstrato
        raise NotImplementedError

    def _begin(self) -> str:
        return "BEGIN"

    def migrate(self) -> list[str]:  # pragma: no cover - abstrato
        raise NotImplementedError

    def aplicaveis(self) -> list[Path]:
        outro = ".sqlite.sql" if self.dialeto == "postgresql" else ".pg.sql"
        return [a for a in sorted(MIGRACOES.glob("*.sql")) if not a.name.endswith(outro)]

    # -- comum
    def conn(self):
        c = getattr(self._local, "c", None)
        if c is None:
            c = self._abrir()
            self._local.c = c
            self._local.depth = 0
        return c

    @contextlib.contextmanager
    def tx(self):
        """Transação (aninhável: só a mais externa faz BEGIN/COMMIT)."""
        c = self.conn()
        if self._local.depth == 0:
            c.execute(self._begin())
        self._local.depth += 1
        try:
            yield c
        except BaseException:
            self._local.depth -= 1
            if self._local.depth == 0:
                c.execute("ROLLBACK")
            raise
        else:
            self._local.depth -= 1
            if self._local.depth == 0:
                c.execute("COMMIT")


class SQLiteDatabase(Database):
    dialeto = "sqlite"

    def __init__(self, path: str):
        super().__init__()
        self.path = path
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)

    def _abrir(self):
        c = sqlite3.connect(self.path, isolation_level=None, timeout=30)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("PRAGMA journal_mode=WAL")
        return c

    def _begin(self) -> str:
        return "BEGIN IMMEDIATE"

    def migrate(self) -> list[str]:
        c = self.conn()
        c.execute("CREATE TABLE IF NOT EXISTS schema_migrations (versao TEXT PRIMARY KEY, aplicada_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        feitas = {r["versao"] for r in c.execute("SELECT versao FROM schema_migrations")}
        aplicadas = []
        for arq in self.aplicaveis():
            if arq.stem in feitas:
                continue
            c.executescript(arq.read_text(encoding="utf-8"))
            c.execute("INSERT INTO schema_migrations(versao) VALUES (?)", (arq.stem,))
            aplicadas.append(arq.stem)
        return aplicadas


class _ConexaoPg:
    """Adapta a conexão psycopg à interface usada pelo domínio (`execute(sql_com_?, params)` -> cursor de dicts)."""
    def __init__(self, raw):
        self.raw = raw

    def execute(self, sql: str, params=None):
        if params is not None and len(params) == 0:
            params = None
        return self.raw.execute(traduzir_sql(sql, params is not None), params)

    def close(self):
        self.raw.close()


class PostgresDatabase(Database):
    dialeto = "postgresql"
    suporta_vetor = True

    def __init__(self, url: str):
        super().__init__()
        self.url = url.replace("postgresql+psycopg://", "postgresql://")

    def _abrir(self):
        import psycopg
        from psycopg.rows import dict_row
        return _ConexaoPg(psycopg.connect(self.url, autocommit=True, row_factory=dict_row))

    def migrate(self) -> list[str]:
        c = self.conn()
        c.execute("SELECT pg_advisory_lock(%s)" % _TRAVA_MIGRACAO)
        try:
            c.execute("CREATE TABLE IF NOT EXISTS schema_migrations (versao TEXT PRIMARY KEY, aplicada_em TEXT NOT NULL)")
            feitas = {r["versao"] for r in c.execute("SELECT versao FROM schema_migrations")}
            aplicadas = []
            for arq in self.aplicaveis():
                if arq.stem in feitas:
                    continue
                with self.tx():  # DDL é transacional no PostgreSQL: a migração entra inteira ou não entra
                    for cmd in separar_comandos(arq.read_text(encoding="utf-8")):
                        c.execute(cmd)
                    from .common.util import agora
                    c.execute("INSERT INTO schema_migrations(versao, aplicada_em) VALUES (?,?)", (arq.stem, agora()))
                aplicadas.append(arq.stem)
            return aplicadas
        finally:
            c.execute("SELECT pg_advisory_unlock(%s)" % _TRAVA_MIGRACAO)


def criar_database(url: str | None, db_path: str | None = None) -> Database:
    """`url`: postgresql://… (padrão do projeto) ou sqlite:///arquivo (testes/offline). Sem `url`, usa SQLite em `db_path`."""
    if url and url.startswith(("postgresql://", "postgres://", "postgresql+psycopg://")):
        return PostgresDatabase(url.replace("postgres://", "postgresql://", 1))
    if url and url.startswith("sqlite:///"):
        return SQLiteDatabase(url[len("sqlite:///"):] or ":memory:")
    if url:
        raise ValueError(f"SINPIN_DATABASE_URL não suportada: {url.split(':')[0]}://…")
    return SQLiteDatabase(db_path or ":memory:")
