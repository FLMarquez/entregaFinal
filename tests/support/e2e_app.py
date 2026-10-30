"""La API real con el LLM y la ingesta del RAG reemplazados, para levantarla con
uvicorn en los tests E2E: `uvicorn tests.support.e2e_app:api`.
"""

from app.main import app as api
from app.rag import ingest as rag_ingest
from tests.support.fake_agents import install

install()
rag_ingest.ingest = lambda force=False: None

__all__ = ["api"]
