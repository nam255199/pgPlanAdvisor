"""Optional API key authentication.

Off by default (matches the original project, which had none) so a quick
local `docker compose up` still just works. Setting ``PGPA_API_KEY``
requires every request to send a matching ``X-API-Key`` header, which is
enough for a small team running this behind a reverse proxy without
standing up a full auth system.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status

from app.config import Settings, get_settings


def require_api_key(request: Request, settings: Settings = Depends(get_settings)) -> None:
    if not settings.api_key:
        return  # auth disabled

    provided = request.headers.get("X-API-Key")
    if provided != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid X-API-Key header.",
        )
