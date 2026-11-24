"""Persistência de relações normativas (sem dependência de outros serviços do grafo)."""
from __future__ import annotations

from ..common.util import agora, novo_id, row, rows
from ..db import Database

TIPOS_COM_EFEITO = ("ALTERA", "REVOGA", "REVOGA_PARCIALMENTE")

COLS = ["id", "tipo", "origem_documento_id", "origem_caminho", "destino_documento_id", "destino_caminho",
        "destino_tipo", "destino_numero", "destino_ano", "destino_emissor", "destino_ref", "data_efeito",
        "texto_novo", "evidencia", "confianca", "status", "origem_deteccao", "efeito_aplicado", "nota_efeito",
        "validado_por", "validado_em", "registrado_em"]


def inserir(db: Database, r: dict) -> str:
    r = {**r}
    r.setdefault("id", novo_id())
    r.setdefault("registrado_em", agora())
    r.setdefault("efeito_aplicado", 0)
    db.conn().execute(f"INSERT INTO relacao({','.join(COLS)}) VALUES ({','.join('?' * len(COLS))})", [r.get(c) for c in COLS])
    return r["id"]


def obter(db: Database, rel_id: str) -> dict | None:
    return row(db.conn().execute("SELECT * FROM relacao WHERE id=?", (rel_id,)).fetchone())


def historico_inserir(db: Database, rel_id: str, anterior: str | None, novo: str, por: str | None, motivo: str | None) -> None:
    db.conn().execute("INSERT INTO relacao_historico(id,relacao_id,status_anterior,status_novo,por,em,motivo) VALUES (?,?,?,?,?,?,?)",
                      (novo_id(), rel_id, anterior, novo, por, agora(), motivo))


def historico(db: Database, rel_id: str) -> list[dict]:
    return rows(db.conn().execute(
        "SELECT h.status_anterior, h.status_novo, h.em, h.motivo, u.login AS por FROM relacao_historico h "
        "LEFT JOIN usuario u ON u.id=h.por WHERE h.relacao_id=? ORDER BY h.em, h.id", (rel_id,)))


def relacoes_com_efeito(db: Database, destino_id: str) -> list[dict]:
    ph = ",".join("?" * len(TIPOS_COM_EFEITO))
    return rows(db.conn().execute(
        f"SELECT * FROM relacao WHERE destino_documento_id=? AND status='CONFIRMADA' AND tipo IN ({ph}) "
        "ORDER BY COALESCE(data_efeito,''), registrado_em, id", (destino_id, *TIPOS_COM_EFEITO)))


def zerar_efeitos(db: Database, destino_id: str) -> None:
    db.conn().execute("UPDATE relacao SET efeito_aplicado=0 WHERE destino_documento_id=?", (destino_id,))


def marcar_efeito(db: Database, rel_id: str, aplicado: bool, nota: str | None) -> None:
    db.conn().execute("UPDATE relacao SET efeito_aplicado=?, nota_efeito=? WHERE id=?", (1 if aplicado else 0, nota, rel_id))


def pendentes_para_resolver(db: Database, tipo: str, numero: str | None) -> list[dict]:
    return rows(db.conn().execute(
        "SELECT * FROM relacao WHERE destino_documento_id IS NULL AND destino_tipo=? AND destino_numero=? "
        "AND origem_deteccao='AUTO' AND validado_por IS NULL", (tipo, numero)))


def apagar_automaticas_do_documento(db: Database, origem_id: str) -> set[str]:
    """Remove relações AUTO ainda não tocadas por humanos; devolve os destinos afetados."""
    c = db.conn()
    alvo = rows(c.execute("SELECT id, destino_documento_id FROM relacao WHERE origem_documento_id=? AND origem_deteccao='AUTO' "
                          "AND validado_por IS NULL", (origem_id,)))
    afetados = {r["destino_documento_id"] for r in alvo if r["destino_documento_id"]}
    for r in alvo:
        c.execute("UPDATE redacao SET encerrada_por_relacao_id=NULL WHERE encerrada_por_relacao_id=?", (r["id"],))
        c.execute("UPDATE redacao SET origem_relacao_id=NULL WHERE origem_relacao_id=?", (r["id"],))
        c.execute("UPDATE dispositivo SET criado_por_relacao_id=NULL WHERE criado_por_relacao_id=?", (r["id"],))
        c.execute("DELETE FROM relacao_historico WHERE relacao_id=?", (r["id"],))
        c.execute("DELETE FROM relacao WHERE id=?", (r["id"],))
    return afetados
