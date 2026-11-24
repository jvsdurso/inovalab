"""Histórico de conversas do COMPREENDER. Conversa = sequência de consultas INDEPENDENTES (cada pergunta refaz a pesquisa);
não há memória de contexto entre perguntas. Privada ao usuário: nem o mesmo órgão enxerga conversas alheias."""
from __future__ import annotations

from ..auditoria import service as auditoria
from ..common.erros import nao_encontrado
from ..common.util import agora, dumps, loads, novo_id, row, rows
from ..db import Database
from ..identidade.service import Contexto

TITULO_MAX = 80


def _titulo(pergunta: str) -> str:
    t = " ".join(pergunta.split())
    return t if len(t) <= TITULO_MAX else t[: TITULO_MAX - 1].rstrip() + "…"


def _propria(db: Database, ctx: Contexto, conversa_id: str) -> dict:
    r = row(db.conn().execute("SELECT * FROM conversa WHERE id=?", (conversa_id,)).fetchone())
    if not r or r["usuario_id"] != ctx.usuario_id:  # inexistente e alheia são indistinguíveis (404)
        raise nao_encontrado("Conversa")
    return r


def validar_posse(db: Database, ctx: Contexto, conversa_id: str) -> None:
    _propria(db, ctx, conversa_id)


def listar(db: Database, ctx: Contexto, limite: int = 100) -> list[dict]:
    return rows(db.conn().execute(
        "SELECT c.id, c.titulo, c.criado_em, c.atualizado_em, "
        "(SELECT COUNT(*) FROM conversa_mensagem m WHERE m.conversa_id=c.id AND m.papel='usuario') AS n_perguntas "
        "FROM conversa c WHERE c.usuario_id=? ORDER BY c.atualizado_em DESC, c.id DESC LIMIT ?",
        (ctx.usuario_id, limite)))


def obter(db: Database, ctx: Contexto, conversa_id: str) -> dict:
    c = _propria(db, ctx, conversa_id)
    ms = rows(db.conn().execute(
        "SELECT id, ordem, papel, conteudo, criado_em FROM conversa_mensagem WHERE conversa_id=? ORDER BY ordem",
        (conversa_id,)))
    for m in ms:
        m["conteudo"] = loads(m["conteudo"], {})
    return {"id": c["id"], "titulo": c["titulo"], "criado_em": c["criado_em"], "atualizado_em": c["atualizado_em"], "mensagens": ms}


def registrar_troca(db: Database, ctx: Contexto, conversa_id: str | None, pergunta: str, data: str, resposta: dict) -> str:
    """Grava pergunta + resposta (snapshot). Sem `conversa_id`, abre uma conversa nova. Devolve o id da conversa."""
    with db.tx() as c:
        agora_ = agora()
        if conversa_id is None:
            conversa_id = novo_id()
            c.execute("INSERT INTO conversa(id,usuario_id,org_id,titulo,criado_em,atualizado_em) VALUES (?,?,?,?,?,?)",
                      (conversa_id, ctx.usuario_id, ctx.org_id, _titulo(pergunta), agora_, agora_))
            prox = 1
        else:
            _propria(db, ctx, conversa_id)
            r = c.execute("SELECT COALESCE(MAX(ordem),0) AS m FROM conversa_mensagem WHERE conversa_id=?", (conversa_id,)).fetchone()
            prox = int(r["m"]) + 1
            c.execute("UPDATE conversa SET atualizado_em=? WHERE id=?", (agora_, conversa_id))
        c.execute("INSERT INTO conversa_mensagem(id,conversa_id,ordem,papel,conteudo,criado_em) VALUES (?,?,?,?,?,?)",
                  (novo_id(), conversa_id, prox, "usuario", dumps({"texto": pergunta, "data": data}), agora_))
        c.execute("INSERT INTO conversa_mensagem(id,conversa_id,ordem,papel,conteudo,criado_em) VALUES (?,?,?,?,?,?)",
                  (novo_id(), conversa_id, prox + 1, "assistente", dumps(resposta), agora_))
    return conversa_id


def renomear(db: Database, ctx: Contexto, conversa_id: str, titulo: str) -> dict:
    _propria(db, ctx, conversa_id)
    titulo = " ".join(titulo.split())[:TITULO_MAX]
    if not titulo:
        titulo = "Conversa"
    db.conn().execute("UPDATE conversa SET titulo=? WHERE id=?", (titulo, conversa_id))
    return {"id": conversa_id, "titulo": titulo}


def excluir(db: Database, ctx: Contexto, conversa_id: str) -> None:
    _propria(db, ctx, conversa_id)
    with db.tx() as c:
        c.execute("DELETE FROM conversa_mensagem WHERE conversa_id=?", (conversa_id,))
        c.execute("DELETE FROM conversa WHERE id=?", (conversa_id,))
    auditoria.registrar(db, ctx, "CONVERSA_EXCLUIDA", "conversa", conversa_id, {})
