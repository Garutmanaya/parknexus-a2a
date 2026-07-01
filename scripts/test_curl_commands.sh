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

echo "Admin login"
curl -k -X POST https://localhost:8030/admin/login -H "Content-Type: application/json" -d '{"username":"admin","password":"admin123"}'; echo

echo "Create user"
curl -k -X POST https://localhost:8030/admin/users -H "Content-Type: application/json" -d '{"user_id":"ui_user_001","display_name":"Demo User","email":"demo@example.com"}'; echo

echo "List users"
curl -k https://localhost:8030/admin/users; echo

echo "Host search"
curl -k -X POST https://localhost:8030/parking/find -H "Content-Type: application/json" -d '{"budget_amount":25,"budget_unit":"day","limit_per_provider":3}'; echo

echo "Host chat"
curl -k -X POST https://localhost:8030/parking/chat -H "Content-Type: application/json" -d '{"message":"Find me cheap EV parking under $25 per day"}'; echo

echo "Garage layout through Host only"
curl -k -X POST https://localhost:8030/garage/layout -H "Content-Type: application/json" -d '{"provider_agent":"company_a_parking_agent"}'; echo

echo "Transactions"
curl -k "https://localhost:8030/transactions?user_id=ui_user_001&limit=5"; echo
