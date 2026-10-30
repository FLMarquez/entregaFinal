"""API FastAPI asíncrona: expone el RAG directo y el orquestador multi-agente
de higiene y seguridad industrial.

- POST /rag/query               -> consulta directa al RAG (sin agentes), rápida.
- POST /tasks                   -> encola una tarea en el orquestador multi-agente
                                    y devuelve un job_id sin bloquear el event loop.
- GET  /tasks/{job_id}          -> consulta el estado del job.
- POST /tasks/{job_id}/approve  -> resuelve una pausa human-in-the-loop (app/hitl.py).
- GET  /graph                   -> diagrama Mermaid del grafo compilado, generado en
                                    caliente desde el código (nunca hardcodeado).
- GET  /health                  -> healthcheck simple.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import AsyncExitStack, asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

load_dotenv()

from app.env_check import validate_environment  # noqa: E402
from app.graph import build_graph  # noqa: E402
from app.hitl import router as hitl_router  # noqa: E402
from app.job_store import JobStore  # noqa: E402
from app.observability import init_observability  # noqa: E402
from app.rag.rag_chain import get_rag_response  # noqa: E402
from app.schemas import (  # noqa: E402
    RAGQueryRequest,
    RAGQueryResponse,
    TaskAccepted,
    TaskRequest,
    TaskStatus,
)
from app.settings import get_settings  # noqa: E402
from app.worker import run_job  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_environment()
    settings = get_settings()
    init_observability()

    # Ingesta inicial del RAG en un thread aparte: es una operación de arranque
    # (una sola vez), no de request -- pero igual evitamos bloquear el loop.
    from app.rag.ingest import ingest

    await asyncio.to_thread(ingest, False)

    from langgraph.checkpoint.redis.aio import AsyncRedisSaver

    stack = AsyncExitStack()
    checkpointer = await stack.enter_async_context(
        AsyncRedisSaver.from_conn_string(settings.redis_url)
    )
    await checkpointer.asetup()

    app.state.graph = build_graph(checkpointer)
    app.state.job_store = JobStore(settings.redis_url, ttl_seconds=settings.job_ttl_seconds)
    app.state.background_tasks = set()

    logger.info("API lista. REDIS_URL=%s", settings.redis_url)
    try:
        yield
    finally:
        await app.state.job_store.close()
        await stack.aclose()


app = FastAPI(
    title="Intelligence System — Higiene y Seguridad Industrial",
    description=(
        "RAG + agentes (Supervisor) + HITL sobre normativa y procedimientos de "
        "higiene y seguridad industrial."
    ),
    version="1.0.0",
    lifespan=lifespan,
)
app.include_router(hitl_router)


def _track(app: FastAPI, task: "asyncio.Task") -> None:
    app.state.background_tasks.add(task)
    task.add_done_callback(app.state.background_tasks.discard)


@app.post("/rag/query", response_model=RAGQueryResponse)
async def rag_query(payload: RAGQueryRequest):
    response = await get_rag_response(payload.question)
    return RAGQueryResponse(**response.model_dump())


@app.post("/tasks", response_model=TaskAccepted, status_code=202)
async def create_task(payload: TaskRequest):
    job_id = uuid.uuid4().hex
    await app.state.job_store.create(job_id, payload.input)

    task = asyncio.create_task(run_job(app.state.graph, app.state.job_store, job_id, payload.input))
    _track(app, task)

    return TaskAccepted(job_id=job_id, status="PENDING")


@app.get("/tasks/{job_id}", response_model=TaskStatus)
async def get_task(job_id: str):
    job = await app.state.job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job no encontrado")
    return TaskStatus(**job)


@app.get("/graph")
async def get_graph():
    return {"mermaid": app.state.graph.get_graph().draw_mermaid()}


@app.get("/health")
async def health():
    return {"status": "ok"}
