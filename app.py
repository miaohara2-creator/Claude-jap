#!/usr/bin/env python3
"""日本語 — aprendizado incremental de japonês com frases geradas pela Claude.

Uso:
    python3 app.py                      # sobe a interface em http://127.0.0.1:8765
    python3 app.py --porta 9000
    python3 app.py --banco /tmp/teste.db --modelo claude-sonnet-5-5
    python3 app.py --cli                # modo terminal (sem navegador)
    python3 app.py --sem-navegador      # não abrir o navegador sozinho

No Windows, use o atalho `iniciar.bat` (duplo clique).
"""

from __future__ import annotations

import argparse
import sys

#: Versão mínima suportada. Não há recurso de 3.10+ no código: todas as
#: anotações são adiadas por `from __future__ import annotations`. A
#: automação do Windows testa 3.9, 3.10 e 3.12 para manter isso verdadeiro.
VERSAO_MINIMA = (3, 9)

if sys.version_info < VERSAO_MINIMA:  # pragma: no cover
    sys.exit(
        f"Este aplicativo precisa do Python {VERSAO_MINIMA[0]}.{VERSAO_MINIMA[1]} "
        f"ou mais novo (encontrei o {sys.version.split()[0]}). "
        "Baixe em https://python.org/downloads"
    )

from nihongo.config import carregar_chave_local, configurar_saida_utf8
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
    parser.add_argument("--sem-navegador", action="store_true",
                        help="não abrir o navegador automaticamente")
    parser.add_argument("--digitar", action="store_true",
                        help="modo terminal: digitar a tradução em vez de se autoavaliar")
    args = parser.parse_args(argv)

    configurar_saida_utf8()
    carregar_chave_local()

    if args.cli:
        from nihongo.cli import run_cli

        return run_cli(db_path=args.banco, model=args.modelo, digitar=args.digitar)

    serve(db_path=args.banco, host=args.host, port=args.porta, model=args.modelo,
          abrir_navegador=not args.sem_navegador)
    return 0


if __name__ == "__main__":
    sys.exit(main())
