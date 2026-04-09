"""License management for Minuta Pro features.

Free features: Local transcription, AI summary (own API key), dashboard, editing
Pro features: Webhook/N8N, Notion export, Auto-summary, CSV/PDF export

License keys are validated via LemonSqueezy API or offline via signed token.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# Pro features that require a license
PRO_FEATURES = {
    "webhook",
    "export_csv",
    "export_pdf",
    "auto_summary",
    "notion_export",
    "lightrag_export",
}

LEMONSQUEEZY_API = "https://api.lemonsqueezy.com/v1"
LICENSE_CACHE_FILE = Path.home() / ".minuta" / "license.json"


class LicenseManager:
    """Manages Pro license validation and caching."""

    def __init__(self):
        self._license_key: str | None = None
        self._is_pro: bool = False
        self._license_data: dict = {}
        self._last_check: float = 0
        self._check_interval = 86400  # Re-validate every 24h
        self._load_cache()

    @property
    def is_pro(self) -> bool:
        return self._is_pro

    @property
    def license_key(self) -> str | None:
        return self._license_key

    @property
    def plan_name(self) -> str:
        return "Pro" if self._is_pro else "Free"

    def feature_allowed(self, feature: str) -> bool:
        """Check if a feature is allowed under the current license."""
        if feature not in PRO_FEATURES:
            return True  # Free feature
        return self._is_pro

    async def activate(self, license_key: str) -> dict:
        """Activate a license key via LemonSqueezy API.

        Returns dict with status and message.
        """
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    f"{LEMONSQUEEZY_API}/licenses/activate",
                    json={
                        "license_key": license_key,
                        "instance_name": _machine_id(),
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get("activated") or data.get("license_key", {}).get("status") == "active":
                        self._license_key = license_key
                        self._is_pro = True
                        self._license_data = data
                        self._last_check = time.time()
                        self._save_cache()
                        logger.info("License activated: Pro")
                        return {"status": "activated", "plan": "Pro"}

                # Activation failed
                return {"status": "invalid", "message": "Ungültiger License Key"}

        except httpx.RequestError as e:
            # Offline? Check if we have a cached valid license
            if self._license_key == license_key and self._is_pro:
                return {"status": "activated", "plan": "Pro", "offline": True}
            return {"status": "error", "message": f"Verbindungsfehler: {e}"}

    async def deactivate(self) -> dict:
        """Deactivate the current license."""
        if self._license_key:
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    await client.post(
                        f"{LEMONSQUEEZY_API}/licenses/deactivate",
                        json={
                            "license_key": self._license_key,
                            "instance_id": _machine_id(),
                        },
                    )
            except httpx.RequestError:
                pass

        self._license_key = None
        self._is_pro = False
        self._license_data = {}
        self._save_cache()
        logger.info("License deactivated")
        return {"status": "deactivated"}

    async def validate(self) -> bool:
        """Re-validate the current license (called periodically)."""
        if not self._license_key:
            return False

        # Skip if recently validated
        if time.time() - self._last_check < self._check_interval:
            return self._is_pro

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    f"{LEMONSQUEEZY_API}/licenses/validate",
                    json={"license_key": self._license_key},
                )
                if response.status_code == 200:
                    data = response.json()
                    valid = data.get("valid", False)
                    self._is_pro = valid
                    self._last_check = time.time()
                    self._save_cache()
                    return valid
        except httpx.RequestError:
            # Offline — trust cached state for grace period (7 days)
            grace = 7 * 86400
            if time.time() - self._last_check < grace:
                return self._is_pro

        self._is_pro = False
        self._save_cache()
        return False

    def get_status(self) -> dict:
        """Return current license status for the API."""
        return {
            "plan": self.plan_name,
            "is_pro": self._is_pro,
            "license_key": _mask_key(self._license_key) if self._license_key else None,
            "pro_features": sorted(PRO_FEATURES),
        }

    def _save_cache(self) -> None:
        """Persist license state to disk."""
        try:
            LICENSE_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "license_key": self._license_key,
                "is_pro": self._is_pro,
                "last_check": self._last_check,
                "checksum": _checksum(self._license_key, self._is_pro),
            }
            LICENSE_CACHE_FILE.write_text(json.dumps(data))
            LICENSE_CACHE_FILE.chmod(0o600)
        except Exception as e:
            logger.warning("Failed to save license cache: %s", e)

    def _load_cache(self) -> None:
        """Load cached license state from disk."""
        try:
            if not LICENSE_CACHE_FILE.exists():
                return
            data = json.loads(LICENSE_CACHE_FILE.read_text())
            # Verify checksum to prevent tampering
            expected = _checksum(data.get("license_key"), data.get("is_pro"))
            if data.get("checksum") != expected:
                logger.warning("License cache checksum mismatch — ignoring")
                return
            self._license_key = data.get("license_key")
            self._is_pro = data.get("is_pro", False)
            self._last_check = data.get("last_check", 0)
            if self._is_pro:
                logger.info("License loaded from cache: Pro")
        except Exception as e:
            logger.warning("Failed to load license cache: %s", e)


def _machine_id() -> str:
    """Generate a stable machine identifier."""
    import platform
    raw = f"{platform.node()}-{platform.machine()}-minuta"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _mask_key(key: str | None) -> str:
    """Mask a license key for display: show first 8 and last 4 chars."""
    if not key or len(key) < 16:
        return "***"
    return f"{key[:8]}...{key[-4:]}"


def _checksum(license_key: str | None, is_pro: bool) -> str:
    """Machine-bound integrity check — cache only valid on same machine."""
    secret = f"minuta-{_machine_id()}"
    data = f"{license_key or ''}:{is_pro}"
    return hmac.new(secret.encode(), data.encode(), hashlib.sha256).hexdigest()[:16]


# Singleton
_license_manager: LicenseManager | None = None


def get_license_manager() -> LicenseManager:
    global _license_manager
    if _license_manager is None:
        _license_manager = LicenseManager()
    return _license_manager
