"""Detecção (determinística, por texto) de relações normativas.

Princípio: só se cria relação quando o TEXTO diz expressamente (ex.: "Fica revogado o art. 6º da
Resolução nº 101"). Nunca se presume que norma posterior revoga anterior. Casos ambíguos ou com
destino não resolvido ficam como SUGERIDA para validação humana (ver grafo/service.py).
"""
from __future__ import annotations

import itertools
import re
from dataclasses import dataclass

from ..normativo.caminhos import romano_para_int, romano_valido
from ..normativo.parser import DispositivoP, RE_ELISAO, parse_dispositivos
from ..normativo.tipos import canon_tipo, norm_numero


@dataclass
class Detectada:
    tipo: str
    origem_caminho: str | None
    destino_tipo: str
    destino_numero: str | None
    destino_ano: int | None
    destino_emissor: str | None
    destino_ref: str
    destino_caminho: str | None
    texto_novo: str | None
    evidencia: str


# ------------------------------------------------------------------ referências a documentos
_TIPOS = (r"lei\s+complementar|lei|decreto-lei|decreto|resolu[cç][aã]o|portaria|"
          r"instru[cç][aã]o\s+normativa|delibera[cç][aã]o|medida\s+provis[oó]ria")
RE_DOC = re.compile(
    rf"\b(?P<tipo>{_TIPOS})(?:\s+(?P<emissor>(?-i:[A-Z][A-Za-z\-]{{1,}})))?\s+n[ºo°\.]*\s*(?P<num>\d+(?:\.\d{{3}})*)"
    r"(?:\s*/\s*(?P<ano1>\d{4})|\s*,?\s*de\s+(?:\d{1,2}\s*[ºo°]?\s+de\s+[a-zç]+\s+de\s+|\d{1,2}/\d{1,2}/)?(?P<ano2>\d{4}))?",
    re.I)

# ------------------------------------------------------------------ referências a dispositivos
_NUM = r"\d+(?:\.\d{3})*\s*[ºo°]?(?:-[A-Za-z])?"
_SEP = r"\s*(?:,|e|a|ao)\s*"
RE_ART_REF = re.compile(rf"\barts?\.?\s*(?P<l>{_NUM}(?:{_SEP}{_NUM})*)", re.I)
RE_PAR_REF = re.compile(rf"(?:§§?|\bpar[aá]grafos?\b)\s*(?P<l>{_NUM}(?:{_SEP}{_NUM})*)", re.I)
RE_PU_REF = re.compile(r"\bpar[aá]grafo\s+[úu]nico\b", re.I)
RE_INC_REF = re.compile(r"\bincisos?\s+(?P<l>(?-i:[IVXLCDM]+)(?:\s*(?:,|e|a|ao)\s*(?-i:[IVXLCDM]+))*)", re.I)
RE_ALI_REF = re.compile(r"\bal[ií]neas?\s+[“\"]?(?P<l>(?-i:[a-z])[”\"]?(?:\s*(?:,|e)\s*[“\"]?(?-i:[a-z])[”\"]?)*)", re.I)
RE_SPLIT_FRASES = re.compile(r"(?:,\s*)?\s+e\s+(?=(?:o|a|os|as)\s)|;")
RE_CONTINUA = re.compile(r"^\s*,?\s*e\s+(?:o|a|os|as)\s", re.I)


def _expande_numeros(lista: str) -> list[tuple[int, str]]:
    itens = [(m.group(0), m.start()) for m in re.finditer(_NUM, lista)]
    out: list[tuple[int, str]] = []
    for i, (txt, pos) in enumerate(itens):
        m = re.match(r"(\d+(?:\.\d{3})*)\s*[ºo°]?(?:-([A-Za-z]))?", txt)
        n, suf = int(m.group(1).replace(".", "")), (m.group(2) or "")
        antes = lista[itens[i - 1][1] + len(itens[i - 1][0]):pos] if i else ""
        if i and re.search(r"\b(a|ao)\b", antes) and not suf and not out[-1][1]:
            out.extend((k, "") for k in range(out[-1][0] + 1, n + 1))  # intervalo "5º a 7º"
        else:
            out.append((n, suf))
    return out


