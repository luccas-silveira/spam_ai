#!/usr/bin/env bash
set -euo pipefail

if [[ "${SKIP_TIME_SYNC:-}" != "1" ]]; then
  if [[ -f scripts/current_time.py ]]; then
    echo "[entrypoint] sincronizando data/hora real..."
    if ! python3 scripts/current_time.py; then
      echo "[entrypoint] aviso: não foi possível sincronizar a hora real" >&2
    fi
  else
    echo "[entrypoint] scripts/current_time.py não encontrado; pulando sincronização" >&2
  fi
else
  echo "[entrypoint] SKIP_TIME_SYNC=1 — pulando sincronização" >&2
fi

echo "[entrypoint] iniciando serviço: $*"
exec "$@"
