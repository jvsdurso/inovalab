"""Produção assistida de minutas (Nota Técnica, Parecer, Despacho, Ofício...).

A minuta é SEMPRE rascunho editável. Em modo generativo o modelo redige as seções a partir das fontes
vigentes; em modo extrativo (sem LLM) o sistema monta a Fundamentação com os trechos literais e deixa
as seções analíticas como [A PREENCHER], sem fingir análise.
A seção "Referências" é gerada pelo sistema (não pelo modelo) a partir das fontes realmente utilizadas.
"""
from __future__ import annotations

import re

from ..auditoria import service as auditoria
from ..common.erros import invalido, nao_encontrado, proibido
from ..common.util import agora, br, dumps, hoje, loads, novo_id, row, rows, sha256
from ..db import Database
from ..ia import orquestrador as ia
from ..ia.providers import LLMProvider
from ..identidade.service import Contexto
from ..pesquisa import service as pesquisa
from .modelos import AVISO_IA, MODELOS, PLACEHOLDER, SECAO_REFERENCIAS


def tipos_disponiveis() -> list[dict]:
    return [{"tipo": k, "nome": v["nome"], "secoes": [{"id": i, "titulo": t} for i, t in v["secoes"]]} for k, v in MODELOS.items()]


def _referencias(fontes: list[dict], usadas: set[int] | None) -> str:
    linhas = []
    for f in fontes:
        if usadas is not None and f["n"] not in usadas:
            continue
        sit = {"VIGENTE": "vigente", "REVOGADO": "REVOGADO", "SUBSTITUIDO": "redação substituída", "NAO_INICIADA": "ainda não vigente"}.get(f["situacao"], f["situacao"])
        extra = f"; redação dada por {f['redacao_dada_por']}" if f["tipo_redacao"] == "ALTERACAO" and f["redacao_dada_por"] else ""
        fonte = f" Fonte: {f['fonte_url']}" if f.get("fonte_url") else ""
        versao = f", versão {f['versao_documento']} do documento" if f.get("versao_documento") else ""
        linhas.append(f"[{f['n']}] {f['rotulo']} — {f['ato']} ({sit} em {br(f.get('data_ref'))}{extra}{versao}).{fonte}")
    return "\n".join(linhas) or "Nenhuma fonte normativa utilizada."


def _fundamentacao_extrativa(fontes: list[dict]) -> str:
    vig = [f for f in fontes if f["situacao"] == "VIGENTE"]
    if not vig:
        return PLACEHOLDER + " (nenhum dispositivo vigente foi identificado para fundamentar)."
    return "\n\n".join(f"{f['rotulo']} da {f['ato']}: «{f['texto']}» [{f['n']}]" for f in vig)


def _secoes_extrativas(tipo: str, assunto: str, instrucoes: str, contexto: str, fontes: list[dict]) -> list[dict]:
    out = []
    for sid, titulo in MODELOS[tipo]["secoes"]:
        if sid in ("assunto", "referencia", "objetivo", "ementa"):
            txt = assunto
        elif sid == "fundamentacao":
            txt = _fundamentacao_extrativa(fontes)
        elif sid in ("relatorio", "historico", "desenvolvimento"):
            txt = contexto.strip() or PLACEHOLDER + " (descreva os fatos e o histórico do caso)."
        else:
            txt = PLACEHOLDER + (f" Instrução registrada: {instrucoes.strip()}" if instrucoes.strip() and sid in ("conclusao", "corpo", "manifestacao") else "")
        out.append({"id": sid, "titulo": titulo, "texto": txt})
    return out


def _parse_secoes_llm(texto: str, tipo: str) -> list[dict] | None:
    ids = [sid for sid, _ in MODELOS[tipo]["secoes"]]
    partes = re.split(r"(?m)^###\s*([a-z_]+)\s*$", texto)
    achados = {partes[i]: partes[i + 1].strip() for i in range(1, len(partes) - 1, 2)}
    if not any(i in achados for i in ids):
        return None
    return [{"id": sid, "titulo": t, "texto": achados.get(sid) or PLACEHOLDER} for sid, t in MODELOS[tipo]["secoes"]]


