"""Ejecuta el grafo en background (patrón "worker" async, no bloquea el event
loop de FastAPI) y mantiene el estado del job actualizado en Redis.

Si el agente falla en cualquier nodo (excepción de LLM, timeout, etc.), la
excepción se captura acá y el job pasa a FAILED con el mensaje de error, en
vez de dejar al cliente esperando para siempre en `GET /tasks/{id}`.
"""
from __future__ import annotations

import logging
from typing import Optional

from langchain_core.messages import HumanMessage
from langgraph.types import Command

from app import job_store
from app.job_store import JobStore

logger = logging.getLogger(__name__)


def _initial_state(user_query: str) -> dict:
    return {
        "messages": [HumanMessage(content=user_query)],
        "user_query": user_query,
        "next_agent": "researcher",
        "task_completed": False,
        "research_data": "",
        "fuentes": [],
        "analysis_data": "",
        "is_critical": False,
        "critical_reason": "",
        "approved": None,
        "approval_comment": None,
        "contributions": [],
        "steps": 0,
        "refinements_used": 0,
    }


async def run_job(graph, store: JobStore, job_id: str, user_query: str) -> None:
    config = {"configurable": {"thread_id": job_id}}
    await store.update(job_id, status=job_store.RUNNING)
    try:
        result = await graph.ainvoke(_initial_state(user_query), config=config)
        await _handle_result(store, job_id, result)
    except Exception as exc:  # noqa: BLE001 - se persiste cualquier falla del agente
        logger.exception("El job %s falló", job_id)
        await store.update(job_id, status=job_store.FAILED, error=str(exc))


async def resume_job(
    graph, store: JobStore, job_id: str, approved: bool, comment: Optional[str]
) -> None:
    config = {"configurable": {"thread_id": job_id}}
    await store.update(job_id, status=job_store.RUNNING, awaiting_approval=None)
    try:
        result = await graph.ainvoke(
            Command(resume={"approved": approved, "comment": comment}), config=config
        )
        await _handle_result(store, job_id, result)
    except Exception as exc:  # noqa: BLE001
        logger.exception("El job %s falló al reanudar", job_id)
        await store.update(job_id, status=job_store.FAILED, error=str(exc))


async def _handle_result(store: JobStore, job_id: str, result: dict) -> None:
    interrupts = result.get("__interrupt__")
    if interrupts:
        raw = interrupts[0]
        payload = raw.value if hasattr(raw, "value") else raw
        await store.update(job_id, status=job_store.AWAITING_APPROVAL, awaiting_approval=payload)
        return

    final_status = job_store.REJECTED if result.get("approved") is False else job_store.DONE
    await store.update(
        job_id,
        status=final_status,
        result={
            "research_data": result.get("research_data"),
            "fuentes": result.get("fuentes", []),
            "analysis_data": result.get("analysis_data"),
            "is_critical": result.get("is_critical", False),
            "critical_reason": result.get("critical_reason"),
            "approved": result.get("approved"),
            "approval_comment": result.get("approval_comment"),
            "contributions": result.get("contributions", []),
            "steps": result.get("steps"),
        },
    )