def _niveis(frase: str) -> dict[str, list[str]]:
    arts = [f"art{n}{s.lower()}" for m in RE_ART_REF.finditer(frase) for n, s in _expande_numeros(m.group("l"))]
    pars = [f"p{n}" for m in RE_PAR_REF.finditer(frase) for n, _ in _expande_numeros(m.group("l"))]
    if RE_PU_REF.search(frase):
        pars.append("pu")
    incs = []
    for m in RE_INC_REF.finditer(frase):
        for r in re.findall(r"[IVXLCDM]+", m.group("l")):
            if romano_valido(r):
                incs.append(f"inc{romano_para_int(r)}")
    alis = [f"al{c}" for m in RE_ALI_REF.finditer(frase) for c in re.findall(r"(?<![a-zà-ú])[a-z](?![a-zà-ú])", m.group("l"))]
    return {"art": arts, "par": pars, "inc": incs, "ali": alis}


def extrair_alvos(trecho: str) -> list[str]:
    """Caminhos de dispositivos mencionados em `trecho` ("o § 2º do art. 3º e o art. 6º" -> art3.p2, art6)."""
    frases = [f for f in RE_SPLIT_FRASES.split(trecho) if f and f.strip()]
    niveis = [_niveis(f) for f in frases]
    ultimo_art: list[str] = []
    for n in reversed(niveis):  # herda o artigo da frase seguinte ("o inciso II e o § 3º do art. 5º")
        if n["art"]:
            ultimo_art = n["art"]
        elif (n["par"] or n["inc"] or n["ali"]) and ultimo_art:
            n["art"] = ultimo_art
    alvos: list[str] = []
    for n in niveis:
        if not n["art"]:
            continue
        for combo in itertools.product(n["art"], n["par"] or [None], n["inc"] or [None], n["ali"] or [None]):
            c = ".".join(p for p in combo if p)
            if c not in alvos:
                alvos.append(c)
    return alvos


# ------------------------------------------------------------------ verbos
_V = re.I
VERBOS: list[tuple[str, re.Pattern, str]] = [
    ("ALTERA", re.compile(r"\bpass(?:a|am)\s+a\s+vigorar\s+acrescid[oa]s?", _V), "ACRESC"),
    ("ALTERA", re.compile(r"\bpass(?:a|am)\s+a\s+vigorar\s+com\s+(?:a|as)\s+seguintes?\s+(?:reda[cç][aã]o|reda[cç][oõ]es|altera[cç][oõ]es)", _V), "POST"),
    ("REVOGA", re.compile(r"\bfic(?:a|am)\s+revogad[oa]s?|\brevoga(?:m)?-se\b|\brevoga(?:m)?(?=\s+(?:o|a|os|as|art|§))", _V), "PRE"),
    ("ALTERA", re.compile(r"\bd[aá]\s+nova\s+reda[cç][aã]o\b|\bd[aá]-se\s+nova\s+reda[cç][aã]o\b", _V), "PRE"),
    ("ALTERA", re.compile(r"\bfic(?:a|am)\s+(?:alterad|acrescentad|inclu[ií]d)[oa]s?", _V), "PRE"),
    ("ALTERA", re.compile(r"\b(?:altera|acrescenta|inclui|insere)(?=\s+(?:o|a|os|as|dispositivos|art|§))", _V), "PRE"),
    ("REGULAMENTA", re.compile(r"\bregulamenta\b", _V), "PRE"),
    ("COMPLEMENTA", re.compile(r"\bcomplementa\b", _V), "PRE"),
    ("CONSOLIDA", re.compile(r"\bconsolida\b", _V), "PRE"),
    ("SUSPENDE", re.compile(r"\bfic(?:a|am)\s+suspens[oa]s?|\bsuspende\b", _V), "PRE"),
    ("RESTABELECE", re.compile(r"\bfic(?:a|am)\s+restabelecid[oa]s?|\brestabelece\b", _V), "PRE"),
]


def _verbos_em(texto: str) -> list[tuple[int, int, str, str]]:
    achados = []
    for tipo, rx, pos in VERBOS:
        for m in rx.finditer(texto):
            if re.search(r"\bn[ãa]o\s+(?:\w+\s+){0,2}$", texto[max(0, m.start() - 24):m.start()], re.I):
                continue  # negação: "não altera ..."
            achados.append((m.start(), m.end(), tipo, pos))
    achados.sort(key=lambda x: (x[0], -(x[1] - x[0])))
    filtrados, fim = [], -1
    for a in achados:  # remove sobreposições (mantém o primeiro/mais longo)
        if a[0] >= fim:
            filtrados.append(a)
            fim = a[1]
    return filtrados


