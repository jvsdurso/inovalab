"""Ingestão: arquivo/texto -> documento versionado -> dispositivos -> relações -> vigência.

Tudo ocorre em UMA transação: ou o documento entra completo (estrutura + relações + efeitos), ou não entra.
"""
from __future__ import annotations

import re

from ..auditoria import service as auditoria
from ..catalogo import service as catalogo
from ..common.armazenamento import Armazenamento
from ..common.erros import invalido, proibido
from ..common.util import agora, dumps, novo_id, sha256, valida_data
from ..config import Settings
from ..db import Database
from ..grafo import service as grafo
from ..identidade.service import Contexto, documento_visivel
from ..normativo import repo
from ..normativo.parser import (DispositivoP, detectar_vigencia_inicio, extrair_metadados, parse_dispositivos)
from ..normativo.tipos import ESCOPO_COMPARTILHADO, ESCOPO_NACIONAL, ESCOPOS, canon_tipo, montar_titulo, norm_numero
from ..vigencia import efeitos
from . import extrator, seguranca


def _trechos(texto: str) -> list[DispositivoP]:
    """Documentos sem estrutura normativa (notas, pareceres, processos): parágrafos viram 'trechos'."""
    paragrafos = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", texto)]
    paragrafos = [p for p in paragrafos if len(p) >= 60]
    return [DispositivoP(f"tx{i}", "TRECHO", p, i) for i, p in enumerate(paragrafos, 1)]


