"""Configuración centralizada de la API, leída desde variables de entorno (.env).

Se usa `pydantic-settings` para validar tipos y centralizar en un único lugar
todo lo que hoy son "números mágicos" o strings sueltos en el resto del código
(URL de Redis, proveedor de LLM, límites del Supervisor, backend de
observabilidad), tal como pide la consigna ("evitar hard-coding").
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Redis: usado tanto para el estado de los jobs (JobStore) como para el
    # checkpointer de LangGraph (AsyncRedisSaver).
    redis_url: str = "redis://localhost:6379/0"
    job_ttl_seconds: int = Field(default=60 * 60 * 24, gt=0)

    # Proveedor de LLM para los agentes (chat). Los embeddings del RAG siempre
    # usan Gemini (ver app/rag/rag_settings.py), independientemente de esto.
    model_provider: str = "gemini"
    model_name: str = "gemini-2.5-flash"

    # Salvaguardas del Supervisor contra el "Supervisor Infinito".
    max_steps: int = Field(default=6, gt=0)
    max_refinements: int = Field(default=1, ge=0)

    # Observabilidad: langsmith | phoenix | none.
    observability_backend: str = "langsmith"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
