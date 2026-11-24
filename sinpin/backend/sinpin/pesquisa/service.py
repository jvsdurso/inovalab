"""Pesquisa normativa: recuperação respeitando permissões e vigência na data de referência.

Fluxo: (1) restringe aos documentos visíveis ao contexto; (2) ranqueia TODAS as redações (inclusive as
já encerradas), (3) classifica cada resultado como VIGENTE / REVOGADO / SUBSTITUIDO / NAO_INICIADA na
`data`, (4) devolve os vigentes como base de resposta e os não vigentes como ALERTA — para que a IA e o
usuário saibam que um dispositivo relevante foi alterado ou revogado, em vez de simplesmente não o ver.
"""
from __future__ import annotations

from ..common.util import br, hoje, loads, rows
from ..db import Database
from ..identidade.service import Contexto, sql_visivel
from ..normativo.caminhos import rotulo_de_caminho
from . import indice, vetorial

_SELECT = (
    "SELECT r.id AS redacao_id, r.texto, r.tipo AS tipo_redacao, r.valido_de, r.valido_ate, r.motivo_fim, "
    "r.encerrada_por_relacao_id, r.origem_documento_id, p.id AS dispositivo_id, p.caminho, p.nivel, "
    "d.id AS documento_id, d.titulo, d.ementa, d.escopo, d.sintetico, d.fonte_url, d.alertas, d.vigencia_inicio, "
    "d.url_origem, d.url_publicacao_dou, d.status_validacao, d.versao_atual "
    "FROM redacao r JOIN dispositivo p ON p.id=r.dispositivo_id JOIN documento d ON d.id=p.documento_id "
    "WHERE r.registrado_ate IS NULL AND "
)


def situacao(r: dict, data: str) -> str:
    if data < r["valido_de"]:
        return "NAO_INICIADA"
    if r["valido_ate"] is not None and data >= r["valido_ate"]:
        return r["motivo_fim"] or "ENCERRADA"
    return "VIGENTE"


def _montar(db: Database, selecionadas: list[dict], data: str) -> list[dict]:
    ids_docs = {r["origem_documento_id"] for r in selecionadas if r["origem_documento_id"]}
    rel_ids = [r["encerrada_por_relacao_id"] for r in selecionadas if r["encerrada_por_relacao_id"]]
    por_rel: dict[str, str] = {}
    if rel_ids:
        ph = ",".join("?" * len(rel_ids))
        por_rel = {x["id"]: x["origem_documento_id"] for x in db.conn().execute(
            f"SELECT id, origem_documento_id FROM relacao WHERE id IN ({ph})", rel_ids)}
        ids_docs |= set(por_rel.values())
    tit: dict[str, str] = {}
    if ids_docs:
        ph = ",".join("?" * len(ids_docs))
        tit = {x["id"]: x["titulo"] for x in db.conn().execute(f"SELECT id, titulo FROM documento WHERE id IN ({ph})", list(ids_docs))}
    out = []
    for i, r in enumerate(selecionadas, 1):
        out.append({
            "n": i, "redacao_id": r["redacao_id"], "dispositivo_id": r["dispositivo_id"], "documento_id": r["documento_id"],
            "ato": r["titulo"], "rotulo": rotulo_de_caminho(r["caminho"]), "caminho": r["caminho"], "texto": r["texto"],
            "situacao": situacao(r, data), "valido_de": r["valido_de"], "valido_ate": r["valido_ate"],
            "tipo_redacao": r["tipo_redacao"], "redacao_dada_por": tit.get(r["origem_documento_id"]),
            "encerrada_por": tit.get(por_rel.get(r["encerrada_por_relacao_id"])) if r["encerrada_por_relacao_id"] else None,
            "escopo": r["escopo"], "sintetico": bool(r["sintetico"]), "fonte_url": r["fonte_url"],
            "url_origem": r["url_origem"], "url_publicacao_dou": r["url_publicacao_dou"],
            "status_validacao": r["status_validacao"], "versao_documento": r["versao_atual"],
            "score": round(r.get("score", 0.0), 3),
        })
    return out


def buscar(db: Database, ctx: Contexto, consulta: str, data: str | None = None, k: int = 6, max_nao_vigentes: int = 3,
           semelhanca: vetorial.Semelhanca | None = None, sim_min: float = 0.45) -> dict:
    data = data or hoje()
    vis, params = sql_visivel(ctx, "d")
    todas = rows(db.conn().execute(_SELECT + vis, params))
    # Dispositivos que apenas "carregam" o texto novo de uma alteração (ex.: "passa a vigorar com a seguinte
    # redação: “…”") não são fonte normativa por si: o conteúdo relevante é a redação dada ao dispositivo alterado.
    veiculos = {(r["origem_documento_id"], r["origem_caminho"]) for r in db.conn().execute(
        "SELECT origem_documento_id, origem_caminho FROM relacao WHERE tipo='ALTERA' AND efeito_aplicado=1 AND texto_novo IS NOT NULL")}
    todas = [r for r in todas if (r["documento_id"], r["caminho"]) not in veiculos]
    caput: dict[tuple, str] = {}
    for r in todas:
        if r["nivel"] == "ARTIGO" and situacao(r, data) == "VIGENTE":
            caput[(r["documento_id"], r["caminho"])] = r["texto"]
    docs_busca = []
    for r in todas:
        art = r["caminho"].split(".")[0]
        ctx_art = caput.get((r["documento_id"], art), "") if r["nivel"] != "ARTIGO" else ""
        docs_busca.append(f'{r["titulo"]} {rotulo_de_caminho(r["caminho"])} {ctx_art} {r["texto"]}')
    scores = indice.ranquear(consulta, docs_busca) if todas else []
    if todas and semelhanca is not None:  # busca híbrida: BM25 + pgvector (permissão já aplicada na consulta vetorial)
        scores = vetorial.fundir([r["redacao_id"] for r in todas], scores, semelhanca(db, ctx, consulta), sim_min)
    for r, s in zip(todas, scores):
        r["score"] = s
        r["_sit"] = situacao(r, data)
    candidatas = sorted((r for r in todas if r["score"] > 0), key=lambda r: -r["score"])
    vigentes = [r for r in candidatas if r["_sit"] == "VIGENTE"][:k]
    topo = vigentes[0]["score"] if vigentes else (candidatas[0]["score"] if candidatas else 0)
    ids_v = {r["redacao_id"] for r in vigentes}
    nao_vig = [r for r in candidatas if r["redacao_id"] not in ids_v and r["_sit"] != "VIGENTE"
               and r["score"] >= 0.5 * topo][:max_nao_vigentes]
    fontes = _montar(db, vigentes + nao_vig, data)
    return {"consulta": consulta, "data": data, "fontes": fontes, "alertas": _alertas(db, ctx, fontes, todas, data)}


