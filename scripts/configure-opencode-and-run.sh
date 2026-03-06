#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SEED="${1:-Build a space transport and logistics web game}"
HOST="${GENERATIONS_HOST:-127.0.0.1}"
PORT="${GENERATIONS_PORT:-80}"
MODEL_NAME="${GENERATIONS_MODEL:-qwen3.5:397b-cloud}"
OPENCODE_MODEL="${GENERATIONS_OPENCODE_MODEL:-ollama/${MODEL_NAME}}"
OPENCODE_CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/opencode"
OPENCODE_CONFIG_PATH="${OPENCODE_CONFIG_DIR}/opencode.json"

if ! command -v ollama >/dev/null 2>&1; then
  echo "ollama is not installed or not on PATH" >&2
  exit 1
fi

if ! command -v opencode >/dev/null 2>&1; then
  echo "opencode is not installed or not on PATH" >&2
  exit 1
fi

if ! ollama list | grep -Fq "${MODEL_NAME}"; then
  echo "required Ollama model not found: ${MODEL_NAME}" >&2
  echo "pull it first with: ollama pull ${MODEL_NAME}" >&2
  exit 1
fi

mkdir -p "${OPENCODE_CONFIG_DIR}"

python3 - "${OPENCODE_CONFIG_PATH}" "${MODEL_NAME}" <<'PY'
import json
import sys
from pathlib import Path

config_path = Path(sys.argv[1])
model_name = sys.argv[2]

if config_path.exists():
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        config = {}
else:
    config = {}

config.setdefault("$schema", "https://opencode.ai/config.json")
provider = config.setdefault("provider", {})
ollama = provider.setdefault("ollama", {})
ollama["npm"] = "@ai-sdk/openai-compatible"
ollama["name"] = "Local Ollama"
options = ollama.setdefault("options", {})
options["baseURL"] = "http://127.0.0.1:11434/v1"
models = ollama.setdefault("models", {})
models[model_name] = {"name": f"Ollama {model_name}"}

config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
PY

echo "OpenCode config updated: ${OPENCODE_CONFIG_PATH}"
echo "Configured model: ${OPENCODE_MODEL}"
echo "Checking OpenCode model list..."
opencode models | grep -F "${OPENCODE_MODEL}" || {
  echo "warning: ${OPENCODE_MODEL} not visible in 'opencode models' yet" >&2
  echo "OpenCode may need a restart or may be reading a different config path" >&2
}

cd "${ROOT_DIR}"
if [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

export GENERATIONS_MODEL="${MODEL_NAME}"
export GENERATIONS_OPENCODE_MODEL="${OPENCODE_MODEL}"
export OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://127.0.0.1:11434}"

exec generations run --seed "${SEED}" --parallel-tasks "${GENERATIONS_PARALLEL_TASKS:-3}" --host "${HOST}" --port "${PORT}" --debug
