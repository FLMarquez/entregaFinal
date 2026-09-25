# Capturas de observabilidad

Después de correr `python scripts/load_test.py` con la API y Redis levantados, entrar al
dashboard de observabilidad activo (LangSmith o Arize Phoenix, según `OBSERVABILITY_BACKEND`)
y guardar acá al menos:

1. **`traces_overview.png`** — lista de las ejecuciones de la corrida, mostrando las
   distintas tareas y (si aplica) las pausas por aprobación humana.
2. **`trace_detail.png`** — el detalle de una traza individual, con los spans de cada nodo
   del grafo (`supervisor`, `researcher`, `analyst`, `human_approval`) y sus tiempos.
3. **`latency_p95.png`** — la latencia p95 calculada por la plataforma para la corrida.
4. **`cost_per_run.png`** — el costo estimado por ejecución (tokens de entrada/salida).

Estas capturas son la evidencia de que el sistema no es una "caja negra": cada nodo del
orquestador queda trazado y auditable end-to-end.
