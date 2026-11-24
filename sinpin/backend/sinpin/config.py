"""Configuração do SINPIN, lida de variáveis de ambiente (prefixo SINPIN_)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]  # raiz do repositório


@dataclass(frozen=True)
class Settings:
    # Banco principal: PostgreSQL. SQLite só para testes/offline (sqlite:///caminho.db ou, sem URL, db_path).
    database_url: str = ""
    db_path: str = str(RAIZ / "data" / "sinpin.db")
    storage_dir: str = str(RAIZ / "data" / "arquivos")
    # origens permitidas por CORS (o frontend Next.js normalmente usa proxy e nem precisa)
    cors_origens: tuple[str, ...] = ("http://localhost:3000", "http://127.0.0.1:3000")
    # Embeddings (pgvector): vazio = busca apenas lexical. Endpoint compatível com OpenAI (/embeddings): Ollama, vLLM, OpenAI…
    embedding_base_url: str = ""
    embedding_model: str = ""
    embedding_api_key: str = ""
    embedding_dim: int = 768
    embedding_sim_min: float = 0.45   # similaridade mínima (cosseno) para um trecho entrar só pelo vetor; ajuste ao modelo
    # "dev": identidade por cabeçalho X-Dev-User (SOMENTE desenvolvimento/hackathon).
    # "oidc": reservado para gov.br/Keycloak (ainda não implementado).
    auth_mode: str = "dev"
    # "extrativo" (sem LLM, offline), "anthropic" ou "openai_compat" (Ollama/vLLM etc.)
    llm_provider: str = "extrativo"
    llm_model: str = "claude-sonnet-5-5"
    anthropic_api_key: str = ""
    openai_base_url: str = ""
    openai_api_key: str = ""
    # Relações detectadas com confiança >= limiar são confirmadas automaticamente
    # (e continuam auditáveis/reversíveis). Abaixo disso, aguardam validação humana.
    limiar_auto_confirmacao: float = 0.8
    seed_demo: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        e = os.environ.get
        ak = e("ANTHROPIC_API_KEY", e("SINPIN_ANTHROPIC_API_KEY", ""))
        base = e("SINPIN_OPENAI_BASE_URL", "")
        provider = e("SINPIN_LLM_PROVIDER", "")
        if not provider:
            provider = "anthropic" if ak else ("openai_compat" if base else "extrativo")
        d = cls()
        return cls(
            database_url=e("SINPIN_DATABASE_URL", "postgresql://sinpin:sinpin@localhost:5432/sinpin"),
            db_path=e("SINPIN_DB_PATH", d.db_path),
            storage_dir=e("SINPIN_STORAGE_DIR", d.storage_dir),
            cors_origens=tuple(o.strip() for o in e("SINPIN_CORS_ORIGINS", ",".join(d.cors_origens)).split(",") if o.strip()),
            embedding_base_url=e("SINPIN_EMBEDDING_BASE_URL", base),
            embedding_model=e("SINPIN_EMBEDDING_MODEL", ""),
            embedding_api_key=e("SINPIN_EMBEDDING_API_KEY", e("SINPIN_OPENAI_API_KEY", "")),
            embedding_dim=int(e("SINPIN_EMBEDDING_DIM", d.embedding_dim)),
            embedding_sim_min=float(e("SINPIN_EMBEDDING_SIM_MIN", d.embedding_sim_min)),
            auth_mode=e("SINPIN_AUTH_MODE", d.auth_mode),
            llm_provider=provider,
            llm_model=e("SINPIN_LLM_MODEL", d.llm_model),
            anthropic_api_key=ak,
            openai_base_url=base,
            openai_api_key=e("SINPIN_OPENAI_API_KEY", ""),
            limiar_auto_confirmacao=float(e("SINPIN_LIMIAR_AUTO", d.limiar_auto_confirmacao)),
            seed_demo=e("SINPIN_SEED_DEMO", "0") == "1",
        )
