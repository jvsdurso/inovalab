"""Fluxo ponta a ponta via HTTP real (FastAPI servido por uvicorn em thread + requests). Requer fastapi/uvicorn instalados."""
import io
import socket
import threading
import time

import pytest
import requests
import uvicorn

from conftest import settings_teste
from sinpin.api.app import create_app


@pytest.fixture()
def servidor(tmp_path):
    s = socket.socket(); s.bind(("127.0.0.1", 0)); porta = s.getsockname()[1]; s.close()
    st = settings_teste(tmp_path, "api", seed_demo=True)
    srv = uvicorn.Server(uvicorn.Config(create_app(st), host="127.0.0.1", port=porta, log_level="warning"))
    t = threading.Thread(target=srv.run, daemon=True); t.start()
    for _ in range(100):
        if srv.started: break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{porta}/api/v1"
    srv.should_exit = True; t.join(timeout=5)


def H(login): return {"X-Dev-User": login}


def test_fluxo_completo(servidor):
    u = servidor
    assert requests.get(u + "/saude").json()["status"] == "ok"
    assert requests.get(u + "/me").status_code == 401  # sem identidade
    me = requests.get(u + "/me", headers=H("senatran.servidor")).json()
    assert me["orgao"]["sigla"] == "SENATRAN" and me["llm"]["generativo"] is False

    docs = requests.get(u + "/documentos", headers=H("senatran.servidor")).json()["documentos"]
    assert len(docs) == 6  # 5 nacionais + portaria da SENATRAN (a IN do DETRAN-XX é invisível)
    assert len(requests.get(u + "/documentos", headers=H("detran.servidor")).json()["documentos"]) == 6

    # importação por upload (multipart) de uma norma institucional nova
    texto = ("PORTARIA SENATRAN Nº 99, DE 5 DE MARÇO DE 2024\n\nDispõe sobre o atendimento prioritário.\n\n"
             "Art. 1º O atendimento prioritário será realizado mediante senha especial.\n\nArt. 2º Esta Portaria entra em vigor na data de sua publicação.\n")
    r = requests.post(u + "/documentos", headers=H("senatran.servidor"), data={"escopo": "INSTITUCIONAL_RESTRITO"},
                      files={"arquivo": ("portaria99.txt", texto.encode("utf-8"), "text/plain")})
    assert r.status_code == 201 and r.json()["dispositivos"] == 2
    novo = r.json()["documento_id"]
    assert requests.get(f"{u}/documentos/{novo}", headers=H("detran.servidor")).status_code == 404

    # pesquisa com vigência na data
    p = requests.post(u + "/pesquisa", headers=H("senatran.servidor"),
                      json={"pergunta": "prazo para o adquirente requerer a transferência de propriedade", "data": "2019-06-01"}).json()
    assert p["modo"] == "extrativo" and "30 (trinta)" in p["resposta"]
    p2 = requests.post(u + "/pesquisa", headers=H("senatran.servidor"),
                       json={"pergunta": "prazo para o adquirente requerer a transferência de propriedade", "data": "2024-06-01"}).json()
    assert "60 (sessenta)" in p2["resposta"] and p2["alertas"]

    # minuta -> edição -> exportação
    m = requests.post(u + "/minutas", headers=H("senatran.servidor"), json={
        "tipo": "NOTA_TECNICA", "assunto": "Prazo de transferência", "data": "2024-06-01",
        "fonte_ids": [f["redacao_id"] for f in p2["fontes"]]}).json()
    assert m["status"] == "RASCUNHO"
    secoes = [{"id": s["id"], "texto": ("Conclusão revisada pelo servidor." if s["id"] == "conclusao" else s["texto"])} for s in m["secoes"]]
    assert requests.put(f"{u}/minutas/{m['id']}", headers=H("senatran.servidor"), json={"secoes": secoes, "status": "EM_REVISAO"}).json()["status"] == "EM_REVISAO"
    docx = requests.get(f"{u}/minutas/{m['id']}/exportar?formato=docx", headers=H("senatran.servidor"))
    assert docx.status_code == 200 and docx.content[:2] == b"PK"
    import docx as d
    assert "Conclusão revisada pelo servidor." in "\n".join(x.text for x in d.Document(io.BytesIO(docx.content)).paragraphs)
    pdf = requests.get(f"{u}/minutas/{m['id']}/exportar?formato=pdf", headers=H("senatran.servidor"))
    assert pdf.content[:4] == b"%PDF"
    assert requests.get(f"{u}/minutas/{m['id']}", headers=H("detran.servidor")).status_code == 404

    # grafo e auditoria
    g = requests.get(u + "/grafo", headers=H("senatran.servidor")).json()
    assert len(g["nos"]) == 7 and any(a["tipo"] == "REVOGA" for a in g["arestas"])
    ac = {e["acao"] for e in requests.get(u + "/auditoria", headers=H("senatran.servidor")).json()["eventos"]}
    assert {"DOCUMENTO_IMPORTADO", "PESQUISA", "MINUTA_GERADA", "MINUTA_EXPORTADA"} <= ac


