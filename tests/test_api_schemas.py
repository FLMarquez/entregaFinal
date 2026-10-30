"""Tests de validación de los esquemas Pydantic de la API (sin levantar el
servidor ni requerir Redis/API keys).
"""

import pytest
from pydantic import ValidationError

from app.schemas import ApprovalRequest, RAGQueryRequest, TaskRequest


def test_task_request_exige_minimo_de_caracteres():
    with pytest.raises(ValidationError):
        TaskRequest(input="ab")
    assert TaskRequest(input="Se cayó un operario del andamio").input


def test_rag_query_request_exige_pregunta_no_vacia():
    with pytest.raises(ValidationError):
        RAGQueryRequest(question="")


def test_approval_request_comment_es_opcional():
    req = ApprovalRequest(approved=True)
    assert req.comment is None
    assert req.approved is True


def test_approval_request_exige_bool_approved():
    with pytest.raises(ValidationError):
        ApprovalRequest(approved="tal vez")
