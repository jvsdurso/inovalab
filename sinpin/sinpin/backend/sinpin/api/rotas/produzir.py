"""Pilar PRODUZIR: modelos, minutas assistidas e exportação DOCX/PDF."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from ...auditoria import service as auditoria
from ...common.erros import invalido
from ...container import Container
from ...identidade.service import Contexto
from ...orgaos import service as orgaos
from ...producao import exportacao, service as producao
from ..deps import data_ou_hoje, get_c, get_ctx
from ..schemas import MinutaEdicaoIn, MinutaIn

router = APIRouter(tags=["PRODUZIR"])


@router.get("/modelos")
def modelos(ctx: Contexto = Depends(get_ctx)):
    return {"tipos": producao.tipos_disponiveis()}


@router.post("/minutas", status_code=201)
def criar_minuta(d: MinutaIn, c: Container = Depends(get_c), ctx: Contexto = Depends(get_ctx)):
    if d.data:
        data_ou_hoje(d.data)
    return producao.gerar(c.db, c.llm, ctx, tipo=d.tipo, assunto=d.assunto, instrucoes=d.instrucoes, contexto=d.contexto,
                          data=d.data, pergunta=d.pergunta, fonte_ids=d.fonte_ids, titulo=d.titulo,
                          semelhanca=c.semelhanca, sim_min=c.settings.embedding_sim_min)


@router.get("/minutas")
def listar_minutas(c: Container = Depends(get_c), ctx: Contexto = Depends(get_ctx)):
    return {"minutas": producao.listar(c.db, ctx)}


@router.get("/minutas/{minuta_id}")
def obter_minuta(minuta_id: str, c: Container = Depends(get_c), ctx: Contexto = Depends(get_ctx)):
    return producao.obter(c.db, ctx, minuta_id)


@router.put("/minutas/{minuta_id}")
def editar_minuta(minuta_id: str, d: MinutaEdicaoIn, c: Container = Depends(get_c), ctx: Contexto = Depends(get_ctx)):
    return producao.atualizar(c.db, ctx, minuta_id, d.titulo,
                              [s.model_dump() for s in d.secoes] if d.secoes is not None else None, d.status)


@router.get("/minutas/{minuta_id}/exportar")
def exportar_minuta(minuta_id: str, formato: str = "docx", c: Container = Depends(get_c), ctx: Contexto = Depends(get_ctx)):
    m = producao.obter(c.db, ctx, minuta_id)
    fmt = formato.lower()
    org = orgaos.obter(c.db, ctx.org_id)["nome"]
    if fmt == "docx":
        dados, mime = exportacao.para_docx(m, org), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif fmt == "pdf":
        dados, mime = exportacao.para_pdf(m, org), "application/pdf"
    else:
        raise invalido("formato deve ser docx ou pdf.")
    auditoria.registrar(c.db, ctx, "MINUTA_EXPORTADA", "minuta", m["id"], {"formato": fmt})
    return Response(dados, media_type=mime, headers={"content-disposition": f'attachment; filename="minuta_{m["id"][:8]}.{fmt}"'})
