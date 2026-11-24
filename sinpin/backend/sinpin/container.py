"""Composição das dependências (raiz de composição). Trocar banco/LLM/armazenamento = mudar aqui."""
from __future__ import annotations

import threading
from dataclasses import dataclass, field

from .common.armazenamento import Armazenamento, ArmazenamentoLocal
from .config import Settings
from .db import Database, criar_database
from .ia.embeddings import Embeddings, criar_embeddings
from .ia.providers import LLMProvider, criar_provider
from .pesquisa import vetorial
from .catalogo import service as catalogo
from .identidade import service as ident
from .orgaos import service as orgaos
from .seed import demo


@dataclass
class Container:
    settings: Settings
    db: Database
    armazenamento: Armazenamento
    llm: LLMProvider
    embeddings: Embeddings | None = None
    semelhanca: vetorial.Semelhanca | None = None
    _trava: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def indexar(self) -> int:
        """Indexa (pgvector) o que ainda não foi indexado; nunca levanta erro."""
        if not self._trava.acquire(blocking=False):   # já há uma indexação em andamento
            return 0
        try:
            return vetorial.indexar_sem_falhar(self.db, self.embeddings)
        finally:
            self._trava.release()


def criar_container(settings: Settings | None = None) -> Container:
    st = settings or Settings.from_env()
    db = criar_database(st.database_url or None, st.db_path)
    db.migrate()
    if st.auth_mode == "dev":
        orgaos.semear_dev(db)
    catalogo.semear_fontes(db)  # fontes oficiais monitoradas (configuração do acervo, não dado de demonstração)
    emb = criar_embeddings(st)
    c = Container(st, db, ArmazenamentoLocal(st.storage_dir), criar_provider(st), emb, vetorial.criar_buscador(emb))
    if st.seed_demo:
        demo.semear(db, st, c.armazenamento)
        if st.auth_mode == "dev":  # referências preliminares do índice (sem texto): só na demonstração
            curador = ident.contexto_por_login(db, "curador")
            if curador:
                catalogo.semear_catalogo_inicial(db, curador)
        c.indexar()
    elif emb is not None:  # embeddings ligados depois de o acervo já existir: indexa o que falta, sem travar a subida
        threading.Thread(target=c.indexar, name="indexar-embeddings", daemon=True).start()
    return c
