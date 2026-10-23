# Capturas de observabilidad

Evidencia de trazabilidad tomada del dashboard de **LangSmith** (proyecto
`higiene-seguridad-intelligence-system`), después de correr una tanda de 6 consultas reales
contra la API (consultas directas al RAG y casos completos por el orquestador multi-agente,
incluyendo dos que dispararon el flujo de aprobación humana).

- **`01_traces_overview.png`** — listado de las ejecuciones (`Tracing` → `Traces`), con
  input/output, estado y latencia de cada una. Se ven 15 trazas (una por nodo con llamada a
  LLM, acumuladas de varias corridas) en la ventana de tiempo reciente.
- **`02_trace_detail_spans_cost_latency.png`** — detalle de una traza individual: el árbol de
  spans del grafo (`supervisor` → `route_from_supervisor`, `researcher` → `agent` →
  `call_model` → `tools`, etc.) y, en el panel "Summary", la **latencia (P50: 5.78s)**, los
  **tokens consumidos (5.615K)** y el **costo estimado (\$0.0033)** de esa ejecución.
- **`03_trace_output_citado.png`** — la respuesta final generada por el Agente de
  Investigación para una consulta sobre espacios confinados, citando explícitamente las
  fuentes (`[Fuente: 06_riesgo_quimico_y_espacios_confinados.md]`) -- evidencia de que el RAG
  responde basado en los documentos reales, no por conocimiento genérico del modelo.
- **`04_rag_tool_retrieval.png`** — el input/output de la tool `buscar_normativa_seguridad`
  dentro de esa misma traza: muestra el fragmento concreto recuperado del vectorstore
  (ChromaDB) antes de que el LLM lo use para responder.

Juntas, estas capturas muestran que ninguna ejecución del sistema es una "caja negra": cada
nodo del grafo, cada llamada a LLM y cada consulta al RAG queda registrada, medida en tiempo
y costo, y es auditable end-to-end.
