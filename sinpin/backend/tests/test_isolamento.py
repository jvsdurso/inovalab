import pytest
from conftest import ctx_de, doc_por_titulo

from sinpin.common.erros import ErroNegocio
from sinpin.grafo import service as grafo
from sinpin.ingestao import service as ingestao
from sinpin.normativo import service as nv
from sinpin.pesquisa import service as pesquisa
from sinpin.producao import service as producao
from sinpin.ia.providers import Extrativo


def test_listagem_e_acesso_direto(c):
    sen, det, cur = ctx_de(c, "senatran.servidor"), ctx_de(c, "detran.servidor"), ctx_de(c, "curador")
    titulos_sen = {d["titulo"] for d in nv.listar_documentos(c.db, sen)}
    titulos_det = {d["titulo"] for d in nv.listar_documentos(c.db, det)}
    assert "Portaria SENATRAN nº 12/2024" in titulos_sen and "Portaria SENATRAN nº 12/2024" not in titulos_det
    assert "Instrução Normativa DETRAN-XX nº 3/2024" in titulos_det and "Instrução Normativa DETRAN-XX nº 3/2024" not in titulos_sen
    assert "Portaria SENATRAN nº 12/2024" not in {d["titulo"] for d in nv.listar_documentos(c.db, cur)}
    port = doc_por_titulo(c, sen, "SENATRAN nº 12")
    for fn in (nv.obter_documento_visivel, nv.compilado):
        with pytest.raises(ErroNegocio) as e:
            fn(c.db, det, port["id"])
        assert e.value.status == 404  # não vaza nem a existência


def test_pesquisa_nao_recupera_documento_de_outro_orgao(c):
    sen, det = ctx_de(c, "senatran.servidor"), ctx_de(c, "detran.servidor")
    q = "indício de fraude documental corregedoria"
    assert any("SENATRAN" in f["ato"] for f in pesquisa.buscar(c.db, sen, q)["fontes"])
    assert not any("SENATRAN" in f["ato"] for f in pesquisa.buscar(c.db, det, q)["fontes"])
    q2 = "agendamento prévio atendimento presencial"
    assert not any("DETRAN-XX" in f["ato"] for f in pesquisa.buscar(c.db, sen, q2)["fontes"])


def test_grafo_e_relacoes_filtrados(c):
    det = ctx_de(c, "detran.servidor")
    g = grafo.grafo(c.db, det)
    assert all("SENATRAN nº 12" not in n["titulo"] for n in g["nos"])
    ids = {n["id"] for n in g["nos"]}
    assert all(a["origem"] in ids and a["destino"] in ids for a in g["arestas"])
    assert all("Portaria SENATRAN" not in r["origem_titulo"] for r in grafo.listar(c.db, det))
    sen = ctx_de(c, "senatran.servidor")
    assert any(r["origem_titulo"] == "Portaria SENATRAN nº 12/2024" for r in grafo.listar(c.db, sen))


def test_minuta_nao_usa_fonte_de_outro_orgao_e_e_privada_ao_orgao(c):
    sen, det = ctx_de(c, "senatran.servidor"), ctx_de(c, "detran.servidor")
    f = pesquisa.buscar(c.db, sen, "indício de fraude documental corregedoria")["fontes"]
    rid = next(x["redacao_id"] for x in f if "SENATRAN" in x["ato"])
    with pytest.raises(ErroNegocio):  # DETRAN tenta usar o id de uma fonte restrita da SENATRAN
        producao.gerar(c.db, Extrativo(), det, tipo="DESPACHO", assunto="teste", fonte_ids=[rid])
    m = producao.gerar(c.db, Extrativo(), sen, tipo="DESPACHO", assunto="fraude documental", fonte_ids=[rid])
    with pytest.raises(ErroNegocio) as e:
        producao.obter(c.db, det, m["id"])
    assert e.value.status == 404


def test_ato_institucional_restrito_nao_altera_vigencia_nacional_para_os_demais(c):
    sen, det, cur = ctx_de(c, "senatran.servidor"), ctx_de(c, "detran.servidor"), ctx_de(c, "curador")
    texto = """PORTARIA SENATRAN Nº 30, DE 10 DE MAIO DE 2024

Altera o art. 5º da Resolução CONTRAN nº 101, de 3 de março de 2018.

Art. 1º O art. 5º da Resolução CONTRAN nº 101, de 3 de março de 2018, passa a vigorar com a seguinte redação:

“Art. 5º O adquirente deverá requerer a transferência no prazo de 999 (novecentos e noventa e nove) dias.” (NR)

Art. 2º Esta Portaria entra em vigor na data de sua publicação.
"""
    ingestao.ingerir(c.db, c.settings, c.armazenamento, sen, nome_arquivo="p30.txt", conteudo=None, texto=texto, escopo="INSTITUCIONAL_RESTRITO")
    for ctx in (sen, det, cur):
        r101 = doc_por_titulo(c, ctx, "CONTRAN nº 101/2018")
        comp = nv.compilado(c.db, ctx, r101["id"], "2024-12-01")
        art5 = next(i for i in comp["dispositivos"] if i["caminho"] == "art5")
        assert "999" not in art5["texto"] and "60 (sessenta)" in art5["texto"], ctx.login
    rel = next(r for r in grafo.listar(c.db, sen) if r["origem_titulo"] == "Portaria SENATRAN nº 30/2024")
    assert rel["efeito_aplicado"] == 0 and "informativa" in rel["nota_efeito"]
    # DETRAN não enxerga nem a relação
    assert not any(r["origem_titulo"] == "Portaria SENATRAN nº 30/2024" for r in grafo.listar(c.db, det))


def test_escopo_nacional_exige_curador(c):
    sen = ctx_de(c, "senatran.servidor")
    with pytest.raises(ErroNegocio) as e:
        ingestao.ingerir(c.db, c.settings, c.armazenamento, sen, nome_arquivo="x.txt", conteudo=None, texto="Art. 1º Texto.", escopo="NACIONAL")
    assert e.value.status == 403


def test_compartilhamento_explicito_libera_leitura(c):
    sen, det = ctx_de(c, "senatran.servidor"), ctx_de(c, "detran.servidor")
    port = doc_por_titulo(c, sen, "SENATRAN nº 12")
    ingestao.compartilhar(c.db, sen, port["id"], ["detran-xx"])
    assert nv.obter_documento_visivel(c.db, det, port["id"])["id"] == port["id"]
    ingestao.compartilhar(c.db, sen, port["id"], [])
    with pytest.raises(ErroNegocio):
        nv.obter_documento_visivel(c.db, det, port["id"])
