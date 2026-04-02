#!/bin/bash
set -euo pipefail

# Deploy Minuta Landing Page to minuta.morovision.ch
# Run this on the Hetzner server

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LANDING_DIR="$(dirname "$SCRIPT_DIR")"
DEPLOY_DIR="/opt/minuta-landing"

echo "=== Deploying Minuta Landing Page ==="

# Create deploy dir on server
mkdir -p "$DEPLOY_DIR"

# Copy files
cp "$LANDING_DIR/index.html" "$DEPLOY_DIR/"
cp "$LANDING_DIR/logo.png" "$DEPLOY_DIR/"
cp "$LANDING_DIR/favicon.ico" "$DEPLOY_DIR/"
cp "$LANDING_DIR/apple-touch-icon.png" "$DEPLOY_DIR/"
cp "$SCRIPT_DIR/Dockerfile" "$DEPLOY_DIR/"
cp "$SCRIPT_DIR/nginx.conf" "$DEPLOY_DIR/"
cp "$SCRIPT_DIR/docker-compose.yml" "$DEPLOY_DIR/"

# Build and start
cd "$DEPLOY_DIR"
docker compose down 2>/dev/null || true
docker compose build --no-cache
docker compose up -d

echo ""
echo "=== Deployed ==="
echo "URL: https://minuta.morovision.ch"
docker compose ps
