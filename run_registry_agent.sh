uvicorn platform_services.registry_agent.main:app \
  --host 0.0.0.0 \
  --port 8020 \
  --ssl-certfile certs/local.crt \
  --ssl-keyfile certs/local.key
