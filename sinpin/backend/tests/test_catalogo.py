import io
import json
import zipfile

import pytest
from conftest import ctx_de, doc_por_titulo

from sinpin.catalogo import lote, service as catalogo
from sinpin.common.erros import ErroNegocio
from sinpin.ingestao import service as ingestao

URL_DOC = "https://www.gov.br/transportes/pt-br/assuntos/transito/arquivos/res_1032_2026.pdf"
URL_ORIGEM = "https://www.gov.br/transportes/pt-br/assuntos/transito/conteudo-Senatran/resolucoes-contran"
URL_DOU = "https://www.in.gov.br/web/dou/-/resolucao-contran-n-1.032-de-1-de-janeiro-de-2026-000000000"

TEXTO_1032 = """RESOLUÇÃO CONTRAN Nº 1.032, DE 5 DE JANEIRO DE 2026

Dispõe sobre a transferência de propriedade.

Art. 1º Esta Resolução estabelece procedimentos de transferência de propriedade de veículos.

Art. 2º Fica revogada a Resolução nº 941, de 2022.

Art. 3º Esta Resolução entra em vigor na data de sua publicação.
"""


TEXTO_941 = """RESOLUÇÃO CONTRAN Nº 941, DE 10 DE MARÇO DE 2022

Dispõe sobre procedimentos antigos de transferência.

Art. 1º Esta Resolução estabelece procedimentos de transferência de veículos.

Art. 2º Esta Resolução entra em vigor na data de sua publicação.
"""


def _ingerir(c, ctx, texto=TEXTO_1032, **kw):
    return ingestao.ingerir(c.db, c.settings, c.armazenamento, ctx, nome_arquivo="res.txt", conteudo=None, texto=texto,
                            escopo="NACIONAL", **kw)


def test_fontes_oficiais_semeadas_mesmo_sem_demo(vazio):
    fontes = {f["id"]: f for f in catalogo.listar_fontes(vazio.db)}
    assert {"ctb-compilado", "resolucoes-contran", "dou", "ro-dou"} <= set(fontes)
    assert "monitoramento" in fontes["ro-dou"]["nota"].lower()


def test_referencias_do_indice_sao_apenas_indice_e_nao_afetam_vigencia(c):
    cur = ctx_de(c, "curador")
    itens = catalogo.listar(c.db, cur)
    r1032 = next(i for i in itens if i["numero"] == "1032")
    assert r1032["status_obtencao"] == "APENAS_INDICE" and r1032["documento_id"] is None
    assert r1032["url_documento"] is None and r1032["url_publicacao_dou"] is None  # nada é inventado
    assert r1032["url_origem"].startswith("https://www.gov.br/")
    assert all(h["resultado"] == "SEM_TEXTO" for h in r1032["conferencia"])
    rel = catalogo.relatorio(c.db, cur)
    assert rel["por_obtencao"]["APENAS_INDICE"] == 6 and len(rel["ausentes_ou_pendentes"]) == 6
    # nenhum documento/relação foi criado por causa do índice
    assert c.db.conn().execute("SELECT COUNT(*) AS n FROM documento WHERE numero IN ('1032','1031')").fetchone()["n"] == 0


