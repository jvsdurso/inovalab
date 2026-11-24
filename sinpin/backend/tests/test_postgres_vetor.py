"""Só roda contra PostgreSQL com pgvector (SINPIN_TEST_DATABASE_URL). Valida a indexação e a consulta vetorial reais,
com um provedor de embeddings FALSO e determinístico (hash de palavras -> vetor), sem depender de modelo."""
import hashlib
import math
import os

import pytest
from conftest import ctx_de, settings_teste

from sinpin.container import criar_container
from sinpin.pesquisa import service as pesquisa, vetorial

pytestmark = pytest.mark.skipif(not os.environ.get("SINPIN_TEST_DATABASE_URL"), reason="requer PostgreSQL+pgvector")
DIM = 768


class FalsoEmb:
    nome, modelo, dim = "falso", "falso", DIM

    def embed(self, textos):
        out = []
        for t in textos:
            v = [0.0] * DIM
            for w in t.lower().split():
                v[int(hashlib.md5(w.encode()).hexdigest(), 16) % DIM] += 1.0
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / n for x in v])
        return out


def test_indexa_e_busca_com_pgvector(tmp_path):
    c = criar_container(settings_teste(tmp_path, "pg", seed_demo=True))
    assert c.db.dialeto == "postgresql"
    emb = FalsoEmb()
    n = vetorial.indexar_pendentes(c.db, emb)
    assert n > 10
    assert c.db.conn().execute("SELECT COUNT(*) AS n FROM redacao WHERE embedding IS NULL AND registrado_ate IS NULL").fetchone()["n"] == 0
    assert vetorial.indexar_pendentes(c.db, emb) == 0                      # idempotente
    busca = vetorial.criar_buscador(emb)
    sen, det = ctx_de(c, "senatran.servidor"), ctx_de(c, "detran.servidor")
    sims = busca(c.db, sen, "prazo transferência propriedade veículo adquirente")
    assert sims and all(0 <= v <= 1.0001 for v in sims.values())
    # permissão aplicada NA consulta vetorial: DETRAN-XX não recebe redações restritas da SENATRAN
    f = pesquisa.buscar(c.db, sen, "indício de fraude documental corregedoria")["fontes"]
    restritos = {x["redacao_id"] for x in f if "SENATRAN" in x["ato"]}
    assert restritos & set(busca(c.db, sen, "indício de fraude documental corregedoria"))
    assert not restritos & set(busca(c.db, det, "indício de fraude documental corregedoria"))