def gerar(db: Database, llm: LLMProvider, ctx: Contexto, *, tipo: str, assunto: str, instrucoes: str = "",
          contexto: str = "", data: str | None = None, pergunta: str | None = None, fonte_ids: list[str] | None = None,
          titulo: str | None = None, semelhanca=None, sim_min: float = 0.45) -> dict:
    tipo = tipo.upper()
    if tipo not in MODELOS:
        raise invalido(f"Tipo de documento inválido. Disponíveis: {', '.join(MODELOS)}.")
    if not assunto.strip():
        raise invalido("Informe o assunto da minuta.")
    data = data or hoje()
    if fonte_ids:
        fontes = pesquisa.evidencias_por_ids(db, ctx, fonte_ids, data)
        for i, f in enumerate(fontes, 1):
            f["n"] = i
        if not fontes:
            raise invalido("Nenhuma das fontes informadas está disponível para o seu perfil.")
    else:
        fontes = pesquisa.buscar(db, ctx, pergunta or f"{assunto} {instrucoes}", data, semelhanca=semelhanca, sim_min=sim_min)["fontes"]
    for f in fontes:
        f["data_ref"] = data
    modo, prompt_hash, uso = "extrativo", None, None
    secoes = None
    if llm.generativo and fontes:
        estrutura = "\n".join(f"### {sid}   ({t})" for sid, t in MODELOS[tipo]["secoes"])
        user = (f"Elabore a MINUTA de {MODELOS[tipo]['nome']} para a data de referência {data}.\n"
                f"Assunto: {assunto}\nInstruções do servidor: {instrucoes or '(nenhuma)'}\n"
                f"Fatos do caso informados pelo servidor (únicos fatos que podem ser afirmados):\n{contexto or '(nenhum informado)'}\n\n"
                f"Fontes:\n{ia.bloco_fontes(fontes)}\n\n"
                "Escreva cada seção sob um marcador de linha exatamente neste formato (uma linha só com o marcador, sem negrito):\n"
                f"{estrutura}\n\n"
                f"Regras adicionais: cite as fontes como [n] na fundamentação; para qualquer fato, nome, número de processo ou data que não tenha "
                f"sido informado, escreva {PLACEHOLDER}; não invente conclusões jurídicas — se a análise exigir juízo próprio, proponha-a e marque "
                "a necessidade de validação humana; use apenas fontes com situacao=\"VIGENTE\" para fundamentar.")
        prompt_hash = sha256((ia.SYSTEM_BASE + user).encode("utf-8"))
        r = llm.gerar(ia.SYSTEM_BASE, user, max_tokens=3500)
        secoes = _parse_secoes_llm(r.texto, tipo)
        modo, uso = r.provider, r.uso
        if secoes is None:
            secoes = _secoes_extrativas(tipo, assunto, instrucoes, contexto, fontes)
            secoes[0]["texto"] += "\n\n(Aviso: a resposta do modelo não pôde ser estruturada e foi descartada; seções montadas em modo extrativo.)"
            modo = "extrativo (resposta do modelo descartada)"
        texto_total = "\n".join(s["texto"] for s in secoes)
        verificacao = ia.verificar(texto_total, fontes)
    else:
        secoes = _secoes_extrativas(tipo, assunto, instrucoes, contexto, fontes)
        verificacao = {"citacoes_usadas": [f["n"] for f in fontes if f["situacao"] == "VIGENTE"], "citacoes_invalidas": [],
                       "trechos_literais_nao_verificados": [], "sem_citacoes": False}
    usadas = set(verificacao["citacoes_usadas"]) or None
    secoes.append({"id": SECAO_REFERENCIAS[0], "titulo": SECAO_REFERENCIAS[1], "texto": _referencias(fontes, usadas)})
    mid, t = novo_id(), agora()
    titulo = titulo or f"{MODELOS[tipo]['nome']} — {assunto[:80]}"
    with db.tx() as c:
        c.execute("INSERT INTO minuta(id,org_id,usuario_id,tipo,assunto,titulo,secoes,fontes,data_referencia,modo_geracao,status,criado_em,atualizado_em) "
                  "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (mid, ctx.org_id, ctx.usuario_id, tipo, assunto, titulo, dumps(secoes), dumps(fontes), data, modo, "RASCUNHO", t, t))
        ia.registrar_execucao(db, ctx, "MINUTA", llm, {"max_tokens": 3500}, prompt_hash, f"{tipo}: {assunto}", data,
                              [f["redacao_id"] for f in fontes], "\n\n".join(s["texto"] for s in secoes), verificacao)
        auditoria.registrar(db, ctx, "MINUTA_GERADA", "minuta", mid, {"tipo": tipo, "modo": modo, "fontes": len(fontes)})
    m = obter(db, ctx, mid)
    m["verificacao"] = verificacao
    m["aviso"] = AVISO_IA
    return m


def _de_row(r: dict) -> dict:
    r["secoes"] = loads(r["secoes"], [])
    r["fontes"] = loads(r["fontes"], [])
    return r


def obter(db: Database, ctx: Contexto, minuta_id: str) -> dict:
    r = row(db.conn().execute("SELECT * FROM minuta WHERE id=?", (minuta_id,)).fetchone())
    if not r or r["org_id"] != ctx.org_id:  # minutas são do órgão que as criou
        raise nao_encontrado("Minuta")
    return _de_row(r)


def listar(db: Database, ctx: Contexto) -> list[dict]:
    rs = rows(db.conn().execute(
        "SELECT m.id, m.tipo, m.titulo, m.assunto, m.status, m.modo_geracao, m.data_referencia, m.criado_em, m.atualizado_em, u.login AS autor "
        "FROM minuta m JOIN usuario u ON u.id=m.usuario_id WHERE m.org_id=? ORDER BY m.atualizado_em DESC", (ctx.org_id,)))
    return rs


def atualizar(db: Database, ctx: Contexto, minuta_id: str, titulo: str | None, secoes: list[dict] | None, status: str | None) -> dict:
    atual = obter(db, ctx, minuta_id)
    if status and status not in ("RASCUNHO", "EM_REVISAO", "APROVADA"):
        raise invalido("Status inválido.")
    if status == "APROVADA" and atual["usuario_id"] != ctx.usuario_id and ctx.perfil == "SERVIDOR":
        raise proibido("Somente o autor ou um administrador do órgão pode marcar a minuta como aprovada.")
    if secoes is not None:
        ids = {s["id"] for s in atual["secoes"]}
        novas = []
        for s in secoes:
            if s.get("id") not in ids:
                raise invalido(f"Seção desconhecida: {s.get('id')}")
            base = next(x for x in atual["secoes"] if x["id"] == s["id"])
            novas.append({"id": base["id"], "titulo": base["titulo"], "texto": str(s.get("texto", ""))})
        secoes_final = novas
    else:
        secoes_final = atual["secoes"]
    with db.tx() as c:
        c.execute("UPDATE minuta SET titulo=?, secoes=?, status=?, atualizado_em=? WHERE id=?",
                  (titulo or atual["titulo"], dumps(secoes_final), status or atual["status"], agora(), minuta_id))
        auditoria.registrar(db, ctx, "MINUTA_EDITADA", "minuta", minuta_id, {"status": status or atual["status"]})
    return obter(db, ctx, minuta_id)