def ingerir(db: Database, st: Settings, armazenamento: Armazenamento, ctx: Contexto, *, nome_arquivo: str | None,
            conteudo: bytes | None, texto: str | None, escopo: str, fonte_url: str | None = None,
            sintetico: bool = False, sobrescritas: dict | None = None, origem: dict | None = None) -> dict:
    """`origem` (opcional): url_documento, url_origem, url_publicacao_dou, data_assinatura, capturado_em, status_validacao.
    `fonte_url` é o link do DOCUMENTO individual (compatibilidade); `origem['url_documento']` tem precedência."""
    sobrescritas = sobrescritas or {}
    origem = dict(origem or {})
    origem["url_documento"] = origem.get("url_documento") or fonte_url
    o, avisos_origem = catalogo.normalizar_origem(db, origem)
    fonte_url = o.get("url_documento")
    if escopo not in ESCOPOS:
        raise invalido(f"Escopo inválido. Use um de: {', '.join(ESCOPOS)}.")
    if escopo == ESCOPO_NACIONAL and not ctx.curador_nacional:
        raise proibido("Somente a curadoria nacional pode cadastrar normas de escopo NACIONAL.")
    avisos: list[str] = []
    if conteudo is not None:
        texto, avisos = extrator.extrair_texto(nome_arquivo, conteudo)
        bruto = conteudo
    elif texto and texto.strip():
        texto = extrator.normalizar(texto)
        bruto = texto.encode("utf-8")
    else:
        raise invalido("Envie um arquivo (TXT, PDF, DOCX) ou cole o texto do documento.")

    md = extrair_metadados(texto)
    tipo = canon_tipo(sobrescritas.get("tipo")) if sobrescritas.get("tipo") else md.tipo
    numero = norm_numero(sobrescritas.get("numero")) if sobrescritas.get("numero") else md.numero
    ano = int(sobrescritas["ano"]) if sobrescritas.get("ano") else md.ano
    emissor = (sobrescritas.get("orgao_emissor") or md.orgao_emissor or None)
    emissor = emissor.upper() if emissor else None
    data_pub = valida_data(sobrescritas.get("data_publicacao")) or md.data_publicacao
    alertas = list(avisos) + avisos_origem
    formato = (nome_arquivo.rsplit(".", 1)[-1].lower() if nome_arquivo and "." in nome_arquivo else "texto")
    if escopo == ESCOPO_NACIONAL and not sintetico and not fonte_url:
        alertas.append("Sem link do documento individual: a origem deste documento não é rastreável. Informe a URL exata do ato.")
    if sobrescritas.get("data_publicacao") and not valida_data(sobrescritas["data_publicacao"]):
        alertas.append("data_publicacao informada é inválida (use AAAA-MM-DD); usada a detectada no texto.")
    vig_ini = valida_data(sobrescritas.get("vigencia_inicio"))
    if not vig_ini:
        vig_ini, certeza = detectar_vigencia_inicio(texto, data_pub)
        if certeza == "PRESUMIDA":
            alertas.append("Início de vigência não identificado no texto; presumida a data do ato. Revise se necessário.")
        elif certeza == "DESCONHECIDA":
            alertas.append("Datas do ato não identificadas: vigência desconhecida (considerada desde sempre). Informe-as para análise temporal correta.")
    titulo = sobrescritas.get("titulo") or (montar_titulo(tipo, emissor, numero, ano) if numero else (nome_arquivo or "Documento sem título"))
    if not md.numero and not sobrescritas.get("numero"):
        alertas.append("Cabeçalho normativo não identificado (tipo/número/ano). Tratado como documento institucional.")
    alertas += seguranca.detectar_injecao(texto)

    dispositivos = parse_dispositivos(texto)
    if not any(d.nivel == "ARTIGO" for d in dispositivos):
        dispositivos = _trechos(texto)
        alertas.append("Estrutura em artigos não identificada; documento indexado por trechos.")
    if not dispositivos:
        raise invalido("Não foi possível identificar conteúdo no documento.")

    h = sha256(bruto if conteudo is not None else texto.encode("utf-8"))
    with db.tx():
        existente = repo.obter_por_ident(db, ctx.org_id, tipo, numero, ano, emissor)
        if existente:
            atual = repo.versao_atual(db, existente["id"])
            if atual and atual["hash"] == h:
                faltantes = {k: v for k, v in (("fonte_url", fonte_url), ("url_origem", o.get("url_origem")),
                                               ("url_publicacao_dou", o.get("url_publicacao_dou")),
                                               ("data_assinatura", o.get("data_assinatura"))) if v and not existente.get(k)}
                repo.atualizar_documento(db, existente["id"], faltantes)  # completa proveniência sem sobrescrever
                catalogo.vincular_documento(db, repo.obter_documento(db, existente["id"]))
                return {"documento_id": existente["id"], "duplicado": True, "nova_versao": False, "titulo": existente["titulo"],
                        "alertas": [], "dispositivos": len(repo.dispositivos_do_documento(db, existente["id"]))}
            doc_id, versao = existente["id"], existente["versao_atual"] + 1
            repo.encerrar_originais_do_documento(db, doc_id)
            repo.atualizar_documento(db, doc_id, {
                "versao_atual": versao, "ementa": md.ementa, "data_publicacao": data_pub, "vigencia_inicio": vig_ini,
                "titulo": titulo, "alertas": dumps(alertas), "fonte_url": fonte_url or existente["fonte_url"],
                "url_origem": o.get("url_origem") or existente.get("url_origem"),
                "url_publicacao_dou": o.get("url_publicacao_dou") or existente.get("url_publicacao_dou"),
                "data_assinatura": o.get("data_assinatura") or existente.get("data_assinatura"), "formato_original": formato,
                "status_validacao": "PENDENTE"})  # o texto mudou: a validação humana anterior não vale para a nova versão
            acao = "DOCUMENTO_NOVA_VERSAO"
        else:
            doc_id, versao = novo_id(), 1
            repo.inserir_documento(db, {
                "id": doc_id, "escopo": escopo, "org_id": ctx.org_id, "tipo": tipo, "numero": numero, "ano": ano,
                "orgao_emissor": emissor, "titulo": titulo, "ementa": md.ementa, "data_publicacao": data_pub,
                "vigencia_inicio": vig_ini, "fonte_url": fonte_url, "sintetico": 1 if sintetico else 0,
                "versao_atual": 1, "alertas": dumps(alertas), "criado_por": ctx.usuario_id, "registrado_em": agora(),
                "url_origem": o.get("url_origem"), "url_publicacao_dou": o.get("url_publicacao_dou"),
                "data_assinatura": o.get("data_assinatura"), "formato_original": formato,
                "status_obtencao": "OBTIDO", "status_validacao": o.get("status_validacao") or "PENDENTE"})
            acao = "DOCUMENTO_IMPORTADO"
        chave = armazenamento.salvar(f"{ctx.org_id}/{doc_id}/v{versao}/{re.sub(r'[^A-Za-z0-9._-]', '_', nome_arquivo or 'texto.txt')}", bruto)
        repo.inserir_versao(db, doc_id, versao, texto, h, nome_arquivo, chave, ctx.usuario_id, o.get("capturado_em"))

        valido_de = vig_ini or data_pub or repo.SEM_DATA
        for d in dispositivos:
            did = repo.garantir_dispositivo(db, doc_id, d.caminho, d.nivel, d.pai, d.grupo, d.ordem)
            repo.inserir_redacao(db, did, "ORIGINAL", d.texto, valido_de, versao_doc=versao)

        documento = repo.obter_documento(db, doc_id)
        catalogo.vincular_documento(db, documento)
        afetados = {doc_id}
        afetados |= grafo.detectar_e_registrar(db, documento, dispositivos, st.limiar_auto_confirmacao)
        afetados |= grafo.resolver_pendentes(db, documento, st.limiar_auto_confirmacao)
        for alvo in afetados:
            efeitos.recalcular(db, alvo)
        auditoria.registrar(db, ctx, acao, "documento", doc_id,
                            {"titulo": titulo, "versao": versao, "escopo": escopo, "hash": h, "dispositivos": len(dispositivos)})
        n_rel = db.conn().execute("SELECT COUNT(*) AS n FROM relacao WHERE origem_documento_id=?", (doc_id,)).fetchone()["n"]
        pend = db.conn().execute("SELECT COUNT(*) AS n FROM relacao WHERE origem_documento_id=? AND status='SUGERIDA'", (doc_id,)).fetchone()["n"]
    return {"documento_id": doc_id, "titulo": titulo, "duplicado": False, "nova_versao": versao > 1, "versao": versao,
            "dispositivos": len(dispositivos), "relacoes_detectadas": n_rel, "relacoes_pendentes": pend,
            "alertas": alertas, "metadados": {"tipo": tipo, "numero": numero, "ano": ano, "emissor": emissor,
                                              "data_publicacao": data_pub, "vigencia_inicio": vig_ini, "ementa": md.ementa},
            "origem": {"url_documento": fonte_url, "url_origem": o.get("url_origem"), "url_publicacao_dou": o.get("url_publicacao_dou"),
                       "data_assinatura": o.get("data_assinatura"), "formato_original": formato, "hash_sha256": h}}


