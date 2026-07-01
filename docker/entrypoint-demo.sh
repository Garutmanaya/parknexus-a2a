#!/usr/bin/env bash
set -euo pipefail

cd /app

mkdir -p /app/logs /app/certs /var/lib/postgresql/data
chown -R postgres:postgres /var/lib/postgresql

# Create local HTTPS certificates for internal agent traffic.
if [[ ! -f certs/local.crt || ! -f certs/local.key ]]; then
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

# Use demo env defaults when a mounted .env is not supplied.
if [[ ! -f .env ]]; then
  cp .env.demo .env
fi

PGDATA=/var/lib/postgresql/data
PG_BIN=/usr/lib/postgresql/15/bin

# Ephemeral DB: initialize on every new container filesystem.
if [[ ! -f "$PGDATA/PG_VERSION" ]]; then
  echo "Initializing ephemeral PostgreSQL demo database..."
  su postgres -c "$PG_BIN/initdb -D $PGDATA"

  cat >> "$PGDATA/postgresql.conf" <<'PGCONF'
listen_addresses = '127.0.0.1'
port = 5432
PGCONF

  cat > "$PGDATA/pg_hba.conf" <<'PGHBA'
local   all             all                                     trust
host    all             all             127.0.0.1/32            md5
host    all             all             ::1/128                 md5
PGHBA

  su postgres -c "$PG_BIN/pg_ctl -D $PGDATA -w start"
  su postgres -c "psql -v ON_ERROR_STOP=1 -d postgres -c \"ALTER USER postgres WITH PASSWORD '${POSTGRES_ADMIN_PASSWORD:-demo_postgres_password}';\""
  su postgres -c "$PG_BIN/pg_ctl -D $PGDATA -m fast -w stop"
fi

exec /usr/bin/supervisord -c /etc/supervisor/conf.d/parknexus.conf
