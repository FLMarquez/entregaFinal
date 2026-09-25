"""Tests de las herramientas de análisis (sin LLM ni red)."""
from app.tools.analysis_tools import clasificar_gravedad, generar_recomendaciones, validar_datos_incidente


def test_clasificar_gravedad_detecta_fatal():
    resultado = clasificar_gravedad.invoke(
        {"texto": "Se produjo el fallecimiento del operario tras la caída."}
    )
    assert "fatal" in resultado.lower()


def test_clasificar_gravedad_detecta_grave():
    resultado = clasificar_gravedad.invoke(
        {"texto": "El trabajador sufrió una fractura expuesta en la pierna."}
    )
    assert "grave" in resultado.lower()


def test_clasificar_gravedad_default_leve():
    resultado = clasificar_gravedad.invoke(
        {"texto": "Un cuasi accidente sin consecuencias en el sector de depósito."}
    )
    assert "leve" in resultado.lower()


def test_validar_datos_incidente_ok():
    resultado = validar_datos_incidente.invoke(
        {
            "texto": "Hoy en el turno tarde, en el sector de depósito, un operario "
            "resbaló al bajar una escalera."
        }
    )
    assert "válidos" in resultado


def test_validar_datos_incidente_insuficiente():
    resultado = validar_datos_incidente.invoke({"texto": "algo paso"})
    assert "inválidos" in resultado or "insuficientes" in resultado


def test_generar_recomendaciones_sugiere_arnes_para_altura():
    resultado = generar_recomendaciones.invoke(
        {"texto": "El operario trabajaba en altura sobre un andamio sin sujeción."}
    )
    assert "arnés" in resultado.lower() or "arnes" in resultado.lower()


def test_generar_recomendaciones_sugiere_espacio_confinado():
    resultado = generar_recomendaciones.invoke(
        {"texto": "Un operario ingresó a un tanque confinado sin autorización previa."}
    )
    assert "confinado" in resultado.lower()


def test_generar_recomendaciones_fallback_generico():
    resultado = generar_recomendaciones.invoke({"texto": "Se rompió una silla de oficina."})
    assert "Recomendaciones" in resultado
