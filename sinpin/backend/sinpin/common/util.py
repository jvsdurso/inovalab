from __future__ import annotations

import hashlib
import json
import threading
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable


_trava = threading.Lock()
_ultimo = datetime.min.replace(tzinfo=timezone.utc)


def agora() -> str:
    """Instante UTC (tempo de sistema / transação), em microssegundos e ESTRITAMENTE crescente no processo.

    A ordem de registro é usada como critério de desempate (ex.: ordem de aplicação de efeitos); por isso nunca
    devolve dois valores iguais, mesmo em relógios de baixa resolução."""
    global _ultimo
    with _trava:
        t = datetime.now(timezone.utc)
        if t <= _ultimo:
            t = _ultimo + timedelta(microseconds=1)
        _ultimo = t
        return t.isoformat(timespec="microseconds")


def hoje() -> str:
    return date.today().isoformat()


def novo_id() -> str:
    return uuid.uuid4().hex


def sha256(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)


def loads(txt: str | None, padrao: Any = None) -> Any:
    if not txt:
        return padrao
    try:
        return json.loads(txt)
    except ValueError:
        return padrao


def row(r) -> dict | None:
    return dict(r) if r is not None else None


def rows(rs: Iterable) -> list[dict]:
    return [dict(r) for r in rs]


def valida_data(s: str | None) -> str | None:
    """Aceita apenas AAAA-MM-DD válidas."""
    if not s:
        return None
    try:
        return date.fromisoformat(s).isoformat()
    except ValueError:
        return None


def br(data: str | None) -> str:
    """AAAA-MM-DD -> DD/MM/AAAA (apresentação)."""
    if not data or len(data) != 10:
        return data or "—"
    return f"{data[8:10]}/{data[5:7]}/{data[0:4]}"
