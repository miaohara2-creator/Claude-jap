"""Credenciais da Claude: conta conectada ou chave de API.

Ha tres formas de o app falar com a Claude, nesta ordem de precedencia (a
mesma que o SDK oficial usa):

1. variavel de ambiente `ANTHROPIC_API_KEY` / `ANTHROPIC_AUTH_TOKEN`;
2. arquivo `chave-api.txt` ao lado do `app.py` (conveniencia no Windows,
   onde definir variavel de ambiente e incomodo);
3. **a conta Claude conectada** -- o perfil OAuth que `ant auth login` grava
   em disco. Sem chave nenhuma para gerenciar: o SDK encontra o perfil
   sozinho.

Cuidado conhecido: uma `ANTHROPIC_API_KEY` definida vence qualquer perfil.
Por isso o app diz qual credencial esta usando, em vez de escolher calado.
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
    """Preenche ANTHROPIC_API_KEY a partir de `chave-api.txt`, se necessário.

    Devolve a origem da credencial ("ambiente", "arquivo", "conta") ou None
    quando não há nenhuma -- nesse caso o app usa o gerador local.

    A conta conectada não precisa de nada aqui: o SDK acha o perfil sozinho.
    Só não podemos definir ANTHROPIC_API_KEY por cima dela, porque a variável
    de ambiente venceria o perfil.
    """
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return "ambiente"
    chave = ler_chave_do_arquivo((raiz or RAIZ) / ARQUIVO_CHAVE)
    if chave:
        os.environ["ANTHROPIC_API_KEY"] = chave
        return "arquivo"
    if conta_claude_conectada():
        return "conta"
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


# ---------------------------------------------------------------------------
# Conta Claude (perfil OAuth gravado por `ant auth login`)
# ---------------------------------------------------------------------------

#: Comando que conecta a conta.
COMANDO_LOGIN = "ant auth login"


def diretorio_config_anthropic(
    plataforma: str | None = None, ambiente: dict | None = None
) -> Path:
    """Pasta onde o SDK e o utilitário `ant` guardam o perfil da conta.

    Windows: ``%APPDATA%\\Anthropic``. Linux/macOS: ``$XDG_CONFIG_HOME/anthropic``
    ou ``~/.config/anthropic``. ``ANTHROPIC_CONFIG_DIR`` tem precedência sobre
    as duas.
    """
    plataforma = plataforma if plataforma is not None else sys.platform
    ambiente = ambiente if ambiente is not None else os.environ

    escolhido = ambiente.get("ANTHROPIC_CONFIG_DIR")
    if escolhido:
        return Path(escolhido)
    if plataforma.startswith("win"):
        base = ambiente.get("APPDATA")
        if base:
            return Path(base) / "Anthropic"
        return Path.home() / "AppData" / "Roaming" / "Anthropic"
    base = ambiente.get("XDG_CONFIG_HOME")
    raiz = Path(base) if base else Path.home() / ".config"
    return raiz / "anthropic"


def conta_claude_conectada(diretorio: Path | None = None) -> bool:
    """True quando o SDK consegue resolver um perfil de conta.

    Com `diretorio`, checa os arquivos daquela pasta (usado nos testes e
    quando o pacote `anthropic` não está instalado). Sem ele, quem responde é
    o próprio SDK: ele exige `configs/<perfil>.json` **e**
    `credentials/<perfil>.json` do perfil ativo, e não de um qualquer.
    """
    if diretorio is None:
        try:
            import anthropic  # noqa: F401
        except ImportError:
            diretorio = diretorio_config_anthropic()
        else:
            from .claude_client import ClaudeClient

            if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
                return False  # a variável venceria o perfil de qualquer forma
            return ClaudeClient.erro_de_credencial() is None

    pasta = diretorio / "credentials"
    try:
        return any(pasta.glob("*.json"))
    except OSError:  # pragma: no cover - disco inacessível
        return False


def origem_credencial(raiz: Path | None = None) -> str | None:
    """Qual credencial o app vai usar, em texto, ou None se não houver nenhuma."""
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return "variável de ambiente"
    if ler_chave_do_arquivo((raiz or RAIZ) / ARQUIVO_CHAVE):
        return f"chave de API ({ARQUIVO_CHAVE})"
    if conta_claude_conectada():
        return "conta Claude conectada"
    return None