def test_ingestao_liga_ao_catalogo_e_confere_hipoteses_do_indice(c):
    cur = ctx_de(c, "curador")
    r = _ingerir(c, cur, fonte_url=URL_DOC, origem={"url_origem": URL_ORIGEM, "url_publicacao_dou": URL_DOU,
                                                    "data_assinatura": "2026-01-05", "capturado_em": "2026-02-01T10:00:00"})
    assert r["origem"]["url_documento"] == URL_DOC and len(r["origem"]["hash_sha256"]) == 64
    item = next(i for i in catalogo.listar(c.db, cur) if i["numero"] == "1032")
    assert item["status_obtencao"] == "OBTIDO" and item["documento_id"] == r["documento_id"]
    assert item["url_documento"] == URL_DOC and item["url_publicacao_dou"] == URL_DOU
    res = {h["numero"]: h["resultado"] for h in item["conferencia"]}
    assert res["941"] == "DETECTADA_PENDENTE"           # o texto revoga a 941, mas a 941 ainda não está no acervo: sem efeito
    assert res["977"] == "NAO_ENCONTRADA_NO_TEXTO"      # o índice disse, o texto não: divergência a revisar
    _ingerir(c, cur, texto=TEXTO_941)                    # chega o ato revogado: a relação se resolve e é confirmada
    item = catalogo.obter_item(c.db, item["id"])
    assert {h["numero"]: h["resultado"] for h in item["conferencia"]}["941"] == "CONFIRMADA_NO_TEXTO"
    rel = catalogo.relatorio(c.db, cur)
    assert any(d["hipotese"]["numero"] == "977" for d in rel["divergencias_do_indice"])
    ver = c.db.conn().execute("SELECT capturado_em FROM documento_versao WHERE documento_id=?", (r["documento_id"],)).fetchone()
    assert ver["capturado_em"] == "2026-02-01T10:00:00"


def test_pagina_geral_nao_pode_ser_link_de_documento(c):
    cur = ctx_de(c, "curador")
    with pytest.raises(ErroNegocio) as e:
        _ingerir(c, cur, fonte_url=URL_ORIGEM)  # índice de Resoluções CONTRAN ≠ documento individual
    assert e.value.status == 422 and "página geral" in e.value.mensagem
    with pytest.raises(ErroNegocio):
        _ingerir(c, cur, fonte_url=URL_DOC, origem={"url_publicacao_dou": "https://www.in.gov.br/inicio"})
    with pytest.raises(ErroNegocio):
        _ingerir(c, cur, fonte_url="ftp://exemplo/x.pdf")
    # o link do CTB compilado É um documento individual: permitido
    catalogo.normalizar_origem(c.db, {"url_documento": "https://www.planalto.gov.br/ccivil_03/leis/l9503compilado.htm"})
    assert c.db.conn().execute("SELECT COUNT(*) AS n FROM documento WHERE numero='1032'").fetchone()["n"] == 0  # nada entrou


def test_enderecos_identicos_geram_aviso(c):
    cur = ctx_de(c, "curador")
    r = _ingerir(c, cur, fonte_url=URL_DOC, origem={"url_origem": URL_DOC})
    assert any("idênticos" in a for a in r["alertas"])


def test_nova_versao_zera_validacao_humana(c):
    cur = ctx_de(c, "curador")
    r = _ingerir(c, cur, fonte_url=URL_DOC)
    ingestao.definir_validacao(c.db, cur, r["documento_id"], "CONFIRMADO", "conferido com o DOU")
    assert catalogo.obter_item(c.db, next(i for i in catalogo.listar(c.db, cur) if i["numero"] == "1032")["id"])["status_validacao"] == "CONFIRMADO"
    r2 = _ingerir(c, cur, texto=TEXTO_1032.replace("procedimentos", "novos procedimentos"))
    assert r2["nova_versao"]
    d = c.db.conn().execute("SELECT status_validacao, fonte_url FROM documento WHERE id=?", (r["documento_id"],)).fetchone()
    assert d["status_validacao"] == "PENDENTE" and d["fonte_url"] == URL_DOC   # link anterior preservado


def test_somente_curador_registra_e_valida(c):
    sen = ctx_de(c, "senatran.servidor")
    with pytest.raises(ErroNegocio) as e:
        catalogo.registrar_item(c.db, sen, {"tipo": "RESOLUCAO", "numero": "1", "ano": 2026})
    assert e.value.status == 403
    cur = ctx_de(c, "curador")
    d = doc_por_titulo(c, cur, "Resolução CONTRAN nº 101") if False else next(
        x for x in __import__("sinpin.normativo.service", fromlist=["x"]).listar_documentos(c.db, cur) if x["numero"] == "101")
    with pytest.raises(ErroNegocio):
        ingestao.definir_validacao(c.db, sen, d["id"], "CONFIRMADO")
    with pytest.raises(ErroNegocio):
        ingestao.definir_validacao(c.db, cur, d["id"], "TALVEZ")


