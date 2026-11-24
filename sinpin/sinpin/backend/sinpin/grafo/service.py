"""Grafo normativo: registro das relações detectadas, resolução de destinos, validação humana e consulta.

Políticas:
 - Só há relação quando o texto a declara. Nada de "norma mais nova revoga a mais antiga".
 - Confiança >= limiar (config) e destino resolvido sem ambiguidade -> CONFIRMADA automaticamente
   (com origem_deteccao='AUTO', reversível). Caso contrário -> SUGERIDA (não produz efeito).
 - Resolução de destino respeita a audiência: ato NACIONAL só referencia atos NACIONAIS;
   ato institucional referencia NACIONAIS ou do próprio órgão.
"""
from __future__ import annotations

from ..auditoria import service as auditoria
from ..common.erros import invalido, nao_encontrado, proibido
from ..common.util import agora, hoje, rows, valida_data
from ..db import Database
from ..identidade.service import Contexto, documento_visivel, sql_visivel
from ..normativo import repo
from ..normativo.caminhos import rotulo_de_caminho
from ..normativo.parser import DispositivoP, fragmento_para_dispositivos
from ..normativo.tipos import ESCOPO_NACIONAL
from ..vigencia import efeitos
from . import repo as grepo
from .detector import Detectada, detectar

TIPOS_INFORMATIVOS = ("REGULAMENTA", "COMPLEMENTA", "CONSOLIDA", "SUSPENDE", "RESTABELECE")


def candidatos_destino(db: Database, origem: dict, tipo: str, numero: str | None, ano: int | None,
                       emissor: str | None) -> list[dict]:
    if not numero:
        return []
    sql = "SELECT * FROM documento WHERE tipo=? AND numero=? AND id<>?"
    args: list = [tipo, numero, origem["id"]]
    if ano:
        sql += " AND ano=?"
        args.append(ano)
    cands = rows(db.conn().execute(sql, args))
    if origem["escopo"] == ESCOPO_NACIONAL:
        cands = [d for d in cands if d["escopo"] == ESCOPO_NACIONAL]
    else:
        cands = [d for d in cands if d["escopo"] == ESCOPO_NACIONAL or d["org_id"] == origem["org_id"]]
    if emissor:
        iguais = [d for d in cands if (d["orgao_emissor"] or "") == emissor]
        cands = iguais or cands
    cands.sort(key=lambda d: (d["escopo"] != ESCOPO_NACIONAL, d["registrado_em"]))
    return cands


def _avaliar(db: Database, rel: dict, destino: dict | None, ambiguo: bool) -> tuple[float, str | None]:
    """(confiança, motivo para não confirmar automaticamente)"""
    if destino is None:
        return 0.4, "Ato referido não encontrado no repositório; importe-o ou associe manualmente."
    if ambiguo:
        return 0.6, "Mais de um ato corresponde à referência; confirme qual é o destino."
    tipo, caminho = rel["tipo"], rel.get("destino_caminho")
    if tipo in TIPOS_INFORMATIVOS:
        return 0.82, None
    if tipo == "REVOGA":
        return 0.9, None
    existe = bool(caminho) and repo.dispositivo_por_caminho(db, destino["id"], caminho) is not None
    if tipo == "REVOGA_PARCIALMENTE":
        return (0.9, None) if existe else (0.55, "Dispositivo revogado não localizado no ato de destino.")
    if tipo == "ALTERA":
        if not caminho:
            return 0.6, "Alteração sem dispositivo-alvo identificado."
        if not rel.get("texto_novo"):
            return 0.6, "Texto novo da alteração não identificado."
        if not fragmento_para_dispositivos(rel["texto_novo"], caminho):
            return 0.55, "O texto novo não corresponde ao dispositivo-alvo."
        return 0.9, None
    return 0.5, None


