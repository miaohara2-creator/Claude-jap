#!/usr/bin/env python3
"""日本語 — aprendizado incremental de japonês com frases geradas pela Claude.

Uso:
    python3 app.py                      # sobe a interface em http://127.0.0.1:8765
    python3 app.py --porta 9000
    python3 app.py --banco /tmp/teste.db --modelo claude-sonnet-5-5
    python3 app.py --cli                # modo terminal (sem navegador)
"""

from __future__ import annotations

import argparse
import sys

from nihongo.server import serve


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Aprendizado incremental de japonês (FSRS + frases da Claude)."
    )
    parser.add_argument("--porta", type=int, default=8765, help="porta HTTP (8765)")
    parser.add_argument("--host", default="127.0.0.1", help="endereço de escuta")
    parser.add_argument("--banco", default=None, help="caminho do banco SQLite")
    parser.add_argument("--modelo", default=None, help="modelo da Claude a usar")
    parser.add_argument("--cli", action="store_true", help="estudar pelo terminal")
    args = parser.parse_args(argv)

    if args.cli:
        from nihongo.cli import run_cli

        return run_cli(db_path=args.banco, model=args.modelo)

    serve(db_path=args.banco, host=args.host, port=args.porta, model=args.modelo)
    return 0


if __name__ == "__main__":
    sys.exit(main())