def test_pesquisa_avisa_documento_sem_validacao_humana(c):
    cur = ctx_de(c, "curador")
    _ingerir(c, cur, fonte_url=URL_DOC)
    from sinpin.pesquisa import service as pesquisa
    b = pesquisa.buscar(c.db, cur, "transferência de propriedade de veículos procedimentos", "2026-06-01")
    f = next(f for f in b["fontes"] if "1.032" in f["ato"] or "1032" in f["ato"])
    assert f["status_validacao"] == "PENDENTE" and f["fonte_url"] == URL_DOC and f["versao_documento"] == 1
    assert any("Sem validação jurídica humana" in a["mensagem"] for a in b["alertas"])


def _zip(manifesto, arquivos):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("manifesto.json", json.dumps(manifesto))
        for n, b in arquivos.items():
            z.writestr(n, b)
    return buf.getvalue()


def test_lote_zip_item_a_item(vazio):
    from sinpin.identidade import service as ident
    cur = ident.contexto_por_login(vazio.db, "curador")
    pacote = _zip({"itens": [
        {"tipo": "RESOLUCAO", "orgao_emissor": "CONTRAN", "numero": "1032", "ano": 2026, "arquivo": "originais/r1032.txt",
         "url_documento": URL_DOC, "url_origem": URL_ORIGEM, "url_publicacao_dou": URL_DOU,
         "relacoes_indice": [{"tipo": "REVOGA", "alvo_tipo": "RESOLUCAO", "numero": "941", "ano": 2022}]},
        {"tipo": "RESOLUCAO", "orgao_emissor": "CONTRAN", "numero": "1019", "ano": 2025},                       # só referência
        {"tipo": "RESOLUCAO", "orgao_emissor": "CONTRAN", "numero": "1020", "ano": 2025, "arquivo": "../../etc/passwd"},  # fora do pacote
        {"tipo": "RESOLUCAO", "orgao_emissor": "CONTRAN", "numero": "1021", "ano": 2025, "arquivo": "originais/r.txt",
         "url_documento": URL_ORIGEM},                                                                           # página geral como documento
    ]}, {"originais/r1032.txt": TEXTO_1032.encode(), "originais/r.txt": TEXTO_1032.encode()})
    r = lote.importar_zip(vazio.db, vazio.settings, vazio.armazenamento, cur, pacote)
    por = {x["ref"]: x for x in r["resultados"]}
    assert por["RESOLUCAO 1032/2026"]["resultado"] == "OBTIDO"
    assert por["RESOLUCAO 1019/2025"]["resultado"] == "APENAS_REFERENCIA"
    assert por["RESOLUCAO 1020/2025"]["resultado"] == "FALHA" and "não consta do pacote" in por["RESOLUCAO 1020/2025"]["erro"]
    assert por["RESOLUCAO 1021/2025"]["resultado"] == "FALHA" and "página geral" in por["RESOLUCAO 1021/2025"]["erro"]
    assert (r["obtidos"], r["apenas_referencia"], r["falhas"]) == (1, 1, 2)
    st = {i["numero"]: i["status_obtencao"] for i in catalogo.listar(vazio.db, cur)}
    assert st == {"1032": "OBTIDO", "1019": "APENAS_INDICE", "1020": "FALHA", "1021": "FALHA"}
    # reimportar o mesmo pacote não duplica
    r2 = lote.importar_zip(vazio.db, vazio.settings, vazio.armazenamento, cur, pacote)
    assert r2["duplicados"] == 1 and vazio.db.conn().execute("SELECT COUNT(*) AS n FROM documento").fetchone()["n"] == 1
    with pytest.raises(ErroNegocio):
        lote.importar_zip(vazio.db, vazio.settings, vazio.armazenamento, cur, b"nao e zip")


def test_lote_exige_curador(vazio):
    from sinpin.identidade import service as ident
    with pytest.raises(ErroNegocio) as e:
        lote.importar_zip(vazio.db, vazio.settings, vazio.armazenamento, ident.contexto_por_login(vazio.db, "detran.servidor"), b"x")
    assert e.value.status == 403


