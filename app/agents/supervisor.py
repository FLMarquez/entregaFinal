"""Supervisor: router inteligente y controlador de flujo del orquestador de
Higiene y Seguridad Industrial.

Separa a propósito dos responsabilidades (diseño validado en la pre-entrega
de agentes, ver README):

1. `decide_next_agent` (función pura, sin LLM): reglas "duras" que garantizan
   terminación. El LLM NUNCA puede saltarse estas reglas -- esto es lo que
   evita el "Supervisor Infinito".
2. `supervisor_node` (usa LLM con salida estructurada `SupervisorReview`):
   aporta el juicio cualitativo ("¿el análisis de riesgo está bien
   fundamentado o hay que refinarlo?"). Se combina con las reglas duras,
   nunca las reemplaza.

Rúbrica de suficiencia (`is_analysis_sufficient`): el análisis se considera
suficiente si incluye un nivel de gravedad explícito (leve/moderado/grave/
fatal) Y al menos una recomendación concreta. Si además el caso es crítico
(grave/fatal), el Supervisor no cierra el caso directamente: lo enruta al
gate `human_approval` (ver app/hitl.py) hasta que un humano confirme el
cierre -- ver `decide_next_agent`.
"""

from __future__ import annotations

import re
from typing import Literal, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.llm_provider import get_llm
from app.settings import get_settings
from app.state import OrchestratorState

SUPERVISOR_RUBRIC = """Sos el Supervisor de un equipo de dos especialistas en higiene y \
seguridad industrial: un Agente de Investigación (busca normativa y procedimientos \
vigentes) y un Agente de Análisis (clasifica la gravedad del caso y recomienda acciones).

Tu trabajo es evaluar si el análisis actual (`analysis_data`) es de buena calidad, dado \
los datos normativos que lo originaron (`research_data`).

Rúbrica de suficiencia:
- Debe incluir un nivel de gravedad explícito (leve, moderado, grave o fatal).
- Debe incluir al menos una recomendación concreta y accionable.
- No debe contradecir la normativa/procedimiento citado por el Investigador.

Si el análisis cumple la rúbrica, `quiere_refinar` debe ser False. Si le falta algún \
elemento o es vago, `quiere_refinar` debe ser True. Justificá tu decisión en una oración \
en español."""


class SupervisorReview(BaseModel):
    quiere_refinar: bool = Field(
        description="True si el análisis actual es insuficiente y el Agente de Análisis debería refinarlo."
    )
    razon: str = Field(description="Justificación breve de la decisión, en español.")


_review_chain = None


def _get_review_chain():
    global _review_chain
    if _review_chain is None:
        _review_chain = get_llm().with_structured_output(SupervisorReview)
    return _review_chain


def is_analysis_sufficient(analysis_text: str) -> bool:
    """Chequeo determinístico de la rúbrica (gravedad + recomendación explícitas)."""
    texto = analysis_text.lower()
    tiene_gravedad = bool(re.search(r"\b(leve|moderad[oa]|grave|fatal)\b", texto))
    tiene_recomendacion = bool(re.search(r"recomend", texto))
    return tiene_gravedad and tiene_recomendacion


def decide_next_agent(
    has_research: bool,
    has_analysis: bool,
    analysis_sufficient: bool,
    refinements_used: int,
    steps: int,
    llm_wants_refine: bool,
    is_critical: bool = False,
    approved: Optional[bool] = None,
) -> Literal["researcher", "analyst", "human_approval", "FINISH"]:
    """Regla dura de enrutamiento. Sin llamadas a LLM: 100% determinística y testeable.

    Garantiza terminación en como mucho `MAX_STEPS` pasos de especialistas, más
    como mucho `MAX_REFINEMENTS` vueltas de refinamiento del Analista, más (a
    lo sumo una vez) el gate de aprobación humana para casos críticos -- sin
    importar lo que "opine" el LLM. Una vez que `approved` deja de ser `None`
    (se aprobó o se rechazó), el caso se cierra igual en ambos casos: el
    rechazo queda registrado en el estado para seguimiento manual, pero nunca
    deja el grafo esperando indefinidamente.
    """
    settings = get_settings()
    if steps >= settings.max_steps:
        return "FINISH"
    if not has_research:
        return "researcher"
    if not has_analysis:
        return "analyst"

    needs_refine = (not analysis_sufficient or llm_wants_refine) and (
        refinements_used < settings.max_refinements
    )
    if needs_refine:
        return "analyst"

    if is_critical and approved is None:
        return "human_approval"

    return "FINISH"


async def supervisor_node(state: OrchestratorState) -> dict:
    settings = get_settings()
    steps = state.get("steps", 0)
    has_research = bool(state.get("research_data"))
    has_analysis = bool(state.get("analysis_data"))
    refinements_used = state.get("refinements_used", 0)
    is_critical = state.get("is_critical", False)
    approved = state.get("approved")

    llm_wants_refine = False
    reason = "Todavía no hay suficiente información para evaluar la calidad del análisis."
    sufficient = False

    if has_research and has_analysis and steps < settings.max_steps:
        sufficient = is_analysis_sufficient(state["analysis_data"])
        context = (
            f"Consulta original del usuario:\n{state.get('user_query', '')}\n\n"
            f"Normativa/procedimiento investigado:\n{state['research_data']}\n\n"
            f"Análisis actual:\n{state['analysis_data']}\n\n"
            f"Chequeo automático de rúbrica (gravedad + recomendación explícitas): "
            f"{'CUMPLE' if sufficient else 'NO CUMPLE'}."
        )
        review = await _get_review_chain().ainvoke(
            [SystemMessage(content=SUPERVISOR_RUBRIC), HumanMessage(content=context)]
        )
        llm_wants_refine = review.quiere_refinar
        reason = review.razon

    next_agent = decide_next_agent(
        has_research,
        has_analysis,
        sufficient,
        refinements_used,
        steps,
        llm_wants_refine,
        is_critical,
        approved,
    )

    updates: dict = {
        "next_agent": next_agent,
        "task_completed": next_agent == "FINISH",
        "messages": [AIMessage(content=f"[Supervisor] {reason}", name="supervisor")],
    }
    if next_agent == "analyst" and has_analysis:
        updates["refinements_used"] = refinements_used + 1
    return updates
