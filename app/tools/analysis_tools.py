"""Herramientas de cómputo para el Agente de Análisis de higiene y seguridad
industrial. Cada una hace una sola cosa, sin LLM ni red (deterministas y
testeables de forma aislada, ver tests/test_tools.py):

- `clasificar_gravedad`: clasificación por palabras clave del nivel de
  gravedad de un caso (leve/moderado/grave/fatal).
- `validar_datos_incidente`: valida que el texto tenga la forma mínima
  esperada de un reporte de incidente (qué pasó + cuándo/dónde).
- `generar_recomendaciones`: sugiere acciones preventivas/correctivas según
  los riesgos detectados, siguiendo la jerarquía de controles (eliminación,
  sustitución, controles de ingeniería, controles administrativos, EPP).
"""
from __future__ import annotations

import re

from langchain_core.tools import tool
from pydantic import BaseModel, Field

PALABRAS_FATAL = {
    "fallecimiento", "fallecio", "falleció", "muerte", "murio", "murió", "deceso",
}
PALABRAS_GRAVE = {
    "amputación", "amputacion", "fractura expuesta", "hospitalización", "hospitalizacion",
    "inconsciente", "pérdida de conciencia", "perdida de conciencia", "quemadura grave",
    "electrocución", "electrocucion", "caída de altura", "caida de altura", "aplastamiento",
}
PALABRAS_MODERADO = {
    "fractura", "esguince", "corte profundo", "quemadura", "intoxicación", "intoxicacion",
    "derivación médica", "derivacion medica", "sutura",
}
PALABRAS_LEVE = {
    "corte leve", "raspón", "raspon", "golpe leve", "cuasi accidente", "casi accidente",
    "sin lesión", "sin lesion",
}


class ClasificarGravedadInput(BaseModel):
    texto: str = Field(description="Descripción del incidente o consulta a clasificar.")


@tool("clasificar_gravedad", args_schema=ClasificarGravedadInput)
def clasificar_gravedad(texto: str) -> str:
    """Clasifica la gravedad de un incidente de higiene y seguridad industrial en
    leve, moderado, grave o fatal, a partir de palabras clave presentes en la
    descripción del caso (por ejemplo, "fractura expuesta" -> grave, "fallecimiento" ->
    fatal). Ante ausencia de señales claras, clasifica como leve por defecto.
    """
    texto_low = texto.lower()

    def _match(palabras: set[str]) -> str | None:
        return next((p for p in palabras if p in texto_low), None)

    hit = _match(PALABRAS_FATAL)
    if hit:
        return f'Gravedad: fatal (señal detectada: "{hit}").'
    hit = _match(PALABRAS_GRAVE)
    if hit:
        return f'Gravedad: grave (señal detectada: "{hit}").'
    hit = _match(PALABRAS_MODERADO)
    if hit:
        return f'Gravedad: moderado (señal detectada: "{hit}").'
    hit = _match(PALABRAS_LEVE)
    if hit:
        return f'Gravedad: leve (señal detectada: "{hit}").'
    return "Gravedad: leve (no se detectaron señales de gravedad mayor; clasificación por defecto)."


class ValidarDatosInput(BaseModel):
    texto: str = Field(description="Descripción del incidente a validar.")


@tool("validar_datos_incidente", args_schema=ValidarDatosInput)
def validar_datos_incidente(texto: str) -> str:
    """Valida que la descripción de un incidente tenga la forma mínima esperada: qué pasó
    (texto libre suficiente) y alguna referencia de cuándo/dónde ocurrió.
    """
    tiene_descripcion = len(texto.strip()) > 20
    tiene_contexto = bool(
        re.search(
            r"\b(hoy|ayer|turno|sector|área|area|planta|obra|deposito|depósito|"
            r"\d{1,2}[:/]\d{1,2}|\d{4})\b",
            texto.lower(),
        )
    )
    if tiene_descripcion and tiene_contexto:
        return "Datos válidos: la descripción incluye el hecho y contexto de cuándo/dónde ocurrió."
    faltantes = []
    if not tiene_descripcion:
        faltantes.append("descripción suficiente del hecho")
    if not tiene_contexto:
        faltantes.append("referencia de cuándo/dónde ocurrió")
    return f"Datos inválidos o insuficientes. Falta: {', '.join(faltantes)}."


class GenerarRecomendacionesInput(BaseModel):
    texto: str = Field(description="Descripción del incidente y normativa relevante.")


@tool("generar_recomendaciones", args_schema=GenerarRecomendacionesInput)
def generar_recomendaciones(texto: str) -> str:
    """Genera recomendaciones preventivas/correctivas concretas según los riesgos
    detectados en el texto, siguiendo la jerarquía de controles (eliminación,
    sustitución, controles de ingeniería, controles administrativos, EPP).
    """
    texto_low = texto.lower()
    recomendaciones = []

    if any(k in texto_low for k in ("altura", "andamio", "escalera", "techo")):
        recomendaciones.append(
            "Verificar uso de arnés con línea de vida y puntos de anclaje certificados "
            "para trabajo en altura (control de ingeniería + EPP)."
        )
    if any(k in texto_low for k in ("epp", "casco", "guante", "protección", "proteccion")):
        recomendaciones.append(
            "Reforzar la entrega y el control de uso efectivo de los EPP correspondientes "
            "al puesto de trabajo."
        )
    if any(k in texto_low for k in ("máquina", "maquina", "corte", "atrapamiento")):
        recomendaciones.append(
            "Revisar guardas de máquina y procedimiento de bloqueo/etiquetado "
            "(lockout/tagout) antes de tareas de mantenimiento."
        )
    if any(k in texto_low for k in ("capacitación", "capacitacion", "inducción", "induccion")):
        recomendaciones.append(
            "Reforzar la capacitación/inducción de seguridad específica para el puesto "
            "y registrar su realización."
        )
    if any(k in texto_low for k in ("quimico", "químico", "tóxico", "toxico", "inhalación", "inhalacion")):
        recomendaciones.append(
            "Verificar hojas de seguridad (MSDS) del producto y disponibilidad de "
            "protección respiratoria adecuada."
        )
    if any(k in texto_low for k in ("confinado", "tanque", "cisterna", "silo")):
        recomendaciones.append(
            "Exigir permiso de entrada a espacio confinado, medición de atmósfera y "
            "vigía externo antes de autorizar el ingreso."
        )

    if not recomendaciones:
        recomendaciones.append(
            "Investigar causas inmediatas y básicas del incidente (actos y condiciones "
            "inseguras) y definir acciones correctivas con responsable y plazo."
        )

    return "Recomendaciones:\n" + "\n".join(f"- {r}" for r in recomendaciones)


def get_analysis_tools() -> list:
    """Devuelve la lista de tools del Agente de Análisis."""
    return [clasificar_gravedad, validar_datos_incidente, generar_recomendaciones]
