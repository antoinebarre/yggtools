#!/usr/bin/env bash
set -euo pipefail

mkdir -p work
requirements="work/runtime-requirements.txt"
uv export --no-dev --no-hashes --format requirements-txt > "$requirements"

if ! grep -Eq '^[A-Za-z0-9_.-]==' "$requirements"; then
    echo "No runtime dependencies to audit."
    exit 0
fi

uv run pip-audit --strict --requirement "$requirements"
