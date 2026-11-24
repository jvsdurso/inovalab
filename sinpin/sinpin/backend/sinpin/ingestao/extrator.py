"""Extração de texto de arquivos (txt/md, html, pdf, docx). OCR NÃO está implementado (PDF escaneado -> aviso)."""
from __future__ import annotations

import io
import re
from html.parser import HTMLParser

from ..common.erros import invalido


def normalizar(texto: str) -> str:
    texto = texto.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n").replace(" ", " ")
    texto = re.sub(r"[ \t]+\n", "\n", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


class _Html(HTMLParser):
    """HTML -> texto. Ignora script/style/head; quebra linha em tags de bloco; DESCARTA texto tachado
    (<strike>/<s>/<del>), que em textos compilados (ex.: Planalto) representa redação revogada/substituída."""
    BLOCOS = {"p", "div", "br", "li", "tr", "table", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "section", "article", "ul", "ol"}
    IGNORAR = {"script", "style", "head", "noscript"}
    TACHADO = {"strike", "s", "del"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.partes: list[str] = []
        self._ign = 0
        self._tach = 0
        self.tachado_descartado = False

    def handle_starttag(self, tag, attrs):
        if tag in self.IGNORAR:
            self._ign += 1
        elif tag in self.TACHADO:
            self._tach += 1
        elif tag in self.BLOCOS:
            self.partes.append("\n")
        elif tag in ("td", "th"):
            self.partes.append(" | ")

    def handle_endtag(self, tag):
        if tag in self.IGNORAR:
            self._ign = max(0, self._ign - 1)
        elif tag in self.TACHADO:
            self._tach = max(0, self._tach - 1)
        elif tag in self.BLOCOS:
            self.partes.append("\n")

    def handle_data(self, data):
        if self._ign:
            return
        if self._tach:
            if data.strip():
                self.tachado_descartado = True
            return
        self.partes.append(data)


def extrair_texto(nome: str | None, conteudo: bytes) -> tuple[str, list[str]]:
    avisos: list[str] = []
    ext = (nome or "").lower().rsplit(".", 1)[-1] if nome and "." in nome else "txt"
    if ext in ("txt", "md", "text"):
        try:
            texto = conteudo.decode("utf-8")
        except UnicodeDecodeError:
            texto = conteudo.decode("latin-1")
            avisos.append("Arquivo não estava em UTF-8; interpretado como Latin-1.")
    elif ext in ("htm", "html"):
        try:
            bruto = conteudo.decode("utf-8")
        except UnicodeDecodeError:
            bruto = conteudo.decode("cp1252", errors="replace")
            avisos.append("HTML não estava em UTF-8; interpretado como Windows-1252 (comum em páginas antigas). Confira acentos.")
        h = _Html()
        h.feed(bruto)
        texto = re.sub(r"[ \t]*\n[ \t]*", "\n", re.sub(r"[ \t\u00a0]+", " ", "".join(h.partes)))
        if h.tachado_descartado:
            avisos.append("Texto tachado (<strike>/<s>/<del>) foi descartado por representar redação revogada em texto compilado. "
                          "Confira com o ato original e a publicação no DOU.")
    elif ext == "pdf":
        from pypdf import PdfReader
        try:
            leitor = PdfReader(io.BytesIO(conteudo))
            texto = "\n".join((p.extract_text() or "") for p in leitor.pages)
        except Exception as e:  # noqa: BLE001 - pypdf lança vários tipos
            raise invalido(f"Não foi possível ler o PDF: {e}")
        if len(texto.strip()) < 40:
            avisos.append("PDF sem texto extraível (provavelmente escaneado). OCR ainda não está implementado.")
    elif ext == "docx":
        import docx
        try:
            d = docx.Document(io.BytesIO(conteudo))
        except Exception as e:  # noqa: BLE001
            raise invalido(f"Não foi possível ler o DOCX: {e}")
        partes = [p.text for p in d.paragraphs]
        for t in d.tables:
            for linha in t.rows:
                partes.append(" | ".join(c.text.strip() for c in linha.cells))
        texto = "\n".join(partes)
    else:
        raise invalido(f"Formato .{ext} não suportado. Use TXT, HTML, PDF ou DOCX.")
    texto = normalizar(texto)
    if not texto:
        raise invalido("Nenhum texto foi extraído do arquivo.")
    return texto, avisos
