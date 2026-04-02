---
name: minuta
description: Minuta - Meeting Transkription & Zusammenfassung Tool für macOS. Verwende diesen Skill für alle Änderungen am minuta Projekt.
triggers:
  - Minuta
  - minuta
  - Meeting Transkription
  - Meeting Notes
  - audiocap
---

# Minuta (minuta)

Meeting-Transkriptions- und Zusammenfassungstool für macOS Apple Silicon.
Repo: https://github.com/robertoslater/minuta

## Architektur

```
┌─────────────────┐    Unix Socket      ┌─────────────────────────┐
│  audiocap        │ ──────────────────> │  Python Backend         │
│  (Swift CLI)     │   PCM Audio 48kHz   │  (FastAPI :8741)        │
│  via .app Bundle │                     │  Resample → 16kHz       │
│                  │                     │  RMS VAD → MLX Whisper  │
│  - ScreenCapture │                     │  → SQLite → WebSocket   │
│    Kit (System)  │                     │  → LLM Summary (Azure)  │
│  - AVAudioEngine │                     │  → Webhook (N8N)        │
│    (Mikrofon)    │                     └────────────┬────────────┘
└─────────────────┘                                   │
                        ┌─────────────────────────────┘
                        │
┌───────────────────────▼──────────────────────┐
│  Next.js Frontend (:3100)                     │
│  Moro Vision Green Theme (insights.track)    │
│  shadcn/ui + Tailwind CSS v4 + Lucide        │
│  Live Transcript (WebSocket)                 │
│  Meeting Archiv + Summary Edit               │
│  Webhook Button → N8N → Notion + Neo4J       │
└──────────────────────────────────────────────┘
```

## Tech Stack

| Komponente | Technologie |
|---|---|
| Audio Capture | Swift CLI (ScreenCaptureKit + AVAudioEngine) in Minuta.app Bundle |
| IPC | Unix Domain Socket (POSIX), length-prefixed binary frames |
| Backend | Python FastAPI, uvicorn, aiosqlite |
| Transkription | MLX Whisper (mlx-community/whisper-large-v3-mlx) lokal auf Neural Engine |
| VAD | RMS-basiert (Silero VAD hatte Kompatibilitätsprobleme mit resampeltem Audio) |
| LLM Summary | Azure OpenAI (gpt-4o), konfigurierbar für Ollama/Langdock |
| Frontend | Next.js 16, Tailwind CSS v4, shadcn/ui (new-york), Lucide React |
| Design | Moro Vision Green Theme (identisch mit insights.track) |
| DB | SQLite (WAL mode) unter ~/.minuta/minuta.db |
| Webhook | N8N (Sally.io-kompatibles Format, Basic Auth, HMAC-SHA256) |

## Projektstruktur

```
minuta/
├── Minuta.app/        # macOS App Bundle (für TCC Permissions)
├── audiocap/                 # Swift CLI
│   ├── Package.swift
│   └── Sources/audiocap/
│       ├── AudioCap.swift          # Entry point (@main)
│       ├── AudioCapture.swift      # ScreenCaptureKit + AVAudioEngine
│       ├── SocketClient.swift      # POSIX Unix Socket
│       ├── Protocol.swift          # Wire protocol frames
│       └── Permissions.swift       # macOS permission helpers
├── backend/                  # Python FastAPI
│   ├── pyproject.toml
│   └── src/minuta/
│       ├── cli.py
│       ├── server/app.py           # FastAPI factory + lifespan
│       ├── server/routers/         # meetings, transcripts, summaries, config, ws, health
│       ├── services/
│       │   ├── audio_manager.py    # Socket server + audiocap subprocess
│       │   ├── meeting_manager.py  # Orchestration (start/stop/post-processing)
│       │   ├── transcriber.py      # RMS VAD + MLX Whisper pipeline
│       │   ├── summarizer.py       # LLM abstraction (Ollama/Azure/Langdock)
│       │   ├── webhook.py          # N8N webhook (Sally.io format)
│       │   └── transcript_hub.py   # WebSocket broadcast
│       ├── models/config.py        # Pydantic settings + TOML
│       ├── models/meeting.py       # Meeting, Transcript, Summary models
│       └── db/                     # SQLite engine + repository
├── frontend/                 # Next.js 16
│   ├── src/app/(dashboard)/        # Pages: /, /record, /meetings, /settings
│   ├── src/components/layout/      # AppSidebar, Topbar
│   ├── src/lib/api.ts              # REST + WebSocket client
│   └── src/lib/store.ts            # Zustand state
├── config.example.toml       # Konfigurationsvorlage
├── Makefile                  # Dev commands
└── install.sh                # Setup script
```

