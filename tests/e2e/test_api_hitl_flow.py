"""Punta a punta por HTTP: uvicorn real en otro proceso contra Redis Stack real.

El reinicio mata el proceso con SIGKILL, sin apagado ordenado: no queda ningún
estado en memoria y nada alcanza a guardarse a último momento. Solo el LLM y la
ingesta del RAG están reemplazados (ver tests/support/e2e_app.py).
"""

import os
import socket
import subprocess
import sys
import time

import httpx
import pytest

from tests.support.fake_agents import CRITICAL_INPUT, NORMAL_INPUT

pytestmark = pytest.mark.e2e

STARTUP_TIMEOUT_S = 120
JOB_TIMEOUT_S = 30


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class ApiServer:
    def __init__(self, redis_url: str, log_path) -> None:
        self.port = _free_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        self._redis_url = redis_url
        self._log_path = log_path
        self._process: subprocess.Popen | None = None

    def start(self) -> None:
        # Reinicio en otro puerto libre: mantiene los tests independientes del TIME_WAIT.
        self.port = _free_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        env = {
            **os.environ,
            "GOOGLE_API_KEY": "clave-falsa-sin-uso",
            "MODEL_PROVIDER": "gemini",
            "REDIS_URL": self._redis_url,
            "OBSERVABILITY_BACKEND": "none",
        }
        with open(self._log_path, "ab") as log:
            self._process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "tests.support.e2e_app:api",
                    "--port",
                    str(self.port),
                ],
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        self._wait_until_healthy()

    def _wait_until_healthy(self) -> None:
        deadline = time.monotonic() + STARTUP_TIMEOUT_S
        while time.monotonic() < deadline:
            if self._process.poll() is not None:
                break
            try:
                if httpx.get(f"{self.base_url}/health", timeout=2).status_code == 200:
                    return
            except httpx.TransportError:
                time.sleep(0.2)
        raise RuntimeError(f"La API no arrancó. Log:\n{self._log_path.read_text(errors='replace')}")

    def kill(self) -> None:
        self._process.kill()
        self._process.wait(timeout=10)

    def post(self, path: str, payload: dict) -> httpx.Response:
        return httpx.post(f"{self.base_url}{path}", json=payload, timeout=10)

    def get(self, path: str) -> httpx.Response:
        return httpx.get(f"{self.base_url}{path}", timeout=10)

    def create_task(self, user_input: str) -> str:
        response = self.post("/tasks", {"input": user_input})
        assert response.status_code == 202
        return response.json()["job_id"]

    def wait_for_status(self, job_id: str, *statuses: str) -> dict:
        deadline = time.monotonic() + JOB_TIMEOUT_S
        job: dict = {}
        while time.monotonic() < deadline:
            job = self.get(f"/tasks/{job_id}").json()
            if job["status"] in statuses:
                return job
            time.sleep(0.1)
        raise AssertionError(f"El job no llegó a {statuses}. Último estado: {job}")


@pytest.fixture
def api(redis_url, tmp_path):
    server = ApiServer(redis_url, tmp_path / "uvicorn.log")
    server.start()
    yield server
    server.kill()


def test_caso_normal_termina_sin_aprobacion(api):
    job_id = api.create_task(NORMAL_INPUT)
    job = api.wait_for_status(job_id, "DONE", "FAILED", "AWAITING_APPROVAL")

    assert job["status"] == "DONE"
    assert job["result"]["is_critical"] is False
    assert job["result"]["fuentes"] == ["03_procedimiento_reporte.md"]


def test_caso_critico_aprobado_de_punta_a_punta(api):
    job_id = api.create_task(CRITICAL_INPUT)
    paused = api.wait_for_status(job_id, "AWAITING_APPROVAL", "FAILED", "DONE")
    assert paused["status"] == "AWAITING_APPROVAL"
    assert "aprobación humana" in paused["awaiting_approval"]["message"]

    response = api.post(f"/tasks/{job_id}/approve", {"approved": True, "comment": "confirmado"})
    assert response.status_code == 200

    job = api.wait_for_status(job_id, "DONE", "REJECTED", "FAILED")
    assert job["status"] == "DONE"
    assert job["result"]["approved"] is True
    assert job["result"]["approval_comment"] == "confirmado"

    # Una decisión ya tomada no se puede volver a tomar.
    assert api.post(f"/tasks/{job_id}/approve", {"approved": False}).status_code == 409


def test_caso_critico_rechazado_queda_registrado(api):
    job_id = api.create_task(CRITICAL_INPUT)
    api.wait_for_status(job_id, "AWAITING_APPROVAL")

    api.post(f"/tasks/{job_id}/approve", {"approved": False, "comment": "falta información"})

    job = api.wait_for_status(job_id, "REJECTED", "DONE", "FAILED")
    assert job["status"] == "REJECTED"
    assert job["result"]["approved"] is False


def test_caso_pausado_sobrevive_a_matar_el_proceso(api):
    job_id = api.create_task(CRITICAL_INPUT)
    before = api.wait_for_status(job_id, "AWAITING_APPROVAL")

    api.kill()
    api.start()

    after = api.get(f"/tasks/{job_id}").json()
    assert after["status"] == "AWAITING_APPROVAL"
    assert after["awaiting_approval"] == before["awaiting_approval"]

    response = api.post(
        f"/tasks/{job_id}/approve", {"approved": True, "comment": "tras el reinicio"}
    )
    assert response.status_code == 200

    job = api.wait_for_status(job_id, "DONE", "REJECTED", "FAILED")
    assert job["status"] == "DONE"
    assert job["result"]["approval_comment"] == "tras el reinicio"
    # Si el grafo hubiera arrancado de nuevo, habría aportes duplicados.
    assert [c["agent"] for c in job["result"]["contributions"]] == ["researcher", "analyst"]


def test_job_inexistente_devuelve_404(api):
    assert api.get("/tasks/no-existe").status_code == 404
    assert api.post("/tasks/no-existe/approve", {"approved": True}).status_code == 404


def test_api_real_no_arranca_sin_api_key(redis_url):
    """Sin reemplazos: la app de producción tiene que cortar con un mensaje claro."""
    env = {**os.environ, "GOOGLE_API_KEY": "", "GEMINI_API_KEY": "", "REDIS_URL": redis_url}
    result = subprocess.run(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(_free_port())],
        env=env,
        capture_output=True,
        text=True,
        timeout=STARTUP_TIMEOUT_S,
        check=False,
    )
    assert result.returncode != 0
    assert "Configuración inválida" in result.stderr
    assert "GOOGLE_API_KEY" in result.stderr
