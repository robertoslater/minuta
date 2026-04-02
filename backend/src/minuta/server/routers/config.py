"""Configuration endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from minuta.models.config import AppSettings
from minuta.server.deps import get_settings

router = APIRouter()


@router.get("/config")
async def get_config(settings: AppSettings = Depends(get_settings)):
    """Return current config with sensitive values redacted."""
    data = settings.model_dump()
    # Redact API keys
    if data["summarization"]["azure"]["api_key"]:
        data["summarization"]["azure"]["api_key"] = "***"
    if data["summarization"]["langdock"]["api_key"]:
        data["summarization"]["langdock"]["api_key"] = "***"
    if data["webhook"]["secret"]:
        data["webhook"]["secret"] = "***"
    return data


@router.get("/config/llm-providers")
async def list_llm_providers(settings: AppSettings = Depends(get_settings)):
    """List available LLM providers and their status."""
    providers = []

    # Ollama
    providers.append({
        "id": "ollama",
        "name": "Ollama (Lokal)",
        "model": settings.summarization.ollama.model,
        "configured": bool(settings.summarization.ollama.base_url),
        "is_default": settings.summarization.default_provider == "ollama",
    })

    # Azure
    providers.append({
        "id": "azure",
        "name": "Azure OpenAI",
        "model": settings.summarization.azure.deployment,
        "configured": bool(settings.summarization.azure.endpoint and settings.summarization.azure.api_key),
        "is_default": settings.summarization.default_provider == "azure",
    })

    # Langdock
    providers.append({
        "id": "langdock",
        "name": "Langdock",
        "model": settings.summarization.langdock.model,
        "configured": bool(settings.summarization.langdock.base_url and settings.summarization.langdock.api_key),
        "is_default": settings.summarization.default_provider == "langdock",
    })

    return providers
