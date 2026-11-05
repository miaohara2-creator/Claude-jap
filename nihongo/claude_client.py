"""Geracao de frases com a API da Claude (SDK oficial `anthropic`).

A frase e gerada em portugues com UMA unica palavra nova (a palavra-chave),
em JSON validado por schema (`output_config.format`). Toda a validacao dura
-- presenca da palavra-chave, ausencia de vocabulario desconhecido -- e feita
em `nihongo/generator.py`; aqui tratamos apenas do transporte.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

DEFAULT_MODEL = "claude-opus-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"

#: Schema da resposta: estrutura exata que o app espera.
SENTENCE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "pt": {
            "type": "string",
            "description": "A frase em português, natural e com contexto claro.",
        },
        "keyword_pt": {
            "type": "string",
            "description": (
                "O trecho EXATO da frase em português que corresponde à palavra-chave "
                "japonesa (precisa aparecer literalmente em `pt`, com a mesma grafia)."
            ),
        },
        "ja": {
            "type": "string",
            "description": "A tradução japonesa de referência, com a palavra-chave na forma pedida.",
        },
        "ja_reading": {
            "type": "string",
            "description": "A mesma frase japonesa escrita só em kana (leitura).",
        },
        "words_used": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Lista de todas as palavras de conteúdo japonesas usadas em `ja` "
                "(na forma de dicionário), incluindo a palavra-chave."
            ),
        },
        "note": {
            "type": "string",
            "description": "Explicação curta em português sobre a forma gramatical usada.",
        },
    },
    "required": ["pt", "keyword_pt", "ja", "ja_reading", "words_used", "note"],
    "additionalProperties": False,
}


@dataclass
class GenerationResult:
    data: dict[str, Any]
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


class ClaudeUnavailable(RuntimeError):
    """Nao ha credencial configurada ou o SDK nao esta instalado."""


class ClaudeRefusal(RuntimeError):
    """O modelo recusou a requisicao."""


class ClaudeClient:
    """Fachada fina sobre `anthropic.Anthropic`."""

    def __init__(
        self,
        model: str | None = None,
        effort: str = "medium",
        max_tokens: int = 2000,
        use_fallbacks: bool = True,
    ) -> None:
        self.model = model or os.environ.get("NIHONGO_MODEL") or DEFAULT_MODEL
        self.effort = effort
        self.max_tokens = max_tokens
        self.use_fallbacks = use_fallbacks
        self._client = None
        self._fallbacks_ok = use_fallbacks

    # -- disponibilidade ---------------------------------------------------

    @staticmethod
    def credentials_present() -> bool:
        if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
            return True
        # perfil gravado por `ant auth login`
        for base in (os.environ.get("XDG_CONFIG_HOME"), os.path.expanduser("~/.config")):
            if base and os.path.isdir(os.path.join(base, "anthropic")):
                return True
        return False

    def available(self) -> bool:
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        return self.credentials_present()

    def _ensure_client(self):
        if self._client is None:
            try:
                import anthropic
            except ImportError as exc:  # pragma: no cover
                raise ClaudeUnavailable(
                    "O pacote `anthropic` não está instalado (pip install anthropic)."
                ) from exc
            if not self.credentials_present():
                raise ClaudeUnavailable(
                    "Nenhuma credencial encontrada: defina ANTHROPIC_API_KEY "
                    "ou rode `ant auth login`."
                )
            self._client = anthropic.Anthropic()
        return self._client

    # -- chamada -----------------------------------------------------------

    def generate_sentence(self, system: str, user: str) -> GenerationResult:
        """Pede uma frase ao modelo e devolve o JSON validado pelo schema."""
        client = self._ensure_client()
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            # O prompt de sistema e estavel -> cacheavel entre rodadas.
            "system": [
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "messages": [{"role": "user", "content": user}],
            "output_config": {
                "effort": self.effort,
                "format": {"type": "json_schema", "schema": SENTENCE_SCHEMA},
            },
        }
        # `fallbacks` (recuperacao automatica quando o modelo recusa) so existe
        # no endpoint beta; sem ele usamos o endpoint estavel.
        if self._fallbacks_ok:
            kwargs["betas"] = [FALLBACK_BETA]
            kwargs["fallbacks"] = "default"

        try:
            endpoint = client.beta.messages if self._fallbacks_ok else client.messages
            response = endpoint.create(**kwargs)
        except Exception as exc:  # beta indisponivel -> tenta sem fallbacks
            if self._fallbacks_ok and _looks_like_beta_error(exc):
                self._fallbacks_ok = False
                kwargs.pop("betas", None)
                kwargs.pop("fallbacks", None)
                response = client.messages.create(**kwargs)
            else:
                raise

        if getattr(response, "stop_reason", None) == "refusal":
            details = getattr(response, "stop_details", None)
            raise ClaudeRefusal(
                f"O modelo recusou a geração ({getattr(details, 'category', 'sem categoria')})."
            )

        text = next(
            (b.text for b in response.content if getattr(b, "type", None) == "text"), None
        )
        if not text:
            raise RuntimeError("Resposta sem bloco de texto.")

        usage = getattr(response, "usage", None)
        return GenerationResult(
            data=json.loads(text),
            model=getattr(response, "model", self.model),
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
        )


def _looks_like_beta_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(
        term in msg
        for term in ("beta", "fallback", "unexpected keyword", "unknown parameter")
    )
