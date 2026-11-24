"""Uso:  python -m sinpin [--demo] [--host 127.0.0.1] [--port 8000]   (equivale a uvicorn sinpin.api.app:create_app --factory)"""
from __future__ import annotations

import argparse
import os

import uvicorn


def main() -> None:
    ap = argparse.ArgumentParser(prog="sinpin")
    ap.add_argument("--host", default=os.environ.get("SINPIN_HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("SINPIN_PORT", "8000")))
    ap.add_argument("--demo", action="store_true", help="carrega normas SINTÉTICAS de demonstração se o banco estiver vazio")
    ap.add_argument("--reload", action="store_true", help="recarrega ao editar o código (desenvolvimento)")
    a = ap.parse_args()
    if a.demo:
        os.environ["SINPIN_SEED_DEMO"] = "1"
    uvicorn.run("sinpin.api.app:create_app", factory=True, host=a.host, port=a.port, reload=a.reload, log_level="info")


if __name__ == "__main__":
    main()
