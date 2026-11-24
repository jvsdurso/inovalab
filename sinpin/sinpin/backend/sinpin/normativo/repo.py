"""Persistência do domínio normativo (documentos, versões, dispositivos, redações)."""
from __future__ import annotations

from ..common.util import agora, novo_id, row, rows
from ..db import Database

SEM_DATA = "0001-01-01"


# -------------------------------------------------------------------- documentos
def obter_documento(db: Database, doc_id: str) -> dict | None:
    return row(db.conn().execute("SELECT * FROM documento WHERE id=?", (doc_id,)).fetchone())


def obter_por_ident(db: Database, org_id: str, tipo: str, numero: str | None, ano: int | None,
                    emissor: str | None) -> dict | None:
    if not numero:
        return None
    return row(db.conn().execute(
        "SELECT * FROM documento WHERE org_id=? AND tipo=? AND COALESCE(numero,'')=? AND COALESCE(ano,0)=? "
        "AND COALESCE(orgao_emissor,'')=?", (org_id, tipo, numero, ano or 0, emissor or "")).fetchone())


def inserir_documento(db: Database, d: dict) -> None:
    cols = ["id", "escopo", "org_id", "tipo", "numero", "ano", "orgao_emissor", "titulo", "ementa",
            "data_publicacao", "vigencia_inicio", "fonte_url", "sintetico", "versao_atual", "alertas",
            "criado_por", "registrado_em", "url_origem", "url_publicacao_dou", "data_assinatura", "formato_original",
            "status_obtencao", "status_validacao"]
    padrao = {"status_obtencao": "OBTIDO", "status_validacao": "PENDENTE"}
    db.conn().execute(f"INSERT INTO documento({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                      [d.get(c) if d.get(c) is not None else padrao.get(c) for c in cols])


def atualizar_documento(db: Database, doc_id: str, campos: dict) -> None:
    if not campos:
        return
    sets = ", ".join(f"{k}=?" for k in campos)
    db.conn().execute(f"UPDATE documento SET {sets} WHERE id=?", [*campos.values(), doc_id])


def inserir_versao(db: Database, doc_id: str, versao: int, texto: str, hash_: str, nome_arquivo: str | None,
                   chave: str | None, por: str | None, capturado_em: str | None = None) -> None:
    db.conn().execute(
        "INSERT INTO documento_versao(id,documento_id,versao,texto,hash,nome_arquivo,arquivo_chave,registrado_em,registrado_por,capturado_em) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)", (novo_id(), doc_id, versao, texto, hash_, nome_arquivo, chave, agora(), por, capturado_em or agora()))


def versao_atual(db: Database, doc_id: str) -> dict | None:
    return row(db.conn().execute(
        "SELECT v.* FROM documento_versao v JOIN documento d ON d.id=v.documento_id AND d.versao_atual=v.versao "
        "WHERE v.documento_id=?", (doc_id,)).fetchone())


def listar_versoes(db: Database, doc_id: str) -> list[dict]:
    return rows(db.conn().execute(
        "SELECT versao, hash, nome_arquivo, registrado_em, registrado_por, capturado_em FROM documento_versao "
        "WHERE documento_id=? ORDER BY versao DESC", (doc_id,)))


def compartilhar(db: Database, doc_id: str, org_ids: list[str]) -> None:
    c = db.conn()
    c.execute("DELETE FROM compartilhamento WHERE documento_id=?", (doc_id,))
    for o in org_ids:
        c.execute("INSERT OR IGNORE INTO compartilhamento(documento_id,org_id) VALUES (?,?)", (doc_id, o))


def orgs_compartilhados(db: Database, doc_id: str) -> set[str]:
    return {r["org_id"] for r in db.conn().execute("SELECT org_id FROM compartilhamento WHERE documento_id=?", (doc_id,))}


# -------------------------------------------------------------------- dispositivos
def garantir_dispositivo(db: Database, doc_id: str, caminho: str, nivel: str, pai: str | None,
                         grupo: str | None, ordem: int, criado_por_relacao_id: str | None = None) -> str:
    c = db.conn()
    r = c.execute("SELECT id FROM dispositivo WHERE documento_id=? AND caminho=?", (doc_id, caminho)).fetchone()
    if r:
        if grupo is not None:
            c.execute("UPDATE dispositivo SET grupo=?, ordem=? WHERE id=?", (grupo, ordem, r["id"]))
        return r["id"]
    did = novo_id()
    c.execute("INSERT INTO dispositivo(id,documento_id,caminho,nivel,pai_caminho,grupo,ordem,criado_por_relacao_id,registrado_em) "
              "VALUES (?,?,?,?,?,?,?,?,?)", (did, doc_id, caminho, nivel, pai, grupo, ordem, criado_por_relacao_id, agora()))
    return did


def dispositivos_do_documento(db: Database, doc_id: str) -> list[dict]:
    return rows(db.conn().execute("SELECT * FROM dispositivo WHERE documento_id=?", (doc_id,)))


def obter_dispositivo(db: Database, disp_id: str) -> dict | None:
    return row(db.conn().execute("SELECT * FROM dispositivo WHERE id=?", (disp_id,)).fetchone())


def dispositivo_por_caminho(db: Database, doc_id: str, caminho: str) -> dict | None:
    return row(db.conn().execute("SELECT * FROM dispositivo WHERE documento_id=? AND caminho=?", (doc_id, caminho)).fetchone())


# -------------------------------------------------------------------- redações
def inserir_redacao(db: Database, dispositivo_id: str, tipo: str, texto: str, valido_de: str,
                    origem_documento_id: str | None = None, origem_relacao_id: str | None = None,
                    versao_doc: int | None = None) -> str:
    rid = novo_id()
    db.conn().execute(
        "INSERT INTO redacao(id,dispositivo_id,tipo,texto,valido_de,origem_documento_id,origem_relacao_id,versao_doc,registrado_em) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (rid, dispositivo_id, tipo, texto, valido_de or SEM_DATA, origem_documento_id, origem_relacao_id, versao_doc, agora()))
    return rid


def encerrar_originais_do_documento(db: Database, doc_id: str) -> None:
    """Nova versão do documento: o sistema deixa de considerar as redações ORIGINAIS anteriores
    (tempo de sistema), preservando-as para auditoria."""
    db.conn().execute(
        "UPDATE redacao SET registrado_ate=? WHERE tipo='ORIGINAL' AND registrado_ate IS NULL AND "
        "dispositivo_id IN (SELECT id FROM dispositivo WHERE documento_id=?)", (agora(), doc_id))


def redacao_aberta_em(db: Database, dispositivo_id: str, data: str) -> dict | None:
    return row(db.conn().execute(
        "SELECT * FROM redacao WHERE dispositivo_id=? AND registrado_ate IS NULL AND valido_de<=? "
        "AND (valido_ate IS NULL OR valido_ate>?) ORDER BY valido_de DESC LIMIT 1", (dispositivo_id, data, data)).fetchone())


def encerrar_redacao(db: Database, redacao_id: str, data: str, motivo: str, relacao_id: str | None) -> None:
    db.conn().execute("UPDATE redacao SET valido_ate=?, motivo_fim=?, encerrada_por_relacao_id=? WHERE id=?",
                      (data, motivo, relacao_id, redacao_id))


def redacoes_do_dispositivo(db: Database, dispositivo_id: str) -> list[dict]:
    return rows(db.conn().execute(
        "SELECT * FROM redacao WHERE dispositivo_id=? AND registrado_ate IS NULL ORDER BY valido_de", (dispositivo_id,)))


def limpar_derivados(db: Database, doc_id: str) -> None:
    """Remove tudo que é DERIVADO de relações (alterações e dispositivos incluídos) e reabre as
    redações originais, para que `vigencia.efeitos.recalcular` reconstrua a partir das relações."""
    c = db.conn()
    c.execute("DELETE FROM redacao WHERE tipo='ALTERACAO' AND dispositivo_id IN (SELECT id FROM dispositivo WHERE documento_id=?)", (doc_id,))
    c.execute("DELETE FROM redacao WHERE dispositivo_id IN (SELECT id FROM dispositivo WHERE documento_id=? AND criado_por_relacao_id IS NOT NULL)", (doc_id,))
    c.execute("DELETE FROM dispositivo WHERE documento_id=? AND criado_por_relacao_id IS NOT NULL", (doc_id,))
    c.execute("UPDATE redacao SET valido_ate=NULL, motivo_fim=NULL, encerrada_por_relacao_id=NULL "
              "WHERE tipo='ORIGINAL' AND registrado_ate IS NULL AND "
              "dispositivo_id IN (SELECT id FROM dispositivo WHERE documento_id=?)", (doc_id,))
    c.execute("UPDATE documento SET vigencia_fim=NULL WHERE id=?", (doc_id,))
