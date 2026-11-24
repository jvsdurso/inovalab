"""Pilar CONHECER: biblioteca, versões, relações, grafo, catálogo do acervo, fontes, auditoria."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Response, UploadFile

from ...auditoria import service as auditoria
from ...catalogo import lote as catalogo_lote, service as catalogo
from ...common.erros import invalido, nao_encontrado
from ...container import Container
from ...grafo import service as grafo
from ...identidade.service import Contexto
from ...ingestao import service as ingestao
from ...normativo import repo, service as normativo
from ...orgaos import service as orgaos
from ..deps import data_ou_hoje, get_c, get_ctx
from ..schemas import CatalogoIn, CompartilharIn, ValidacaoDocumentoIn, ValidarRelacaoIn

router = APIRouter(tags=["CONHECER"])


@router.get("/orgaos")
def listar_orgaos(c: Container = Depends(get_c), ctx: Contexto = Depends(get_ctx)):
    return {"orgaos": orgaos.listar(c.db)}


# ------------------------------------------------------------------ documentos
@router.get("/documentos")
def listar_documentos(q: str | None = None, tipo: str | None = None, escopo: str | None = None,
                      c: Container = Depends(get_c), ctx: Contexto = Depends(get_ctx)):
    return {"documentos": normativo.listar_documentos(c.db, ctx, q, tipo, escopo)}


@router.post("/documentos", status_code=201)
def importar_documento(
        response: Response, tarefas: BackgroundTasks,
        arquivo: UploadFile | None = File(default=None), texto: str | None = Form(default=None),
        escopo: str = Form(default="INSTITUCIONAL_RESTRITO"),
        fonte_url: str | None = Form(default=None), url_origem: str | None = Form(default=None),
        url_publicacao_dou: str | None = Form(default=None), data_assinatura: str | None = Form(default=None),
        status_validacao: str | None = Form(default=None),
        tipo: str | None = Form(default=None), numero: str | None = Form(default=None), ano: str | None = Form(default=None),
        titulo: str | None = Form(default=None), data_publicacao: str | None = Form(default=None),
        vigencia_inicio: str | None = Form(default=None), orgao_emissor: str | None = Form(default=None),
        c: Container = Depends(get_c), ctx: Contexto = Depends(get_ctx)):
    conteudo = arquivo.file.read() if arquivo is not None and arquivo.filename else None
    nome = arquivo.filename if conteudo else None
    sobrescritas = {k: v for k, v in dict(tipo=tipo, numero=numero, ano=ano, titulo=titulo, data_publicacao=data_publicacao,
                                          vigencia_inicio=vigencia_inicio, orgao_emissor=orgao_emissor).items() if v}
    origem = {k: v for k, v in dict(url_origem=url_origem, url_publicacao_dou=url_publicacao_dou,
                                    data_assinatura=data_assinatura, status_validacao=status_validacao).items() if v}
    res = ingestao.ingerir(c.db, c.settings, c.armazenamento, ctx, nome_arquivo=nome, conteudo=conteudo or None, texto=texto,
                           escopo=escopo, fonte_url=fonte_url or None, sintetico=False, sobrescritas=sobrescritas, origem=origem)
    if res.get("duplicado"):
        response.status_code = 200
    else:
        tarefas.add_task(c.indexar)   # embeddings (pgvector) em segundo plano
    return res


@router.get("/documentos/{doc_id}")
def obter_documento(doc_id: str, data: str | None = None, c: Container = Depends(get_c), ctx: Contexto = Depends(get_ctx)):
    doc = normativo.obter_documento_visivel(c.db, ctx, doc_id)
    comp = normativo.compilado(c.db, ctx, doc_id, data_ou_hoje(data))
    rels = grafo.listar(c.db, ctx, documento_id=doc_id)
    org = orgaos.obter(c.db, doc["org_id"])
    doc["orgao"] = org["sigla"] if org else None
    doc["versoes"] = repo.listar_versoes(c.db, doc_id)
    doc["situacao"] = comp["situacao"]
    return {"documento": doc, "compilado": comp, "relacoes": rels}


@router.post("/documentos/{doc_id}/compartilhar")
def compartilhar_documento(doc_id: str, d: CompartilharIn, c: Container = Depends(get_c), ctx: Contexto = Depends(get_ctx)):
    return ingestao.compartilhar(c.db, ctx, doc_id, d.org_ids)


@router.post("/documentos/{doc_id}/validacao")
def validar_documento(doc_id: str, d: ValidacaoDocumentoIn, c: Container = Depends(get_c), ctx: Contexto = Depends(get_ctx)):
    return ingestao.definir_validacao(c.db, ctx, doc_id, d.status.upper(), d.motivo)


@router.get("/dispositivos/{disp_id}/historico")
def historico_dispositivo(disp_id: str, c: Container = Depends(get_c), ctx: Contexto = Depends(get_ctx)):
    return normativo.historico_dispositivo(c.db, ctx, disp_id)


# ------------------------------------------------------------------ relações e grafo
@router.get("/relacoes")
def listar_relacoes(status: str | None = None, documento_id: str | None = None,
                    c: Container = Depends(get_c), ctx: Contexto = Depends(get_ctx)):
    return {"relacoes": grafo.listar(c.db, ctx, status, documento_id)}


@router.post("/relacoes/{rel_id}/validar")
def validar_relacao(rel_id: str, d: ValidarRelacaoIn, tarefas: BackgroundTasks,
                    c: Container = Depends(get_c), ctx: Contexto = Depends(get_ctx)):
    r = grafo.validar(c.db, ctx, rel_id, d.acao.upper(), d.motivo, d.data_efeito, d.texto_novo, d.destino_documento_id)
    tarefas.add_task(c.indexar)   # a validação pode criar novas redações (alterações)
    return {"relacao": r, "historico": grafo.historico(c.db, ctx, rel_id)}


@router.get("/relacoes/{rel_id}/historico")
def historico_relacao(rel_id: str, c: Container = Depends(get_c), ctx: Contexto = Depends(get_ctx)):
    return {"historico": grafo.historico(c.db, ctx, rel_id)}


@router.get("/grafo")
def obter_grafo(c: Container = Depends(get_c), ctx: Contexto = Depends(get_ctx)):
    return grafo.grafo(c.db, ctx)


# ------------------------------------------------------------------ catálogo do acervo
@router.get("/fontes")
def listar_fontes(c: Container = Depends(get_c), ctx: Contexto = Depends(get_ctx)):
    return {"fontes": catalogo.listar_fontes(c.db)}


@router.get("/catalogo")
def listar_catalogo(status_obtencao: str | None = None, q: str | None = None,
                    c: Container = Depends(get_c), ctx: Contexto = Depends(get_ctx)):
    return {"itens": catalogo.listar(c.db, ctx, status_obtencao, q)}


@router.get("/catalogo/relatorio")
def relatorio_catalogo(c: Container = Depends(get_c), ctx: Contexto = Depends(get_ctx)):
    return catalogo.relatorio(c.db, ctx)


@router.post("/catalogo/itens", status_code=201)
def registrar_itens(d: CatalogoIn, response: Response, c: Container = Depends(get_c), ctx: Contexto = Depends(get_ctx)):
    from ...common.erros import ErroNegocio
    ok, erros = [], []
    for n, it in enumerate(d.itens, 1):
        try:
            ok.append(catalogo.registrar_item(c.db, ctx, it))
        except ErroNegocio as e:
            if e.status == 403:
                raise
            erros.append({"item": n, "erro": e.mensagem})
    if not ok:
        response.status_code = 422
    return {"registrados": len(ok), "itens": ok, "erros": erros}


@router.post("/catalogo/importar")
def importar_lote(tarefas: BackgroundTasks, pacote: UploadFile | None = File(default=None),
                  c: Container = Depends(get_c), ctx: Contexto = Depends(get_ctx)):
    dados = pacote.file.read() if pacote is not None else b""
    if not dados:
        raise invalido("Envie o pacote .zip no campo 'pacote'.")
    res = catalogo_lote.importar_zip(c.db, c.settings, c.armazenamento, ctx, dados)
    tarefas.add_task(c.indexar)
    return res


# ------------------------------------------------------------------ auditoria
@router.get("/auditoria")
def listar_auditoria(c: Container = Depends(get_c), ctx: Contexto = Depends(get_ctx)):
    return {"eventos": auditoria.listar(c.db, ctx)}
