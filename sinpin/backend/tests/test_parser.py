from sinpin.grafo.detector import detectar, extrair_alvos, extrair_citacoes
from sinpin.normativo.parser import (detectar_vigencia_inicio, extrair_metadados, fragmento_para_dispositivos,
                                     parse_dispositivos)

TEXTO = """RESOLUÇÃO CONTRAN Nº 101, DE 3 DE MARÇO DE 2018

Regulamenta o art. 4º da Lei nº 1.001, de 12 de janeiro de 2015.

CAPÍTULO I
DO PROCEDIMENTO

Art. 3º O requerimento será instruído com:
I - documento de identificação;
II - certificado de registro; e
III - comprovante de pagamento.
§ 1º O comprovante poderá ser dispensado.
§ 2º A procuração é obrigatória:
a) para terceiros; e
b) para pessoa jurídica.
Art. 5º-A Texto do artigo
com quebra de linha.
Parágrafo único. Texto do parágrafo único.
Art. 10. Esta Resolução entra em vigor 30 (trinta) dias após a data de sua publicação.
"""


def test_metadados():
    md = extrair_metadados(TEXTO)
    assert (md.tipo, md.numero, md.ano, md.orgao_emissor) == ("RESOLUCAO", "101", 2018, "CONTRAN")
    assert md.data_publicacao == "2018-03-03"
    assert md.ementa.startswith("Regulamenta o art. 4º")
    assert md.titulo == "Resolução CONTRAN nº 101/2018"


def test_estrutura_e_caminhos():
    ds = {d.caminho: d for d in parse_dispositivos(TEXTO)}
    assert list(ds) == ["art3", "art3.inc1", "art3.inc2", "art3.inc3", "art3.p1", "art3.p2", "art3.p2.ala", "art3.p2.alb",
                        "art5a", "art5a.pu", "art10"]
    assert ds["art3.inc2"].rotulo == "Art. 3º, II"
    assert ds["art3.p2.alb"].rotulo == "Art. 3º, § 2º, alínea b"
    assert ds["art5a"].rotulo == "Art. 5º-A" and "quebra de linha" in ds["art5a"].texto
    assert ds["art3"].grupo.startswith("CAPÍTULO I")
    assert ds["art3.inc1"].texto == "documento de identificação;"


def test_vigencia_inicio():
    assert detectar_vigencia_inicio(TEXTO, "2018-03-03") == ("2018-04-02", "EXPLICITA")
    assert detectar_vigencia_inicio("Esta Lei entra em vigor na data de sua publicação.", "2020-01-10") == ("2020-01-10", "EXPLICITA")
    assert detectar_vigencia_inicio("Esta Resolução entra em vigor em 1º de julho de 2021.", "2021-06-14") == ("2021-07-01", "EXPLICITA")
    assert detectar_vigencia_inicio("Sem cláusula.", "2021-06-14") == ("2021-06-14", "PRESUMIDA")


def test_alvos_de_dispositivos():
    assert extrair_alvos("o § 2º do art. 3º e o art. 6º da ") == ["art3.p2", "art6"]
    assert extrair_alvos("os §§ 1º e 2º do art. 4º") == ["art4.p1", "art4.p2"]
    assert extrair_alvos("o inciso II do art. 5º") == ["art5.inc2"]
    assert extrair_alvos("os arts. 5º e 6º") == ["art5", "art6"]
    assert extrair_alvos("os arts. 5º a 7º") == ["art5", "art6", "art7"]
    assert extrair_alvos("a alínea b do inciso III do § 1º do art. 4º") == ["art4.p1.inc3.alb"]
    assert extrair_alvos("o art. 5º-A") == ["art5a"]
    assert extrair_alvos("o inciso II e o § 3º do art. 5º") == ["art5.inc2", "art5.p3"]
    assert extrair_alvos("a Resolução nº 52") == []


def test_citacoes():
    assert extrair_citacoes("redação: “II - novo;” (NR)") == ["II - novo;"]
    assert extrair_citacoes("sem aspas") == []


def test_fragmento_relativo_ao_alvo():
    ds = fragmento_para_dispositivos("II - novo texto;", "art5.inc2")
    assert [d.caminho for d in ds] == ["art5.inc2"]
    ds = fragmento_para_dispositivos("Art. 5º Caput novo:\nI - a;\nII - ......\nIII - c", "art5")
    assert [d.caminho for d in ds] == ["art5", "art5.inc1", "art5.inc3"]  # elisão (II) não vira alteração
    assert fragmento_para_dispositivos("Art. 6º Outro", "art5") == []


def test_detector_nao_presume_revogacao_por_recencia():
    # "Revogam-se as disposições em contrário" não identifica ato -> nenhuma relação
    ds = parse_dispositivos("Art. 1º Esta Resolução vigora.\nArt. 2º Revogam-se as disposições em contrário.")
    assert detectar(None, ds) == []


def test_detector_negacao():
    ds = parse_dispositivos("Art. 1º Esta Portaria não altera a Resolução nº 101, de 2018.")
    assert detectar(None, ds) == []


def test_detector_incisos_herdam_verbo():
    texto = ("Art. 2º Ficam revogados:\nI - o inciso II do art. 3º da Resolução nº 101, de 2018;\n"
             "II - o art. 4º da Resolução nº 52, de 2012.")
    rels = {(d.tipo, d.destino_numero, d.destino_caminho) for d in detectar(None, parse_dispositivos(texto))}
    assert rels == {("REVOGA_PARCIALMENTE", "101", "art3.inc2"), ("REVOGA_PARCIALMENTE", "52", "art4")}
