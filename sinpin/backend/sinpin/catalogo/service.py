"""Catálogo do acervo e proveniência documental.

Regras (definição do acervo):
 - Cada documento guarda TRÊS endereços distintos: do documento individual, da página de origem e da publicação no DOU.
 - Endereço de página geral (índice, portal, home do DOU) NUNCA é aceito como link de documento individual.
 - Referência obtida só de índice (APENAS_INDICE) é registrada como tal: não tem texto nem efeito jurídico.
 - Relações informadas por índice são HIPÓTESES; só viram relação quando o texto do ato as declara (e são conferidas aqui).
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

from ..auditoria import service as auditoria
from ..common.erros import invalido, proibido
from ..common.util import agora, dumps, loads, novo_id, row, rows, valida_data
from ..db import Database
from ..identidade.service import Contexto, sql_visivel
from ..normativo.tipos import ESCOPO_NACIONAL, TIPOS_RELACAO, canon_tipo, montar_titulo, norm_numero

STATUS_OBTENCAO = ("OBTIDO", "APENAS_INDICE", "PENDENTE", "FALHA")
STATUS_VALIDACAO = ("CONFIRMADO", "PENDENTE", "CONTROVERTIDO", "REJEITADO")
# funções de fonte que são páginas GERAIS (não podem ser o link de um documento individual)
_GERAIS = ("INDICE", "PUBLICACAO", "PESQUISA", "MONITORAMENTO", "INSTITUCIONAL")
SEED = Path(__file__).resolve().parent.parent / "seed"


# ------------------------------------------------------------------ URLs
def _chave_url(u: str) -> str:
    p = urlparse(u.strip())
    return f"{p.scheme.lower()}://{p.netloc.lower()}{p.path.rstrip('/')}" + (f"?{p.query}" if p.query else "")


def _paginas_gerais(db: Database) -> set[str]:
    ph = ",".join("?" * len(_GERAIS))
    return {_chave_url(r["url"]) for r in db.conn().execute(f"SELECT url FROM fonte WHERE funcao IN ({ph})", _GERAIS)}


def _url(valor, campo: str) -> str | None:
    if valor is None or not str(valor).strip():
        return None
    v = str(valor).strip()
    p = urlparse(v)
    if p.scheme not in ("http", "https") or not p.netloc:
        raise invalido(f"{campo} deve ser um endereço http(s) completo (recebido: {v[:80]!r}).")
    return v


def normalizar_origem(db: Database, dados: dict) -> tuple[dict, list[str]]:
    """Valida e normaliza os campos de proveniência. Levanta erro para violações; devolve avisos para suspeitas."""
    avisos: list[str] = []
    out: dict = {}
    for campo in ("url_documento", "url_origem", "url_publicacao_dou"):
        out[campo] = _url(dados.get(campo), campo)
    gerais = _paginas_gerais(db)
    for campo in ("url_documento", "url_publicacao_dou"):
        if out[campo] and _chave_url(out[campo]) in gerais:
            raise invalido(f"{campo} é o endereço de uma página geral (índice/portal/DOU) cadastrada como fonte. "
                           "Informe o endereço do documento individual ou deixe em branco.")
    if out["url_publicacao_dou"] and "in.gov.br" not in urlparse(out["url_publicacao_dou"]).netloc.lower():
        avisos.append("url_publicacao_dou não aponta para in.gov.br; confirme que é a edição do DOU.")
    iguais = [(a, b) for a, b in (("url_documento", "url_origem"), ("url_documento", "url_publicacao_dou"), ("url_origem", "url_publicacao_dou"))
              if out[a] and out[b] and _chave_url(out[a]) == _chave_url(out[b])]
    for a, b in iguais:
        avisos.append(f"{a} e {b} são idênticos; esses endereços costumam ser diferentes. Confira.")
    for campo in ("data_assinatura", "data_publicacao", "capturado_em"):
        v = dados.get(campo)
        if v:
            ok = valida_data(str(v)[:10])
            if not ok:
                avisos.append(f"{campo} inválida (use AAAA-MM-DD); ignorada.")
            out[campo] = str(v) if campo == "capturado_em" and ok else ok
    so = dados.get("status_obtencao")
    sv = dados.get("status_validacao")
    if so:
        if so not in STATUS_OBTENCAO:
            raise invalido(f"status_obtencao deve ser um de: {', '.join(STATUS_OBTENCAO)}.")
        out["status_obtencao"] = so
    if sv:
        if sv not in STATUS_VALIDACAO:
            raise invalido(f"status_validacao deve ser um de: {', '.join(STATUS_VALIDACAO)}.")
        out["status_validacao"] = sv
    return out, avisos


# ------------------------------------------------------------------ fontes oficiais
def semear_fontes(db: Database) -> int:
    n = 0
    for f in json.loads((SEED / "fontes_oficiais.json").read_text(encoding="utf-8")):
        cur = db.conn().execute(
            "INSERT OR IGNORE INTO fonte(id,nome,url,funcao,utilizacao,nota,registrado_em) VALUES (?,?,?,?,?,?,?)",
            (f["id"], f["nome"], f["url"], f["funcao"], f.get("utilizacao"), f.get("nota"), agora()))
        n += cur.rowcount
    return n


def listar_fontes(db: Database) -> list[dict]:
    return rows(db.conn().execute("SELECT * FROM fonte ORDER BY funcao, nome"))


# ------------------------------------------------------------------ itens do catálogo
def _relacoes_indice(lista) -> list[dict]:
    out = []
    for h in lista or []:
        if not isinstance(h, dict):
            raise invalido("relacoes_indice deve ser uma lista de objetos.")
        tipo = str(h.get("tipo", "")).upper()
        if tipo not in TIPOS_RELACAO:
            raise invalido(f"relacoes_indice: tipo inválido ({tipo!r}). Use um de: {', '.join(TIPOS_RELACAO)}.")
        num = norm_numero(str(h["numero"])) if h.get("numero") else None
        out.append({"tipo": tipo, "alvo_tipo": canon_tipo(h.get("alvo_tipo")) if h.get("alvo_tipo") else None,
                    "numero": num, "ano": int(h["ano"]) if h.get("ano") else None,
                    "observacao": (str(h["observacao"])[:500] if h.get("observacao") else None)})
    return out


def _achar_doc_nacional(db: Database, tipo: str, numero: str, ano: int, emissor: str | None) -> dict | None:
    return row(db.conn().execute(
        "SELECT * FROM documento WHERE escopo=? AND tipo=? AND numero=? AND ano=? AND (?='' OR orgao_emissor IS NULL OR orgao_emissor=?)",
        (ESCOPO_NACIONAL, tipo, numero, ano, emissor or "", emissor or "")).fetchone())


def registrar_item(db: Database, ctx: Contexto, dados: dict, *, auditar: bool = True) -> dict:
    """Cria/atualiza um item do catálogo (identidade: tipo+número+ano+emissor). Nunca rebaixa um item já OBTIDO."""
    if not ctx.curador_nacional:
        raise proibido("Somente a curadoria nacional pode registrar itens no catálogo do acervo nacional.")
    tipo = canon_tipo(dados.get("tipo"))
    numero = norm_numero(str(dados["numero"])) if dados.get("numero") else None
    if not numero or not dados.get("ano"):
        raise invalido("Item do catálogo exige tipo, número e ano.")
    try:
        ano = int(dados["ano"])
    except (TypeError, ValueError):
        raise invalido("ano inválido.")
    emissor = (dados.get("orgao_emissor") or "").strip().upper() or None
    o, avisos = normalizar_origem(db, dados)
    rels = _relacoes_indice(dados.get("relacoes_indice"))
    titulo = dados.get("titulo") or montar_titulo(tipo, emissor, numero, ano)
    agora_ = agora()
    with db.tx() as c:
        ex = row(c.execute("SELECT * FROM catalogo_item WHERE tipo=? AND numero=? AND ano=? AND COALESCE(orgao_emissor,'')=?",
                           (tipo, numero, ano, emissor or "")).fetchone())
        if ex:
            campos = {k: v for k, v in o.items() if k in ("url_documento", "url_origem", "url_publicacao_dou", "data_assinatura", "data_publicacao",
                                                           "status_validacao") and v}
            # status_obtencao nunca regride a partir de OBTIDO
            if o.get("status_obtencao") and ex["status_obtencao"] != "OBTIDO":
                campos["status_obtencao"] = o["status_obtencao"]
            if dados.get("observacao"):
                campos["observacao"] = str(dados["observacao"])[:1000]
            if rels:
                antigos = loads(ex["relacoes_indice"], [])
                campos["relacoes_indice"] = dumps(antigos + [r for r in rels if r not in antigos])
            if dados.get("titulo"):
                campos["titulo"] = titulo
            campos["atualizado_em"] = agora_
            sets = ", ".join(f"{k}=?" for k in campos)
            c.execute(f"UPDATE catalogo_item SET {sets} WHERE id=?", [*campos.values(), ex["id"]])
            item_id, criado = ex["id"], False
        else:
            item_id, criado = novo_id(), True
            c.execute(
                "INSERT INTO catalogo_item(id,tipo,numero,ano,orgao_emissor,titulo,url_documento,url_origem,url_publicacao_dou,data_assinatura,"
                "data_publicacao,status_obtencao,status_validacao,relacoes_indice,observacao,registrado_em,atualizado_em) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (item_id, tipo, numero, ano, emissor, titulo, o.get("url_documento"), o.get("url_origem"), o.get("url_publicacao_dou"),
                 o.get("data_assinatura"), o.get("data_publicacao"), o.get("status_obtencao") or "APENAS_INDICE",
                 o.get("status_validacao") or "PENDENTE", dumps(rels), (str(dados["observacao"])[:1000] if dados.get("observacao") else None),
                 agora_, agora_))
        doc = _achar_doc_nacional(db, tipo, numero, ano, emissor)
        if doc:
            _ligar(db, item_id, doc)
        if auditar:
            auditoria.registrar(db, ctx, "CATALOGO_ITEM_REGISTRADO" if criado else "CATALOGO_ITEM_ATUALIZADO", "catalogo_item", item_id,
                                {"titulo": titulo, "status_obtencao": o.get("status_obtencao")})
    item = obter_item(db, item_id)
    item["avisos"] = avisos
    return item


def _ligar(db: Database, item_id: str, doc: dict) -> None:
    """Liga item <-> documento obtido; completa lacunas de proveniência nos dois sentidos (sem sobrescrever)."""
    c = db.conn()
    it = row(c.execute("SELECT * FROM catalogo_item WHERE id=?", (item_id,)).fetchone())
    c.execute("UPDATE catalogo_item SET documento_id=?, status_obtencao='OBTIDO', "
              "url_documento=COALESCE(url_documento,?), url_origem=COALESCE(url_origem,?), url_publicacao_dou=COALESCE(url_publicacao_dou,?), "
              "data_assinatura=COALESCE(data_assinatura,?), data_publicacao=COALESCE(data_publicacao,?), atualizado_em=? WHERE id=?",
              (doc["id"], doc.get("fonte_url"), doc.get("url_origem"), doc.get("url_publicacao_dou"), doc.get("data_assinatura"),
               doc.get("data_publicacao"), agora(), item_id))
    c.execute("UPDATE documento SET fonte_url=COALESCE(fonte_url,?), url_origem=COALESCE(url_origem,?), "
              "url_publicacao_dou=COALESCE(url_publicacao_dou,?), data_assinatura=COALESCE(data_assinatura,?) WHERE id=?",
              (it["url_documento"], it["url_origem"], it["url_publicacao_dou"], it["data_assinatura"], doc["id"]))


def vincular_documento(db: Database, doc: dict) -> None:
    """Chamado pela ingestão: se o documento NACIONAL já constava do catálogo, marca-o como OBTIDO e liga os dois."""
    if doc["escopo"] != ESCOPO_NACIONAL or not doc.get("numero") or not doc.get("ano"):
        return
    it = row(db.conn().execute(
        "SELECT id FROM catalogo_item WHERE tipo=? AND numero=? AND ano=? AND (orgao_emissor IS NULL OR ?='' OR orgao_emissor=?)",
        (doc["tipo"], doc["numero"], doc["ano"], doc.get("orgao_emissor") or "", doc.get("orgao_emissor") or "")).fetchone())
    if it:
        _ligar(db, it["id"], doc)
    elif not doc.get("sintetico"):  # obtido sem passar por índice: entra no catálogo (dados sintéticos de demonstração, não)
        db.conn().execute(
            "INSERT OR IGNORE INTO catalogo_item(id,tipo,numero,ano,orgao_emissor,titulo,url_documento,url_origem,url_publicacao_dou,data_assinatura,"
            "data_publicacao,status_obtencao,status_validacao,documento_id,registrado_em,atualizado_em) VALUES (?,?,?,?,?,?,?,?,?,?,?,'OBTIDO',?,?,?,?)",
            (novo_id(), doc["tipo"], doc["numero"], doc["ano"], doc.get("orgao_emissor"), doc["titulo"], doc.get("fonte_url"), doc.get("url_origem"),
             doc.get("url_publicacao_dou"), doc.get("data_assinatura"), doc.get("data_publicacao"), doc.get("status_validacao") or "PENDENTE",
             doc["id"], agora(), agora()))


def obter_item(db: Database, item_id: str) -> dict:
    r = row(db.conn().execute("SELECT * FROM catalogo_item WHERE id=?", (item_id,)).fetchone())
    return _enriquecer(db, r)


def _enriquecer(db: Database, r: dict) -> dict:
    r["relacoes_indice"] = loads(r["relacoes_indice"], [])
    r["conferencia"] = _conferir(db, r)
    return r


def _conferir(db: Database, item: dict) -> list[dict]:
    """Confronta cada hipótese do índice com o que o TEXTO do ato obtido efetivamente declara."""
    out = []
    for h in item["relacoes_indice"]:
        base = {**h}
        if not item["documento_id"]:
            out.append({**base, "resultado": "SEM_TEXTO"})
            continue
        if not h.get("numero"):
            out.append({**base, "resultado": "NAO_VERIFICAVEL"})
            continue
        tipos = ("REVOGA", "REVOGA_PARCIALMENTE") if h["tipo"] == "REVOGA" else (h["tipo"],)
        ph = ",".join("?" * len(tipos))
        sql = f"SELECT status FROM relacao WHERE origem_documento_id=? AND tipo IN ({ph}) AND destino_numero=?"
        args = [item["documento_id"], *tipos, h["numero"]]
        if h.get("ano"):
            sql += " AND (destino_ano=? OR destino_ano IS NULL)"
            args.append(h["ano"])
        st = {r["status"] for r in db.conn().execute(sql, args)}
        res = ("CONFIRMADA_NO_TEXTO" if "CONFIRMADA" in st else "DETECTADA_PENDENTE" if "SUGERIDA" in st
               else "REJEITADA" if st else "NAO_ENCONTRADA_NO_TEXTO")
        out.append({**base, "resultado": res})
    return out


def listar(db: Database, ctx: Contexto, status_obtencao: str | None = None, q: str | None = None) -> list[dict]:
    where, args = ["1=1"], []
    if status_obtencao:
        where.append("status_obtencao=?")
        args.append(status_obtencao)
    if q:
        where.append("(LOWER(titulo) LIKE ? OR numero LIKE ? OR LOWER(COALESCE(observacao,'')) LIKE ?)")
        args += [f"%{q.lower()}%", f"%{q}%", f"%{q.lower()}%"]
    rs = rows(db.conn().execute(
        f"SELECT * FROM catalogo_item WHERE {' AND '.join(where)} ORDER BY ano DESC, CAST(numero AS INTEGER) DESC", args))
    return [_enriquecer(db, r) for r in rs]


def relatorio(db: Database, ctx: Contexto) -> dict:
    """Relatório de pendências do acervo: ausentes, sem proveniência completa, sem validação e divergências do índice."""
    itens = listar(db, ctx)
    por_obt = {s: 0 for s in STATUS_OBTENCAO}
    por_val = {s: 0 for s in STATUS_VALIDACAO}
    for i in itens:
        por_obt[i["status_obtencao"]] += 1
        por_val[i["status_validacao"]] += 1
    resumo = lambda i: {"id": i["id"], "titulo": i["titulo"], "status_obtencao": i["status_obtencao"], "observacao": i["observacao"]}
    ausentes = [resumo(i) for i in itens if i["status_obtencao"] != "OBTIDO"]
    sem_url = [resumo(i) for i in itens if i["status_obtencao"] == "OBTIDO" and not i["url_documento"]]
    sem_dou = [resumo(i) for i in itens if i["status_obtencao"] == "OBTIDO" and not i["url_publicacao_dou"]]
    diverg = [{"item_id": i["id"], "titulo": i["titulo"], "hipotese": h} for i in itens for h in i["conferencia"]
              if h["resultado"] in ("NAO_ENCONTRADA_NO_TEXTO", "REJEITADA")]
    vis, par = sql_visivel(ctx, "d")
    docs_sem_origem = rows(db.conn().execute(
        f"SELECT d.id, d.titulo, d.escopo, d.fonte_url, d.url_publicacao_dou FROM documento d WHERE {vis} AND d.sintetico=0 "
        "AND (d.fonte_url IS NULL OR d.url_publicacao_dou IS NULL) ORDER BY d.titulo", par))
    for d in docs_sem_origem:
        d["faltando"] = [n for n, v in (("link do documento", d.pop("fonte_url")), ("link da publicação no DOU", d.pop("url_publicacao_dou"))) if not v]
    return {"total_itens": len(itens), "por_obtencao": por_obt, "por_validacao": por_val, "ausentes_ou_pendentes": ausentes,
            "obtidos_sem_link_documento": sem_url, "obtidos_sem_link_dou": sem_dou, "divergencias_do_indice": diverg,
            "documentos_sem_origem_completa": docs_sem_origem}


def semear_catalogo_inicial(db: Database, ctx: Contexto) -> int:
    d = json.loads((SEED / "catalogo_inicial.json").read_text(encoding="utf-8"))
    fonte = row(db.conn().execute("SELECT url FROM fonte WHERE id=?", (d.get("fonte_origem"),)).fetchone())
    n = 0
    for it in d["itens"]:
        existe = db.conn().execute("SELECT 1 FROM catalogo_item WHERE tipo=? AND numero=? AND ano=?",
                                   (canon_tipo(it["tipo"]), norm_numero(it["numero"]), it["ano"])).fetchone()
        if existe:
            continue
        dados = dict(it)
        if fonte:
            dados["url_origem"] = fonte["url"]
            dados["observacao"] = " ".join(x for x in (it.get("observacao"), d.get("nota_origem")) if x)
        registrar_item(db, ctx, dados, auditar=False)
        n += 1
    return n
