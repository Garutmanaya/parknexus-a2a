#!/usr/bin/env bash
set -euo pipefail
uvicorn platform_services.host_agent.main:app --host 0.0.0.0 --port 8030 --ssl-certfile certs/local.crt --ssl-keyfile certs/local.key
