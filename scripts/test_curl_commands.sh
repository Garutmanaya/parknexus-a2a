#!/usr/bin/env bash
set -euo pipefail

echo "Health checks"
curl -k https://localhost:8011/health; echo
curl -k https://localhost:8012/health; echo
curl -k https://localhost:8020/health; echo
curl -k https://localhost:8030/health; echo

echo "Register providers"
curl -k -X POST https://localhost:8020/agents/register -H "Content-Type: application/json" -d '{"agent_base_url":"https://localhost:8011"}'; echo
curl -k -X POST https://localhost:8020/agents/register -H "Content-Type: application/json" -d '{"agent_base_url":"https://localhost:8012"}'; echo

echo "Host search"
curl -k -X POST https://localhost:8030/parking/find -H "Content-Type: application/json" -d '{"budget_amount":25,"budget_unit":"day","limit_per_provider":3}'; echo

echo "Host chat"
curl -k -X POST https://localhost:8030/parking/chat -H "Content-Type: application/json" -d '{"message":"Find me cheap EV parking under $25 per day"}'; echo

echo "Garage layout"
curl -k -X POST https://localhost:8030/garage/layout -H "Content-Type: application/json" -d '{"provider_url":"https://localhost:8011"}'; echo
