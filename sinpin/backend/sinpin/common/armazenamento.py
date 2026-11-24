"""Armazenamento de arquivos originais. Interface mínima; hoje em disco local, depois S3-compatível."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol


class Armazenamento(Protocol):
    def salvar(self, chave: str, dados: bytes) -> str: ...
    def ler(self, chave: str) -> bytes: ...


class ArmazenamentoLocal:
    def __init__(self, raiz: str):
        self.raiz = Path(raiz)
        self.raiz.mkdir(parents=True, exist_ok=True)

    def _caminho(self, chave: str) -> Path:
        p = (self.raiz / chave).resolve()
        if self.raiz.resolve() not in p.parents:
            raise ValueError("chave inválida")
        return p

    def salvar(self, chave: str, dados: bytes) -> str:
        p = self._caminho(chave)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(dados)
        return chave

    def ler(self, chave: str) -> bytes:
        return self._caminho(chave).read_bytes()
