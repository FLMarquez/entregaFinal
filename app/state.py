"""Estado compartido del orquestador multi-agente de Higiene y Seguridad Industrial.

Extiende `MessagesState` (que ya trae `messages` con el reducer `add_messages`)
con los campos que necesita el Supervisor para enrutar el flujo entre
especialistas y para el gate de aprobación humana (HITL) en casos críticos,
sin perder contexto entre agentes ni entre reinicios del servidor (el estado
se persiste vía el checkpointer de Redis, ver `app/graph.py` y `app/main.py`).
"""
from __future__ import annotations

import operator
from typing import Annotated, List, Literal, Optional, TypedDict

from langgraph.graph import MessagesState


class Contribution(TypedDict):
    """Un aporte puntual de un agente al estado compartido (para trazabilidad)."""

    agent: str
    summary: str
    step: int


class OrchestratorState(MessagesState):
    """Estado compartido entre Supervisor, Investigador, Analista y HITL."""

    # Consulta original del usuario. Se guarda aparte de `messages` para que
    # cada especialista reciba SOLO esto (o el dato que corresponda), nunca el
    # historial completo -- evita la "contaminación de contexto".
    user_query: str

    # Próximo nodo a ejecutar, decidido por el Supervisor (única fuente de
    # verdad sobre el flujo).
    next_agent: Literal["researcher", "analyst", "human_approval", "FINISH"]

    # True cuando el Supervisor considera que el caso está listo para cerrarse.
    task_completed: bool

    # Resultado del Agente de Investigación: normativa/procedimiento encontrado.
    research_data: str
    fuentes: List[str]

    # Resultado del Agente de Análisis: gravedad + recomendaciones.
    analysis_data: str
    is_critical: bool
    critical_reason: str

    # Resultado del gate human-in-the-loop (ver app/hitl.py). `None` mientras
    # no se resolvió; `True`/`False` una vez que un humano aprobó/rechazó.
    approved: Optional[bool]
    approval_comment: Optional[str]

    # Traza de quién contribuyó qué, en qué paso. `operator.add` concatena en
    # vez de sobreescribir.
    contributions: Annotated[list[Contribution], operator.add]

    # Contador de pasos de especialistas ejecutados (no cuenta al Supervisor
    # ni al gate de aprobación humana). Alimenta la salvaguarda MAX_STEPS.
    steps: int

    # Cuántas veces se le pidió al Analista refinar su output. Acotado por
    # MAX_REFINEMENTS en app/agents/supervisor.py.
    refinements_used: int
