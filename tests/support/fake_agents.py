"""Reemplazos determinísticos del LLM para los tests con Redis real.

Solo se sustituyen los agentes ReAct y la cadena de revisión del Supervisor,
que son lo que llama al LLM. Los nodos, el enrutamiento, el interrupt del HITL,
el checkpointer y el JobStore son los reales.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage

from app.agents import analyst_agent, research_agent, supervisor
from app.agents.supervisor import SupervisorReview

CRITICAL_INPUT = "Un trabajador falleció tras caer desde un andamio de 4 metros."
NORMAL_INPUT = "Un operario sufrió un corte leve en la mano al manipular una chapa."


def _research_answer(_task: str) -> str:
    return "Corresponde aplicar el procedimiento de reporte. [Fuente: 03_procedimiento_reporte.md]"


def _analysis_answer(task: str) -> str:
    gravedad = "fatal" if "falleció" in task else "leve"
    return f"Gravedad: {gravedad}. Recomendación: reforzar el uso de EPP."


class FakeAgent:
    def __init__(self, answer) -> None:
        self._answer = answer
        self.calls = 0

    async def ainvoke(self, payload: dict) -> dict:
        self.calls += 1
        task = payload["messages"][-1].content
        return {"messages": [AIMessage(content=self._answer(task))]}


class FakeReviewChain:
    async def ainvoke(self, _messages: list) -> SupervisorReview:
        return SupervisorReview(quiere_refinar=False, razon="Cumple la rúbrica.")


def install(setattr_fn=setattr) -> tuple[FakeAgent, FakeAgent]:
    """Instala los reemplazos y devuelve (investigador, analista) para contar llamadas."""
    researcher = FakeAgent(_research_answer)
    analyst = FakeAgent(_analysis_answer)
    setattr_fn(research_agent, "_agent", researcher)
    setattr_fn(analyst_agent, "_agent", analyst)
    setattr_fn(supervisor, "_review_chain", FakeReviewChain())
    return researcher, analyst
