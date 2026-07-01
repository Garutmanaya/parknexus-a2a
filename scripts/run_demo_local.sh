#!/usr/bin/env bash
set -euo pipefail
IMAGE_NAME=${IMAGE_NAME:-parknexus-a2a-demo:latest}
CONTAINER_NAME=${CONTAINER_NAME:-parknexus-a2a-demo}
OPENAI_API_KEY_ARG=${OPENAI_API_KEY:+-e OPENAI_API_KEY=$OPENAI_API_KEY}

docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
# shellcheck disable=SC2086
docker run --name "$CONTAINER_NAME" \
  -p 8080:8080 \
  -p 8030:8030 \
  -p 8020:8020 \
  -p 8011:8011 \
  -p 8012:8012 \
  $OPENAI_API_KEY_ARG \
  "$IMAGE_NAME"
