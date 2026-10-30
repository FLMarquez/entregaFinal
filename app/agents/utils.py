"""Utilidades compartidas entre agentes."""

from __future__ import annotations

from langchain_core.messages import BaseMessage


def extract_text(message: BaseMessage) -> str:
    """Normaliza `message.content` a `str`.

    Algunos proveedores (p. ej. Gemini) devuelven `content` como una lista de
    bloques (`[{"type": "text", "text": "..."}]`) en vez de un string plano.
    El resto del código (regex de la rúbrica, tools de análisis, etc.) espera
    siempre texto, así que se normaliza en un único lugar.
    """
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                parts.append(part.get("text", ""))
        return "".join(parts)
    return str(content)
