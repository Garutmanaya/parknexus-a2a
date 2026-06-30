#!/usr/bin/env bash
set -euo pipefail
source .env

docker exec -it parknexus-postgres psql -U "${POSTGRES_ADMIN_USER}" -d postgres -c "DROP DATABASE IF EXISTS ${COMPANY_A_DB_NAME};"
docker exec -it parknexus-postgres psql -U "${POSTGRES_ADMIN_USER}" -d postgres -c "DROP DATABASE IF EXISTS ${COMPANY_B_DB_NAME};"
echo "Provider databases dropped. Restart provider services to recreate schema and seed data."
