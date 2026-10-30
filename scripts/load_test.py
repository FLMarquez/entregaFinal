"""Prueba de carga / generación de trazas: dispara varias tareas contra la API
para poblar el dashboard de observabilidad (LangSmith o Phoenix) con al menos
5 ejecuciones distintas del orquestador -- requisito de la entrega final.

Dos de las consultas describen incidentes graves/fatales a propósito, para
disparar el flujo human-in-the-loop; el script las aprueba automáticamente
para poder medir la corrida completa de punta a punta.

El costo por ejecución y la latencia p95 se calculan después sobre estas trazas con
scripts/langsmith_metrics.py, no con este script:
acá solo se generan las trazas y se imprime una latencia aproximada del lado
del cliente, como referencia.

Uso:
    python scripts/load_test.py
"""

from __future__ import annotations

import asyncio
import statistics
import time

import httpx

BASE_URL = "http://localhost:8000"

TASKS = [
    "¿Qué elementos de protección personal corresponden ante riesgo de caída de altura?",
    "Un operario sufrió un corte leve en la mano al manipular una chapa, sin necesidad de puntos.",
    "Un trabajador falleció tras una caída desde un andamio de 4 metros en el turno tarde, en el sector de obra.",
    "¿Cuáles son los pasos a seguir inmediatamente después de un accidente de trabajo?",
    "Se detectó una fractura expuesta en la pierna de un operario tras un atrapamiento con una máquina, hoy en planta.",
    "¿Qué se debe verificar antes de autorizar el ingreso a un espacio confinado?",
]

POLL_INTERVAL_S = 0.5
IN_PROGRESS_STATUSES = {"PENDING", "RUNNING", "AWAITING_APPROVAL"}


async def run_one(client: httpx.AsyncClient, text: str) -> dict:
    start = time.perf_counter()
    resp = await client.post(f"{BASE_URL}/tasks", json={"input": text})
    resp.raise_for_status()
    job_id = resp.json()["job_id"]

    status = "PENDING"
    while status in IN_PROGRESS_STATUSES:
        await asyncio.sleep(POLL_INTERVAL_S)
        job = (await client.get(f"{BASE_URL}/tasks/{job_id}")).json()
        status = job["status"]

        if status == "AWAITING_APPROVAL":
            await client.post(
                f"{BASE_URL}/tasks/{job_id}/approve",
                json={"approved": True, "comment": "auto-aprobado por scripts/load_test.py"},
            )
            status = "RUNNING"

    elapsed = time.perf_counter() - start
    return {"job_id": job_id, "input": text, "status": status, "latency_s": elapsed}


async def main() -> None:
    async with httpx.AsyncClient(timeout=180) as client:
        results = await asyncio.gather(*(run_one(client, t) for t in TASKS))

    latencies = sorted(r["latency_s"] for r in results)
    p95 = statistics.quantiles(latencies, n=100)[94] if len(latencies) > 1 else latencies[0]

    print(f"\n=== Resultados de {len(TASKS)} ejecuciones (para trazas de observabilidad) ===")
    for r in results:
        print(
            f"- {r['job_id']}: status={r['status']} "
            f'latencia={r["latency_s"]:.2f}s input="{r["input"][:60]}"'
        )

    print(f"\nLatencia p95 aproximada (medida en el cliente): {p95:.2f}s")
    print(
        "Costo por ejecución y latencia p95 'oficiales': revisá el dashboard de "
        "LangSmith/Phoenix y guardá las capturas en /screenshots."
    )


if __name__ == "__main__":
    asyncio.run(main())
