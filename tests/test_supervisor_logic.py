"""Tests de la lógica de enrutamiento del Supervisor (no requieren API key).

`decide_next_agent` e `is_analysis_sufficient` son funciones puras (sin LLM),
pensadas para verificar -- sin gastar cuota de ninguna API -- que el grafo
SIEMPRE termina, que las reglas de refinamiento se respetan, y que el gate de
aprobación humana para casos críticos se dispara exactamente una vez.
"""
from app.agents.supervisor import decide_next_agent, is_analysis_sufficient


def test_sin_research_va_a_researcher():
    assert decide_next_agent(False, False, False, 0, 0, False) == "researcher"


def test_con_research_sin_analysis_va_a_analyst():
    assert decide_next_agent(True, False, False, 0, 1, False) == "analyst"


def test_analisis_suficiente_no_critico_finaliza():
    assert decide_next_agent(True, True, True, 0, 2, False, is_critical=False) == "FINISH"


def test_analisis_insuficiente_pide_refinamiento_una_vez():
    assert decide_next_agent(True, True, False, 0, 2, True) == "analyst"


def test_refinamiento_agotado_finaliza_aunque_llm_insista():
    """Aunque el LLM pida refinar de nuevo, el límite de refinamientos manda."""
    assert decide_next_agent(True, True, False, 1, 3, True) == "FINISH"


def test_max_steps_fuerza_finish_sin_importar_nada():
    """Salvaguarda dura: al llegar a MAX_STEPS, se termina sí o sí."""
    assert decide_next_agent(False, False, False, 0, 6, True) == "FINISH"


def test_caso_critico_sin_aprobacion_va_a_human_approval():
    assert (
        decide_next_agent(True, True, True, 0, 2, False, is_critical=True, approved=None)
        == "human_approval"
    )


def test_caso_critico_ya_aprobado_finaliza():
    assert (
        decide_next_agent(True, True, True, 0, 2, False, is_critical=True, approved=True)
        == "FINISH"
    )


def test_caso_critico_ya_rechazado_tambien_finaliza():
    """El Supervisor cierra el caso tanto si se aprueba como si se rechaza: el
    rechazo queda registrado en el estado (approved=False) para seguimiento
    manual, pero nunca debe dejar el grafo esperando indefinidamente."""
    assert (
        decide_next_agent(True, True, True, 0, 2, False, is_critical=True, approved=False)
        == "FINISH"
    )


def test_es_terminacion_garantizada_incluso_con_caso_critico():
    """Simula una corrida completa (con refinamientos y HITL) y verifica que
    siempre termina, sin exceder MAX_STEPS pasos de especialistas."""
    has_research = has_analysis = False
    sufficient = False
    refinements_used = 0
    steps = 0
    is_critical = True
    approved = None
    visited = []

    for _ in range(50):  # cota de seguridad del propio test
        next_agent = decide_next_agent(
            has_research, has_analysis, sufficient, refinements_used, steps, True, is_critical, approved
        )
        visited.append(next_agent)
        if next_agent == "FINISH":
            break
        if next_agent == "researcher":
            has_research = True
        elif next_agent == "analyst":
            if has_analysis:
                refinements_used += 1
            has_analysis = True
            sufficient = True
            steps += 1
        elif next_agent == "human_approval":
            approved = True

    assert visited[-1] == "FINISH"
    assert steps <= 6


def test_is_analysis_sufficient_requiere_gravedad_y_recomendacion():
    assert is_analysis_sufficient("Gravedad: grave. Recomendación: reforzar EPP.")
    assert not is_analysis_sufficient("El caso parece bastante serio.")
    assert not is_analysis_sufficient("Gravedad: leve, sin más detalle.")