# ------------------------------------------------------------------ citações (texto novo)
def extrair_citacoes(texto: str) -> list[str]:
    out, depth, buf = [], 0, []
    for ch in texto:
        if ch == "“":
            if depth > 0:
                buf.append(ch)
            else:
                buf = []
            depth += 1
        elif ch == "”" and depth > 0:
            depth -= 1
            if depth == 0:
                out.append("".join(buf).strip())
            else:
                buf.append(ch)
        elif depth > 0:
            buf.append(ch)
    if not out and texto.count('"') >= 2:
        partes = texto.split('"')
        out = [p.strip() for p in partes[1::2] if p.strip()]
    return out


def remover_citacoes(texto: str) -> str:
    out, depth = [], 0
    for ch in texto:
        if ch == "“":
            depth += 1
            out.append(" ")
        elif ch == "”" and depth > 0:
            depth -= 1
        elif depth == 0:
            out.append(ch)
    t = "".join(out)
    if '"' in t and t.count('"') % 2 == 0:
        t = re.sub(r'"[^"]*"', " ", t)
    return re.sub(r"\s+", " ", t)


def limpar_fragmento(blocos: list[str]) -> str | None:
    txt = "\n".join(b for b in blocos if b)
    txt = re.sub(r"\((?:NR|AC)\)", "", txt).strip()
    return txt or None


# ------------------------------------------------------------------ núcleo
def _alvos_por_ref(janela: str, refs: list[re.Match]) -> list[tuple[re.Match, list[str]]]:
    res: list[tuple[re.Match, list[str]]] = []
    inicio = 0
    for m in refs:
        res.append((m, extrair_alvos(janela[inicio:m.start()])))
        inicio = m.end()
    cauda = janela[inicio:]
    if res and RE_CONTINUA.match(cauda):
        extra = extrair_alvos(cauda)
        res[-1] = (res[-1][0], res[-1][1] + [a for a in extra if a not in res[-1][1]])
    return res


def _topo_do_fragmento(fragmento: str) -> list[str]:
    devs = parse_dispositivos(fragmento)
    caminhos = [d.caminho for d in devs if not RE_ELISAO.match(d.texto or "")]
    return [c for c in caminhos if not any(c != o and c.startswith(o + ".") for o in caminhos)]


def _de_unidade(texto_bruto: str, origem_caminho: str | None,
                verbo_herdado: tuple[str, str] | None) -> tuple[list[Detectada], tuple[str, str] | None]:
    """Relações de UMA unidade de texto (ementa ou dispositivo). Retorna também o verbo "herdável"
    pelos dispositivos filhos (ex.: caput "Ficam revogados:" seguido de incisos com as referências)."""
    citacoes = extrair_citacoes(texto_bruto)
    fragmento = limpar_fragmento(citacoes)
    texto = remover_citacoes(texto_bruto)
    verbos = _verbos_em(texto)
    tem_doc = bool(RE_DOC.search(texto))
    herdavel = (verbos[0][2], "PRE") if verbos and not tem_doc and verbos[0][2] in ("REVOGA", "ALTERA", "SUSPENDE", "RESTABELECE") else None
    if not verbos and verbo_herdado and tem_doc:
        verbos = [(0, 0, verbo_herdado[0], "PRE")]
    out: list[Detectada] = []
    pendentes: list[tuple[str, list[str]]] = []  # verbos cujos alvos vêm antes do nome do ato
    for i, (ini, fim, tipo, pos) in enumerate(verbos):
        prox = verbos[i + 1][0] if i + 1 < len(verbos) else len(texto)
        ante = verbos[i - 1][1] if i else 0
        janela = texto[fim:prox] if pos == "PRE" else texto[ante:ini]
        refs = list(RE_DOC.finditer(janela))
        if pos == "ACRESC":  # "A Resolução X passa a vigorar acrescida do seguinte art. 5º-A:"
            pares = [(refs[-1], extrair_alvos(texto[fim:prox]))] if refs else []
        else:
            pares = _alvos_por_ref(janela, refs)
        if not pares:
            alvos = extrair_alvos(janela)
            if alvos:
                pendentes.append((tipo, alvos))
            continue
        for par in pares:
            _emitir(out, tipo, par, texto_bruto, origem_caminho, fragmento)
        for tipo_p, alvos_p in pendentes:  # "Altera o inciso II do art. 5º e acrescenta o art. 5º-A à Resolução X"
            _emitir(out, tipo_p, (pares[0][0], alvos_p), texto_bruto, origem_caminho, fragmento)
        pendentes = []
    return _dedup_local(out), herdavel


