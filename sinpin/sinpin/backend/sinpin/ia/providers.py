"""Camada de abstração de modelos de linguagem.

Três implementações:
 - `Extrativo`: sem LLM. Não gera texto; o orquestrador monta a resposta a partir de trechos literais.
   Funciona offline e é o padrão quando não há chave configurada.
 - `Anthropic`: API Messages (POST https://api.anthropic.com/v1/messages).
 - `OpenAICompat`: qualquer servidor compatível com /chat/completions (Ollama, vLLM, LM Studio...),
   útil para executar modelos LOCAIS com documentos sensíveis.

As duas últimas usam apenas `requests` e NÃO foram exercitadas contra os serviços reais no ambiente de
desenvolvimento (sem rede/chave): valide com uma chamada real antes da demonstração.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..common.erros import ErroNegocio
from ..config import Settings


@dataclass
class ResultadoLLM:
    texto: str
    provider: str
    modelo: str
    uso: dict | None = None


class LLMProvider(Protocol):
    nome: str
    modelo: str
    generativo: bool

    def gerar(self, system: str, user: str, max_tokens: int = 2000) -> ResultadoLLM: ...


class Extrativo:
    nome, modelo, generativo = "extrativo", "nenhum", False

    def gerar(self, system: str, user: str, max_tokens: int = 2000) -> ResultadoLLM:  # pragma: no cover
        raise RuntimeError("Provider extrativo não gera texto.")


class Anthropic:
    nome, generativo = "anthropic", True
    URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key: str, modelo: str):
        self.api_key, self.modelo = api_key, modelo

    def gerar(self, system: str, user: str, max_tokens: int = 2000) -> ResultadoLLM:
        import requests
        try:
            r = requests.post(
                self.URL,
                headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": self.modelo, "max_tokens": max_tokens, "system": system,
                      "messages": [{"role": "user", "content": user}]},
                timeout=120)
        except requests.RequestException as e:
            raise ErroNegocio(502, "llm_indisponivel", f"Falha ao contatar o provedor de IA: {e}")
        if r.status_code != 200:
            raise ErroNegocio(502, "llm_erro", f"Provedor de IA retornou {r.status_code}: {r.text[:300]}")
        d = r.json()
        texto = "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
        return ResultadoLLM(texto, self.nome, d.get("model", self.modelo), d.get("usage"))


class OpenAICompat:
    nome, generativo = "openai_compat", True

    def __init__(self, base_url: str, api_key: str, modelo: str):
        self.base_url, self.api_key, self.modelo = base_url.rstrip("/"), api_key, modelo

    def gerar(self, system: str, user: str, max_tokens: int = 2000) -> ResultadoLLM:
        import requests
        headers = {"content-type": "application/json"}
        if self.api_key:
            headers["authorization"] = f"Bearer {self.api_key}"
        try:
            r = requests.post(f"{self.base_url}/chat/completions", headers=headers, timeout=300, json={
                "model": self.modelo, "max_tokens": max_tokens,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
        except requests.RequestException as e:
            raise ErroNegocio(502, "llm_indisponivel", f"Falha ao contatar o provedor de IA: {e}")
        if r.status_code != 200:
            raise ErroNegocio(502, "llm_erro", f"Provedor de IA retornou {r.status_code}: {r.text[:300]}")
        d = r.json()
        return ResultadoLLM(d["choices"][0]["message"]["content"], self.nome, d.get("model", self.modelo), d.get("usage"))


def criar_provider(st: Settings) -> LLMProvider:
    if st.llm_provider == "anthropic" and st.anthropic_api_key:
        return Anthropic(st.anthropic_api_key, st.llm_model)
    if st.llm_provider == "openai_compat" and st.openai_base_url:
        return OpenAICompat(st.openai_base_url, st.openai_api_key, st.llm_model)
    return Extrativo()
