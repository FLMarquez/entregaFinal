"""Tests del subsistema RAG que no requieren API key ni vectorstore real:
formateo de citas y validación del esquema Pydantic de salida.
"""

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.rag.formatting import format_retrieved_docs
from app.rag.rag_chain import RAGResponse


def test_format_retrieved_docs_etiqueta_la_fuente():
    docs = [
        SimpleNamespace(
            metadata={"source": "data/05_trabajo_en_altura.md"}, page_content="contenido A"
        ),
        SimpleNamespace(
            metadata={"source": "data/02_prevencion_riesgos.md"}, page_content="contenido B"
        ),
    ]
    resultado = format_retrieved_docs(docs)
    assert "[Fuente: 05_trabajo_en_altura.md]" in resultado
    assert "[Fuente: 02_prevencion_riesgos.md]" in resultado
    assert "contenido A" in resultado and "contenido B" in resultado


def test_format_retrieved_docs_vacio():
    assert format_retrieved_docs([]) == ""


def test_rag_response_valida_campos_requeridos():
    respuesta = RAGResponse(respuesta="No hay información.", tiene_informacion=False, fuentes=[])
    assert respuesta.tiene_informacion is False
    assert respuesta.fuentes == []


def test_rag_response_rechaza_tipo_incorrecto():
    with pytest.raises(ValidationError):
        RAGResponse(respuesta="ok", tiene_informacion="no-es-un-bool-valido", fuentes=[])
