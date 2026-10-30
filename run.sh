#!/usr/bin/env bash
# Levanta todo el sistema (Redis + API) con una sola instrucción.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Se creó .env a partir de .env.example."
fi

# Último valor de una variable en .env, sin comillas ni CR de fin de línea (Windows).
env_value() {
  { grep -E "^$1=" .env || true; } | tail -n 1 | cut -d= -f2- | tr -d "\r\"' "
}

missing=()
if [ -z "$(env_value GOOGLE_API_KEY)" ] && [ -z "$(env_value GEMINI_API_KEY)" ]; then
  missing+=("GOOGLE_API_KEY (obligatoria: los embeddings del RAG siempre usan Gemini)")
fi
case "$(env_value MODEL_PROVIDER)" in
  openai) [ -n "$(env_value OPENAI_API_KEY)" ] || missing+=("OPENAI_API_KEY (MODEL_PROVIDER=openai)") ;;
  anthropic) [ -n "$(env_value ANTHROPIC_API_KEY)" ] || missing+=("ANTHROPIC_API_KEY (MODEL_PROVIDER=anthropic)") ;;
esac

if [ "${#missing[@]}" -gt 0 ]; then
  echo "ERROR: faltan variables obligatorias en .env:" >&2
  printf '  - %s\n' "${missing[@]}" >&2
  exit 1
fi

docker compose up --build
