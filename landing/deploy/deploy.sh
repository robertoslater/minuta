#!/bin/bash
set -euo pipefail

# ═══════════════════════════════════════════════════
# Minuta Landing Page – Deployment to Hetzner
# Target: minuta.morovision.ch
# Server: Docker VM 10.10.10.10 (via WireGuard VPN)
# ═══════════════════════════════════════════════════

# ── Config ──
DOCKER_HOST="root@10.10.10.10"
JUMP_HOST="root@10.10.99.1"
REMOTE_DIR="/opt/localAIagent"
MINUTA_DIR="${REMOTE_DIR}/minuta-landing"
COMPOSE_FILE="${REMOTE_DIR}/docker-compose-minuta.yml"
LOCAL_DIR="$(cd "$(dirname "$0")/.." && pwd)"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err() { echo -e "${RED}[✗]${NC} $1"; exit 1; }

SSH_CMD="ssh -o ConnectTimeout=5"

# ── Step 1: Check VPN ──
echo ""
echo "═══ Minuta Landing Page Deployment ═══"
echo ""

# Try direct connection first, then jump host
if $SSH_CMD $DOCKER_HOST "echo ok" &>/dev/null; then
    log "Direkte SSH-Verbindung zu Docker VM OK"
    SSH="$SSH_CMD $DOCKER_HOST"
    SCP="scp"
    SCP_HOST="$DOCKER_HOST"
elif $SSH_CMD -J $JUMP_HOST $DOCKER_HOST "echo ok" &>/dev/null; then
    log "SSH via Jump-Host zu Docker VM OK"
    SSH="$SSH_CMD -J $JUMP_HOST $DOCKER_HOST"
    SCP="scp -o ProxyJump=$JUMP_HOST"
    SCP_HOST="$DOCKER_HOST"
else
    err "Keine SSH-Verbindung möglich. Ist WireGuard VPN aktiv?\n    Starte VPN: wg-quick up wg0"
fi

# ── Step 2: Create remote directory ──
log "Erstelle Remote-Verzeichnis..."
$SSH "mkdir -p ${MINUTA_DIR}"

# ── Step 3: Copy files ──
log "Kopiere Minuta Landing Page Dateien..."

$SCP "${LOCAL_DIR}/index.html" "${SCP_HOST}:${MINUTA_DIR}/"
$SCP "${LOCAL_DIR}/logo.png" "${SCP_HOST}:${MINUTA_DIR}/"
$SCP "${LOCAL_DIR}/favicon.ico" "${SCP_HOST}:${MINUTA_DIR}/"
$SCP "${LOCAL_DIR}/apple-touch-icon.png" "${SCP_HOST}:${MINUTA_DIR}/"
$SCP "${LOCAL_DIR}/deploy/Dockerfile" "${SCP_HOST}:${MINUTA_DIR}/"
$SCP "${LOCAL_DIR}/deploy/nginx.conf" "${SCP_HOST}:${MINUTA_DIR}/"

# Docker Compose (separate file)
$SCP "${LOCAL_DIR}/deploy/docker-compose.yml" "${SCP_HOST}:${COMPOSE_FILE}"

log "Dateien kopiert"

# ── Step 4: Build & Start ──
log "Baue und starte Container..."
$SSH "cd ${REMOTE_DIR} && docker compose -f docker-compose-minuta.yml up -d --build"

# ── Step 5: Health Check ──
log "Warte auf Container-Start (5s)..."
sleep 5

$SSH "docker ps --filter name=minuta-landing --format '{{.Status}}'" | while read status; do
    if echo "$status" | grep -q "Up"; then
        log "Container läuft: $status"
    else
        warn "Container Status: $status"
    fi
done

# ── Step 6: External Check ──
echo ""
log "Prüfe HTTPS-Zugang..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "https://minuta.morovision.ch" 2>/dev/null || echo "000")

if [ "$HTTP_CODE" = "200" ]; then
    log "Landing Page erreichbar (HTTP 200)"
elif [ "$HTTP_CODE" = "000" ]; then
    warn "Seite noch nicht erreichbar – DNS-Propagation kann 1-2 Min dauern"
    warn "Erstelle CNAME oder A-Record: minuta.morovision.ch → dein Hetzner Server"
else
    warn "HTTP-Code: $HTTP_CODE"
fi

echo ""
echo "═══════════════════════════════════════════"
echo -e "  ${GREEN}Minuta Landing Page deployed!${NC}"
echo "  URL: https://minuta.morovision.ch"
echo "═══════════════════════════════════════════"
echo ""
