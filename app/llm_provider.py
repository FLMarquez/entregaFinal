"""Selección de proveedor de LLM (chat) para los agentes del orquestador.

Mismo patrón validado en las pre-entregas anteriores: por defecto Gemini
(capa gratuita), pero configurable vía `MODEL_PROVIDER` sin tocar el código de
los agentes. Si hay más de una `GEMINI_API_KEY_*` en el entorno, se rota
automáticamente entre ellas ante error de cuota (429), usando un chat model
que sigue siendo un `ChatGoogleGenerativeAI` real (compatible con
`create_react_agent` y `.with_structured_output`, a diferencia de un wrapper
"a mano" que solo implemente `ainvoke`).

Los embeddings del RAG se configuran aparte, en `app/rag/rag_settings.py`
(siempre Gemini), porque son un componente independiente del chat LLM.
"""
from __future__ import annotations

import os

from app.settings import get_settings


def _collect_gemini_keys() -> list[str]:
    """Junta GOOGLE_API_KEY/GEMINI_API_KEY + GEMINI_API_KEY_1..N del entorno."""
    keys: list[str] = []
    primary = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if primary:
        keys.append(primary)

    i = 1
    while True:
        extra = os.getenv(f"GEMINI_API_KEY_{i}")
        if not extra:
            break
        if extra not in keys:
            keys.append(extra)
        i += 1

    return keys


def get_llm(temperature: float = 0.0):
    """Devuelve el chat model configurado según `MODEL_PROVIDER`.

    Se centraliza acá para que el Supervisor y ambos especialistas usen el
    mismo modelo y sea trivial cambiar de proveedor con una sola variable de
    entorno (nunca hardcodeado en los agentes).
    """
    settings = get_settings()
    provider = settings.model_provider.lower()

    if provider == "gemini":
        keys = _collect_gemini_keys()
        if not keys:
            raise RuntimeError(
                "Falta GOOGLE_API_KEY/GEMINI_API_KEY. Copiá .env.example a .env y "
                "completá tu API key gratuita de Google AI Studio "
                "(https://aistudio.google.com/app/apikey)."
            )
        model = os.getenv("GEMINI_MODEL", settings.model_name or "gemini-2.5-flash")

        if len(keys) == 1:
            from langchain_google_genai import ChatGoogleGenerativeAI

            return ChatGoogleGenerativeAI(model=model, google_api_key=keys[0], temperature=temperature)

        from app.rotating_llm import RotatingChatGoogleGenerativeAI

        return RotatingChatGoogleGenerativeAI(
            model=model, google_api_key=keys[0], temperature=temperature, api_keys=keys
        )

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("Falta OPENAI_API_KEY en el .env.")
        return ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=temperature)

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        if not os.getenv("ANTHROPIC_API_KEY"):
            raise RuntimeError("Falta ANTHROPIC_API_KEY en el .env.")
        return ChatAnthropic(
            model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5"), temperature=temperature
        )

    raise ValueError(f"MODEL_PROVIDER='{provider}' no soportado. Usá gemini, openai o anthropic.")
