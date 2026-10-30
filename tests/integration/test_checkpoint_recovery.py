"""Persistencia real del HITL: AsyncRedisSaver + JobStore contra Redis Stack.

Cada `server_session` arma desde cero el checkpointer, el grafo y el JobStore, y
los cierra al salir, igual que el lifespan de la API en cada arranque. Lo único
que comparten dos sesiones es lo que quedó guardado en Redis.
"""

import uuid
from contextlib import asynccontextmanager

import pytest
from langgraph.checkpoint.redis.aio import AsyncRedisSaver

from app import job_store
from app.graph import build_graph
from app.job_store import JobStore
from app.worker import resume_job, run_job
from tests.support.fake_agents import CRITICAL_INPUT, NORMAL_INPUT, install

pytestmark = pytest.mark.integration


@asynccontextmanager
async def server_session(redis_url: str):
    async with AsyncRedisSaver.from_conn_string(redis_url) as checkpointer:
        await checkpointer.asetup()
        store = JobStore(redis_url)
        try:
            yield build_graph(checkpointer), store
        finally:
            await store.close()


async def start_job(graph, store: JobStore, user_input: str) -> str:
    job_id = uuid.uuid4().hex
    await store.create(job_id, user_input)
    await run_job(graph, store, job_id, user_input)
    return job_id


def graph_config(job_id: str) -> dict:
    return {"configurable": {"thread_id": job_id}}


@pytest.fixture
def fake_agents(monkeypatch):
    return install(monkeypatch.setattr)


async def test_caso_no_critico_termina_sin_pausa(redis_url, fake_agents):
    async with server_session(redis_url) as (graph, store):
        job_id = await start_job(graph, store, NORMAL_INPUT)

        job = await store.get(job_id)
        state = await graph.aget_state(graph_config(job_id))

    assert job["status"] == job_store.DONE
    assert job["result"]["is_critical"] is False
    assert state.next == ()


@pytest.mark.parametrize(
    ("approved", "final_status"), [(True, job_store.DONE), (False, job_store.REJECTED)]
)
async def test_caso_pausado_se_recupera_tras_reinicio(
    redis_url, fake_agents, approved, final_status
):
    researcher, analyst = fake_agents

    async with server_session(redis_url) as (graph, store):
        job_id = await start_job(graph, store, CRITICAL_INPUT)
        assert (await store.get(job_id))["status"] == job_store.AWAITING_APPROVAL

    # Nada del primer arranque sigue vivo: el estado sale solo de Redis.
    async with server_session(redis_url) as (graph, store):
        paused = await store.get(job_id)
        assert paused["status"] == job_store.AWAITING_APPROVAL
        assert paused["awaiting_approval"]["reason"]

        state = await graph.aget_state(graph_config(job_id))
        assert state.next == ("human_approval",)
        assert state.values["user_query"] == CRITICAL_INPUT
        assert state.values["is_critical"] is True
        assert "Gravedad: fatal" in state.values["analysis_data"]

        await resume_job(graph, store, job_id, approved, "decisión tras el reinicio")

        job = await store.get(job_id)
        state = await graph.aget_state(graph_config(job_id))

    assert job["status"] == final_status
    assert job["awaiting_approval"] is None
    assert job["result"]["approved"] is approved
    assert job["result"]["approval_comment"] == "decisión tras el reinicio"
    assert state.next == ()
    # Se reanuda desde el checkpoint: los especialistas no se vuelven a ejecutar.
    assert researcher.calls == 1
    assert analyst.calls == 1
    assert [c["agent"] for c in job["result"]["contributions"]] == ["researcher", "analyst"]


async def test_cada_job_pausado_se_recupera_con_su_propio_estado(redis_url, fake_agents):
    other_input = f"{CRITICAL_INPUT} Ocurrió en el sector de obra."

    async with server_session(redis_url) as (graph, store):
        first = await start_job(graph, store, CRITICAL_INPUT)
        second = await start_job(graph, store, other_input)

    async with server_session(redis_url) as (graph, store):
        await resume_job(graph, store, first, True, None)

        first_job = await store.get(first)
        second_job = await store.get(second)
        second_state = await graph.aget_state(graph_config(second))

    assert first_job["status"] == job_store.DONE
    assert second_job["status"] == job_store.AWAITING_APPROVAL
    assert second_state.next == ("human_approval",)
    assert second_state.values["user_query"] == other_input
