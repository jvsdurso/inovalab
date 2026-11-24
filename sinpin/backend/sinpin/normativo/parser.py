"""Extração de metadados e da estrutura (artigos, §, incisos, alíneas) de atos normativos.

Heurísticas baseadas na técnica legislativa brasileira. Não é um parser perfeito: limitações
conhecidas estão no README (ex.: itens numerados, anexos/tabelas, PDFs escaneados sem OCR).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

from .caminhos import (nivel_do_segmento, pai_de_caminho, romano_para_int, romano_valido, rotulo_de_caminho,
                       seg_artigo)
from .tipos import canon_tipo, montar_titulo, norm_numero, sem_acentos

MESES = {"janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6, "julho": 7,
         "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12}


# --------------------------------------------------------------------------- datas / metadados

def data_por_extenso(s: str) -> str | None:
    t = sem_acentos(s.lower())
    m = re.search(r"(\d{1,2})\s*[oº°]?\s+de\s+([a-z]+)\s+de\s+(\d{4})", t)
    if m and m.group(2) in MESES:
        try:
            return date(int(m.group(3)), MESES[m.group(2)], int(m.group(1))).isoformat()
        except ValueError:
            return None
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", t)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
        except ValueError:
            return None
    return None


TIPOS_RE = (r"lei\s+complementar|lei|decreto-lei|decreto|resolu[cç][aã]o|portaria|"
            r"instru[cç][aã]o\s+normativa|delibera[cç][aã]o|medida\s+provis[oó]ria|nota\s+t[eé]cnica|"
            r"ordem\s+de\s+servi[cç]o")
RE_CABECALHO = re.compile(
    rf"^\s*(?P<tipo>{TIPOS_RE})\b(?P<meio>[^\n]*?)\bn[ºo°\.]*\s*(?P<num>\d+(?:\.\d{{3}})*)(?P<resto>.*)$", re.I)
RE_EMENTA = re.compile(
    r"^(disp[õo]e|altera|regulamenta|estabelece|revoga|aprova|institui|define|consolida|acrescenta|"
    r"disciplina|fixa|cria|normatiza|trata|torna|autoriza|determina|delega|institui)\b", re.I)


@dataclass
class Metadados:
    tipo: str = "OUTRO"
    numero: str | None = None
    ano: int | None = None
    orgao_emissor: str | None = None
    data_publicacao: str | None = None
    ementa: str | None = None
    titulo: str | None = None
    linha_cabecalho: int | None = None


def extrair_metadados(texto: str) -> Metadados:
    md = Metadados()
    linhas = [l.strip() for l in texto.splitlines()]
    for i, l in enumerate(linhas[:40]):
        if not l:
            continue
        m = RE_CABECALHO.match(l)
        if not m:
            continue
        md.linha_cabecalho = i
        md.tipo = canon_tipo(re.sub(r"\s+", " ", m.group("tipo")))
        emissor = m.group("meio").strip(" ,-–—")
        md.orgao_emissor = emissor.upper() if emissor and len(emissor) <= 30 else None
        md.numero = norm_numero(m.group("num"))
        resto = m.group("resto")
        md.data_publicacao = data_por_extenso(resto)
        if not md.data_publicacao:  # cabeçalho quebrado em duas linhas
            seguinte = next((x for x in linhas[i + 1:i + 3] if x), "")
            md.data_publicacao = data_por_extenso(resto + " " + seguinte)
        ma = re.search(r"/\s*(\d{4})", resto) or re.search(r"\b(\d{4})\b", resto)
        if md.data_publicacao:
            md.ano = int(md.data_publicacao[:4])
        elif ma:
            md.ano = int(ma.group(1))
        # ementa: primeira linha após o cabeçalho que comece com verbo de ementa
        buf: list[str] = []
        for x in linhas[i + 1:i + 14]:
            if not x:
                if buf:
                    break
                continue
            if x.startswith("Art"):
                break
            if not buf and not RE_EMENTA.match(x):
                continue
            buf.append(x)
        if buf:
            md.ementa = " ".join(buf)
        break
    md.titulo = montar_titulo(md.tipo, md.orgao_emissor, md.numero, md.ano) if md.numero else None
    return md


def detectar_vigencia_inicio(texto: str, data_pub: str | None) -> tuple[str | None, str]:
    """Retorna (data, certeza) com certeza em EXPLICITA | PRESUMIDA | DESCONHECIDA."""
    t = sem_acentos(texto.lower())
    if re.search(r"entra(?:m)? em vigor\s+na\s+data\s+(?:de\s+sua|da)\s+publicacao", t):
        return data_pub, ("EXPLICITA" if data_pub else "DESCONHECIDA")
    m = re.search(r"(?:entra(?:m)? em vigor|produz(?:em)? efeitos|vigencia)[^.]{0,80}?"
                  r"(?:em|a partir de|a contar de)\s+(\d{1,2})\s*[oº°]?\s+de\s+([a-z]+)\s+de\s+(\d{4})", t)
    if m and m.group(2) in MESES:
        try:
            return date(int(m.group(3)), MESES[m.group(2)], int(m.group(1))).isoformat(), "EXPLICITA"
        except ValueError:
            pass
    m = re.search(r"entra(?:m)? em vigor[^.]{0,60}?(\d{1,3})\s*(?:\([^)]*\)\s*)?dias(?:\s+corridos)?\s+"
                  r"(?:apos|contados\s+d[ae])\s+(?:a\s+)?(?:data\s+d[ea]\s+)?(?:sua\s+)?publicacao", t)
    if m and data_pub:
        return (date.fromisoformat(data_pub) + timedelta(days=int(m.group(1)))).isoformat(), "EXPLICITA"
    if data_pub:
        return data_pub, "PRESUMIDA"
    return None, "DESCONHECIDA"


# --------------------------------------------------------------------------- dispositivos

@dataclass
class DispositivoP:
    caminho: str
    nivel: str
    texto: str
    ordem: int
    grupo: str | None = None

    @property
    def rotulo(self) -> str:
        return rotulo_de_caminho(self.caminho)

    @property
    def pai(self) -> str | None:
        return pai_de_caminho(self.caminho)


RE_ART = re.compile(
    r"^Art\.?\s*(?P<n>\d+(?:\.\d{3})*)\s*[ºo°]?(?:-(?P<suf>[A-Z])\b)?\s*(?:[.\-–—:]\s*|\s+)?(?P<resto>.*)$")
RE_PAR = re.compile(r"^§\s*(?P<n>\d+)\s*[ºo°]?\s*(?:[.\-–—:]\s*|\s+)?(?P<resto>.*)$")
RE_PU = re.compile(r"^Par[áa]grafo\s+[úu]nico\s*(?:[.\-–—:]\s*|\s+)?(?P<resto>.*)$", re.I)
RE_INC = re.compile(r"^(?P<rom>[IVXLCDM]+)\s*[-–—]\s+(?P<resto>.*)$")
RE_ALI = re.compile(r"^(?P<l>[a-z])\)\s+(?P<resto>.*)$")
RE_GRUPO = re.compile(r"^(?:LIVRO|T[ÍI]TULO|CAP[ÍI]TULO|SE[ÇC][ÃA]O|SUBSE[ÇC][ÃA]O)\s+[IVXLCDM\d]+\b.*$", re.I)
RE_ELISAO = re.compile(r"^[\s\.…\(\)\-–—]*$")


class _Estado:
    def __init__(self, prefixo: str = ""):
        self.art = self.par = self.inc = self.ali = None
        for seg in filter(None, prefixo.split(".")):
            n = nivel_do_segmento(seg)
            if n == "ARTIGO":
                self.art = seg
            elif n == "PARAGRAFO":
                self.par = seg
            elif n == "INCISO":
                self.inc = seg
            elif n == "ALINEA":
                self.ali = seg

    def abrir(self, nivel: str, seg: str) -> str:
        if nivel == "ARTIGO":
            self.art, self.par, self.inc, self.ali = seg, None, None, None
        elif nivel == "PARAGRAFO":
            self.par, self.inc, self.ali = seg, None, None
        elif nivel == "INCISO":
            self.inc, self.ali = seg, None
        elif nivel == "ALINEA":
            self.ali = seg
        return ".".join(p for p in (self.art, self.par, self.inc, self.ali) if p)


def _atualiza_aspas(linha: str, depth: int, reto: bool) -> tuple[int, bool]:
    depth = max(0, depth + linha.count("“") - linha.count("”"))
    if linha.count('"') % 2 == 1:
        reto = not reto
    return depth, reto


def parse_dispositivos(texto: str, prefixo: str = "") -> list[DispositivoP]:
    """Estrutura `texto` em dispositivos. `prefixo` permite interpretar fragmentos
    (ex.: o texto entre aspas de um ato modificador) a partir de um dispositivo-pai."""
    st = _Estado(prefixo)
    out: list[DispositivoP] = []
    cur: DispositivoP | None = None
    depth, reto = 0, False
    grupo: str | None = None
    aguarda_titulo = False

    def abrir(nivel: str, seg: str, resto: str):
        nonlocal cur
        caminho = st.abrir(nivel, seg)
        cur = DispositivoP(caminho, nivel, resto.strip(), len(out), grupo)
        out.append(cur)

    for bruto in texto.splitlines():
        linha = bruto.strip()
        if not linha:
            continue
        em_aspas = depth > 0 or reto
        abre = linha[0] in '“"'
        if em_aspas or abre:  # bloco citado: nunca gera dispositivos próprios
            depth, reto = _atualiza_aspas(linha, depth, reto)
            if cur is not None:
                sep = " " if (not em_aspas and depth == 0 and not reto) else "\n"
                cur.texto += sep + linha
            continue
        if aguarda_titulo:
            aguarda_titulo = False
            if linha.isupper() and len(linha) < 120:
                grupo = f"{grupo} — {linha}"
                continue
        if RE_GRUPO.match(linha):
            grupo = linha
            aguarda_titulo = True
            cur = None
            continue
        if m := RE_ART.match(linha):
            n = int(m.group("n").replace(".", ""))
            abrir("ARTIGO", seg_artigo(n, m.group("suf") or ""), m.group("resto"))
        elif (m := RE_PAR.match(linha)) and st.art:
            abrir("PARAGRAFO", f"p{int(m.group('n'))}", m.group("resto"))
        elif (m := RE_PU.match(linha)) and st.art:
            abrir("PARAGRAFO", "pu", m.group("resto"))
        elif (m := RE_INC.match(linha)) and romano_valido(m.group("rom")) and st.art:
            abrir("INCISO", f"inc{romano_para_int(m.group('rom'))}", m.group("resto"))
        elif (m := RE_ALI.match(linha)) and (st.inc or st.par or st.art):
            abrir("ALINEA", f"al{m.group('l')}", m.group("resto"))
        elif cur is not None:
            cur.texto += " " + linha
        # estado de aspas após linha de dispositivo (ex.: "Art. 2º ... redação: “Art. 5º ...")
        depth, reto = _atualiza_aspas(linha, depth, reto)
    for d in out:
        d.texto = re.sub(r"[ \t]+", " ", d.texto).strip()
    return out


def e_elisao(texto: str) -> bool:
    """Linhas como 'I - ......' ou '§ 1º (...)' em citações: dispositivo mantido, não alterado."""
    return bool(RE_ELISAO.match(texto or ""))


def fragmento_para_dispositivos(fragmento: str, caminho_alvo: str) -> list[DispositivoP]:
    """Interpreta o texto novo de uma alteração, relativo ao dispositivo-alvo, e devolve apenas
    os dispositivos que são o alvo ou descendentes dele (sem elisões)."""
    from .caminhos import descende_de
    prefixo = ".".join(caminho_alvo.split(".")[:-1])
    devs = parse_dispositivos(fragmento, prefixo=prefixo)
    return [d for d in devs if descende_de(d.caminho, caminho_alvo) and not e_elisao(d.texto)]


def estrutura_resumo(devs: list[DispositivoP]) -> dict:
    return {"total": len(devs), "artigos": sum(1 for d in devs if d.nivel == "ARTIGO")}
