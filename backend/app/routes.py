"""HTTP routes.

Versioned under ``/api/v1`` so the JSON contract can evolve without
breaking existing integrations pinned to v1. ``/health`` stays unversioned
at the root, which is the common convention for infra health checks
(load balancers, container orchestrators) that shouldn't need to know
about API versioning.
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Response

from app.analyzer.engine import analyze
from app.analyzer.parser import PlanParseError
from app.analyzer.report import to_markdown
from app.config import Settings, Thresholds, get_settings, get_thresholds
from app.db import get_history_store
from app.models import AnalyzeRequest, AnalyzeResponse, HistoryListResponse
from app.security import require_api_key

logger = logging.getLogger("pgplanadvisor.api")

health_router = APIRouter(tags=["health"])
router = APIRouter(prefix="/api/v1", tags=["v1"], dependencies=[Depends(require_api_key)])


@health_router.get("/health")
def health(settings: Settings = Depends(get_settings)):
    return {"status": "ok", "app": settings.app_name, "version": settings.app_version}


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze_endpoint(
    req: AnalyzeRequest,
    settings: Settings = Depends(get_settings),
    thresholds: Thresholds = Depends(get_thresholds),
):
    approx_size = len(json.dumps(req.plan, default=str))
    if approx_size > settings.max_plan_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Plan payload too large ({approx_size} bytes, limit {settings.max_plan_bytes}).",
        )

    try:
        result = analyze(req.plan, req.query, thresholds=thresholds)
    except PlanParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - surface as a clean 400 instead of a stack trace
        logger.exception("Unexpected error analyzing plan")
        raise HTTPException(status_code=400, detail=f"Could not analyze this plan: {exc}") from exc

    result.label = req.label

    store = get_history_store(settings)
    if req.save:
        if store is None:
            raise HTTPException(
                status_code=400,
                detail="History persistence is disabled on this server (PGPA_HISTORY_ENABLED=false).",
            )
        result.saved = True
        store.save(result)

    return result


@router.post("/analyze/export")
def analyze_and_export(
    req: AnalyzeRequest,
    settings: Settings = Depends(get_settings),
    thresholds: Thresholds = Depends(get_thresholds),
):
    """Analyze and return a Markdown report directly, without requiring
    history persistence to be enabled. Handy for CI jobs or scripts that
    just want a report artifact."""
    try:
        result = analyze(req.plan, req.query, thresholds=thresholds)
    except PlanParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    result.label = req.label
    markdown = to_markdown(result)
    return Response(content=markdown, media_type="text/markdown")


@router.get("/history", response_model=HistoryListResponse)
def list_history(limit: int = 50, offset: int = 0, settings: Settings = Depends(get_settings)):
    store = get_history_store(settings)
    if store is None:
        raise HTTPException(status_code=404, detail="History persistence is disabled on this server.")
    limit = max(1, min(limit, 200))
    items, total = store.list(limit=limit, offset=offset)
    return HistoryListResponse(items=items, total=total)


@router.get("/history/{analysis_id}", response_model=AnalyzeResponse)
def get_history_item(analysis_id: str, settings: Settings = Depends(get_settings)):
    store = get_history_store(settings)
    if store is None:
        raise HTTPException(status_code=404, detail="History persistence is disabled on this server.")
    result = store.get(analysis_id)
    if result is None:
        raise HTTPException(status_code=404, detail="No saved analysis with that id.")
    return result


@router.delete("/history/{analysis_id}", status_code=204)
def delete_history_item(analysis_id: str, settings: Settings = Depends(get_settings)):
    store = get_history_store(settings)
    if store is None:
        raise HTTPException(status_code=404, detail="History persistence is disabled on this server.")
    if not store.delete(analysis_id):
        raise HTTPException(status_code=404, detail="No saved analysis with that id.")
    return Response(status_code=204)


@router.get("/history/{analysis_id}/export")
def export_history_item(analysis_id: str, settings: Settings = Depends(get_settings)):
    store = get_history_store(settings)
    if store is None:
        raise HTTPException(status_code=404, detail="History persistence is disabled on this server.")
    result = store.get(analysis_id)
    if result is None:
        raise HTTPException(status_code=404, detail="No saved analysis with that id.")
    markdown = to_markdown(result)
    return Response(
        content=markdown,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="pgplanadvisor-{analysis_id}.md"'},
    )