def test_extracao_html_descarta_tachado_e_mantem_estrutura(vazio):
    from sinpin.identidade import service as ident
    from sinpin.ingestao import extrator
    cur = ident.contexto_por_login(vazio.db, "curador")
    html = ("<html><head><title>x</title><style>p{}</style></head><body><p>RESOLUÇÃO CONTRAN Nº 1.040, DE 2 DE FEVEREIRO DE 2026</p>"
            "<p>Dispõe sobre testes.</p><p>Art. 1º Esta Resolução trata de <strike>texto antigo</strike> testes de extração em HTML.</p>"
            "<p>Art. 2º Esta Resolução entra em vigor na data de sua publicação.</p><script>alert(1)</script></body></html>")
    texto, avisos = extrator.extrair_texto("res.html", html.encode("utf-8"))
    assert "texto antigo" not in texto and "alert" not in texto and "x\n" not in texto.split("RESOLUÇÃO")[0]
    assert "Art. 1º Esta Resolução trata de testes de extração em HTML." in texto.replace("  ", " ")
    assert any("tachado" in a for a in avisos)
    r = ingestao.ingerir(vazio.db, vazio.settings, vazio.armazenamento, cur, nome_arquivo="res.html", conteudo=html.encode("utf-8"),
                         texto=None, escopo="NACIONAL", fonte_url="https://exemplo.gov.br/res1040.html")
    assert r["dispositivos"] == 2 and r["origem"]["url_documento"].endswith("res1040.html")
    assert vazio.db.conn().execute("SELECT formato_original FROM documento").fetchone()["formato_original"] == "html"


def test_traducao_sql_para_postgres():
    from sinpin.db import separar_comandos, traduzir_sql
    assert traduzir_sql("SELECT * FROM t WHERE a=? AND b LIKE ?") == "SELECT * FROM t WHERE a=%s AND b LIKE %s"
    assert traduzir_sql("INSERT OR IGNORE INTO t(a,b) VALUES (?,?)") == "INSERT INTO t(a,b) VALUES (%s,%s) ON CONFLICT DO NOTHING"
    assert traduzir_sql("SELECT '100%' AS x, ?") == "SELECT '100%%' AS x, %s"          # % literal é escapado
    assert traduzir_sql("SELECT 1; SELECT 2", com_params=False) == "SELECT 1; SELECT 2"  # sem parâmetros: intacto
    assert separar_comandos("-- c; x\nCREATE TABLE a(x INT);\nCREATE INDEX i ON a(x);\n") == ["CREATE TABLE a(x INT)", "CREATE INDEX i ON a(x)"]


def test_todas_as_migracoes_sao_divisiveis_e_sem_construcoes_sqlite():
    import re
    from sinpin.db import MIGRACOES, separar_comandos
    for arq in MIGRACOES.glob("*.sql"):
        txt = arq.read_text(encoding="utf-8")
        assert separar_comandos(txt), arq.name
        if not arq.name.endswith(".sqlite.sql"):
            assert not re.search(r"AUTOINCREMENT|PRAGMA|WITHOUT ROWID|\bREAL\b", txt), arq.name


def test_divisor_de_migracoes_equivale_ao_executescript():
    """O PostgreSQL aplica as migrações comando a comando: o divisor não pode quebrar nenhum comando."""
    import sqlite3
    from sinpin.db import MIGRACOES, separar_comandos
    a, b = sqlite3.connect(":memory:"), sqlite3.connect(":memory:")
    for arq in sorted(MIGRACOES.glob("*.sql")):
        if arq.name.endswith((".pg.sql",)):
            continue
        txt = arq.read_text(encoding="utf-8")
        a.executescript(txt)
        for cmd in separar_comandos(txt):
            b.execute(cmd)
    def esquema(c):  # estrutura (colunas/índices), ignorando comentários que o sqlite guarda no texto do DDL
        objs = [(r[0], r[1]) for r in c.execute("SELECT type, name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY 1, 2")]
        cols = [(n, tuple(c.execute(f"PRAGMA table_info({n})").fetchall())) for t, n in objs if t == "table"]
        return objs, cols
    assert esquema(a) == esquema(b) and len(esquema(a)[0]) > 20
