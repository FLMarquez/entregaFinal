"""Agente de Análisis: clasifica gravedad y recomienda acciones sobre el caso.

No vuelve a buscar información: recibe `state["research_data"]` (la normativa
o procedimiento ya encontrado) como único contexto y usa sus tools para
clasificar la gravedad del caso, validar los datos de entrada y generar
recomendaciones. Si clasifica el caso como "grave" o "fatal", marca
`is_critical=True` en el estado, lo que dispara el gate human-in-the-loop en
el Supervisor antes de poder cerrarse (ver app/agents/supervisor.py y
app/hitl.py).
"""
from __future__ import annotations

import re

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.prebuilt import create_react_agent

from app.agents.utils import extract_text
from app.llm_provider import get_llm
from app.state import OrchestratorState
from app.tools.analysis_tools import get_analysis_tools

ANALYST_SYSTEM_PROMPT = """Sos el Agente de Análisis de un equipo de higiene y seguridad \
industrial.

Recibís la consulta del usuario y la normativa/procedimiento ya recolectado por el Agente \
de Investigación. Tu tarea, en este orden:
1. Usar `clasificar_gravedad` sobre la descripción del caso para determinar el nivel de \
   gravedad (leve/moderado/grave/fatal).
2. Usar `validar_datos_incidente` para confirmar que la información de entrada era \
   suficiente (qué pasó, cuándo y dónde).
3. Usar `generar_recomendaciones` para obtener acciones preventivas o correctivas \
   concretas, basadas en la normativa investigada.

Devolvé un resumen breve y estructurado con: el nivel de gravedad explícito ("Gravedad: \
..."), el resultado de la validación y al menos una recomendación concreta ("Recomendación: \
..."). No vuelvas a buscar normativa nueva: trabajá exclusivamente con el texto que se te \
pasó."""

_agent = None

CRITICAL_LEVELS = {"grave", "fatal"}

_GRAVEDAD_RE = re.compile(r"gravedad[^a-zA-Z]{0,15}(leve|moderad[oa]|grave|fatal)", re.IGNORECASE)


def _get_agent():
    global _agent
    if _agent is None:
        _agent = create_react_agent(
            get_llm(), tools=get_analysis_tools(), prompt=ANALYST_SYSTEM_PROMPT
        )
    return _agent


def _extract_gravedad(text: str) -> str | None:
    match = _GRAVEDAD_RE.search(text)
    if not match:
        return None
    nivel = match.group(1).lower()
    return "moderado" if nivel == "moderada" else nivel


async def analyst_node(state: OrchestratorState) -> dict:
    user_query = state.get("user_query", "")
    research_data = state.get("research_data", "")
    task = (
        f"Consulta original del usuario:\n{user_query}\n\n"
        f"Normativa/procedimiento encontrado:\n{research_data}"
    )

    if state.get("refinements_used", 0) > 0:
        task += (
            "\n\nNota del Supervisor: tu análisis anterior fue considerado insuficiente. "
            "Asegurate de incluir un nivel de gravedad EXPLÍCITO (leve/moderado/grave/fatal) "
            "y al menos una recomendación concreta en tu respuesta final."
        )

    result = await _get_agent().ainvoke({"messages": [HumanMessage(content=task)]})
    final_text = extract_text(result["messages"][-1])

    nivel = _extract_gravedad(final_text)
    is_critical = nivel in CRITICAL_LEVELS if nivel else False
    critical_reason = (
        f"El Agente de Análisis clasificó el caso como '{nivel}', lo que requiere "
        "confirmación humana antes de cerrarlo."
        if is_critical
        else ""
    )

    step = state.get("steps", 0) + 1
    return {
        "analysis_data": final_text,
        "is_critical": is_critical,
        "critical_reason": critical_reason,
        "messages": [AIMessage(content=final_text, name="analyst")],
        "contributions": [
            {"agent": "analyst", "summary": final_text[:200], "step": step}
        ],
        "steps": step,
    }
