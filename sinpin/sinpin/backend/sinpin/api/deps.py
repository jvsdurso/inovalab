"""Dependências injetadas nas rotas (container, contexto institucional, datas)."""
from __future__ import annotations

from fastapi import Depends, Header, Request

from ..common.erros import ErroNegocio, invalido
from ..common.util import hoje, valida_data
from ..container import Container
from ..identidade import service as ident


def get_c(request: Request) -> Container:
    return request.app.state.c


def get_ctx(c: Container = Depends(get_c), x_dev_user: str | None = Header(default=None)) -> ident.Contexto:
    """Contexto do usuário. Modo "dev": cabeçalho X-Dev-User (SOMENTE desenvolvimento). OIDC/gov.br: ponto de troca."""
    if c.settings.auth_mode == "dev":
        ctx = ident.contexto_por_login(c.db, x_dev_user) if x_dev_user else None
        if not ctx:
            raise ErroNegocio(401, "nao_autenticado", "Usuário de desenvolvimento não informado ou desconhecido (cabeçalho X-Dev-User).")
        return ctx
    raise ErroNegocio(501, "auth_nao_implementada", "Autenticação OIDC (Keycloak/gov.br) ainda não implementada.")


def data_ou_hoje(valor: str | None, nome: str = "data") -> str:
    if valor and not valida_data(valor):
        raise invalido(f"{nome} deve estar no formato AAAA-MM-DD.")
    return valor or hoje()
