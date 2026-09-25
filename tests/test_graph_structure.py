"""Verifica la estructura del grafo (sin invocarlo, sin requerir API key ni
Redis): construir el grafo solo registra los nodos, no llama a ningún LLM
(los agentes se instancian de forma perezosa recién al ejecutarse).
"""
from app.graph import build_graph


def test_grafo_tiene_los_nodos_esperados():
    graph = build_graph()
    nodos = set(graph.get_graph().nodes.keys())
    esperados = {"__start__", "supervisor", "researcher", "analyst", "human_approval", "__end__"}
    assert esperados.issubset(nodos)


def test_grafo_genera_diagrama_mermaid():
    graph = build_graph()
    mermaid = graph.get_graph().draw_mermaid()
    assert "supervisor" in mermaid
    assert "human_approval" in mermaid
    assert "researcher" in mermaid
    assert "analyst" in mermaid
