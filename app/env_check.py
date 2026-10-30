"""Validación de variables de entorno al arrancar la API.

Sin esto, una API key faltante recién aparece en la primera ingesta o en el
primer job, como un error poco claro a mitad de camino. Acá se juntan todos los
problemas de configuración y se informan juntos, para corregirlos de una sola vez.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from urllib.parse import urlparse

from pydantic import ValidationError

from app.settings import Settings

_PROVIDER_KEYS = {
    "gemini": ("GOOGLE_API_KEY", "GEMINI_API_KEY"),
    "openai": ("OPENAI_API_KEY",),
    "anthropic": ("ANTHROPIC_API_KEY",),
}
_OBSERVABILITY_BACKENDS = {"langsmith", "phoenix", "none"}


class EnvironmentValidationError(RuntimeError):
    """La configuración del entorno no permite arrancar el sistema."""


def _has_any(env: Mapping[str, str], names: tuple[str, ...]) -> bool:
    return any(env.get(name, "").strip() for name in names)


def find_env_problems(env: Mapping[str, str]) -> list[str]:
    problems: list[str] = []

    # Los embeddings del RAG usan siempre Gemini, sea cual sea MODEL_PROVIDER.
    if not _has_any(env, _PROVIDER_KEYS["gemini"]):
        problems.append(
            "Falta GOOGLE_API_KEY (o GEMINI_API_KEY): es obligatoria porque los embeddings del RAG "
            "siempre usan Gemini. Se obtiene gratis en https://aistudio.google.com/app/apikey"
        )

    provider = env.get("MODEL_PROVIDER", "gemini").strip().lower()
    if provider not in _PROVIDER_KEYS:
        problems.append(
            f"MODEL_PROVIDER='{provider}' no es válido. Usá gemini, openai o anthropic."
        )
    elif provider != "gemini" and not _has_any(env, _PROVIDER_KEYS[provider]):
        problems.append(
            f"Falta {_PROVIDER_KEYS[provider][0]}: es obligatoria con MODEL_PROVIDER={provider}."
        )

    redis_url = env.get("REDIS_URL", "redis://localhost:6379/0").strip()
    if urlparse(redis_url).scheme not in {"redis", "rediss"}:
        problems.append(
            f"REDIS_URL='{redis_url}' no es válida. Debe empezar con redis:// o rediss://."
        )

    backend = env.get("OBSERVABILITY_BACKEND", "langsmith").strip().lower()
    if backend not in _OBSERVABILITY_BACKENDS:
        problems.append(
            f"OBSERVABILITY_BACKEND='{backend}' no es válido. Usá langsmith, phoenix o none."
        )

    return problems


def validate_environment() -> None:
    """Corta el arranque con un mensaje claro si la configuración no es válida."""
    problems = find_env_problems(os.environ)
    try:
        Settings()
    except ValidationError as exc:
        problems.extend(
            f"{'.'.join(str(part) for part in error['loc']).upper()}: {error['msg']}"
            for error in exc.errors()
        )

    if problems:
        detail = "\n".join(f"  - {problem}" for problem in problems)
        raise EnvironmentValidationError(
            f"Configuración inválida, la API no puede arrancar:\n{detail}\n"
            "Revisá tu .env (la plantilla es .env.example)."
        )
