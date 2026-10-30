"""Validación de entorno al arrancar: en la API (app/env_check.py) y en run.sh."""

import shutil
import subprocess
from pathlib import Path

import pytest

from app.env_check import EnvironmentValidationError, find_env_problems, validate_environment

REPO_ROOT = Path(__file__).resolve().parent.parent
VALID = {"GOOGLE_API_KEY": "key"}


def test_entorno_minimo_valido_no_tiene_problemas():
    assert find_env_problems(VALID) == []


def test_gemini_api_key_tambien_sirve_para_embeddings():
    assert find_env_problems({"GEMINI_API_KEY": "key"}) == []


@pytest.mark.parametrize("value", ["", "   "])
def test_google_api_key_vacia_es_un_problema(value):
    problems = find_env_problems({"GOOGLE_API_KEY": value})
    assert len(problems) == 1
    assert "GOOGLE_API_KEY" in problems[0]


def test_otro_proveedor_igual_requiere_key_de_gemini_para_embeddings():
    problems = find_env_problems({"MODEL_PROVIDER": "openai", "OPENAI_API_KEY": "key"})
    assert len(problems) == 1
    assert "embeddings" in problems[0]


@pytest.mark.parametrize(
    ("provider", "key"), [("openai", "OPENAI_API_KEY"), ("anthropic", "ANTHROPIC_API_KEY")]
)
def test_proveedor_requiere_su_propia_key(provider, key):
    problems = find_env_problems({**VALID, "MODEL_PROVIDER": provider})
    assert len(problems) == 1
    assert key in problems[0]


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("MODEL_PROVIDER", "llama"),
        ("REDIS_URL", "localhost:6379"),
        ("OBSERVABILITY_BACKEND", "datadog"),
    ],
)
def test_valor_invalido_es_un_problema(name, value):
    problems = find_env_problems({**VALID, name: value})
    assert len(problems) == 1
    assert name in problems[0]


def test_informa_todos_los_problemas_juntos():
    assert len(find_env_problems({"MODEL_PROVIDER": "llama", "REDIS_URL": "x"})) == 3


def test_validate_environment_incluye_tipos_invalidos_de_settings(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("MAX_STEPS", "0")
    with pytest.raises(EnvironmentValidationError) as exc:
        validate_environment()
    assert "GOOGLE_API_KEY" in str(exc.value)
    assert "MAX_STEPS" in str(exc.value)


@pytest.fixture
def run_sh(tmp_path):
    """run.sh aislado, con un `docker` falso que solo registra que fue invocado."""
    if shutil.which("bash") is None:
        pytest.skip("Requiere bash.")
    shutil.copy(REPO_ROOT / "run.sh", tmp_path)
    shutil.copy(REPO_ROOT / ".env.example", tmp_path)
    fake_docker = tmp_path / "docker"
    fake_docker.write_text('#!/bin/sh\necho "$@" > docker_called\n', newline="\n")
    fake_docker.chmod(0o755)

    def run() -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", "-c", f'PATH="{tmp_path.as_posix()}:$PATH" bash run.sh'],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
        )

    return tmp_path, run


def test_run_sh_falla_sin_api_key_y_no_levanta_docker(run_sh):
    folder, run = run_sh
    result = run()  # sin .env: lo crea desde .env.example, con la key vacía
    assert result.returncode == 1
    assert "GOOGLE_API_KEY" in result.stderr
    assert (folder / ".env").exists()
    assert not (folder / "docker_called").exists()


def test_run_sh_tolera_fin_de_linea_de_windows_sin_valor(run_sh):
    folder, run = run_sh
    (folder / ".env").write_bytes(b"GOOGLE_API_KEY=\r\n")
    assert run().returncode == 1


def test_run_sh_exige_la_key_del_proveedor_elegido(run_sh):
    folder, run = run_sh
    (folder / ".env").write_text("GOOGLE_API_KEY=key\nMODEL_PROVIDER=openai\n", newline="\n")
    result = run()
    assert result.returncode == 1
    assert "OPENAI_API_KEY" in result.stderr


def test_run_sh_con_key_levanta_docker_compose(run_sh):
    folder, run = run_sh
    (folder / ".env").write_text("GOOGLE_API_KEY=key\n", newline="\n")
    result = run()
    assert result.returncode == 0, result.stderr
    assert (folder / "docker_called").read_text().strip() == "compose up --build"
