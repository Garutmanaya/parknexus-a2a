#!/usr/bin/env bash
set -euo pipefail

PGDATA=${PGDATA:-/var/lib/postgresql/data}

POSTGRES_BIN="$(find /usr/lib/postgresql -type f -path '*/bin/postgres' -perm -111 | sort | tail -n 1)"

if [[ -z "${POSTGRES_BIN}" || ! -x "${POSTGRES_BIN}" ]]; then
  echo "ERROR: postgres binary not found"
  find /usr/lib/postgresql -maxdepth 5 -type f -path '*/bin/*' | sort || true
  exit 1
fi

echo "Using postgres binary: ${POSTGRES_BIN}"
exec su postgres -c "\"${POSTGRES_BIN}\" -D \"${PGDATA}\""