## Konfiguration

Datei: `~/.minuta/config.toml`

Wichtige Einstellungen:
- `summarization.default_provider`: "azure" | "ollama" | "langdock"
- `summarization.azure.endpoint/api_key/deployment`: Azure OpenAI Credentials
- `webhook.url`: N8N Webhook URL
- `webhook.basic_auth_user/password`: N8N Basic Auth
- `speaker.user_name`: Label für eigene Stimme (Default: "Ich")

## Ports

- Backend: `localhost:8741`
- Frontend: `localhost:3100` (Port 3000 ist von OpenWebUI belegt)
- Health Check: `GET localhost:8741/api/health`

## macOS Berechtigungen

Minuta.app braucht:
- **Mikrofon** (System Settings > Datenschutz > Mikrofon)
- **Screen Recording / Systemaudio** (System Settings > Datenschutz > Aufnahme von Bildschirm & Systemaudio)

Die App muss einmal manuell gestartet werden damit macOS den Permission-Dialog zeigt:
```bash
open -a Minuta.app --args --no-system --socket /dev/null
```

## Webhook Format (Sally.io-kompatibel)

Der Webhook sendet im Sally.io-Format für Kompatibilität mit dem bestehenden N8N Workflow:
```json
{
  "recordingSummaryId": "meeting-id",
  "appointmentSubject": "Meeting Titel",
  "appointmentDate": "ISO datetime",
  "meetingPlatform": "Minuta",
  "transcriptionTool": "Minuta",
  "company": "Firmenname",
  "project": "Projektname",
  "domain": "example.com",
  "summary": "**Hauptpunkte**\n- Punkt 1\n...",
  "topics": [...],
  "decisions": [...],
  "tasks": [...]
}
```

## Bekannte Einschränkungen

- Audio Resampling: 48kHz → 16kHz via einfaches Index-Resampling (nicht ideal, aber funktional)
- VAD: RMS-basiert statt Silero VAD (Silero hatte Dimension-Fehler mit resampeltem Audio)
- System Audio: Nur mit Screen Recording Berechtigung, fällt graceful auf Mic-only zurück
- Minuta.app muss bei audiocap-Updates neu kopiert werden (`swift build && cp`)

## Dev Commands

```bash
make dev-backend      # Backend mit auto-reload
make dev-frontend     # Frontend auf :3100
make build-audiocap   # Swift binary kompilieren
make install          # Alles installieren
```

## Change History

### v0.1.0 (2026-04-02) - Initial Release
- Swift audiocap CLI mit ScreenCaptureKit + AVAudioEngine
- Python FastAPI Backend mit MLX Whisper Transkription
- Next.js 16 Dashboard im Moro Vision Design
- Live-Transkript via WebSocket
- Azure OpenAI gpt-4o Zusammenfassung
- N8N Webhook Integration (Sally.io-kompatibles Format)
- Meeting-Titel und Zusammenfassung editierbar
- Meta-Felder: Unternehmen, Projekt, Domain
- Minuta.app Bundle für macOS TCC Permissions
- Sidebar Logo wie insights.track
