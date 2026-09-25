"""Cadena RAG (LCEL) asíncrona para consultas directas (`POST /rag/query`),
independiente del flujo multi-agente.

Arma: retriever (ChromaDB) -> prompt "filtro de veracidad" -> LLM (Gemini) ->
`PydanticOutputParser` -> `RAGResponse`. El prompt instruye al modelo a
responder únicamente con lo que aparece en el CONTEXTO recuperado, y a decir
explícitamente que no tiene esa información si la pregunta no puede
responderse con los fragmentos recuperados (evita alucinaciones ante
preguntas fuera de dominio).
"""
from __future__ import annotations

from pathlib import Path
from typing import List

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.rag.formatting import format_retrieved_docs
from app.rag.rag_settings import COLLECTION_NAME, PERSIST_DIR, TOP_K, get_embeddings, get_rag_llm


class RAGResponse(BaseModel):
    """Estructura de salida de la cadena RAG (validada con Pydantic)."""

    respuesta: str = Field(
        description="Respuesta a la pregunta del usuario, basada exclusivamente en el CONTEXTO."
    )
    tiene_informacion: bool = Field(
        description=(
            "true si el CONTEXTO tenía información suficiente para responder; "
            "false si se respondió que no se tiene esa información."
        )
    )
    fuentes: List[str] = Field(
        default_factory=list,
        description=(
            "Nombres de archivo de /data efectivamente usados para responder. "
            "Lista vacía si tiene_informacion es false."
        ),
    )


_PARSER = PydanticOutputParser(pydantic_object=RAGResponse)

_SYSTEM_PROMPT = """Eres un asistente técnico especializado en higiene y seguridad \
industrial y accidentes laborales.

Respondé ÚNICAMENTE basándote en el CONTEXTO provisto a continuación, que proviene de \
documentos internos de higiene y seguridad industrial. No uses conocimiento externo ni \
supongas información que no esté explícitamente en el CONTEXTO.

Si la respuesta a la pregunta NO se encuentra en el CONTEXTO, indicá explícitamente que \
no tenés acceso a esa información en los documentos disponibles (tiene_informacion=false \
y respuesta indicándolo). Nunca inventes ni completes con conocimiento general.

Citá en "fuentes" los nombres de archivo que aparecen como [Fuente: nombre_archivo] en el \
CONTEXTO y que efectivamente usaste para responder.

{format_instructions}
"""

_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", _SYSTEM_PROMPT),
        ("human", "CONTEXTO:\n{context}\n\nPREGUNTA: {question}"),
    ]
).partial(format_instructions=_PARSER.get_format_instructions())


_vectorstore = None
_chain = None


def _load_vectorstore():
    global _vectorstore
    if _vectorstore is None:
        from langchain_chroma import Chroma

        if not Path(PERSIST_DIR).exists():
            from app.rag.ingest import ingest

            ingest(force=False)

        # Mismo modelo de embeddings que en ingest.py (rag_settings.get_embeddings),
        # imprescindible para que la búsqueda por similitud tenga sentido.
        _vectorstore = Chroma(
            collection_name=COLLECTION_NAME,
            embedding_function=get_embeddings(),
            persist_directory=PERSIST_DIR,
        )
    return _vectorstore


def _build_chain():
    global _chain
    if _chain is None:
        from langchain_core.runnables import RunnablePassthrough

        retriever = _load_vectorstore().as_retriever(search_kwargs={"k": TOP_K})
        _chain = (
            {"context": retriever | format_retrieved_docs, "question": RunnablePassthrough()}
            | _PROMPT
            | get_rag_llm()
            | _PARSER
        )
    return _chain


async def get_rag_response(query: str) -> RAGResponse:
    """Ejecuta el flujo RAG completo de forma asíncrona para una consulta dada.

    1. Busca por similitud los TOP_K fragmentos más relevantes en ChromaDB.
    2. Arma el prompt con esos fragmentos como CONTEXTO.
    3. Llama al LLM (Gemini) de forma asíncrona.
    4. Parsea la respuesta a un modelo Pydantic (RAGResponse) con texto y fuentes.
    """
    chain = _build_chain()
    return await chain.ainvoke(query)
