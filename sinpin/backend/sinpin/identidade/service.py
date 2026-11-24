"""Identidade e controle de acesso.

IMPORTANTE (hackathon): a autenticação é um *stub de desenvolvimento* (cabeçalho X-Dev-User).
A integração gov.br/Keycloak (OIDC) deve substituir apenas `autenticar()` em api/app.py: o resto
do sistema consome somente o objeto `Contexto`.

A regra de visibilidade de documentos mora aqui, em UM lugar (`sql_visivel`), e é aplicada por todos
os módulos (listagem, pesquisa, grafo, minutas). Nenhuma consulta a documentos deve existir sem ela.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..db import Database

PERFIS = ("SERVIDOR", "ADMIN_ORGAO", "CURADOR_NACIONAL")


@dataclass(frozen=True)
class Contexto:
    usuario_id: str
    login: str
    nome: str
    org_id: str
    org_sigla: str
    perfil: str

    @property
    def curador_nacional(self) -> bool:
        return self.perfil == "CURADOR_NACIONAL"


def contexto_por_login(db: Database, login: str) -> Contexto | None:
    r = db.conn().execute(
        "SELECT u.id, u.login, u.nome, u.org_id, u.perfil, o.sigla FROM usuario u "
        "JOIN orgao o ON o.id=u.org_id WHERE u.login=? AND u.ativo=1",
        (login,),
    ).fetchone()
    if not r:
        return None
    return Contexto(r["id"], r["login"], r["nome"], r["org_id"], r["sigla"], r["perfil"])


def listar_usuarios_dev(db: Database) -> list[dict]:
    rs = db.conn().execute(
        "SELECT u.login, u.nome, u.perfil, o.sigla AS orgao FROM usuario u "
        "JOIN orgao o ON o.id=u.org_id WHERE u.ativo=1 ORDER BY o.sigla, u.login"
    )
    return [dict(r) for r in rs]


def sql_visivel(ctx: Contexto, alias: str = "d") -> tuple[str, list]:
    """Fragmento SQL (e parâmetros) que restringe `alias` (tabela documento) ao que `ctx` pode ver.

    - NACIONAL: todos.
    - INSTITUCIONAL_RESTRITO: apenas o órgão proprietário.
    - INSTITUCIONAL_COMPARTILHADO: proprietário + órgãos com registro em `compartilhamento`.
    """
    a = alias
    sql = (
        f"({a}.escopo='NACIONAL' OR {a}.org_id=? OR ({a}.escopo='INSTITUCIONAL_COMPARTILHADO' AND "
        f"EXISTS (SELECT 1 FROM compartilhamento cp WHERE cp.documento_id={a}.id AND cp.org_id=?)))"
    )
    return sql, [ctx.org_id, ctx.org_id]


def documento_visivel(db: Database, ctx: Contexto, documento_id: str) -> bool:
    sql, params = sql_visivel(ctx, "d")
    r = db.conn().execute(f"SELECT 1 FROM documento d WHERE d.id=? AND {sql}", [documento_id, *params]).fetchone()
    return r is not None
