"""Shared Haiku client for lightweight classification tasks.

Both InterventionClassifier and IntentRouter use Claude Haiku for
sub-200ms classification calls. This module provides a single shared
AsyncAnthropic client to avoid duplicate connection pools.
"""
from __future__ import annotations

from typing import Optional

from anthropic import AsyncAnthropic

from ...config.settings import settings

_haiku_client: Optional[AsyncAnthropic] = None


def get_haiku_client() -> AsyncAnthropic:
    """Get or lazily create the shared AsyncAnthropic client for Haiku calls."""
    global _haiku_client
    if _haiku_client is None:
        client_kwargs = {"api_key": settings.anthropic_api_key}
        if settings.anthropic_base_url:
            client_kwargs["base_url"] = settings.anthropic_base_url
        _haiku_client = AsyncAnthropic(**client_kwargs)
    return _haiku_client
