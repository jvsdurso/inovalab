"""Gestão de órgãos/instituições (MVP: cadastro básico e dados-base de desenvolvimento)."""
from __future__ import annotations

from ..common.util import agora, novo_id
from ..db import Database

# Dados-base de desenvolvimento. Em produção, órgãos e usuários virão do IdP (gov.br/Keycloak).
ORGAOS_DEV = [
    ("sinpin", "SINPIN", "Curadoria Nacional SINPIN"),
    ("senatran", "SENATRAN", "Secretaria Nacional de Trânsito"),
    ("detran-xx", "DETRAN-XX", "Departamento Estadual de Trânsito (demonstração)"),
]
USUARIOS_DEV = [
    ("curador", "Curador Nacional (demo)", "sinpin", "CURADOR_NACIONAL"),
    ("senatran.servidor", "Servidor SENATRAN (demo)", "senatran", "SERVIDOR"),
    ("detran.servidor", "Servidor DETRAN-XX (demo)", "detran-xx", "SERVIDOR"),
]


def listar(db: Database) -> list[dict]:
    return [dict(r) for r in db.conn().execute("SELECT id, sigla, nome FROM orgao ORDER BY sigla")]


def obter(db: Database, org_id: str) -> dict | None:
    r = db.conn().execute("SELECT id, sigla, nome FROM orgao WHERE id=?", (org_id,)).fetchone()
    return dict(r) if r else None


def semear_dev(db: Database) -> None:
    """Idempotente."""
    with db.tx() as c:
        for oid, sigla, nome in ORGAOS_DEV:
            c.execute("INSERT OR IGNORE INTO orgao(id,sigla,nome,registrado_em) VALUES (?,?,?,?)", (oid, sigla, nome, agora()))
        for login, nome, org, perfil in USUARIOS_DEV:
            c.execute(
                "INSERT OR IGNORE INTO usuario(id,login,nome,org_id,perfil) VALUES (?,?,?,?,?)",
                (novo_id(), login, nome, org, perfil),
            )
