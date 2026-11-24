"""Importação em lote de um pacote .zip: `manifesto.json` + arquivos originais.

Formato do manifesto:
{ "itens": [ { "tipo": "RESOLUCAO", "orgao_emissor": "CONTRAN", "numero": "1032", "ano": 2026,
               "arquivo": "originais/res_1032_2026.pdf",                 # opcional: sem arquivo = só referência
               "url_documento": "...", "url_origem": "...", "url_publicacao_dou": "...",
               "data_assinatura": "AAAA-MM-DD", "data_publicacao": "AAAA-MM-DD", "capturado_em": "AAAA-MM-DDTHH:MM:SS",
               "status_validacao": "PENDENTE", "observacao": "...",
               "relacoes_indice": [ {"tipo": "REVOGA", "alvo_tipo": "RESOLUCAO", "numero": "941", "ano": 2022} ] } ] }

Segurança: o zip NUNCA é extraído em disco; cada arquivo é lido em memória pelo nome declarado no manifesto, que precisa
existir no pacote. Há limites de quantidade e tamanho (proteção contra zip bomb). Itens são independentes: um erro não
derruba o lote, e o resultado por item é devolvido.
"""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import PurePosixPath

from ..common.armazenamento import Armazenamento
from ..common.erros import ErroNegocio, invalido, proibido
from ..config import Settings
from ..db import Database
from ..identidade.service import Contexto
from ..ingestao import service as ingestao
from . import service as catalogo

MAX_ENTRADAS = 2000
MAX_ARQUIVO = 60 * 1024 * 1024
MAX_TOTAL = 400 * 1024 * 1024
MAX_MANIFESTO = 5 * 1024 * 1024
CAMPOS_ORIGEM = ("url_documento", "url_origem", "url_publicacao_dou", "data_assinatura", "capturado_em", "status_validacao")


def importar_zip(db: Database, st: Settings, armazenamento: Armazenamento, ctx: Contexto, dados: bytes) -> dict:
    if not ctx.curador_nacional:
        raise proibido("Somente a curadoria nacional pode importar lotes para o acervo nacional.")
    try:
        z = zipfile.ZipFile(io.BytesIO(dados))
    except zipfile.BadZipFile:
        raise invalido("O arquivo enviado não é um .zip válido.")
    infos = {i.filename: i for i in z.infolist() if not i.is_dir()}
    if len(infos) > MAX_ENTRADAS or sum(i.file_size for i in infos.values()) > MAX_TOTAL:
        raise invalido("Pacote acima dos limites (quantidade ou tamanho total).")
    nome_m = next((n for n in infos if PurePosixPath(n).name.lower() == "manifesto.json" and len(PurePosixPath(n).parts) <= 2), None)
    if not nome_m:
        raise invalido("O pacote precisa conter manifesto.json (na raiz).")
    if infos[nome_m].file_size > MAX_MANIFESTO:
        raise invalido("manifesto.json grande demais.")
    base = PurePosixPath(nome_m).parent
    try:
        manifesto = json.loads(z.read(nome_m).decode("utf-8-sig"))
        itens = manifesto["itens"]
        assert isinstance(itens, list)
    except (ValueError, KeyError, AssertionError, UnicodeDecodeError):
        raise invalido('manifesto.json inválido: esperado {"itens": [...]}.')

    resultados, cont = [], {"obtidos": 0, "apenas_referencia": 0, "duplicados": 0, "falhas": 0}
    for n, it in enumerate(itens, 1):
        ref = f"{it.get('tipo', '?')} {it.get('numero', '?')}/{it.get('ano', '?')}" if isinstance(it, dict) else f"item {n}"
        res = {"item": n, "ref": ref, "resultado": None, "avisos": [], "erro": None}
        try:
            if not isinstance(it, dict):
                raise invalido("Item do manifesto deve ser um objeto.")
            catalogo.registrar_item(db, ctx, it)
            arq = it.get("arquivo")
            if not arq:
                res["resultado"] = "APENAS_REFERENCIA"
                cont["apenas_referencia"] += 1
            else:
                nome = str(PurePosixPath(base, arq)) if str(base) != "." else str(PurePosixPath(arq))
                info = infos.get(nome)
                if info is None:
                    raise invalido(f"Arquivo declarado não consta do pacote: {arq!r}.")
                if info.file_size > MAX_ARQUIVO:
                    raise invalido(f"Arquivo acima do limite de tamanho: {arq!r}.")
                sobre = {k: it[k] for k in ("tipo", "numero", "ano", "orgao_emissor", "titulo", "data_publicacao", "vigencia_inicio") if it.get(k)}
                r = ingestao.ingerir(
                    db, st, armazenamento, ctx, nome_arquivo=PurePosixPath(arq).name, conteudo=z.read(info), texto=None,
                    escopo="NACIONAL", fonte_url=it.get("url_documento"), sobrescritas=sobre,
                    origem={k: it.get(k) for k in CAMPOS_ORIGEM if it.get(k)})
                res["resultado"] = "DUPLICADO" if r.get("duplicado") else "OBTIDO"
                res["documento_id"] = r["documento_id"]
                res["avisos"] = r.get("alertas", [])
                cont["duplicados" if r.get("duplicado") else "obtidos"] += 1
        except ErroNegocio as e:
            res["resultado"], res["erro"] = "FALHA", e.mensagem
            cont["falhas"] += 1
            if isinstance(it, dict) and it.get("arquivo"):  # registra a falha de obtenção no catálogo
                try:
                    catalogo.registrar_item(db, ctx, {**{k: it.get(k) for k in ("tipo", "numero", "ano", "orgao_emissor")},
                                                      "status_obtencao": "FALHA", "observacao": f"Falha na importação: {e.mensagem}"[:900]}, auditar=False)
                except ErroNegocio:
                    pass
        resultados.append(res)
    return {"total": len(itens), **cont, "resultados": resultados}
