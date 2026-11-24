"""Exportação de minutas para DOCX (python-docx) e PDF (reportlab)."""
from __future__ import annotations

import io
from xml.sax.saxutils import escape

from .modelos import AVISO_IA

_SUBST = {"→": "->", "≥": ">=", "≤": "<=", "•": "-", "‑": "-", "​": ""}


def _limpar(t: str) -> str:
    for a, b in _SUBST.items():
        t = t.replace(a, b)
    return t


def _paragrafos(txt: str) -> list[str]:
    return [p.strip() for p in _limpar(txt).split("\n\n") if p.strip()] or [""]


def para_docx(minuta: dict, orgao_nome: str) -> bytes:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Cm, Pt

    d = Document()
    for s in d.sections:
        s.left_margin, s.right_margin, s.top_margin, s.bottom_margin = Cm(3), Cm(2), Cm(2.5), Cm(2)
        s.header.paragraphs[0].text = "MINUTA — DOCUMENTO EM ELABORAÇÃO (não oficial até aprovação)"
        s.header.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        s.footer.paragraphs[0].text = AVISO_IA
    st = d.styles["Normal"]
    st.font.name, st.font.size = "Arial", Pt(12)
    p = d.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run(orgao_nome.upper()).bold = True
    t = d.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    t.add_run(_limpar(minuta["titulo"]).upper()).bold = True
    for sec in minuta["secoes"]:
        h = d.add_paragraph()
        h.paragraph_format.space_before = Pt(12)
        h.add_run(_limpar(sec["titulo"])).bold = True
        for par in _paragrafos(sec["texto"]):
            q = d.add_paragraph(par)
            q.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            q.paragraph_format.first_line_indent = Cm(1.25)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def para_pdf(minuta: dict, orgao_nome: str) -> bytes:
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    base = ParagraphStyle("b", fontName="Helvetica", fontSize=11, leading=15, alignment=TA_JUSTIFY, firstLineIndent=1.0 * cm, spaceAfter=6)
    cab = ParagraphStyle("c", parent=base, alignment=TA_CENTER, firstLineIndent=0, fontName="Helvetica-Bold", spaceAfter=4)
    sec = ParagraphStyle("s", parent=base, firstLineIndent=0, fontName="Helvetica-Bold", spaceBefore=10, alignment=0)

    def rodape(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        meio = _limpar(AVISO_IA).find(" ", 105)
        canvas.drawCentredString(A4[0] / 2, 1.3 * cm, _limpar(AVISO_IA)[:meio])
        canvas.drawCentredString(A4[0] / 2, 0.95 * cm, _limpar(AVISO_IA)[meio + 1:])
        canvas.drawCentredString(A4[0] / 2, A4[1] - 1.2 * cm, "MINUTA - DOCUMENTO EM ELABORACAO (nao oficial ate aprovacao)")
        canvas.restoreState()

    def fmt(t: str) -> str:
        return escape(_limpar(t)).replace("\n", "<br/>")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=3 * cm, rightMargin=2 * cm, topMargin=2.5 * cm, bottomMargin=2.2 * cm,
                            title=_limpar(minuta["titulo"]))
    story = [Paragraph(fmt(orgao_nome.upper()), cab), Paragraph(fmt(minuta["titulo"].upper()), cab), Spacer(1, 10)]
    for s in minuta["secoes"]:
        story.append(Paragraph(fmt(s["titulo"]), sec))
        for par in _paragrafos(s["texto"]):
            story.append(Paragraph(fmt(par), base))
    doc.build(story, onFirstPage=rodape, onLaterPages=rodape)
    return buf.getvalue()