def compartilhar(db: Database, ctx: Contexto, doc_id: str, org_ids: list[str]) -> dict:
    d = repo.obter_documento(db, doc_id)
    if not d or d["org_id"] != ctx.org_id:
        from ..common.erros import nao_encontrado
        raise nao_encontrado("Documento")
    if d["escopo"] == ESCOPO_NACIONAL:
        raise invalido("Documentos nacionais já são visíveis a todos.")
    with db.tx():
        repo.compartilhar(db, doc_id, [o for o in org_ids if o != ctx.org_id])
        novo = ESCOPO_COMPARTILHADO if org_ids else "INSTITUCIONAL_RESTRITO"
        repo.atualizar_documento(db, doc_id, {"escopo": novo})
        auditoria.registrar(db, ctx, "DOCUMENTO_COMPARTILHADO", "documento", doc_id, {"orgaos": org_ids})
        # a audiência mudou: efeitos de/para este documento precisam ser reavaliados
        rels = db.conn().execute("SELECT DISTINCT destino_documento_id AS x FROM relacao WHERE origem_documento_id=? "
                                 "AND destino_documento_id IS NOT NULL", (doc_id,)).fetchall()
        for r in rels:
            efeitos.recalcular(db, r["x"])
        efeitos.recalcular(db, doc_id)
    return {"documento_id": doc_id, "escopo": novo, "orgaos": org_ids}


def definir_validacao(db: Database, ctx: Contexto, doc_id: str, status: str, motivo: str | None = None) -> dict:
    """Validação jurídica HUMANA do documento (confirmado / pendente / controvertido / rejeitado). Auditada."""
    from ..common.erros import nao_encontrado
    if status not in catalogo.STATUS_VALIDACAO:
        raise invalido(f"status deve ser um de: {', '.join(catalogo.STATUS_VALIDACAO)}.")
    d = repo.obter_documento(db, doc_id)
    if not d or not documento_visivel(db, ctx, doc_id):
        raise nao_encontrado("Documento")   # invisível: não vaza existência
    if d["escopo"] == ESCOPO_NACIONAL and not ctx.curador_nacional:
        raise proibido("Somente a curadoria nacional valida documentos de escopo NACIONAL.")
    if d["org_id"] != ctx.org_id and d["escopo"] != ESCOPO_NACIONAL:
        raise proibido("Somente o órgão responsável valida este documento.")
    with db.tx():
        repo.atualizar_documento(db, doc_id, {"status_validacao": status})
        db.conn().execute("UPDATE catalogo_item SET status_validacao=?, atualizado_em=? WHERE documento_id=?", (status, agora(), doc_id))
        auditoria.registrar(db, ctx, "DOCUMENTO_VALIDACAO", "documento", doc_id,
                            {"de": d["status_validacao"], "para": status, "motivo": (motivo or "")[:500]})
    return {"documento_id": doc_id, "status_validacao": status}
