"""Modelos Pydantic de entrada da API."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PesquisaIn(BaseModel):
    pergunta: str = Field(min_length=3, max_length=2000)
    data: str | None = None
    k: int = Field(default=6, ge=1, le=15)
    conversa_id: str | None = None   # se informado, a troca é anexada a essa conversa; senão abre uma nova


class ValidarRelacaoIn(BaseModel):
    acao: str
    motivo: str | None = Field(default=None, max_length=1000)
    data_efeito: str | None = None
    texto_novo: str | None = None
    destino_documento_id: str | None = None


class CompartilharIn(BaseModel):
    org_ids: list[str] = []


class ValidacaoDocumentoIn(BaseModel):
    status: str
    motivo: str | None = Field(default=None, max_length=500)


class CatalogoIn(BaseModel):
    itens: list[dict[str, Any]] = Field(max_length=2000)


class MinutaIn(BaseModel):
    tipo: str
    assunto: str = Field(min_length=3, max_length=500)
    instrucoes: str = Field(default="", max_length=4000)
    contexto: str = Field(default="", max_length=8000)
    data: str | None = None
    pergunta: str | None = None
    fonte_ids: list[str] | None = None
    titulo: str | None = None


class SecaoIn(BaseModel):
    id: str
    texto: str


class MinutaEdicaoIn(BaseModel):
    titulo: str | None = None
    secoes: list[SecaoIn] | None = None
    status: str | None = None


class ConversaRenomearIn(BaseModel):
    titulo: str = Field(min_length=1, max_length=200)
