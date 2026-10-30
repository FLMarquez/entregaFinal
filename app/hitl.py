"""Human-in-the-loop: nodo de aprobación humana + endpoint para resolverla.

En este dominio (higiene y seguridad industrial), el gate de aprobación se
dispara cuando el Agente de Análisis clasifica un caso como crítico (gravedad
"grave" o "fatal"): un humano (responsable de H&S) debe confirmar antes de que
el sistema dé el caso por cerrado -- por ejemplo, para validar que
efectivamente corresponde la denuncia formal ante la ART/SRT.

`human_approval_node` llama a `interrupt(...)`, lo que congela la ejecución
del grafo en este punto (el estado queda persistido en Redis vía el
checkpointer, ver app/main.py). La ejecución solo continúa cuando alguien
llama a `POST /tasks/{job_id}/approve`, que reanuda el grafo con
`Command(resume=...)`. Como el nodo vuelve al Supervisor (igual que
researcher/analyst), la decisión de aprobar/rechazar queda registrada en el
estado compartido y es el Supervisor -- única fuente de verdad del flujo --
quien decide terminar (ver app/agents/supervisor.py::decide_next_agent).
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Request
from langchain_core.messages import AIMessage
from langgraph.types import interrupt

from app import job_store
from app.schemas import ApprovalRequest
from app.state import OrchestratorState

router = APIRouter()


def human_approval_node(state: OrchestratorState) -> dict:
    decision = interrupt(
        {
            "message": (
                "Se requiere aprobación humana: el caso fue clasificado como "
                "crítico y necesita confirmación antes de cerrarse."
            ),
            "reason": state.get("critical_reason"),
            "research_data": state.get("research_data"),
            "analysis_data": state.get("analysis_data"),
        }
    )
    if isinstance(decision, dict):
        approved = bool(decision.get("approved"))
        comment = decision.get("comment")
    else:
        approved = bool(decision)
        comment = None

    return {
        "approved": approved,
        "approval_comment": comment,
        "messages": [
            AIMessage(
                content=f"[Aprobación humana] approved={approved} comentario={comment or '-'}",
                name="human_approval",
            )
        ],
    }


@router.post("/tasks/{job_id}/approve")
async def approve_task(job_id: str, payload: ApprovalRequest, request: Request):
    from app.worker import resume_job  # import diferido: evita import circular con graph.py

    store = request.app.state.job_store
    job = await store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job no encontrado")
    if job["status"] != job_store.AWAITING_APPROVAL:
        raise HTTPException(
            status_code=409,
            detail=f"El job no está esperando aprobación (status actual={job['status']})",
        )

    task = asyncio.create_task(
        resume_job(request.app.state.graph, store, job_id, payload.approved, payload.comment)
    )
    request.app.state.background_tasks.add(task)
    task.add_done_callback(request.app.state.background_tasks.discard)

    return {"job_id": job_id, "status": job_store.RUNNING}