def evidencias_por_ids(db: Database, ctx: Contexto, redacao_ids: list[str], data: str | None = None) -> list[dict]:
    """Recarrega fontes já escolhidas (ex.: pesquisa anterior), reaplicando a regra de visibilidade."""
    data = data or hoje()
    if not redacao_ids:
        return []
    vis, params = sql_visivel(ctx, "d")
    ph = ",".join("?" * len(redacao_ids))
    rs = rows(db.conn().execute(_SELECT + vis + f" AND r.id IN ({ph})", [*params, *redacao_ids]))
    ordem = {rid: i for i, rid in enumerate(redacao_ids)}
    rs.sort(key=lambda r: ordem[r["redacao_id"]])
    return _montar(db, rs, data)


def _alertas(db: Database, ctx: Contexto, fontes: list[dict], todas: list[dict], data: str) -> list[dict]:
    al: list[dict] = []
    if not any(f["situacao"] == "VIGENTE" for f in fontes):
        al.append({"nivel": "atencao", "mensagem": "Nenhum dispositivo VIGENTE suficientemente relevante foi encontrado na base consultada."})
    for f in fontes:
        quem = f"{f['rotulo']} da {f['ato']}"
        if f["situacao"] == "VIGENTE" and f["tipo_redacao"] == "ALTERACAO":
            al.append({"nivel": "info", "mensagem": f"{quem}: redação vigente dada por {f['redacao_dada_por'] or 'ato modificador'} (desde {br(f['valido_de'])})."})
        elif f["situacao"] == "REVOGADO":
            al.append({"nivel": "atencao", "mensagem": f"{quem} foi REVOGADO em {br(f['valido_ate'])}{' por ' + f['encerrada_por'] if f['encerrada_por'] else ''}: não aplicável em {br(data)}."})
        elif f["situacao"] == "SUBSTITUIDO":
            al.append({"nivel": "atencao", "mensagem": f"{quem}: esta redação foi substituída em {br(f['valido_ate'])}{' por ' + f['encerrada_por'] if f['encerrada_por'] else ''}; não aplicável em {br(data)}."})
        elif f["situacao"] == "NAO_INICIADA":
            al.append({"nivel": "atencao", "mensagem": f"{quem}: só passa a vigorar em {br(f['valido_de'])}; não aplicável em {br(data)}."})
        if f["sintetico"]:
            msg = "Base de demonstração: documentos SINTÉTICOS (fictícios), não são normas reais."
            if not any(a["mensagem"] == msg for a in al):
                al.append({"nivel": "atencao", "mensagem": msg})
    nao_validados = sorted({f["ato"] for f in fontes if f["status_validacao"] != "CONFIRMADO" and not f["sintetico"]})
    if nao_validados:
        al.append({"nivel": "info", "mensagem": "Sem validação jurídica humana registrada: " + "; ".join(nao_validados)
                   + ". A presença no acervo não atesta, por si só, que o ato esteja vigente."})
    docs = {f["documento_id"] for f in fontes}
    if docs:
        ph = ",".join("?" * len(docs))
        vo, po = sql_visivel(ctx, "o")
        n = db.conn().execute(
            f"SELECT COUNT(*) AS n FROM relacao r JOIN documento o ON o.id=r.origem_documento_id WHERE r.status='SUGERIDA' "
            f"AND (r.origem_documento_id IN ({ph}) OR r.destino_documento_id IN ({ph})) AND {vo}", [*docs, *docs, *po]).fetchone()["n"]
        if n:
            al.append({"nivel": "atencao", "mensagem": f"Há {n} relação(ões) normativa(ões) pendente(s) de validação humana envolvendo os atos citados; a vigência apresentada pode estar incompleta."})
        ph2 = ",".join("?" * len(docs))
        for r in db.conn().execute(f"SELECT titulo, alertas FROM documento WHERE id IN ({ph2})", list(docs)):
            for a in loads(r["alertas"], []):
                if a.startswith("Possível instrução embutida"):
                    al.append({"nivel": "atencao", "mensagem": f"{r['titulo']}: {a}"})
    return al
