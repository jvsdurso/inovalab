"""Consultas de leitura do cadastro normativo (biblioteca / texto compilado / histórico)."""
from __future__ import annotations

from ..common.erros import nao_encontrado
from ..common.util import hoje, loads, row, rows
from ..db import Database
from ..identidade.service import Contexto, documento_visivel, sql_visivel
from . import repo
from .caminhos import chave_ordem, rotulo_de_caminho


def listar_documentos(db: Database, ctx: Contexto, q: str | None = None, tipo: str | None = None,
                      escopo: str | None = None, limite: int = 200) -> list[dict]:
    vis, params = sql_visivel(ctx, "d")
    where, args = [vis], list(params)
    if q:
        where.append("(LOWER(d.titulo) LIKE ? OR LOWER(COALESCE(d.ementa,'')) LIKE ?)")
        args += [f"%{q.lower()}%", f"%{q.lower()}%"]
    if tipo:
        where.append("d.tipo=?")
        args.append(tipo)
    if escopo:
        where.append("d.escopo=?")
        args.append(escopo)
    sql = (
        "SELECT d.id, d.escopo, d.org_id, o.sigla AS orgao, d.tipo, d.numero, d.ano, d.titulo, d.ementa, "
        "d.data_publicacao, d.vigencia_inicio, d.vigencia_fim, d.sintetico, d.versao_atual, d.alertas, "
        "(SELECT COUNT(*) FROM dispositivo p WHERE p.documento_id=d.id) AS n_dispositivos "
        f"FROM documento d JOIN orgao o ON o.id=d.org_id WHERE {' AND '.join(where)} "
        "ORDER BY COALESCE(d.data_publicacao,'') DESC, d.titulo LIMIT ?"
    )
    out = rows(db.conn().execute(sql, [*args, limite]))
    ref = hoje()
    for d in out:
        d["alertas"] = loads(d["alertas"], [])
        d["situacao"] = situacao_documento(d, ref)
    return out


def situacao_documento(doc: dict, data: str) -> str:
    ini, fim = doc.get("vigencia_inicio"), doc.get("vigencia_fim")
    if ini and data < ini:
        return "NAO_INICIADA"
    if fim and data >= fim:
        return "REVOGADA"
    return "VIGENTE"


def obter_documento_visivel(db: Database, ctx: Contexto, doc_id: str) -> dict:
    if not documento_visivel(db, ctx, doc_id):
        raise nao_encontrado("Documento")
    d = repo.obter_documento(db, doc_id)
    if not d:
        raise nao_encontrado("Documento")
    d["alertas"] = loads(d["alertas"], [])
    return d


def _titulos(db: Database, ids: set[str]) -> dict[str, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    ph = ",".join("?" * len(ids))
    return {r["id"]: r["titulo"] for r in db.conn().execute(f"SELECT id, titulo FROM documento WHERE id IN ({ph})", list(ids))}


def compilado(db: Database, ctx: Contexto, doc_id: str, data: str | None = None) -> dict:
    """Texto do documento como vigorava em `data` (tempo VÁLIDO), com marcas de alteração/revogação."""
    doc = obter_documento_visivel(db, ctx, doc_id)
    data = data or hoje()
    rs = rows(db.conn().execute(
        "SELECT p.id AS dispositivo_id, p.caminho, p.nivel, p.grupo, r.id AS redacao_id, r.tipo AS tipo_redacao, r.texto, "
        "r.valido_de, r.valido_ate, r.motivo_fim, r.origem_documento_id, r.encerrada_por_relacao_id "
        "FROM dispositivo p JOIN redacao r ON r.dispositivo_id=p.id "
        "WHERE p.documento_id=? AND r.registrado_ate IS NULL ORDER BY r.valido_de", (doc_id,)))
    por_disp: dict[str, list[dict]] = {}
    for r in rs:
        por_disp.setdefault(r["dispositivo_id"], []).append(r)
    rel_origem = {r["id"]: r["origem_documento_id"] for r in db.conn().execute(
        "SELECT id, origem_documento_id FROM relacao WHERE destino_documento_id=?", (doc_id,))}
    tit = _titulos(db, {r["origem_documento_id"] for r in rs} | set(rel_origem.values()))
    itens = []
    for did, lista in por_disp.items():
        base = lista[0]
        escolhida, situacao = None, None
        for r in lista:
            if r["valido_de"] <= data and (r["valido_ate"] is None or r["valido_ate"] > data):
                escolhida, situacao = r, "VIGENTE"
                break
        if escolhida is None:
            if all(r["valido_de"] > data for r in lista):
                escolhida, situacao = lista[0], "NAO_INICIADA"
            else:
                escolhida = [r for r in lista if r["valido_de"] <= data][-1]
                situacao = escolhida["motivo_fim"] or "ENCERRADA"
        enc_por = tit.get(rel_origem.get(escolhida["encerrada_por_relacao_id"])) if escolhida["encerrada_por_relacao_id"] else None
        itens.append({
            "dispositivo_id": did, "caminho": base["caminho"], "rotulo": rotulo_de_caminho(base["caminho"]),
            "nivel": base["nivel"], "grupo": base["grupo"], "texto": escolhida["texto"], "situacao": situacao,
            "tipo_redacao": escolhida["tipo_redacao"], "valido_de": escolhida["valido_de"],
            "valido_ate": escolhida["valido_ate"], "n_redacoes": len(lista),
            "redacao_dada_por": tit.get(escolhida["origem_documento_id"]),
            "encerrada_por": enc_por,
        })
    itens.sort(key=lambda i: chave_ordem(i["caminho"]))
    return {"documento": {k: doc[k] for k in ("id", "titulo", "tipo", "numero", "ano", "escopo", "vigencia_inicio", "vigencia_fim")},
            "data": data, "situacao": situacao_documento(doc, data), "dispositivos": itens}


def historico_dispositivo(db: Database, ctx: Contexto, disp_id: str) -> dict:
    d = repo.obter_dispositivo(db, disp_id)
    if not d or not documento_visivel(db, ctx, d["documento_id"]):
        raise nao_encontrado("Dispositivo")
    reds = rows(db.conn().execute(
        "SELECT id, tipo, texto, valido_de, valido_ate, motivo_fim, origem_documento_id, registrado_em, registrado_ate, versao_doc "
        "FROM redacao WHERE dispositivo_id=? ORDER BY valido_de, registrado_em", (disp_id,)))
    tit = _titulos(db, {r["origem_documento_id"] for r in reds})
    for r in reds:
        r["redacao_dada_por"] = tit.get(r["origem_documento_id"])
    return {"dispositivo_id": disp_id, "documento_id": d["documento_id"], "caminho": d["caminho"],
            "rotulo": rotulo_de_caminho(d["caminho"]), "redacoes": reds}
