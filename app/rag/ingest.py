"""Módulo de ingesta (setup) del sistema RAG.

Lee los documentos de `/data` (.md/.txt), los fragmenta con
`RecursiveCharacterTextSplitter` y persiste los embeddings en una colección
local de ChromaDB. Si la colección ya existe y tiene documentos, no vuelve a
indexar (salvo `--force`), para no gastar tiempo ni cuota de API de más.

Uso:
    python -m app.rag.ingest            # indexa solo si la base no existe o está vacía
    python -m app.rag.ingest --force    # borra la colección existente y reindexa todo
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.rag.rag_settings import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    COLLECTION_NAME,
    DATA_DIR,
    PERSIST_DIR,
    get_embeddings,
)


def load_documents(data_dir: str):
    """Carga todos los .txt y .md de data_dir como Documents de LangChain."""
    from langchain_community.document_loaders import TextLoader

    data_path = Path(data_dir)
    if not data_path.exists():
        raise FileNotFoundError(f"No existe la carpeta de datos: {data_path.resolve()}")

    files = sorted(list(data_path.glob("*.md")) + list(data_path.glob("*.txt")))
    if not files:
        raise FileNotFoundError(f"No se encontraron archivos .txt/.md en {data_path.resolve()}")

    documents = []
    for file_path in files:
        documents.extend(TextLoader(str(file_path), encoding="utf-8").load())
    return documents


def chunk_documents(documents, chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP):
    """Fragmenta los documentos en chunks con superposición (overlap), medidos en tokens."""
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n## ", "\n### ", "\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_documents(documents)


def collection_already_populated() -> bool:
    """Chequea si la colección persistida ya tiene documentos cargados."""
    from langchain_chroma import Chroma

    if not Path(PERSIST_DIR).exists():
        return False
    try:
        store = Chroma(
            collection_name=COLLECTION_NAME,
            embedding_function=get_embeddings(),
            persist_directory=PERSIST_DIR,
        )
        return store._collection.count() > 0
    except Exception:
        return False


def ingest(force: bool = False):
    """Puebla (o reutiliza) la colección de ChromaDB con los documentos de /data."""
    from langchain_chroma import Chroma

    if not force and collection_already_populated():
        print(
            f"[ingest] La colección '{COLLECTION_NAME}' en '{PERSIST_DIR}' ya tiene "
            "documentos indexados. Se omite la reindexación (usá --force para forzarla)."
        )
        return Chroma(
            collection_name=COLLECTION_NAME,
            embedding_function=get_embeddings(),
            persist_directory=PERSIST_DIR,
        )

    print(f"[ingest] Cargando documentos desde '{DATA_DIR}'...")
    documents = load_documents(DATA_DIR)
    print(f"[ingest] {len(documents)} documento(s) cargado(s).")

    chunks = chunk_documents(documents)
    print(
        f"[ingest] {len(chunks)} fragmento(s) generado(s) "
        f"(chunk_size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})."
    )

    embeddings = get_embeddings()

    if force:
        # Recrea la colección desde cero para evitar duplicados al reindexar.
        Chroma(
            collection_name=COLLECTION_NAME,
            embedding_function=embeddings,
            persist_directory=PERSIST_DIR,
        ).delete_collection()

    store = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        persist_directory=PERSIST_DIR,
    )
    print(f"[ingest] Colección '{COLLECTION_NAME}' persistida en '{PERSIST_DIR}'.")
    return store


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Borra la colección existente y reindexa todos los documentos.",
    )
    args = parser.parse_args()

    try:
        ingest(force=args.force)
    except Exception as exc:
        print(f"[ingest] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
