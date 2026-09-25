"""Construcción del orquestador multi-agente: topología jerárquica
Supervisor -> Especialistas, con un gate human-in-the-loop para casos críticos.

Flujo:
    START -> supervisor -(routing)-> researcher | analyst | human_approval | END
    researcher -> supervisor
    analyst -> supervisor
    human_approval -> supervisor

El Supervisor es el ÚNICO nodo con aristas condicionales: los especialistas y
el nodo de aprobación humana siempre vuelven a él (nunca se comunican entre
sí), lo que lo mantiene como única fuente de verdad sobre el estado del flujo
-- incluida la decisión de pedir aprobación humana antes de cerrar un caso
crítico (ver app/agents/supervisor.py::decide_next_agent).
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.agents.analyst_agent import analyst_node
from app.agents.research_agent import research_node
from app.agents.supervisor import supervisor_node
from app.hitl import human_approval_node
from app.state import OrchestratorState


def route_from_supervisor(state: OrchestratorState) -> str:
    next_agent = state["next_agent"]
    return END if next_agent == "FINISH" else next_agent


def build_graph(checkpointer=None):
    graph = StateGraph(OrchestratorState)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("researcher", research_node)
    graph.add_node("analyst", analyst_node)
    graph.add_node("human_approval", human_approval_node)

    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "researcher": "researcher",
            "analyst": "analyst",
            "human_approval": "human_approval",
            END: END,
        },
    )
    graph.add_edge("researcher", "supervisor")
    graph.add_edge("analyst", "supervisor")
    graph.add_edge("human_approval", "supervisor")

    return graph.compile(checkpointer=checkpointer)


# Grafo sin checkpointer persistente: solo para generar el diagrama Mermaid
# (regenerarlo con `python -c "from app.graph import app; print(app.get_graph().draw_mermaid())"`)
# y para tests de estructura que no requieren Redis (ver tests/test_graph_structure.py).
app = build_graph()
