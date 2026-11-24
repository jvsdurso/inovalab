"""Proteção contra instruções maliciosas embutidas em documentos importados (prompt injection).

Defesa em camadas: (1) sinalização na ingestão (aqui); (2) fontes sempre enviadas ao LLM como DADO,
em tags, com instrução explícita de ignorá-las (ia/orquestrador.py); (3) verificação das citações da
resposta contra as fontes. Nenhuma delas é infalível — por isso a revisão humana é obrigatória.
"""
from __future__ import annotations

import re

PADROES = [
    r"ignor(?:e|ar)\s+(?:todas?\s+)?(?:as\s+)?(?:instru[cç][õo]es|regras|orienta[cç][õo]es)",
    r"desconsider(?:e|ar)\s+(?:todas?\s+)?(?:as\s+)?(?:instru[cç][õo]es|regras)",
    r"ignore\s+(?:all\s+|any\s+)?(?:previous|prior|above)\s+instructions",
    r"disregard\s+(?:the\s+)?(?:system|previous)",
    r"(?:system|developer)\s+prompt",
    r"voc[êe]\s+(?:agora\s+)?(?:é|deve|precisa)\s+(?:um|uma|obedecer|responder)",
    r"you\s+are\s+now\b",
    r"revele?\s+(?:o\s+)?(?:seu\s+)?prompt",
    r"<\s*/?\s*(?:fonte|system|instruction)",
]
_RX = [re.compile(p, re.I) for p in PADROES]


def detectar_injecao(texto: str) -> list[str]:
    alertas = []
    for rx in _RX:
        m = rx.search(texto)
        if m:
            ini = max(0, m.start() - 30)
            alertas.append("Possível instrução embutida no documento: «…%s…». Conteúdo tratado como dado." %
                           re.sub(r"\s+", " ", texto[ini:m.end() + 30]))
    return alertas[:5]
