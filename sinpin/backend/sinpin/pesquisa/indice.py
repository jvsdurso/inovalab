"""Tokenização e ranqueamento lexical (BM25) para português.

Implementação própria, sem dependências, adequada ao volume do MVP (milhares de dispositivos por
consulta já filtrados por permissão). A interface `ranquear` é o ponto de troca por busca vetorial
(pgvector) ou híbrida, mantendo o filtro de permissão aplicado ANTES da recuperação.
"""
from __future__ import annotations

import math
import re
from collections import Counter

from ..normativo.tipos import sem_acentos

STOP = set("""a o as os um uma uns umas de do da dos das em no na nos nas por para com sem sob sobre entre ate ao aos
e ou mas que se como quando onde qual quais quem seu sua seus suas esta este estes estas essa esse isso isto ser
sao foi era sera ha tem ter pode podem deve devem art artigo paragrafo inciso alinea""".split())

_SUFIXOS = ["amentos", "amento", "adores", "adora", "acoes", "acao", "icoes", "icao", "idades", "idade", "mente",
            "ismos", "ismo", "iveis", "ivel", "oes", "ais", "eis", "res", "ores", "ar", "er", "ir", "as", "os", "es", "s", "a", "o"]


def _radical(t: str) -> str:
    for suf in _SUFIXOS:
        if t.endswith(suf) and len(t) - len(suf) >= 4:
            return t[: -len(suf)]
    return t


def tokenizar(texto: str) -> list[str]:
    t = sem_acentos(texto.lower())
    return [_radical(w) for w in re.findall(r"[a-z0-9]+", t) if w not in STOP and len(w) > 1]


def ranquear(consulta: str, documentos: list[str], k1: float = 1.4, b: float = 0.75) -> list[float]:
    """Pontuação BM25 de cada documento para a consulta."""
    q = set(tokenizar(consulta))
    toks = [tokenizar(d) for d in documentos]
    n = len(toks)
    if not q or not n:
        return [0.0] * n
    avgdl = sum(len(t) for t in toks) / n or 1.0
    df = Counter()
    for t in toks:
        for w in q & set(t):
            df[w] += 1
    scores = []
    for t in toks:
        tf = Counter(t)
        dl = len(t) or 1
        s = 0.0
        for w in q:
            if tf[w]:
                idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
                s += idf * tf[w] * (k1 + 1) / (tf[w] + k1 * (1 - b + b * dl / avgdl))
        scores.append(s)
    return scores
