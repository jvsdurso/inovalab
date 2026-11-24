"""Busca vetorial (pgvector) e fusão com a lexical (BM25).

 - A PERMISSÃO é aplicada na própria consulta SQL (`sql_visivel`): o que o usuário não pode ver nunca é recuperado.
 - Sem provedor de embeddings ou fora do PostgreSQL, tudo isto é ignorado e a busca segue lexical.
"""
from __future__ import annotations

import logging
from typing import Callable

from ..common.util import rows
from ..db import Database
from ..identidade.service import Contexto, sql_visivel
from ..ia.embeddings import Embeddings
from ..normativo.caminhos import rotulo_de_caminho

log = logging.getLogger("sinpin.vetorial")
Semelhanca = Callable[[Database, Contexto, str], dict[str, float]]  # consulta -> {redacao_id: similaridade 0..1}
MAX_CHARS = 2000


def _vetor(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.7g}" for x in v) + "]"


def indexar_pendentes(db: Database, emb: Embeddings | None, lote: int = 32, maximo: int = 5000) -> int:
    """Gera embeddings das redações vigentes para o sistema que ainda não têm. Devolve quantas indexou."""
    if emb is None or not db.suporta_vetor:
        return 0
    total = 0
    while total < maximo:
        rs = rows(db.conn().execute(
            "SELECT r.id, r.texto, p.caminho, d.titulo FROM redacao r JOIN dispositivo p ON p.id=r.dispositivo_id "
            "JOIN documento d ON d.id=p.documento_id WHERE r.embedding IS NULL AND r.registrado_ate IS NULL LIMIT ?", (lote,)))
        if not rs:
            break
        textos = [f'{r["titulo"]} {rotulo_de_caminho(r["caminho"])}. {r["texto"]}'[:MAX_CHARS] for r in rs]
        vetores = emb.embed(textos)
        with db.tx():
            for r, v in zip(rs, vetores):
                db.conn().execute("UPDATE redacao SET embedding=?::vector WHERE id=?", (_vetor(v), r["id"]))
        total += len(rs)
    return total


def indexar_sem_falhar(db: Database, emb: Embeddings | None) -> int:
    """Uso pós-escrita: a indexação vetorial NUNCA derruba a operação principal (a busca lexical continua funcionando)."""
    try:
        return indexar_pendentes(db, emb)
    except Exception as e:  # noqa: BLE001
        log.warning("Indexação vetorial falhou (a busca lexical segue ativa): %s", e)
        return 0


def criar_buscador(emb: Embeddings | None, limite: int = 60) -> Semelhanca | None:
    if emb is None:
        return None

    def semelhanca(db: Database, ctx: Contexto, consulta: str) -> dict[str, float]:
        if not db.suporta_vetor:
            return {}
        try:
            v = _vetor(emb.embed([consulta[:MAX_CHARS]])[0])
        except Exception as e:  # noqa: BLE001
            log.warning("Embedding da consulta falhou (busca só lexical): %s", e)
            return {}
        vis, params = sql_visivel(ctx, "d")
        rs = db.conn().execute(
            "SELECT r.id AS redacao_id, 1 - (r.embedding <=> ?::vector) AS sim FROM redacao r "
            "JOIN dispositivo p ON p.id=r.dispositivo_id JOIN documento d ON d.id=p.documento_id "
            f"WHERE r.registrado_ate IS NULL AND r.embedding IS NOT NULL AND {vis} "
            "ORDER BY r.embedding <=> ?::vector LIMIT ?", (v, *params, v, limite))
        return {r["redacao_id"]: float(r["sim"]) for r in rs}

    return semelhanca


def fundir(redacao_ids: list[str], bm25: list[float], sims: dict[str, float], sim_min: float = 0.45,
           peso_lexical: float = 0.6) -> list[float]:
    """Combina BM25 (normalizado pelo maior valor) com a similaridade vetorial (>= sim_min). Alinhado a `redacao_ids`."""
    topo = max(bm25, default=0.0)
    out = []
    for rid, b in zip(redacao_ids, bm25):
        lex = (b / topo) if topo > 0 else 0.0
        s = sims.get(rid, 0.0)
        vet = s if s >= sim_min else 0.0
        out.append(peso_lexical * lex + (1 - peso_lexical) * vet)
    return out
