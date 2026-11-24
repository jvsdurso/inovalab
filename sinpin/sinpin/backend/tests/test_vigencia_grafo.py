from conftest import ctx_de, doc_por_titulo

from sinpin.common.erros import ErroNegocio
from sinpin.grafo import service as grafo
from sinpin.ingestao import service as ingestao
from sinpin.normativo import service as nv
from sinpin.seed import demo


def texto_art(c, ctx, doc, caminho, data):
    comp = nv.compilado(c.db, ctx, doc["id"], data)
    it = next((i for i in comp["dispositivos"] if i["caminho"] == caminho), None)
    return it


def test_pergunta_no_tempo_prazo_de_transferencia(c):
    ctx = ctx_de(c, "senatran.servidor")
    r101 = doc_por_titulo(c, ctx, "CONTRAN nº 101/2018")
    # antes da vigência da própria Res. 101 (30 dias após 03/03/2018)
    assert texto_art(c, ctx, r101, "art5", "2018-03-15")["situacao"] == "NAO_INICIADA"
    # redação original
    a = texto_art(c, ctx, r101, "art5", "2019-01-01")
    assert a["situacao"] == "VIGENTE" and "30 (trinta) dias" in a["texto"] and a["tipo_redacao"] == "ORIGINAL"
    # alterada pela Res. 340 em 01/10/2023 (a antiga redação continua consultável no passado)
    assert texto_art(c, ctx, r101, "art5", "2023-09-30")["texto"].count("30 (trinta)") == 1
    b = texto_art(c, ctx, r101, "art5", "2023-10-01")
    assert "60 (sessenta) dias" in b["texto"] and b["redacao_dada_por"] == "Resolução CONTRAN nº 340/2023"


def test_alteracao_de_inciso_e_inclusao_de_artigo(c):
    ctx = ctx_de(c, "senatran.servidor")
    r101 = doc_por_titulo(c, ctx, "CONTRAN nº 101/2018")
    assert "data da escritura" in texto_art(c, ctx, r101, "art5.inc2", "2021-06-30")["texto"]
    novo = texto_art(c, ctx, r101, "art5.inc2", "2021-07-01")
    assert "ato de liberalidade" in novo["texto"] and novo["redacao_dada_por"].endswith("215/2021")
    # art. 5º-A não existia antes de 01/07/2021
    assert texto_art(c, ctx, r101, "art5a", "2021-06-30") is None or texto_art(c, ctx, r101, "art5a", "2021-06-30")["situacao"] == "NAO_INICIADA"
    assert texto_art(c, ctx, r101, "art5a", "2022-01-01")["situacao"] == "VIGENTE"


def test_revogacoes_parciais_e_total(c):
    ctx = ctx_de(c, "senatran.servidor")
    r101 = doc_por_titulo(c, ctx, "CONTRAN nº 101/2018")
    assert texto_art(c, ctx, r101, "art6", "2023-09-30")["situacao"] == "VIGENTE"
    art6 = texto_art(c, ctx, r101, "art6", "2024-01-01")
    assert art6["situacao"] == "REVOGADO" and art6["encerrada_por"].endswith("340/2023")
    assert texto_art(c, ctx, r101, "art3.p2", "2024-01-01")["situacao"] == "REVOGADO"
    assert texto_art(c, ctx, r101, "art3.p1", "2024-01-01")["situacao"] == "VIGENTE"  # não afetado
    r52 = doc_por_titulo(c, ctx, "CONTRAN nº 52/2012")
    assert r52["situacao"] == "REVOGADA"
    assert nv.compilado(c.db, ctx, r52["id"], "2017-01-01")["situacao"] == "VIGENTE"
    assert nv.compilado(c.db, ctx, r52["id"], "2018-04-02")["situacao"] == "REVOGADA"


def test_relacao_nao_presume_revogacao_por_recencia(c):
    ctx = ctx_de(c, "senatran.servidor")
    r101 = doc_por_titulo(c, ctx, "CONTRAN nº 101/2018")
    # a Res. 340 é posterior, mas só revoga o que o texto diz; o art. 4º segue vigente
    assert texto_art(c, ctx, r101, "art4", "2024-06-01")["situacao"] == "VIGENTE"


