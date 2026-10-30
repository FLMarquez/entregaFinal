"""Herramienta de investigación: retriever real sobre la base vectorial de
higiene y seguridad industrial (ChromaDB), expuesta como tool asíncrona de
LangChain para el Agente de Investigación (`create_react_agent`).

A diferencia de una búsqueda simulada por keywords, esto usa embeddings reales
(`app.rag.rag_settings.get_embeddings()`) contra los documentos indexados en
`/data` por `app.rag.ingest`. El mismo modelo de embeddings se usa para
indexar y para consultar, para que la distancia vectorial tenga sentido.

`retriever.ainvoke(...)` es async nativo de LangChain (si el vectorstore solo
implementa el método sync, LangChain lo corre en un thread aparte para no
bloquear el event loop), en línea con el resto de la app -- ninguna llamada a
LLM/DB del sistema usa E/S bloqueante dentro de una función `async def`.
"""

from __future__ import annotations

from pathlib import Path

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.rag.formatting import format_retrieved_docs
from app.rag.rag_settings import COLLECTION_NAME, PERSIST_DIR, TOP_K, get_embeddings

_vectorstore = None


def _get_vectorstore():
    global _vectorstore
    if _vectorstore is None:
        from langchain_chroma import Chroma

        if not Path(PERSIST_DIR).exists():
            from app.rag.ingest import ingest

            ingest(force=False)

        _vectorstore = Chroma(
            collection_name=COLLECTION_NAME,
            embedding_function=get_embeddings(),
            persist_directory=PERSIST_DIR,
        )
    return _vectorstore


class BuscarNormativaInput(BaseModel):
    query: str = Field(
        description="Consulta en lenguaje natural sobre higiene y seguridad industrial."
    )


@tool("buscar_normativa_seguridad", args_schema=BuscarNormativaInput)
async def buscar_normativa_seguridad(query: str) -> str:
    """Busca en la base vectorial de normativa y procedimientos de higiene y seguridad
    industrial (marco normativo, prevención de riesgos, reporte de accidentes, primeros
    auxilios, trabajo en altura, riesgo químico y espacios confinados). Devuelve los
    fragmentos más relevantes, cada uno etiquetado con su fuente. Usar SIEMPRE esta
    herramienta antes de responder: no inventar normativa que no venga de acá.
    """
    retriever = _get_vectorstore().as_retriever(search_kwargs={"k": TOP_K})
    docs = await retriever.ainvoke(query)
    formatted = format_retrieved_docs(docs)
    return formatted or "No se encontraron fragmentos relevantes en la base de conocimiento."


def get_research_tools() -> list:
    """Devuelve la lista de tools del Agente de Investigación."""
    return [buscar_normativa_seguridad]
