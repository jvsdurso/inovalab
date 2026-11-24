"""Vigência: aplica os EFEITOS das relações confirmadas sobre as redações dos dispositivos.

`recalcular(doc)` é idempotente: descarta tudo o que é derivado de relações e reconstrói, em ordem
cronológica, a partir das redações originais + relações CONFIRMADAS. Assim confirmar, rejeitar ou
corrigir uma relação sempre produz um estado consistente (não há "desfazer" manual).

Escopo dos efeitos (isolamento institucional): um ato só altera a vigência de outro se a audiência
do ato de origem cobrir a do destino. Ex.: portaria restrita da SENATRAN não muda a vigência de uma
resolução NACIONAL para os demais órgãos — a relação fica apenas como informativa.
"""
from __future__ import annotations

from ..db import Database
from ..grafo import repo as grepo
from ..normativo import repo
from ..normativo.caminhos import descende_de, nivel_do_segmento, pai_de_caminho
from ..normativo.parser import fragmento_para_dispositivos
from ..normativo.tipos import ESCOPO_NACIONAL, ESCOPO_RESTRITO


def pode_aplicar_efeito(db: Database, origem: dict, destino: dict) -> bool:
    if origem["escopo"] == ESCOPO_NACIONAL:
        return True
    if destino["escopo"] == ESCOPO_NACIONAL or destino["org_id"] != origem["org_id"]:
        return False
    if destino["escopo"] == ESCOPO_RESTRITO:
        return True
    if origem["escopo"] == ESCOPO_RESTRITO:
        return False
    return repo.orgs_compartilhados(db, destino["id"]) <= repo.orgs_compartilhados(db, origem["id"])


def recalcular(db: Database, doc_id: str) -> dict:
    destino = repo.obter_documento(db, doc_id)
    resumo = {"documento_id": doc_id, "aplicadas": 0, "informativas": 0, "sem_efeito": 0}
    if not destino:
        return resumo
    with db.tx():
        repo.limpar_derivados(db, doc_id)
        grepo.zerar_efeitos(db, doc_id)
        fim_total: str | None = None
        for rel in grepo.relacoes_com_efeito(db, doc_id):
            origem = repo.obter_documento(db, rel["origem_documento_id"])
            data = rel["data_efeito"]
            if not origem or not pode_aplicar_efeito(db, origem, destino):
                grepo.marcar_efeito(db, rel["id"], False,
                                    "Relação informativa: o ato de origem não tem alcance sobre a audiência do destino; vigência não alterada.")
                resumo["informativas"] += 1
                continue
            if not data:
                grepo.marcar_efeito(db, rel["id"], False, "Data de efeito desconhecida; informe-a na validação.")
                resumo["sem_efeito"] += 1
                continue
            if rel["tipo"] == "REVOGA":
                ok, nota = _revoga(db, destino, rel, data, None)
                if ok:
                    fim_total = data if fim_total is None else min(fim_total, data)
            elif rel["tipo"] == "REVOGA_PARCIALMENTE":
                ok, nota = _revoga(db, destino, rel, data, rel["destino_caminho"])
            else:
                ok, nota = _altera(db, destino, rel, data)
            grepo.marcar_efeito(db, rel["id"], ok, nota)
            resumo["aplicadas" if ok else "sem_efeito"] += 1
        if fim_total:
            repo.atualizar_documento(db, doc_id, {"vigencia_fim": fim_total})
    return resumo


def _revoga(db: Database, destino: dict, rel: dict, data: str, caminho: str | None) -> tuple[bool, str]:
    alvos = [d for d in repo.dispositivos_do_documento(db, destino["id"]) if caminho is None or descende_de(d["caminho"], caminho)]
    if not alvos:
        return False, "Dispositivo revogado não encontrado no destino; requer validação humana."
    n = 0
    for d in alvos:
        aberta = repo.redacao_aberta_em(db, d["id"], data)
        if aberta:
            repo.encerrar_redacao(db, aberta["id"], data, "REVOGADO", rel["id"])
            n += 1
    return (n > 0), (f"{n} redação(ões) encerrada(s) em {data}." if n else "Nenhuma redação aberta na data do efeito.")


def _altera(db: Database, destino: dict, rel: dict, data: str) -> tuple[bool, str]:
    caminho, frag = rel["destino_caminho"], rel["texto_novo"]
    if not caminho or not frag:
        return False, "Dispositivo-alvo ou texto novo não identificados; nenhuma alteração aplicada (validação humana)."
    devs = fragmento_para_dispositivos(frag, caminho)
    if not devs:
        return False, "O texto novo não pôde ser estruturado para o dispositivo-alvo; nenhuma alteração aplicada."
    feitas, puladas = 0, 0
    for d in devs:
        disp = repo.dispositivo_por_caminho(db, destino["id"], d.caminho)
        if disp is None:
            did = repo.garantir_dispositivo(db, destino["id"], d.caminho, d.nivel, pai_de_caminho(d.caminho), None, 100000,
                                            criado_por_relacao_id=rel["id"])
        else:
            did = disp["id"]
            aberta = repo.redacao_aberta_em(db, did, data)
            if aberta is None:
                puladas += 1
                continue
            repo.encerrar_redacao(db, aberta["id"], data, "SUBSTITUIDO", rel["id"])
        repo.inserir_redacao(db, did, "ALTERACAO", d.texto, data, rel["origem_documento_id"], rel["id"])
        feitas += 1
    nota = f"{feitas} dispositivo(s) com nova redação desde {data}."
    if puladas:
        nota += f" {puladas} ignorado(s) por não terem redação vigente na data."
    return feitas > 0, nota