def _inserir_detectada(db: Database, origem: dict, det: Detectada, limiar: float) -> str:
    cands = candidatos_destino(db, origem, det.destino_tipo, det.destino_numero, det.destino_ano, det.destino_emissor)
    destino = cands[0] if cands else None
    rel = {
        "tipo": det.tipo, "origem_documento_id": origem["id"], "origem_caminho": det.origem_caminho,
        "destino_documento_id": destino["id"] if destino else None, "destino_caminho": det.destino_caminho,
        "destino_tipo": det.destino_tipo, "destino_numero": det.destino_numero, "destino_ano": det.destino_ano,
        "destino_emissor": det.destino_emissor, "destino_ref": det.destino_ref,
        "data_efeito": origem.get("vigencia_inicio") or origem.get("data_publicacao"),
        "texto_novo": det.texto_novo, "evidencia": det.evidencia, "origem_deteccao": "AUTO",
    }
    conf, motivo = _avaliar(db, rel, destino, len(cands) > 1)
    rel["confianca"] = conf
    rel["status"] = "CONFIRMADA" if conf >= limiar else "SUGERIDA"
    rel["nota_efeito"] = motivo
    rid = grepo.inserir(db, rel)
    grepo.historico_inserir(db, rid, None, rel["status"], None, "Detecção automática (confiança %.2f)" % conf)
    return rid


def detectar_e_registrar(db: Database, origem: dict, dispositivos: list[DispositivoP], limiar: float) -> set[str]:
    """Detecta as relações de `origem`, substitui as automáticas anteriores e devolve os destinos a recalcular."""
    afetados = grepo.apagar_automaticas_do_documento(db, origem["id"])
    for det in detectar(origem.get("ementa"), dispositivos):
        rid = _inserir_detectada(db, origem, det, limiar)
        r = grepo.obter(db, rid)
        if r["destino_documento_id"]:
            afetados.add(r["destino_documento_id"])
    return afetados


def resolver_pendentes(db: Database, novo: dict, limiar: float) -> set[str]:
    """Um ato acabou de ser importado: resolve referências que aguardavam por ele (ordem de importação irrelevante)."""
    afetados: set[str] = set()
    for rel in grepo.pendentes_para_resolver(db, novo["tipo"], novo["numero"]):
        if rel["destino_ano"] and novo["ano"] and rel["destino_ano"] != novo["ano"]:
            continue
        origem = repo.obter_documento(db, rel["origem_documento_id"])
        cands = candidatos_destino(db, origem, rel["destino_tipo"], rel["destino_numero"], rel["destino_ano"], rel["destino_emissor"])
        if not cands:
            continue
        destino = cands[0]
        rel["destino_documento_id"] = destino["id"]
        conf, motivo = _avaliar(db, rel, destino, len(cands) > 1)
        status = "CONFIRMADA" if conf >= limiar else "SUGERIDA"
        db.conn().execute("UPDATE relacao SET destino_documento_id=?, confianca=?, status=?, nota_efeito=? WHERE id=?",
                          (destino["id"], conf, status, motivo, rel["id"]))
        grepo.historico_inserir(db, rel["id"], rel["status"], status, None, "Destino resolvido após importação de %s" % novo["titulo"])
        afetados.add(destino["id"])
    return afetados


# ------------------------------------------------------------------ consulta
def _enriquecer(r: dict) -> dict:
    r["origem_rotulo"] = rotulo_de_caminho(r["origem_caminho"]) if r.get("origem_caminho") else None
    r["destino_rotulo"] = rotulo_de_caminho(r["destino_caminho"]) if r.get("destino_caminho") else None
    r["pendente_validacao"] = r["status"] == "SUGERIDA"
    return r


def listar(db: Database, ctx: Contexto, status: str | None = None, documento_id: str | None = None,
           limite: int = 500) -> list[dict]:
    vo, po = sql_visivel(ctx, "o")
    vd, pd = sql_visivel(ctx, "dd")
    where = [vo, f"(r.destino_documento_id IS NULL OR {vd})"]
    args = [*po, *pd]
    if status:
        where.append("r.status=?")
        args.append(status)
    if documento_id:
        where.append("(r.origem_documento_id=? OR r.destino_documento_id=?)")
        args += [documento_id, documento_id]
    sql = ("SELECT r.*, o.titulo AS origem_titulo, dd.titulo AS destino_titulo FROM relacao r "
           "JOIN documento o ON o.id=r.origem_documento_id LEFT JOIN documento dd ON dd.id=r.destino_documento_id "
           f"WHERE {' AND '.join(where)} ORDER BY r.registrado_em DESC, r.id DESC LIMIT ?")
    return [_enriquecer(r) for r in rows(db.conn().execute(sql, [*args, limite]))]


def obter_visivel(db: Database, ctx: Contexto, rel_id: str) -> dict:
    r = grepo.obter(db, rel_id)
    if not r or not documento_visivel(db, ctx, r["origem_documento_id"]):
        raise nao_encontrado("Relação")
    if r["destino_documento_id"] and not documento_visivel(db, ctx, r["destino_documento_id"]):
        raise nao_encontrado("Relação")
    return r


