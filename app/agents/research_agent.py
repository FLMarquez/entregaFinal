"""Agente de Investigación: busca normativa y procedimientos, no los interpreta.

Se construye con `create_react_agent` (LangGraph) y la tool
`buscar_normativa_seguridad`, que consulta la base vectorial (ChromaDB) de
documentos de higiene y seguridad industrial (marco normativo, prevención de
riesgos, procedimiento de reporte, primeros auxilios, trabajo en altura,
riesgo químico y espacios confinados -- ver `/data`).

Para evitar la "contaminación de contexto": el nodo NO le pasa al agente todo
`state["messages"]` (que incluye mensajes del Supervisor y del Analista). Le
pasa únicamente la consulta del usuario, en un `HumanMessage` nuevo.
"""

from __future__ import annotations

import re

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.prebuilt import create_react_agent

from app.agents.utils import extract_text
from app.llm_provider import get_llm
from app.state import OrchestratorState
from app.tools.rag_tools import get_research_tools

RESEARCH_SYSTEM_PROMPT = """Sos el Agente de Investigación de un equipo de higiene y \
seguridad industrial.

Tu única tarea es usar la herramienta `buscar_normativa_seguridad` para encontrar \
normativa, procedimientos o guías relevantes a la consulta del usuario, y devolver un \
resumen conciso de los hallazgos citando las fuentes recuperadas (los fragmentos vienen \
etiquetados como [Fuente: nombre_archivo]). No inventes normativa ni procedimientos que \
no vengan de la herramienta: si no encontrás información relevante, decilo explícitamente. \
No clasifiques gravedad ni des recomendaciones: eso es trabajo del Agente de Análisis, que \
recibirá tu resumen a continuación."""

_agent = None


def _get_agent():
    global _agent
    if _agent is None:
        _agent = create_react_agent(
            get_llm(), tools=get_research_tools(), prompt=RESEARCH_SYSTEM_PROMPT
        )
    return _agent


async def research_node(state: OrchestratorState) -> dict:
    task = state.get("user_query", "")
    result = await _get_agent().ainvoke({"messages": [HumanMessage(content=task)]})
    final_text = extract_text(result["messages"][-1])

    fuentes = sorted(set(re.findall(r"\[Fuente:\s*([^\]]+)\]", final_text)))

    step = state.get("steps", 0) + 1
    return {
        "research_data": final_text,
        "fuentes": fuentes,
        "messages": [AIMessage(content=final_text, name="researcher")],
        "contributions": [{"agent": "researcher", "summary": final_text[:200], "step": step}],
        "steps": step,
    }
