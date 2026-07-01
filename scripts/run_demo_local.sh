#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME=${IMAGE_NAME:-parknexus-a2a-demo:latest}
CONTAINER_NAME=${CONTAINER_NAME:-parknexus-a2a-demo}
ENV_FILE=${ENV_FILE:-.env.demo}

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "ERROR: env file not found: ${ENV_FILE}"
  echo "Create it from .env.demo.example:"
  echo "  cp .env.demo.example .env.demo"
  echo "Then edit .env.demo and export sensitive values as needed."
  exit 1
fi

OPENAI_API_KEY_ARG=()
if [[ -n "${OPENAI_API_KEY:-}" ]]; then
  OPENAI_API_KEY_ARG=(-e "OPENAI_API_KEY=${OPENAI_API_KEY}")
fi

docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true

docker run --name "$CONTAINER_NAME" \
  --env-file "$ENV_FILE" \
  -p 8080:8080 \
  -p 8030:8030 \
  -p 8020:8020 \
  -p 8011:8011 \
  -p 8012:8012 \
  "${OPENAI_API_KEY_ARG[@]}" \
  "$IMAGE_NAME"
