"""Modelos Pydantic de entrada/salida de la API.

Centralizar los esquemas acá (en vez de `BaseModel` sueltos en cada router)
deja explícito qué contrato expone la API, habilita la documentación
automática de FastAPI (`/docs`) y valida entradas/salidas en un único lugar,
tal como pide la consigna de la entrega final.
"""
from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field


class TaskRequest(BaseModel):
    input: str = Field(
        min_length=3,
        description=(
            "Consulta o descripción del incidente/consulta de higiene y "
            "seguridad industrial a resolver."
        ),
    )


class TaskAccepted(BaseModel):
    job_id: str
    status: str


class TaskStatus(BaseModel):
    job_id: str
    status: str
    input: str
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    awaiting_approval: Optional[dict[str, Any]] = None
    created_at: float
    updated_at: float


class ApprovalRequest(BaseModel):
    approved: bool = Field(description="True para aprobar el cierre del caso, False para rechazarlo.")
    comment: Optional[str] = Field(default=None, description="Comentario del aprobador humano.")


class RAGQueryRequest(BaseModel):
    question: str = Field(
        min_length=3,
        description="Pregunta puntual sobre normativa o procedimientos de higiene y seguridad.",
    )


class RAGQueryResponse(BaseModel):
    respuesta: str
    tiene_informacion: bool
    fuentes: List[str] = Field(default_factory=list)
