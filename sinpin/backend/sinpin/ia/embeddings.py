"""Provedores de embeddings (camada de abstração, como a de LLM). Sem provedor configurado, a busca é só lexical.

Os textos enviados ao provedor incluem normas de escopo institucional restrito: para esse conteúdo, prefira um modelo
LOCAL (Ollama/vLLM) a um serviço externo.
"""
from __future__ import annotations

from typing import Protocol

import requests

from ..config import Settings


class ErroEmbedding(RuntimeError):
    pass


class Embeddings(Protocol):
    nome: str
    modelo: str
    dim: int

    def embed(self, textos: list[str]) -> list[list[float]]: ...


class OpenAICompatEmbeddings:
    """POST {base_url}/embeddings — compatível com Ollama (…/v1), vLLM, OpenAI e similares."""
    nome = "openai_compat"

    def __init__(self, base_url: str, modelo: str, api_key: str = "", dim: int = 768, timeout: int = 60):
        self.base_url, self.modelo, self.api_key, self.dim, self.timeout = base_url.rstrip("/"), modelo, api_key, dim, timeout

    def embed(self, textos: list[str]) -> list[list[float]]:
        if not textos:
            return []
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        try:
            r = requests.post(f"{self.base_url}/embeddings", headers=h, json={"model": self.modelo, "input": textos}, timeout=self.timeout)
            r.raise_for_status()
            dados = sorted(r.json()["data"], key=lambda d: d.get("index", 0))
            vetores = [[float(x) for x in d["embedding"]] for d in dados]
        except (requests.RequestException, KeyError, ValueError, TypeError) as e:
            raise ErroEmbedding(f"Falha ao obter embeddings de {self.base_url}: {e}") from e
        if len(vetores) != len(textos):
            raise ErroEmbedding("O provedor devolveu quantidade de vetores diferente da enviada.")
        if any(len(v) != self.dim for v in vetores):
            raise ErroEmbedding(f"Dimensão dos embeddings ({len(vetores[0])}) difere de SINPIN_EMBEDDING_DIM/coluna vector({self.dim}).")
        return vetores


def criar_embeddings(st: Settings) -> Embeddings | None:
    if st.embedding_base_url and st.embedding_model:
        return OpenAICompatEmbeddings(st.embedding_base_url, st.embedding_model, st.embedding_api_key, st.embedding_dim)
    return None