def test_ordem_de_importacao_nao_importa(vazio, c):
    # importa a Res. 340 ANTES da 101: relação fica pendente e é resolvida (com efeitos) quando a 101 chegar
    curador = ctx_de(vazio, "curador")
    arq = demo.PASTA
    def imp(nome):
        return ingestao.ingerir(vazio.db, vazio.settings, vazio.armazenamento, curador, nome_arquivo=nome,
                                conteudo=(arq / nome).read_bytes(), texto=None, escopo="NACIONAL", sintetico=True)
    r = imp("05_resolucao_340_2023.txt")
    assert r["relacoes_pendentes"] == 3
    imp("03_resolucao_101_2018.txt")
    r101 = doc_por_titulo(vazio, curador, "101/2018")
    assert "60 (sessenta)" in texto_art(vazio, curador, r101, "art5", "2024-01-01")["texto"]
    assert texto_art(vazio, curador, r101, "art6", "2024-01-01")["situacao"] == "REVOGADO"
    assert not [r for r in grafo.listar(vazio.db, curador, status="SUGERIDA") if "340" in r["origem_titulo"]]
    # já as relações da Res. 101 com a Lei e a Res. 52 (ainda não importadas) seguem pendentes, sem efeito
    assert {r["destino_ref"].split(",")[0] for r in grafo.listar(vazio.db, curador, status="SUGERIDA")} == {"Lei nº 1.001", "Resolução CONTRAN nº 52"}


def test_validacao_humana_rejeitar_desfaz_efeito_e_confirmar_refaz(c):
    ctx = ctx_de(c, "curador")
    r101 = doc_por_titulo(c, ctx, "CONTRAN nº 101/2018")
    rel = next(r for r in grafo.listar(c.db, ctx) if r["tipo"] == "REVOGA_PARCIALMENTE" and r["destino_rotulo"] == "Art. 6º")
    grafo.validar(c.db, ctx, rel["id"], "REJEITAR", "teste")
    assert texto_art(c, ctx, r101, "art6", "2024-01-01")["situacao"] == "VIGENTE"
    h = grafo.validar(c.db, ctx, rel["id"], "CONFIRMAR", "refeito")
    assert h["status"] == "CONFIRMADA" and texto_art(c, ctx, r101, "art6", "2024-01-01")["situacao"] == "REVOGADO"
    hist = grafo.historico(c.db, ctx, rel["id"])
    assert [x["status_novo"] for x in hist] == ["CONFIRMADA", "REJEITADA", "CONFIRMADA"]
    # servidor de outro órgão não valida relação de norma nacional
    outro = ctx_de(c, "detran.servidor")
    try:
        grafo.validar(c.db, outro, rel["id"], "REJEITAR")
        assert False, "deveria negar"
    except ErroNegocio as e:
        assert e.status == 403


def test_nova_versao_do_documento_preserva_historico_de_sistema(c):
    ctx = ctx_de(c, "curador")
    r52 = doc_por_titulo(c, ctx, "CONTRAN nº 52/2012")
    txt = (demo.PASTA / "02_resolucao_52_2012.txt").read_text(encoding="utf-8").replace("15 (quinze)", "20 (vinte)")
    res = ingestao.ingerir(c.db, c.settings, c.armazenamento, ctx, nome_arquivo="r52.txt", conteudo=None, texto=txt, escopo="NACIONAL")
    assert res["nova_versao"] and res["versao"] == 2
    comp = nv.compilado(c.db, ctx, r52["id"], "2012-06-01")
    assert "20 (vinte)" in next(i for i in comp["dispositivos"] if i["caminho"] == "art1")["texto"]
    # a redação anterior continua registrada (tempo de sistema), porém deixa de ser considerada
    n = c.db.conn().execute("SELECT COUNT(*) n FROM redacao r JOIN dispositivo p ON p.id=r.dispositivo_id WHERE p.documento_id=? "
                            "AND r.registrado_ate IS NOT NULL", (r52["id"],)).fetchone()["n"]
    assert n == 3
    # reimportar o mesmo conteúdo não duplica
    dup = ingestao.ingerir(c.db, c.settings, c.armazenamento, ctx, nome_arquivo="r52.txt", conteudo=None, texto=txt, escopo="NACIONAL")
    assert dup["duplicado"]
