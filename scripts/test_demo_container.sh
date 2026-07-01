#!/usr/bin/env bash
set -euo pipefail
BASE_UI=${BASE_UI:-http://localhost:8080}
BASE_HOST=${BASE_HOST:-https://localhost:8030}
BASE_REGISTRY=${BASE_REGISTRY:-https://localhost:8020}
BASE_A=${BASE_A:-https://localhost:8011}
BASE_B=${BASE_B:-https://localhost:8012}

echo "UI"
curl -fsS "$BASE_UI" >/dev/null && echo "UI OK"

echo "Health"
curl -kfsS "$BASE_A/health"; echo
curl -kfsS "$BASE_B/health"; echo
curl -kfsS "$BASE_REGISTRY/health"; echo
curl -kfsS "$BASE_HOST/health"; echo

echo "System status"
curl -kfsS "$BASE_HOST/system/status"; echo

echo "Providers"
curl -kfsS "$BASE_HOST/providers"; echo

echo "Admin login"
curl -kfsS -X POST "$BASE_HOST/admin/login" -H "Content-Type: application/json" -d '{"username":"admin","password":"admin123"}'; echo

echo "User login"
curl -kfsS -X POST "$BASE_HOST/user/login" -H "Content-Type: application/json" -d '{"user_id":"demo","password":"demo123"}'; echo

echo "Parking find"
curl -kfsS -X POST "$BASE_HOST/parking/find" -H "Content-Type: application/json" -d '{"budget_amount":25,"budget_unit":"day","limit_per_provider":2}'; echo

echo "Garage layout"
curl -kfsS -X POST "$BASE_HOST/garage/layout" -H "Content-Type: application/json" -d '{"provider_agent":"company_a_parking_agent"}' >/dev/null && echo "Layout OK"
