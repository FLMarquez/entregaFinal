"""Cálculo de métricas de scripts/langsmith_metrics.py, con trazas armadas a mano."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from scripts.langsmith_metrics import group_executions, percentile, render_table

START = datetime(2026, 10, 1, tzinfo=UTC)


def make_run(run_id, seconds, thread_id=None, cost=0.01, tokens=100, error=None, name="LangGraph"):
    return SimpleNamespace(
        id=run_id,
        name=name,
        start_time=START,
        end_time=START + timedelta(seconds=seconds) if seconds is not None else None,
        total_cost=cost,
        total_tokens=tokens,
        error=error,
        extra={"metadata": {"thread_id": thread_id}} if thread_id else {},
    )


def test_percentil_por_rango_mas_cercano():
    values = [float(v) for v in range(1, 21)]
    assert percentile(values, 95) == 19.0
    assert percentile(values, 50) == 10.0
    assert percentile([7.0], 95) == 7.0


def test_las_dos_trazas_de_un_caso_con_hitl_son_una_sola_ejecucion():
    executions = group_executions(
        [
            make_run("a", 4, thread_id="job-1", cost=0.02, tokens=300),
            make_run("b", 1, thread_id="job-1", cost=0.01, tokens=100),
            make_run("c", 2, thread_id="job-2"),
        ]
    )
    by_latency = sorted(executions, key=lambda e: e.latency_s)
    assert len(executions) == 2
    assert by_latency[1].latency_s == 5.0
    assert round(by_latency[1].cost_usd, 2) == 0.03
    assert by_latency[1].tokens == 400


def test_ignora_trazas_sin_terminar_y_acepta_costo_faltante():
    executions = group_executions([make_run("a", None), make_run("b", 1, cost=None, tokens=None)])
    assert len(executions) == 1
    assert executions[0].cost_usd == 0.0


def test_tabla_separa_flujos_y_no_mezcla_exitosas_con_fallidas():
    table = render_table(
        group_executions(
            [
                make_run("a", 40, error="429"),
                make_run("b", 2),
                make_run("c", 4),
                make_run("d", 1, name="RunnableSequence"),
            ]
        )
    )
    assert "| `LangGraph` | exitosa | 2 | 2.00 s | 4.00 s |" in table
    assert "| `LangGraph` | con error | 1 | 40.00 s | 40.00 s |" in table
    assert "| `RunnableSequence` | exitosa | 1 |" in table
