#!/usr/bin/env bash
set -euo pipefail
IMAGE_NAME=${IMAGE_NAME:-parknexus-a2a-demo:latest}
docker build -f Dockerfile.demo -t "$IMAGE_NAME" .
echo "Built $IMAGE_NAME"
