FROM python:3.12.15-slim AS base

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Imagen de tests y linters (docker-compose.test.yml). No incluye .env (ver .dockerignore).
FROM base AS test

COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY pyproject.toml run.sh cli.py .env.example ./
COPY app ./app
COPY data ./data
COPY scripts ./scripts
COPY tests ./tests

# Imagen de producción: es la última etapa, la que construye `docker compose up --build`.
FROM base AS production

COPY app ./app
COPY data ./data
COPY scripts ./scripts

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
