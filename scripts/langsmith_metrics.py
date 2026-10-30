"""Latencia p50/p95 y costo por ejecución, leídos de las trazas reales de LangSmith.

Una ejecución es un thread de LangGraph: un caso con HITL genera dos trazas raíz
(hasta la pausa y desde la reanudación) que acá se suman, así el costo es el del
caso completo y la latencia no incluye el tiempo que el caso esperó al humano.

Uso (requiere LANGSMITH_API_KEY y, opcionalmente, LANGSMITH_PROJECT):
    python scripts/langsmith_metrics.py --days 14
"""

from __future__ import annotations

import argparse
import math
import os
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from dotenv import load_dotenv

DEFAULT_PROJECT = "higiene-seguridad-intelligence-system"


@dataclass
class Execution:
    name: str
    latency_s: float = 0.0
    cost_usd: float = 0.0
    tokens: int = 0
    failed: bool = False


def percentile(values: list[float], pct: float) -> float:
    """Percentil por rango más cercano: siempre es un valor realmente observado."""
    ordered = sorted(values)
    rank = max(math.ceil(pct / 100 * len(ordered)), 1)
    return ordered[rank - 1]


def group_executions(runs: Iterable) -> list[Execution]:
    executions: dict[str, Execution] = {}
    for run in runs:
        if run.end_time is None:
            continue
        metadata = (run.extra or {}).get("metadata", {})
        key = metadata.get("thread_id") or str(run.id)
        execution = executions.setdefault(key, Execution(name=run.name))
        execution.latency_s += (run.end_time - run.start_time).total_seconds()
        execution.cost_usd += float(run.total_cost or 0)
        execution.tokens += int(run.total_tokens or 0)
        execution.failed = execution.failed or bool(run.error)
    return list(executions.values())


def render_table(executions: list[Execution]) -> str:
    # Exitosas y fallidas por separado: una falla corta el flujo a mitad de camino,
    # así que mezclarlas distorsiona tanto la latencia como el costo.
    groups: dict[tuple[str, bool], list[Execution]] = defaultdict(list)
    for execution in executions:
        groups[(execution.name, execution.failed)].append(execution)

    lines = [
        "| Flujo | Resultado | Ejecuciones | Latencia p50 | Latencia p95 | Tokens promedio | "
        "Costo promedio | Costo p95 |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for (name, failed), group in sorted(groups.items()):
        latencies = [e.latency_s for e in group]
        costs = [e.cost_usd for e in group]
        lines.append(
            f"| `{name}` | {'con error' if failed else 'exitosa'} | {len(group)} | "
            f"{percentile(latencies, 50):.2f} s | {percentile(latencies, 95):.2f} s | "
            f"{sum(e.tokens for e in group) / len(group):,.0f} | "
            f"${sum(costs) / len(group):.4f} | ${percentile(costs, 95):.4f} |"
        )
    return "\n".join(lines)


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=14, help="Ventana de tiempo hacia atrás.")
    args = parser.parse_args()

    if not os.getenv("LANGSMITH_API_KEY"):
        raise SystemExit("Falta LANGSMITH_API_KEY.")

    from langsmith import Client

    project = os.getenv("LANGSMITH_PROJECT", DEFAULT_PROJECT)
    runs = Client().list_runs(
        project_name=project,
        is_root=True,
        start_time=datetime.now(UTC) - timedelta(days=args.days),
    )
    executions = group_executions(runs)
    if not executions:
        raise SystemExit(f"No hay trazas en '{project}' en los últimos {args.days} días.")

    print(
        f"Proyecto: {project}. Ventana: {args.days} días. Medido el {datetime.now(UTC):%Y-%m-%d}.\n"
    )
    print(render_table(executions))


if __name__ == "__main__":
    main()
