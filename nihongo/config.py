"""Configuracao local do aplicativo (chave da API fora de variavel de ambiente).

No Windows, definir uma variavel de ambiente e incomodo, entao aceitamos a
chave num arquivo `chave-api.txt` ao lado do `app.py`. A variavel de ambiente
tem precedencia; o arquivo e apenas a alternativa conveniente.
"""

from __future__ import annotations

import os
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
