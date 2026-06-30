#!/usr/bin/env bash
set -euo pipefail
python -m agent_runtime.run --config agents/company_a/agent.yaml --a2a agents/company_a/a2a.yaml --port 8011 --ssl-certfile certs/local.crt --ssl-keyfile certs/local.key
