"""macOS System Tray application using rumps."""

from __future__ import annotations

import subprocess
import threading
import webbrowser

import httpx
import rumps


BACKEND_URL = "http://127.0.0.1:8741"


class MinutaTray(rumps.App):
    """System tray app for controlling Minuta."""

    def __init__(self):
        super().__init__(
            name="Minuta",
            title="MS",
            icon=None,  # Uses title text as icon
            menu=[
                rumps.MenuItem("Aufnahme starten", callback=self.toggle_recording),
                None,  # Separator
                rumps.MenuItem("Dashboard oeffnen", callback=self.open_dashboard),
                rumps.MenuItem("Status", callback=self.show_status),
                None,
                rumps.MenuItem("Beenden", callback=self.quit_app),
            ],
        )
        self._recording = False
        self._meeting_id = None

    @rumps.clicked("Aufnahme starten")
    def toggle_recording(self, sender):
        if self._recording:
            self._stop_recording(sender)
        else:
            self._start_recording(sender)

    def _start_recording(self, sender):
        try:
            r = httpx.post(
                f"{BACKEND_URL}/api/meetings",
                json={"title": "", "audio_source": "mic+system"},
                timeout=10,
            )
            r.raise_for_status()
            data = r.json()
            self._meeting_id = data["id"]
            self._recording = True
            sender.title = "Aufnahme stoppen"
            self.title = "REC"
            rumps.notification(
                title="Minuta",
                subtitle="Aufnahme gestartet",
                message="Audio wird aufgezeichnet und transkribiert.",
            )
        except Exception as e:
            rumps.notification(
                title="Minuta",
                subtitle="Fehler",
                message=f"Aufnahme konnte nicht gestartet werden: {e}",
            )

    def _stop_recording(self, sender):
        if not self._meeting_id:
            return
        try:
            r = httpx.post(
                f"{BACKEND_URL}/api/meetings/{self._meeting_id}/stop",
                timeout=10,
            )
            r.raise_for_status()
            self._recording = False
            self._meeting_id = None
            sender.title = "Aufnahme starten"
            self.title = "MS"
            rumps.notification(
                title="Minuta",
                subtitle="Aufnahme gestoppt",
                message="Zusammenfassung wird erstellt...",
            )
        except Exception as e:
            rumps.notification(
                title="Minuta",
                subtitle="Fehler",
                message=f"Aufnahme konnte nicht gestoppt werden: {e}",
            )

    @rumps.clicked("Dashboard oeffnen")
    def open_dashboard(self, _):
        webbrowser.open("http://localhost:3000")

    @rumps.clicked("Status")
    def show_status(self, _):
        try:
            r = httpx.get(f"{BACKEND_URL}/api/health", timeout=3)
            data = r.json()
            rumps.notification(
                title="Minuta Status",
                subtitle=f"Status: {data['status']}",
                message=f"Uptime: {data['uptime_seconds']}s | Model: {data['transcription_model']}",
            )
        except Exception:
            rumps.notification(
                title="Minuta",
                subtitle="Backend nicht erreichbar",
                message="Starte den Backend-Server mit 'minuta start'",
            )

    @rumps.clicked("Beenden")
    def quit_app(self, _):
        if self._recording:
            self._stop_recording(rumps.MenuItem(""))
        rumps.quit_application()


def run_tray():
    """Entry point for the tray application."""
    MinutaTray().run()