def historico(db: Database, ctx: Contexto, rel_id: str) -> list[dict]:
    obter_visivel(db, ctx, rel_id)
    return grepo.historico(db, rel_id)


def validar(db: Database, ctx: Contexto, rel_id: str, acao: str, motivo: str | None = None,
            data_efeito: str | None = None, texto_novo: str | None = None,
            destino_documento_id: str | None = None) -> dict:
    rel = obter_visivel(db, ctx, rel_id)
    origem = repo.obter_documento(db, rel["origem_documento_id"])
    if origem["org_id"] != ctx.org_id or (origem["escopo"] == ESCOPO_NACIONAL and not ctx.curador_nacional):
        raise proibido("Somente o órgão responsável pelo ato de origem (ou a curadoria nacional) pode validar esta relação.")
    novo = {"CONFIRMAR": "CONFIRMADA", "REJEITAR": "REJEITADA", "REVERTER": "SUGERIDA"}.get(acao)
    if not novo:
        raise invalido("Ação inválida. Use CONFIRMAR, REJEITAR ou REVERTER.")
    if data_efeito and not valida_data(data_efeito):
        raise invalido("data_efeito deve estar no formato AAAA-MM-DD.")
    with db.tx():
        destino_antigo = rel["destino_documento_id"]
        if destino_documento_id:
            if not documento_visivel(db, ctx, destino_documento_id):
                raise nao_encontrado("Documento de destino")
            db.conn().execute("UPDATE relacao SET destino_documento_id=? WHERE id=?", (destino_documento_id, rel_id))
            rel["destino_documento_id"] = destino_documento_id
        if novo == "CONFIRMADA" and not rel["destino_documento_id"]:
            raise invalido("Não é possível confirmar uma relação cujo ato de destino ainda não foi identificado.")
        if data_efeito:
            db.conn().execute("UPDATE relacao SET data_efeito=? WHERE id=?", (data_efeito, rel_id))
        if texto_novo:
            db.conn().execute("UPDATE relacao SET texto_novo=? WHERE id=?", (texto_novo, rel_id))
        db.conn().execute("UPDATE relacao SET status=?, validado_por=?, validado_em=? WHERE id=?",
                          (novo, ctx.usuario_id, agora(), rel_id))
        grepo.historico_inserir(db, rel_id, rel["status"], novo, ctx.usuario_id, motivo)
        auditoria.registrar(db, ctx, "RELACAO_" + novo, "relacao", rel_id, {"acao": acao, "motivo": motivo})
        for d in {x for x in (destino_antigo, rel["destino_documento_id"]) if x}:
            efeitos.recalcular(db, d)
    return _enriquecer(grepo.obter(db, rel_id))


def grafo(db: Database, ctx: Contexto) -> dict:
    """Nós = documentos visíveis; arestas agregadas por (origem, destino, tipo)."""
    vis, params = sql_visivel(ctx, "d")
    nos = rows(db.conn().execute(
        f"SELECT d.id, d.titulo, d.tipo, d.escopo, d.data_publicacao, d.vigencia_fim, d.sintetico, o.sigla AS orgao "
        f"FROM documento d JOIN orgao o ON o.id=d.org_id WHERE {vis} ORDER BY COALESCE(d.data_publicacao,''), d.titulo", params))
    ids = {n["id"] for n in nos}
    ref = hoje()
    for n in nos:
        n["situacao"] = "REVOGADA" if n["vigencia_fim"] and n["vigencia_fim"] <= ref else "VIGENTE"
    arestas: dict[tuple, dict] = {}
    for r in listar(db, ctx, limite=5000):
        if r["status"] == "REJEITADA" or not r["destino_documento_id"] or r["destino_documento_id"] not in ids:
            continue
        k = (r["origem_documento_id"], r["destino_documento_id"], r["tipo"])
        a = arestas.setdefault(k, {"origem": k[0], "destino": k[1], "tipo": k[2], "qtd": 0, "pendentes": 0, "dispositivos": []})
        a["qtd"] += 1
        a["pendentes"] += 1 if r["status"] == "SUGERIDA" else 0
        if r.get("destino_rotulo"):
            a["dispositivos"].append(r["destino_rotulo"])
    return {"nos": nos, "arestas": list(arestas.values())}
