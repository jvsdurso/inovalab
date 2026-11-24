"""Trilha de auditoria: registra operações relevantes (append-only)."""
from __future__ import annotations

from ..common.util import agora, dumps, loads, novo_id
from ..db import Database
from ..identidade.service import Contexto


def registrar(db: Database, ctx: Contexto | None, acao: str, entidade: str | None = None,
              entidade_id: str | None = None, detalhes: dict | None = None) -> None:
    db.conn().execute(
        "INSERT INTO auditoria(id,em,usuario_id,org_id,acao,entidade,entidade_id,detalhes) VALUES (?,?,?,?,?,?,?,?)",
        (novo_id(), agora(), ctx.usuario_id if ctx else None, ctx.org_id if ctx else None, acao, entidade,
         entidade_id, dumps(detalhes or {})),
    )


def listar(db: Database, ctx: Contexto, limite: int = 100) -> list[dict]:
    """Cada órgão enxerga apenas a própria trilha."""
    rs = db.conn().execute(
        "SELECT a.em, a.acao, a.entidade, a.entidade_id, a.detalhes, u.login FROM auditoria a "
        "LEFT JOIN usuario u ON u.id=a.usuario_id WHERE a.org_id=? ORDER BY a.em DESC, a.id DESC LIMIT ?",
        (ctx.org_id, limite),
    )
    out = []
    for r in rs:
        d = dict(r)
        d["detalhes"] = loads(d["detalhes"], {})
        out.append(d)
    return out
