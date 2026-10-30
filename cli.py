"""CLI simple para probar el orquestador sin necesidad de levantar Redis ni la
API (usa un checkpointer en memoria, no persistente entre reinicios). Útil
para demos rápidas locales y para regenerar el diagrama Mermaid del README.

Uso:
    python cli.py "Un operario sufrió una fractura expuesta al caer de un andamio."

Sin argumentos, corre una consulta de demo que fuerza el flujo completo
Investigador -> Analista -> (posible aprobación humana por caso crítico).
"""

from __future__ import annotations

import asyncio
import sys

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from app.graph import build_graph

DEMO_QUERY = (
    "Un operario sufrió una caída desde un andamio de 3 metros durante el turno "
    "tarde en el sector de obra, con sospecha de fractura. Indicame la gravedad, "
    "la normativa de trabajo en altura aplicable y las recomendaciones."
)

_graph = build_graph(checkpointer=MemorySaver())


async def run(query: str) -> dict:
    initial_state = {
        "messages": [HumanMessage(content=query)],
        "user_query": query,
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
    config = {"configurable": {"thread_id": "cli-demo"}}
    return await _graph.ainvoke(initial_state, config=config)


def print_trace(final_state: dict) -> None:
    print("=" * 70)
    print("TRAZA DE CONTRIBUCIONES")
    print("=" * 70)
    for c in final_state["contributions"]:
        print(f"[paso {c['step']}] {c['agent']}: {c['summary']}")

    interrupts = final_state.get("__interrupt__")
    if interrupts:
        print("\n" + "=" * 70)
        print("ESPERANDO APROBACIÓN HUMANA (caso crítico)")
        print("=" * 70)
        payload = interrupts[0].value if hasattr(interrupts[0], "value") else interrupts[0]
        print(payload)
        return

    print("\n" + "=" * 70)
    print("RESPUESTA FINAL (Análisis)")
    print("=" * 70)
    print(final_state["analysis_data"])
    print(f"\nis_critical = {final_state.get('is_critical')}")
    print(f"task_completed = {final_state['task_completed']}")


if __name__ == "__main__":
    query = " ".join(sys.argv[1:]) or DEMO_QUERY
    print(f"Consulta: {query}\n")
    state = asyncio.run(run(query))
    print_trace(state)
