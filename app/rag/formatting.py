"""Utilidad compartida para formatear documentos recuperados del vectorstore.

Etiqueta cada fragmento con su fuente (`[Fuente: nombre_archivo]`). La usan
tanto la cadena RAG directa (`rag_chain.py`) como la tool del Agente de
Investigación (`tools/rag_tools.py`), para que el formato de citas sea
idéntico en ambos casos y no se duplique la lógica.
"""
from __future__ import annotations

from pathlib import Path


def format_retrieved_docs(docs) -> str:
    """Concatena los fragmentos recuperados, cada uno etiquetado con su fuente."""
    if not docs:
        return ""
    parts = []
    for doc in docs:
        source = Path(doc.metadata.get("source", "desconocido")).name
        parts.append(f"[Fuente: {source}]\n{doc.page_content}")
    return "\n\n---\n\n".join(parts)