def test_validacoes_de_entrada_e_erros(servidor):
    u, h = servidor, H("senatran.servidor")
    assert requests.post(u + "/pesquisa", headers=h, json={"pergunta": "x"}).status_code == 422
    assert requests.post(u + "/pesquisa", headers=h, json={"pergunta": "prazo da transferência", "data": "31/12/2024"}).status_code == 422
    assert requests.post(u + "/documentos", headers=h, data={"escopo": "NACIONAL", "texto": "Art. 1º Algo."}).status_code == 403
    assert requests.post(u + "/documentos", headers=h, data={"escopo": "INSTITUCIONAL_RESTRITO"}).status_code == 422
    assert requests.get(u + "/minutas/inexistente", headers=h).status_code == 404
    assert requests.get(u + "/documentos/..%2f..", headers=h).status_code == 404
    base = u.replace("/api/v1", "")
    esquema = requests.get(base + "/openapi.json").json()          # documentação OpenAPI gerada pelo FastAPI
    assert "/api/v1/pesquisa" in esquema["paths"] and "/api/v1/catalogo/importar" in esquema["paths"]
    assert requests.get(base + "/docs").status_code == 200
    r = requests.post(u + "/pesquisa", headers=h, json={"pergunta": "x"}).json()   # erro de validação no formato do projeto
    assert r["erro"]["codigo"] == "invalido" and r["erro"]["detalhes"][0]["campo"] == "pergunta"


def test_api_catalogo_proveniencia(servidor):
    import json, zipfile
    u = servidor
    cur, sen = H("curador"), H("senatran.servidor")
    assert len(requests.get(u + "/fontes", headers=sen).json()["fontes"]) >= 9
    itens = requests.get(u + "/catalogo", headers=sen).json()["itens"]
    assert {i["numero"] for i in itens} >= {"1032", "1019"}
    # pacote .zip por upload (multipart); servidor comum não pode
    buf = io.BytesIO()
    texto = ("RESOLUÇÃO CONTRAN Nº 1.019, DE 3 DE MARÇO DE 2025\n\nInstitui o Regimento Interno.\n\n"
             "Art. 1º Fica instituído o Regimento Interno das Câmaras Temáticas.\n\nArt. 2º Esta Resolução entra em vigor na data de sua publicação.\n")
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("manifesto.json", json.dumps({"itens": [{"tipo": "RESOLUCAO", "orgao_emissor": "CONTRAN", "numero": "1019", "ano": 2025,
                                                            "arquivo": "r1019.txt", "url_documento": "https://exemplo.gov.br/r1019.pdf"}]}))
        z.writestr("r1019.txt", texto)
    arq = {"pacote": ("lote.zip", buf.getvalue(), "application/zip")}
    assert requests.post(u + "/catalogo/importar", headers=sen, files=arq).status_code == 403
    r = requests.post(u + "/catalogo/importar", headers=cur, files={"pacote": ("lote.zip", buf.getvalue(), "application/zip")})
    assert r.status_code == 200 and r.json()["obtidos"] == 1, r.text
    rel = requests.get(u + "/catalogo/relatorio", headers=sen).json()
    assert rel["por_obtencao"]["OBTIDO"] == 1 and rel["por_obtencao"]["APENAS_INDICE"] == 5
    assert any("DOU" in x["faltando"][-1] for x in rel["documentos_sem_origem_completa"]) or rel["obtidos_sem_link_dou"]
    doc = next(d for d in requests.get(u + "/documentos", headers=sen).json()["documentos"] if d["numero"] == "1019")
    det = requests.get(f"{u}/documentos/{doc['id']}", headers=sen).json()["documento"]
    assert det["fonte_url"] == "https://exemplo.gov.br/r1019.pdf" and det["status_validacao"] == "PENDENTE" and det["formato_original"] == "txt"
    assert requests.post(f"{u}/documentos/{doc['id']}/validacao", headers=sen, json={"status": "CONFIRMADO"}).status_code == 403
    ok = requests.post(f"{u}/documentos/{doc['id']}/validacao", headers=cur, json={"status": "confirmado", "motivo": "conferido no DOU"})
    assert ok.status_code == 200 and ok.json()["status_validacao"] == "CONFIRMADO"
    # link de página geral recusado no upload de documento
    ruim = requests.post(u + "/documentos", headers=cur, data={"escopo": "NACIONAL", "texto": texto.replace("1.019", "1.500"),
                                                               "fonte_url": "https://www.in.gov.br/inicio"})
    assert ruim.status_code == 422


def test_api_historico_de_conversas(servidor):
    u = servidor
    q = {"pergunta": "prazo para transferência de propriedade", "data": "2024-06-01"}
    r1 = requests.post(u + "/pesquisa", headers=H("senatran.servidor"), json=q).json()
    cid = r1["conversa_id"]
    r2 = requests.post(u + "/pesquisa", headers=H("senatran.servidor"), json={**q, "conversa_id": cid}).json()
    assert r2["conversa_id"] == cid
    nova = requests.post(u + "/pesquisa", headers=H("senatran.servidor"), json=q).json()["conversa_id"]
    assert nova != cid
    lista = requests.get(u + "/conversas", headers=H("senatran.servidor")).json()["conversas"]
    assert {x["id"] for x in lista} == {cid, nova}
    cv = requests.get(f"{u}/conversas/{cid}", headers=H("senatran.servidor")).json()
    assert len(cv["mensagens"]) == 4 and cv["mensagens"][1]["conteudo"]["fontes"]
    # privada: outro usuário não vê, não anexa e não apaga
    assert requests.get(f"{u}/conversas/{cid}", headers=H("detran.servidor")).status_code == 404
    assert requests.post(u + "/pesquisa", headers=H("detran.servidor"), json={**q, "conversa_id": cid}).status_code == 404
    assert requests.delete(f"{u}/conversas/{cid}", headers=H("detran.servidor")).status_code == 404
    assert requests.delete(f"{u}/conversas/{cid}", headers=H("senatran.servidor")).status_code == 204
    assert requests.get(f"{u}/conversas/{cid}", headers=H("senatran.servidor")).status_code == 404
