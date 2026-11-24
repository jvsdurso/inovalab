"""Pilar COMPREENDER: pesquisa fundamentada (BM25 + pgvector) com citações verificáveis e vigência na data."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ...auditoria import service as auditoria
from ...conversas import service as conversas
from ...container import Container
from ...ia import orquestrador
from ...identidade.service import Contexto
from ...pesquisa import service as pesquisa
from ..deps import data_ou_hoje, get_c, get_ctx
from ..schemas import ConversaRenomearIn, PesquisaIn

router = APIRouter(tags=["COMPREENDER"])


@router.post("/pesquisa")
def pesquisar(d: PesquisaIn, c: Container = Depends(get_c), ctx: Contexto = Depends(get_ctx)):
    data = data_ou_hoje(d.data)
    if d.conversa_id:
        conversas.validar_posse(c.db, ctx, d.conversa_id)  # falha ANTES de gastar a pesquisa/LLM
    busca = pesquisa.buscar(c.db, ctx, d.pergunta, data, d.k, semelhanca=c.semelhanca, sim_min=c.settings.embedding_sim_min)
    resp = orquestrador.responder(c.db, c.llm, ctx, d.pergunta, data, busca)
    auditoria.registrar(c.db, ctx, "PESQUISA", "ia_execucao", resp["execucao_id"],
                        {"pergunta": d.pergunta[:300], "data": data, "fontes": len(busca["fontes"])})
    saida = {"pergunta": d.pergunta, "data": data, **resp, "fontes": busca["fontes"], "alertas": busca["alertas"]}
    saida["conversa_id"] = conversas.registrar_troca(c.db, ctx, d.conversa_id, d.pergunta, data, saida)
    return saida


@router.get("/conversas")
def listar_conversas(c: Container = Depends(get_c), ctx: Contexto = Depends(get_ctx)):
    return {"conversas": conversas.listar(c.db, ctx)}


@router.get("/conversas/{conversa_id}")
def obter_conversa(conversa_id: str, c: Container = Depends(get_c), ctx: Contexto = Depends(get_ctx)):
    return conversas.obter(c.db, ctx, conversa_id)


@router.put("/conversas/{conversa_id}")
def renomear_conversa(conversa_id: str, d: ConversaRenomearIn, c: Container = Depends(get_c), ctx: Contexto = Depends(get_ctx)):
    return conversas.renomear(c.db, ctx, conversa_id, d.titulo)


@router.delete("/conversas/{conversa_id}", status_code=204)
def excluir_conversa(conversa_id: str, c: Container = Depends(get_c), ctx: Contexto = Depends(get_ctx)):
    conversas.excluir(c.db, ctx, conversa_id)
