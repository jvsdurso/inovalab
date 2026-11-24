"""Busca híbrida (BM25 + pgvector). Aqui a similaridade vetorial é simulada; a parte SQL do pgvector só roda no PostgreSQL
(ver tests/test_postgres_vetor.py)."""
import pytest
from conftest import ctx_de

from sinpin.ia import embeddings
from sinpin.pesquisa import service as pesquisa, vetorial


def test_fundir_combina_bm25_e_vetor_com_piso_de_similaridade():
    ids = ["a", "b", "c"]
    out = vetorial.fundir(ids, [4.0, 2.0, 0.0], {"b": 0.9, "c": 0.2}, sim_min=0.45)
    assert out[0] == pytest.approx(0.6)                    # só lexical (o maior BM25)
    assert out[1] == pytest.approx(0.6 * 0.5 + 0.4 * 0.9)  # lexical + vetor
    assert out[2] == 0.0                                   # similaridade abaixo do piso: ignorada
    assert vetorial.fundir(["x"], [0.0], {"x": 0.8})[0] == pytest.approx(0.4 * 0.8)  # só vetor entra se passar do piso


def _art5(c, ctx):
    f = pesquisa.buscar(c.db, ctx, "prazo para requerer a transferência de propriedade do veículo", "2019-06-01")["fontes"]
    return next(x for x in f if x["rotulo"].startswith("Art. 5"))


def test_busca_hibrida_recupera_por_significado_sem_palavra_em_comum(c):
    sen = ctx_de(c, "senatran.servidor")
    alvo = _art5(c, sen)
    consulta = "alienação de automóvel"   # nenhuma palavra em comum com o texto
    assert not any(f["redacao_id"] == alvo["redacao_id"] for f in pesquisa.buscar(c.db, sen, consulta, "2019-06-01")["fontes"])
    fake = lambda db, ctx, q: {alvo["redacao_id"]: 0.82}
    fontes = pesquisa.buscar(c.db, sen, consulta, "2019-06-01", semelhanca=fake)["fontes"]
    assert fontes and fontes[0]["redacao_id"] == alvo["redacao_id"]


def test_vetor_nunca_traz_o_que_o_usuario_nao_pode_ver(c):
    sen, det = ctx_de(c, "senatran.servidor"), ctx_de(c, "detran.servidor")
    f = pesquisa.buscar(c.db, sen, "indício de fraude documental corregedoria")["fontes"]
    restritos = {x["redacao_id"]: 0.99 for x in f if "SENATRAN" in x["ato"]}
    assert restritos
    fontes = pesquisa.buscar(c.db, det, "fraude", semelhanca=lambda db, ctx, q: restritos)["fontes"]
    assert not any("SENATRAN" in x["ato"] for x in fontes)


def test_embeddings_openai_compat(monkeypatch):
    class R:
        def __init__(self, dados): self._d = dados
        def raise_for_status(self): pass
        def json(self): return self._d
    chamadas = []
    def post(url, headers=None, json=None, timeout=None):
        chamadas.append((url, json))
        return R({"data": [{"index": 1, "embedding": [0.0, 1.0]}, {"index": 0, "embedding": [1.0, 0.0]}]})
    monkeypatch.setattr(embeddings.requests, "post", post)
    e = embeddings.OpenAICompatEmbeddings("http://ollama:11434/v1/", "nomic-embed-text", dim=2)
    assert e.embed(["a", "b"]) == [[1.0, 0.0], [0.0, 1.0]]          # reordenado por index
    assert chamadas[0][0] == "http://ollama:11434/v1/embeddings" and chamadas[0][1]["model"] == "nomic-embed-text"
    with pytest.raises(embeddings.ErroEmbedding, match="Dimensão"):
        embeddings.OpenAICompatEmbeddings("http://x", "m", dim=3).embed(["a", "b"])


def test_indexacao_e_noop_fora_do_postgres_e_sem_provedor(c):
    assert vetorial.indexar_pendentes(c.db, None) == 0
    assert vetorial.indexar_pendentes(c.db, embeddings.OpenAICompatEmbeddings("http://x", "m")) == 0   # SQLite: sem vetor
    assert c.indexar() == 0 and c.semelhanca is None and c.embeddings is None
