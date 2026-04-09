"""Audio manager: Unix socket server + audiocap subprocess management."""

from __future__ import annotations

import asyncio
import logging
import os
import struct
from pathlib import Path

from minuta.models.config import AppSettings

logger = logging.getLogger(__name__)

# Wire protocol message types
MSG_AUDIO_CHUNK = 0x01
MSG_CONTROL = 0x02
MSG_METADATA = 0x03
MSG_ERROR = 0x04
MSG_HEARTBEAT = 0xFF


class AudioManager:
    """Manages the audiocap subprocess and Unix socket communication."""

    def __init__(self, settings: AppSettings):
        self.settings = settings
        self.socket_path = settings.audio.socket_path
        self._process: asyncio.subprocess.Process | None = None
        self._server: asyncio.Server | None = None
        self._audio_callback = None
        self._running = False

    async def start(self, audio_callback=None) -> None:
        """Start the Unix socket server and the audiocap subprocess."""
        self._audio_callback = audio_callback
        self._running = True

        # Remove stale socket
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)

        # Start socket server
        self._server = await asyncio.start_unix_server(
            self._handle_client, path=self.socket_path
        )
        logger.info("Audio socket server listening on %s", self.socket_path)

        # Start audiocap via `open -a` so it runs as its own app with TCC permissions
        app_path = self._find_app()
        if app_path is None:
            logger.warning("Minuta.app not found - audio capture disabled")
            return

        extra_args = ["--socket", self.socket_path, "--sample-rate", str(self.settings.audio.sample_rate)]
        if not self.settings.audio.microphone:
            extra_args.append("--no-mic")
        if not self.settings.audio.system_audio:
            extra_args.append("--no-system")

        # Use `open -a` to launch as proper macOS app (gets own TCC permissions)
        self._process = await asyncio.create_subprocess_exec(
            "open", "-a", str(app_path), "--args", *extra_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        logger.info("audiocap launched via Minuta.app")

        # `open` returns immediately, so we wait a bit for audiocap to connect
        await asyncio.sleep(2)
        if not self._server:
            logger.warning("audiocap did not connect within timeout")

    async def stop(self) -> None:
        """Stop the audiocap subprocess and socket server."""
        self._running = False

        if self._process and self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._process.kill()
            logger.info("audiocap stopped")

        if self._server:
            self._server.close()
            await self._server.wait_closed()

        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle a connection from audiocap."""
        logger.info("audiocap connected via socket")
        try:
            while self._running:
                # Read frame: 4 bytes length + 1 byte type + payload
                header = await reader.readexactly(5)
                payload_len = struct.unpack(">I", header[:4])[0]
                msg_type = header[4]

                if payload_len > 0:
                    payload = await reader.readexactly(payload_len)
                else:
                    payload = b""

                if msg_type == MSG_AUDIO_CHUNK and self._audio_callback:
                    await self._audio_callback(payload)
                elif msg_type == MSG_METADATA:
                    import json
                    meta = json.loads(payload)
                    logger.debug("Audio metadata: %s", meta)
                elif msg_type == MSG_HEARTBEAT:
                    pass  # Keep-alive
                elif msg_type == MSG_ERROR:
                    import json
                    error = json.loads(payload)
                    logger.error("audiocap error: %s", error)

        except asyncio.IncompleteReadError:
            logger.info("audiocap disconnected")
        except Exception as e:
            logger.error("Socket handler error: %s", e)
        finally:
            writer.close()

    async def _read_audiocap_output(self) -> None:
        """Read and log audiocap stdout/stderr."""
        if not self._process or not self._process.stdout:
            return
        while True:
            line = await self._process.stdout.readline()
            if not line:
                break
            text = line.decode().rstrip()
            if text:
                logger.info("audiocap: %s", text)
        rc = await self._process.wait()
        if rc != 0:
            logger.error("audiocap exited with code %d", rc)

    def _find_app(self) -> Path | None:
        """Locate Minuta.app bundle."""
        project_root = Path(__file__).parent.parent.parent.parent.parent
        app_path = project_root / "Minuta.app"
        if app_path.exists():
            return app_path
        return None

    def _find_audiocap(self) -> Path | None:
        """Locate the audiocap binary."""
        project_root = Path(__file__).parent.parent.parent.parent.parent
        candidates = [
            project_root / "audiocap" / ".build" / "release" / "audiocap",
            project_root / "audiocap" / ".build" / "debug" / "audiocap",
            Path.home() / ".minuta" / "bin" / "audiocap",
        ]
        # Also check PATH
        import shutil
        path_bin = shutil.which("audiocap")
        if path_bin:
            candidates.insert(0, Path(path_bin))

        for p in candidates:
            if p.exists():
                return p
        return None
