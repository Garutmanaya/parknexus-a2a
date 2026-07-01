#!/usr/bin/env bash
set -euo pipefail

cd /app

echo "Starting ParkNexus A2A demo container..."

mkdir -p /app/logs /app/certs /var/lib/postgresql/data
chown -R postgres:postgres /var/lib/postgresql

# Create local HTTPS certificates for internal agent traffic.
if [[ ! -f certs/local.crt || ! -f certs/local.key ]]; then
  echo "Creating local HTTPS certificates..."

  openssl req -x509 \
    -newkey rsa:4096 \
    -keyout certs/local.key \
    -out certs/local.crt \
    -sha256 \
    -days 365 \
    -nodes \
    -subj "/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,DNS:127.0.0.1,IP:127.0.0.1,IP:0.0.0.0"
fi

PGDATA=${PGDATA:-/var/lib/postgresql/data}

PG_BIN="$(dirname "$(find /usr/lib/postgresql -type f -path '*/bin/initdb' -perm -111 | sort | tail -n 1)")"

if [[ -z "${PG_BIN}" || ! -x "${PG_BIN}/initdb" ]]; then
  echo "ERROR: Could not find PostgreSQL initdb binary."
  find /usr/lib/postgresql -maxdepth 5 -type f -path '*/bin/*' | sort || true
  exit 1
fi

echo "Using PostgreSQL binaries from: ${PG_BIN}"

# Demo mode: PostgreSQL is ephemeral. Initialize when PGDATA is empty.
if [[ ! -f "${PGDATA}/PG_VERSION" ]]; then
  echo "Initializing ephemeral PostgreSQL demo database..."

  rm -rf "${PGDATA}"
  mkdir -p "${PGDATA}"
  chown -R postgres:postgres "${PGDATA}"

  su postgres -c "\"${PG_BIN}/initdb\" -D \"${PGDATA}\""

  cat >> "${PGDATA}/postgresql.conf" <<'PGCONF'
listen_addresses = '127.0.0.1'
port = 5432
PGCONF

  cat > "${PGDATA}/pg_hba.conf" <<'PGHBA'
local   all             all                                     trust
host    all             all             127.0.0.1/32            md5
host    all             all             ::1/128                 md5
PGHBA

  chown postgres:postgres "${PGDATA}/postgresql.conf" "${PGDATA}/pg_hba.conf"

  echo "Starting PostgreSQL for initial password setup..."
  su postgres -c "\"${PG_BIN}/pg_ctl\" -D \"${PGDATA}\" -w start"

  su postgres -c "psql -v ON_ERROR_STOP=1 -d postgres -c \"ALTER USER postgres WITH PASSWORD '${POSTGRES_ADMIN_PASSWORD:-demo_postgres_password}';\""

  echo "Stopping PostgreSQL after initialization..."
  su postgres -c "\"${PG_BIN}/pg_ctl\" -D \"${PGDATA}\" -m fast -w stop"
fi

echo "Starting all ParkNexus services with supervisord..."
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/parknexus.conf
