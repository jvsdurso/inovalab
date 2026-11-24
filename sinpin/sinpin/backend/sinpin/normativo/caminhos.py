"""Caminhos estáveis de dispositivos normativos.

Um caminho identifica um dispositivo dentro do documento, independentemente da redação:
    art5            Art. 5º                  art5a      Art. 5º-A
    art5.p1         Art. 5º, § 1º            art5.pu    Art. 5º, parágrafo único
    art5.inc2       Art. 5º, II              art5.p1.inc2.alb   Art. 5º, § 1º, II, b
    tx3             Trecho 3 (documentos sem estrutura normativa)
"""
from __future__ import annotations

import re

_ROMANOS = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
            (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
_VAL = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
_RE_ROMANO = re.compile(r"^M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$")


def romano_valido(s: str) -> bool:
    return bool(s) and bool(_RE_ROMANO.match(s))


def romano_para_int(s: str) -> int:
    total, prev = 0, 0
    for ch in reversed(s):
        v = _VAL[ch]
        if v < prev:
            total -= v
        else:
            total += v
            prev = v
    return total


def int_para_romano(n: int) -> str:
    out = ""
    for v, s in _ROMANOS:
        while n >= v:
            out += s
            n -= v
    return out


def ordinal(n: int) -> str:
    return f"{n}º" if n < 10 else str(n)


_RE_ART = re.compile(r"^art(\d+)([a-z]?)$")
_RE_P = re.compile(r"^p(\d+)$")
_RE_INC = re.compile(r"^inc(\d+)$")
_RE_AL = re.compile(r"^al([a-z])$")
_RE_TX = re.compile(r"^tx(\d+)$")


def seg_artigo(n: int, sufixo: str = "") -> str:
    return f"art{n}{sufixo.lower()}"


def nivel_do_segmento(seg: str) -> str | None:
    if _RE_ART.match(seg):
        return "ARTIGO"
    if seg == "pu" or _RE_P.match(seg):
        return "PARAGRAFO"
    if _RE_INC.match(seg):
        return "INCISO"
    if _RE_AL.match(seg):
        return "ALINEA"
    if _RE_TX.match(seg):
        return "TRECHO"
    return None


def caminho_valido(caminho: str) -> bool:
    return bool(caminho) and all(nivel_do_segmento(s) for s in caminho.split("."))


def rotulo_segmento(seg: str) -> str:
    if m := _RE_ART.match(seg):
        return f"Art. {ordinal(int(m.group(1)))}" + (f"-{m.group(2).upper()}" if m.group(2) else "")
    if seg == "pu":
        return "parágrafo único"
    if m := _RE_P.match(seg):
        return f"§ {ordinal(int(m.group(1)))}"
    if m := _RE_INC.match(seg):
        return int_para_romano(int(m.group(1)))
    if m := _RE_AL.match(seg):
        return f"alínea {m.group(1)}"
    if m := _RE_TX.match(seg):
        return f"Trecho {m.group(1)}"
    return seg


def rotulo_de_caminho(caminho: str) -> str:
    return ", ".join(rotulo_segmento(s) for s in caminho.split("."))


def pai_de_caminho(caminho: str) -> str | None:
    partes = caminho.split(".")
    return ".".join(partes[:-1]) or None


def descende_de(caminho: str, ancestral: str) -> bool:
    return caminho == ancestral or caminho.startswith(ancestral + ".")


def chave_ordem(caminho: str) -> tuple:
    """Ordenação natural: caput, incisos do caput, parágrafos (e seus incisos/alíneas)."""
    out = []
    anterior = None
    for seg in caminho.split("."):
        if m := _RE_ART.match(seg):
            out.append((0, int(m.group(1)), m.group(2)))
        elif seg == "pu":
            out.append((2, 0, ""))
        elif m := _RE_P.match(seg):
            out.append((2, int(m.group(1)), ""))
        elif m := _RE_INC.match(seg):
            out.append((1 if anterior == "art" else 3, int(m.group(1)), ""))
        elif m := _RE_AL.match(seg):
            out.append((4, ord(m.group(1)), ""))
        elif m := _RE_TX.match(seg):
            out.append((0, int(m.group(1)), ""))
        else:
            out.append((9, 0, seg))
        anterior = "art" if _RE_ART.match(seg) else "outro"
    return tuple(out)
