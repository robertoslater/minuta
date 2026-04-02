#!/bin/bash
set -euo pipefail

# ============================================
# Minuta - Installation Script
# macOS Apple Silicon only
# ============================================

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'
BOLD='\033[1m'

info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

echo ""
echo -e "${BOLD}╔══════════════════════════════════════╗${NC}"
echo -e "${BOLD}║     Minuta - Installation     ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════╝${NC}"
echo ""

# --- Check macOS + Apple Silicon ---
if [[ "$(uname)" != "Darwin" ]]; then
    error "Dieses Tool laeuft nur auf macOS."
fi

ARCH=$(uname -m)
if [[ "$ARCH" != "arm64" ]]; then
    error "Apple Silicon (M1/M2/M3/M4) erforderlich. Erkannt: $ARCH"
fi

MACOS_VERSION=$(sw_vers -productVersion)
info "macOS $MACOS_VERSION auf $ARCH erkannt"

# --- Check Xcode CLI Tools ---
if ! xcode-select -p &>/dev/null; then
    info "Xcode Command Line Tools werden installiert..."
    xcode-select --install
    echo "Bitte installiere die Xcode CLI Tools und starte dieses Script erneut."
    exit 1
fi
info "Xcode CLI Tools vorhanden"

# --- Check/Install Homebrew ---
if ! command -v brew &>/dev/null; then
    warn "Homebrew nicht gefunden. Bitte installiere es: https://brew.sh"
    exit 1
fi

# --- Check/Install Node.js ---
if ! command -v node &>/dev/null; then
    info "Node.js wird installiert..."
    brew install node
fi
info "Node.js $(node --version) vorhanden"

# --- Check/Install uv ---
if ! command -v uv &>/dev/null; then
    info "uv (Python Package Manager) wird installiert..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi
info "uv vorhanden"

# --- Check/Install FFmpeg ---
if ! command -v ffmpeg &>/dev/null; then
    info "FFmpeg wird installiert..."
    brew install ffmpeg
fi
info "FFmpeg vorhanden"

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_DIR="$HOME/.minuta"

# --- Python Backend ---
info "Python Backend wird eingerichtet..."
cd "$PROJECT_DIR/backend"
uv sync
info "Python Dependencies installiert"

# --- Swift audiocap ---
info "Swift audiocap wird kompiliert..."
cd "$PROJECT_DIR/audiocap"
swift build -c release 2>&1 | tail -3
info "audiocap kompiliert"

# --- Next.js Frontend ---
info "Next.js Frontend wird eingerichtet..."
cd "$PROJECT_DIR/frontend"
npm install --silent
info "Frontend Dependencies installiert"

# --- Config ---
mkdir -p "$CONFIG_DIR"
if [[ ! -f "$CONFIG_DIR/config.toml" ]]; then
    cp "$PROJECT_DIR/config.example.toml" "$CONFIG_DIR/config.toml"
    info "Konfiguration erstellt: $CONFIG_DIR/config.toml"
else
    info "Konfiguration existiert bereits: $CONFIG_DIR/config.toml"
fi

# --- MLX Whisper Model (optional) ---
echo ""
read -p "$(echo -e "${YELLOW}MLX Whisper Modell jetzt herunterladen? (~3 GB) [y/N]${NC} ")" -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    info "Whisper Modell wird heruntergeladen (kann einige Minuten dauern)..."
    cd "$PROJECT_DIR/backend"
    uv run python -c "
import mlx_whisper
print('Modell wird geladen/heruntergeladen...')
# Trigger download by loading the model
result = mlx_whisper.transcribe(
    __import__('numpy').zeros(16000, dtype=__import__('numpy').float32),
    path_or_hf_repo='mlx-community/whisper-large-v3-mlx',
    language='de'
)
print('Whisper Modell bereit!')
" 2>&1 || warn "Whisper Modell konnte nicht heruntergeladen werden. Wird beim ersten Start automatisch geladen."
fi

# --- Ollama (optional) ---
echo ""
read -p "$(echo -e "${YELLOW}Ollama installieren fuer lokale LLM Zusammenfassung? [y/N]${NC} ")" -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if ! command -v ollama &>/dev/null; then
        brew install ollama
    fi
    info "Ollama installiert. Starte mit: ollama serve"
    read -p "$(echo -e "${YELLOW}Llama 3.2:8b Modell herunterladen? [y/N]${NC} ")" -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        ollama pull llama3.2:8b
    fi
fi

echo ""
echo -e "${GREEN}${BOLD}╔══════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}║   Installation abgeschlossen!        ║${NC}"
echo -e "${GREEN}${BOLD}╚══════════════════════════════════════╝${NC}"
echo ""
echo -e "${BOLD}Naechste Schritte:${NC}"
echo ""
echo "  1. Konfiguration anpassen:"
echo "     nano ~/.minuta/config.toml"
echo ""
echo "  2. Backend starten:"
echo "     cd $PROJECT_DIR && make dev-backend"
echo ""
echo "  3. Frontend starten (neues Terminal):"
echo "     cd $PROJECT_DIR && make dev-frontend"
echo ""
echo "  4. Dashboard oeffnen:"
echo "     http://localhost:3000"
echo ""
echo -e "${YELLOW}Wichtig: macOS Berechtigungen${NC}"
echo "  - Mikrofon: System Settings > Privacy & Security > Microphone"
echo "  - Screen Recording: System Settings > Privacy & Security > Screen Recording"
echo "  (Wird beim ersten Start automatisch abgefragt)"
echo ""
