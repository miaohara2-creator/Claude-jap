"""Configuracao local do aplicativo (chave da API fora de variavel de ambiente).

No Windows, definir uma variavel de ambiente e incomodo, entao aceitamos a
chave num arquivo `chave-api.txt` ao lado do `app.py`. A variavel de ambiente
tem precedencia; o arquivo e apenas a alternativa conveniente.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO_CHAVE = "chave-api.txt"


def ler_chave_do_arquivo(caminho: Path) -> str | None:
    """Primeira linha util do arquivo (ignora vazias e comentarios com #)."""
    try:
        conteudo = caminho.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return None
    for linha in conteudo.splitlines():
        linha = linha.strip()
        if linha and not linha.startswith("#"):
            return linha
    return None


def carregar_chave_local(raiz: Path | None = None) -> str | None:
    """Preenche ANTHROPIC_API_KEY a partir de `chave-api.txt`, se necessario.

    Devolve a origem da chave ("ambiente", "arquivo") ou None se nao houver
    chave nenhuma -- nesse caso o app usa o gerador local.
    """
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return "ambiente"
    chave = ler_chave_do_arquivo((raiz or RAIZ) / ARQUIVO_CHAVE)
    if chave:
        os.environ["ANTHROPIC_API_KEY"] = chave
        return "arquivo"
    return None


def configurar_saida_utf8() -> None:
    """Garante que o terminal aceite japonês.

    No Windows o console costuma usar cp1252, e qualquer `print` com kanji
    derruba o aplicativo com UnicodeEncodeError. Isso acontece sempre que o
    app é iniciado fora do `iniciar.bat` (que define PYTHONUTF8) ou com a
    saída redirecionada. Reconfigurar aqui resolve na origem.
    """
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):  # pragma: no cover
            pass


#: O pacote `anthropic` exige Python 3.10+. O app em si roda em 3.9.
VERSAO_MINIMA_API = (3, 10)


def python_suporta_api() -> bool:
    return sys.version_info >= VERSAO_MINIMA_API
