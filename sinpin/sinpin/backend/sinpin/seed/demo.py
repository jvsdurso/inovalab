"""Dados de demonstração: normas 100% SINTÉTICAS (fictícias), importadas pelo mesmo caminho do usuário.

Cobrem: regulamentação (Lei -> Resolução), revogação total (Res. 101 revoga Res. 52), alteração de inciso
e inclusão de artigo (Res. 215), alteração de caput e revogações parciais (Res. 340), ato restrito da SENATRAN
e ato restrito do DETRAN-XX (para demonstrar o isolamento institucional).
NÃO são normas reais. Não use para decisões.
"""
from __future__ import annotations

from pathlib import Path

from ..config import Settings
from ..common.armazenamento import Armazenamento
from ..db import Database
from ..identidade import service as ident
from ..ingestao import service as ingestao

PASTA = Path(__file__).resolve().parent / "normas"

# (arquivo, escopo, login de quem importa)
MANIFESTO = [
    ("01_lei_1001_2015.txt", "NACIONAL", "curador"),
    ("02_resolucao_52_2012.txt", "NACIONAL", "curador"),
    ("03_resolucao_101_2018.txt", "NACIONAL", "curador"),
    ("04_resolucao_215_2021.txt", "NACIONAL", "curador"),
    ("05_resolucao_340_2023.txt", "NACIONAL", "curador"),
    ("06_portaria_senatran_12_2024.txt", "INSTITUCIONAL_RESTRITO", "senatran.servidor"),
    ("07_in_detran_xx_3_2024.txt", "INSTITUCIONAL_RESTRITO", "detran.servidor"),
]


def semear(db: Database, st: Settings, armazenamento: Armazenamento) -> list[dict]:
    n = db.conn().execute("SELECT COUNT(*) AS n FROM documento").fetchone()["n"]
    if n:
        return []
    out = []
    for arquivo, escopo, login in MANIFESTO:
        ctx = ident.contexto_por_login(db, login)
        r = ingestao.ingerir(db, st, armazenamento, ctx, nome_arquivo=arquivo, conteudo=(PASTA / arquivo).read_bytes(),
                             texto=None, escopo=escopo, sintetico=True)
        out.append(r)
    return out
