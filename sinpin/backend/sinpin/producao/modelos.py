"""Modelos (estruturas) de documentos administrativos. Ajustáveis por instituição no futuro."""
from __future__ import annotations

PLACEHOLDER = "[A PREENCHER PELO SERVIDOR]"

MODELOS: dict[str, dict] = {
    "NOTA_TECNICA": {
        "nome": "Nota Técnica",
        "secoes": [("assunto", "Assunto"), ("relatorio", "I — Relatório"), ("fundamentacao", "II — Fundamentação normativa"),
                   ("analise", "III — Análise"), ("conclusao", "IV — Conclusão")],
    },
    "PARECER": {
        "nome": "Parecer",
        "secoes": [("ementa", "Ementa"), ("relatorio", "I — Relatório"), ("fundamentacao", "II — Fundamentação"),
                   ("conclusao", "III — Conclusão")],
    },
    "DESPACHO": {
        "nome": "Despacho",
        "secoes": [("referencia", "Referência"), ("corpo", "Despacho"), ("encaminhamento", "Encaminhamento")],
    },
    "OFICIO": {
        "nome": "Ofício",
        "secoes": [("destinatario", "Destinatário"), ("assunto", "Assunto"), ("corpo", "Corpo do ofício"), ("fecho", "Fecho")],
    },
    "INFORMACAO": {
        "nome": "Informação",
        "secoes": [("assunto", "Assunto"), ("historico", "Histórico"), ("fundamentacao", "Fundamentação normativa"),
                   ("conclusao", "Conclusão")],
    },
    "RELATORIO": {
        "nome": "Relatório",
        "secoes": [("objetivo", "Objetivo"), ("desenvolvimento", "Desenvolvimento"), ("fundamentacao", "Fundamentação normativa"),
                   ("conclusao", "Conclusões e recomendações")],
    },
    "MANIFESTACAO": {
        "nome": "Manifestação administrativa",
        "secoes": [("assunto", "Assunto"), ("manifestacao", "Manifestação"), ("fundamentacao", "Fundamentação normativa"),
                   ("conclusao", "Conclusão")],
    },
}

SECAO_REFERENCIAS = ("referencias", "Referências normativas (geradas automaticamente)")
AVISO_IA = ("Minuta elaborada com apoio de inteligência artificial. O conteúdo deve ser integralmente revisado e "
            "aprovado pelo servidor responsável antes de qualquer uso oficial.")