def _emitir(out: list[Detectada], tipo: str, par: tuple[re.Match, list[str]], texto: str, origem_caminho: str | None,
            fragmento: str | None) -> None:
    ref, alvos = par
    tipo_doc = canon_tipo(ref.group("tipo"))
    ano = ref.group("ano1") or ref.group("ano2")
    emissor = ref.group("emissor")
    emissor = emissor.upper() if emissor and emissor.upper() not in ("N", "NO") else None
    base = dict(origem_caminho=origem_caminho, destino_tipo=tipo_doc, destino_numero=norm_numero(ref.group("num")),
                destino_ano=int(ano) if ano else None, destino_emissor=emissor, destino_ref=ref.group(0).strip(),
                evidencia=re.sub(r"\s+", " ", texto).strip()[:600])
    if tipo == "ALTERA" and fragmento and not alvos:
        alvos = _topo_do_fragmento(fragmento)  # alvos deduzidos do próprio texto novo
    if not alvos:
        t = "REVOGA" if tipo == "REVOGA" else tipo
        out.append(Detectada(tipo=t, destino_caminho=None, texto_novo=fragmento if tipo == "ALTERA" else None, **base))
        return
    for a in alvos:
        t = "REVOGA_PARCIALMENTE" if tipo == "REVOGA" else tipo
        out.append(Detectada(tipo=t, destino_caminho=a, texto_novo=fragmento if tipo == "ALTERA" else None, **base))


def _dedup_local(lista: list[Detectada]) -> list[Detectada]:
    vistos, out = set(), []
    for d in lista:
        k = (d.tipo, d.destino_tipo, d.destino_numero, d.destino_ano, d.destino_caminho, d.origem_caminho)
        if k not in vistos:
            vistos.add(k)
            out.append(d)
    return out


def detectar(ementa: str | None, dispositivos: list[DispositivoP]) -> list[Detectada]:
    """Detecta relações a partir da ementa e dos dispositivos de UM documento."""
    todas: list[Detectada] = []
    if ementa:
        todas += _de_unidade(ementa, None, None)[0]
    herdados: dict[str, tuple[str, str]] = {}
    for d in dispositivos:
        pai = d.pai
        heranca = None
        while pai:
            if pai in herdados:
                heranca = herdados[pai]
                break
            pai = ".".join(pai.split(".")[:-1]) or None
        dets, herdado = _de_unidade(d.texto, d.caminho, heranca)
        todas += dets
        if herdado:
            herdados[d.caminho] = herdado
    return _consolidar(todas)


def _consolidar(todas: list[Detectada]) -> list[Detectada]:
    """Remove duplicidades entre ementa e corpo: prefere a relação com dispositivo de origem/texto novo,
    e descarta relação em nível de documento quando existe relação por dispositivo do mesmo tipo/destino."""
    def chave_doc(d: Detectada):
        return (d.destino_tipo, d.destino_numero, d.destino_ano)

    com_alvo = {(chave_doc(d), d.tipo.replace("_PARCIALMENTE", "")) for d in todas if d.destino_caminho}
    filtradas = [d for d in todas if d.destino_caminho or (chave_doc(d), d.tipo.replace("_PARCIALMENTE", "")) not in com_alvo]
    melhor: dict[tuple, Detectada] = {}
    for d in filtradas:
        k = (d.tipo, chave_doc(d), d.destino_caminho)
        atual = melhor.get(k)
        score = (bool(d.texto_novo), d.origem_caminho is not None)
        if atual is None or score > (bool(atual.texto_novo), atual.origem_caminho is not None):
            melhor[k] = d
    return list(melhor.values())
