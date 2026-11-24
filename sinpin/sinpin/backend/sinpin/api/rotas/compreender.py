"""Pilar COMPREENDER: pesquisa fundamentada (BM25 + pgvector) com citações verificáveis e vigência na data."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ...auditoria import service as auditoria
from ...container import Container
from ...ia import orquestrador
from ...identidade.service import Contexto
from ...pesquisa import service as pesquisa
from ..deps import data_ou_hoje, get_c, get_ctx
from ..schemas import PesquisaIn

router = APIRouter(tags=["COMPREENDER"])


@router.post("/pesquisa")
def pesquisar(d: PesquisaIn, c: Container = Depends(get_c), ctx: Contexto = Depends(get_ctx)):
    data = data_ou_hoje(d.data)
    busca = pesquisa.buscar(c.db, ctx, d.pergunta, data, d.k, semelhanca=c.semelhanca, sim_min=c.settings.embedding_sim_min)
    resp = orquestrador.responder(c.db, c.llm, ctx, d.pergunta, data, busca)
    auditoria.registrar(c.db, ctx, "PESQUISA", "ia_execucao", resp["execucao_id"],
                        {"pergunta": d.pergunta[:300], "data": data, "fontes": len(busca["fontes"])})
    return {"pergunta": d.pergunta, "data": data, **resp, "fontes": busca["fontes"], "alertas": busca["alertas"]}
