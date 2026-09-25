"""Configuración del subsistema RAG (ingesta + retriever).

Se centraliza acá la construcción del modelo de embeddings para garantizar
que la ingesta (`ingest.py`) y toda consulta (`tools/rag_tools.py`,
`rag_chain.py`) usen exactamente el mismo modelo: si difieren, la distancia
vectorial entre la consulta y los documentos indexados deja de tener sentido
(el error #1 más común en sistemas RAG). Los embeddings siempre usan Gemini
(capa gratuita), independientemente del `MODEL_PROVIDER` elegido para el chat
de los agentes en `app/llm_provider.py`.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

DATA_DIR = os.getenv("RAG_DATA_DIR", "./data")
PERSIST_DIR = os.getenv("RAG_PERSIST_DIR", "./vectorstore")
COLLECTION_NAME = os.getenv("RAG_COLLECTION_NAME", "higiene_seguridad_industrial")

EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "models/gemini-embedding-001")
LLM_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "50"))
TOP_K = int(os.getenv("RAG_TOP_K", "4"))


def get_embeddings():
    """Modelo de embeddings usado tanto para indexar como para consultar."""
    if not GOOGLE_API_KEY:
        raise RuntimeError(
            "Falta GOOGLE_API_KEY/GEMINI_API_KEY. Los embeddings del RAG usan Gemini "
            "(capa gratuita: https://aistudio.google.com/app/apikey), independientemente "
            "del MODEL_PROVIDER configurado para el chat de los agentes."
        )
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    return GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL, google_api_key=GOOGLE_API_KEY)


def get_rag_llm(temperature: float = 0.0):
    """LLM de generación para la cadena RAG directa (`rag_chain.py`, `POST /rag/query`)."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(model=LLM_MODEL, google_api_key=GOOGLE_API_KEY, temperature=temperature)
