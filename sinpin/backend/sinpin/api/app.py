"""API HTTP (v1) em FastAPI. Rotas finas: validam a entrada e delegam aos serviços de domínio.

Os serviços são síncronos; as rotas são `def` (o FastAPI as executa em thread pool). Documentação interativa em /docs.
Execução:  uvicorn sinpin.api.app:create_app --factory   (ou  python -m sinpin)
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .. import __version__
from ..common.erros import ErroNegocio, nao_encontrado
from ..config import Settings
from ..container import Container, criar_container
from ..identidade import service as ident
from ..orgaos import service as orgaos
from .deps import get_c, get_ctx
from .rotas import compreender, conhecer, produzir

log = logging.getLogger("sinpin")
P = "/api/v1"


async def _erro_negocio(request: Request, exc: ErroNegocio):
    return JSONResponse(exc.como_dict(), status_code=exc.status)


async def _erro_validacao(request: Request, exc: RequestValidationError):
    detalhes = [{"campo": ".".join(str(x) for x in e["loc"] if x not in ("body", "query", "path")), "erro": e["msg"]} for e in exc.errors()]
    return JSONResponse({"erro": {"codigo": "invalido", "mensagem": "Dados inválidos.", "detalhes": detalhes}}, status_code=422)


async def _erro_interno(request: Request, exc: Exception):
    log.exception("erro não tratado", exc_info=exc)
    return JSONResponse({"erro": {"codigo": "interno", "mensagem": "Erro interno. Consulte os logs do servidor."}}, status_code=500)


geral = APIRouter(tags=["Geral"])


@geral.get("/saude")
def saude(c: Container = Depends(get_c)):
    return {"status": "ok", "versao": __version__, "banco": c.db.dialeto}


@geral.get("/dev/usuarios")
def dev_usuarios(c: Container = Depends(get_c)):
    if c.settings.auth_mode != "dev":
        raise nao_encontrado()
    return {"usuarios": ident.listar_usuarios_dev(c.db)}


@geral.get("/me")
def me(c: Container = Depends(get_c), ctx: ident.Contexto = Depends(get_ctx)):
    return {"login": ctx.login, "nome": ctx.nome, "perfil": ctx.perfil, "orgao": orgaos.obter(c.db, ctx.org_id),
            "auth_mode": c.settings.auth_mode,
            "llm": {"provider": c.llm.nome, "modelo": c.llm.modelo, "generativo": c.llm.generativo},
            "busca": {"vetorial": c.embeddings is not None and c.db.suporta_vetor,
                      "modelo_embeddings": c.embeddings.modelo if c.embeddings else None}}


def create_app(settings: Settings | None = None) -> FastAPI:
    c = criar_container(settings)
    app = FastAPI(title="SINPIN API", version=__version__,
                  description="Sistema Nacional de Pesquisa e Inteligência Normativa — CONHECER · COMPREENDER · PRODUZIR. "
                              "Autenticação de desenvolvimento: cabeçalho X-Dev-User (gov.br/OIDC ainda não integrado).")
    app.state.c = c
    app.add_middleware(CORSMiddleware, allow_origins=list(c.settings.cors_origens), allow_methods=["*"], allow_headers=["*"],
                       expose_headers=["content-disposition"])
    app.add_exception_handler(ErroNegocio, _erro_negocio)
    app.add_exception_handler(RequestValidationError, _erro_validacao)
    app.add_exception_handler(Exception, _erro_interno)
    for r in (geral, conhecer.router, compreender.router, produzir.router):
        app.include_router(r, prefix=P)
    return app
