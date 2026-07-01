#!/usr/bin/env bash
set -euo pipefail

wait_url() {
  local url="$1"
  local name="$2"
  for i in $(seq 1 90); do
    if curl -kfsS "$url" >/dev/null 2>&1; then
      echo "$name is ready"
      return 0
    fi
    sleep 2
  done
  echo "Timed out waiting for $name at $url" >&2
  return 1
}

wait_url "https://127.0.0.1:8011/health" "provider_a"
wait_url "https://127.0.0.1:8012/health" "provider_b"
wait_url "https://127.0.0.1:8020/health" "registry"
wait_url "https://127.0.0.1:8030/health" "host"

echo "Registering demo providers..."
curl -kfsS -X POST https://127.0.0.1:8020/agents/register \
  -H "Content-Type: application/json" \
  -d '{"agent_base_url":"https://localhost:8011"}' || true

echo
curl -kfsS -X POST https://127.0.0.1:8020/agents/register \
  -H "Content-Type: application/json" \
  -d '{"agent_base_url":"https://localhost:8012"}' || true

echo

echo "Creating demo user if missing..."
curl -kfsS -X POST https://127.0.0.1:8030/admin/users \
  -H "Content-Type: application/json" \
  -d '{"user_id":"demo","password":"demo123","display_name":"Demo User","email":"demo@example.com","first_name":"Demo","last_name":"User"}' || true

echo

echo "ParkNexus demo bootstrap completed. UI is available on http://localhost:8080"
