from __future__ import annotations

import re
import unicodedata

ESCOPO_NACIONAL = "NACIONAL"
ESCOPO_COMPARTILHADO = "INSTITUCIONAL_COMPARTILHADO"
ESCOPO_RESTRITO = "INSTITUCIONAL_RESTRITO"
ESCOPOS = (ESCOPO_NACIONAL, ESCOPO_COMPARTILHADO, ESCOPO_RESTRITO)

TIPOS_RELACAO = ("ALTERA", "REVOGA", "REVOGA_PARCIALMENTE", "REGULAMENTA",
                 "COMPLEMENTA", "CONSOLIDA", "SUSPENDE", "RESTABELECE")

_NOMES = {
    "LEI": "Lei", "LEI_COMPLEMENTAR": "Lei Complementar", "DECRETO": "Decreto",
    "DECRETO_LEI": "Decreto-Lei", "RESOLUCAO": "Resolução", "PORTARIA": "Portaria",
    "INSTRUCAO_NORMATIVA": "Instrução Normativa", "DELIBERACAO": "Deliberação",
    "MEDIDA_PROVISORIA": "Medida Provisória", "NOTA_TECNICA": "Nota Técnica",
    "ORDEM_DE_SERVICO": "Ordem de Serviço", "OUTRO": "Documento",
}


def sem_acentos(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def canon_tipo(s: str | None) -> str:
    if not s:
        return "OUTRO"
    k = re.sub(r"[\s\-]+", "_", sem_acentos(s).strip().upper())
    return k if k in _NOMES else "OUTRO"


def nome_tipo(k: str) -> str:
    return _NOMES.get(k, "Documento")


def norm_numero(n: str | None) -> str | None:
    if not n:
        return None
    d = re.sub(r"\D", "", n)
    return d.lstrip("0") or ("0" if d else None)


def montar_titulo(tipo: str, emissor: str | None, numero: str | None, ano: int | None) -> str:
    t = nome_tipo(tipo)
    if emissor:
        t += f" {emissor}"
    if numero:
        t += f" nº {numero}"
        if ano:
            t += f"/{ano}"
    return t
