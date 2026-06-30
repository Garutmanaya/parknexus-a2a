#!/usr/bin/env bash
set -e

mkdir -p certs

openssl req -x509 \
  -newkey rsa:4096 \
  -keyout certs/local.key \
  -out certs/local.crt \
  -sha256 \
  -days 365 \
  -nodes \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"

echo "Local HTTPS certs created:"
echo "  certs/local.crt"
echo "  certs/local.key"
