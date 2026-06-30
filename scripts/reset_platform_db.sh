#!/usr/bin/env bash
set -euo pipefail
source .env

docker exec -i parknexus-postgres psql -U "${POSTGRES_ADMIN_USER}" -d postgres <<SQL
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${PLATFORM_DB_NAME}';
DROP DATABASE IF EXISTS ${PLATFORM_DB_NAME};
SQL

echo "Platform DB reset. Restart registry/host to recreate platform tables."
