#!/usr/bin/env bash
# Levanta todo el sistema (Redis + API) con una sola instrucción.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Se creó .env a partir de .env.example. Completá tus API keys antes de usar el sistema."
fi

docker compose up --build
