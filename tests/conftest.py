"""Configuración compartida de los tests.

Los tests de integración y E2E usan Redis real pero nunca un LLM real, así que
no gastan cuota y no deben ensuciar el dashboard de observabilidad.
"""

import os

import pytest
import redis

os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"


@pytest.fixture(scope="session")
def redis_url() -> str:
    """URL de Redis Stack. Sin TEST_REDIS_URL se omite el test; con ella, si
    Redis no responde el test falla (un omitido silencioso ocultaría el problema)."""
    url = os.getenv("TEST_REDIS_URL")
    if not url:
        pytest.skip("Definí TEST_REDIS_URL para correr contra Redis Stack real.")
    client = redis.from_url(url)
    try:
        client.ping()
    finally:
        client.close()
    return url
