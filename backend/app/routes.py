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

from app.analyzer.compare import compare_plans
from app.analyzer.engine import analyze
from app.analyzer.ingest import extract_plans_from_log
from app.analyzer.parser import PlanParseError
from app.analyzer.report import to_markdown
from app.config import Settings, Thresholds, get_settings, get_thresholds
from app.db import get_history_store
from app.models import (
    AnalyzeRequest,
    AnalyzeResponse,
    BatchAnalyzeRequest,
    BatchAnalyzeResponse,
    CompareRequest,
    CompareResponse,
    HistoryListResponse,
)
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


@router.post("/compare", response_model=CompareResponse)
def compare_endpoint(
    req: CompareRequest,
    settings: Settings = Depends(get_settings),
    thresholds: Thresholds = Depends(get_thresholds),
):
    """Analyze two plans (e.g. before/after an index change) and return a
    structural diff: per-node time/row deltas plus findings that newly
    appeared or disappeared between the two runs."""
    for label, req_side in (("baseline", req.baseline), ("current", req.current)):
        approx_size = len(json.dumps(req_side.plan, default=str))
        if approx_size > settings.max_plan_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"{label} plan payload too large ({approx_size} bytes, limit {settings.max_plan_bytes}).",
            )

    try:
        baseline_result = analyze(req.baseline.plan, req.baseline.query, thresholds=thresholds)
        current_result = analyze(req.current.plan, req.current.query, thresholds=thresholds)
    except PlanParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    baseline_result.label = req.baseline.label
    current_result.label = req.current.label
    return compare_plans(baseline_result, current_result, thresholds)


@router.post("/analyze/batch", response_model=BatchAnalyzeResponse)
def analyze_batch(
    req: BatchAnalyzeRequest,
    settings: Settings = Depends(get_settings),
    thresholds: Thresholds = Depends(get_thresholds),
):
    """Analyze every plan found in a pasted auto_explain log excerpt at
    once, so captured slow-query logs don't have to be split by hand."""
    approx_size = len(req.log_text.encode("utf-8"))
    if approx_size > settings.max_plan_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Log payload too large ({approx_size} bytes, limit {settings.max_plan_bytes}).",
        )

    entries = extract_plans_from_log(req.log_text)
    if len(entries) > settings.max_batch_entries:
        raise HTTPException(
            status_code=413,
            detail=f"Log contains {len(entries)} plan entries, limit is {settings.max_batch_entries}. "
            "Split the log and submit it in smaller batches.",
        )

    store = get_history_store(settings) if req.save else None
    if req.save and store is None:
        raise HTTPException(
            status_code=400,
            detail="History persistence is disabled on this server (PGPA_HISTORY_ENABLED=false).",
        )

    results: list[AnalyzeResponse] = []
    parse_errors: list[str] = []
    for entry in entries:
        try:
            result = analyze(entry.raw_text, None, thresholds=thresholds)
        except PlanParseError as exc:
            parse_errors.append(f"line {entry.line_number}: {exc}")
            continue
        except Exception as exc:  # noqa: BLE001 - one bad entry shouldn't fail the batch
            logger.exception("Unexpected error analyzing batch entry at line %s", entry.line_number)
            parse_errors.append(f"line {entry.line_number}: {exc}")
            continue

        if store is not None:
            result.saved = True
            store.save(result)
        results.append(result)

    results.sort(key=lambda r: r.total_runtime_ms, reverse=True)
    return BatchAnalyzeResponse(entries_found=len(entries), results=results, parse_errors=parse_errors)


@router.get("/history", response_model=HistoryListResponse)
def list_history(
    limit: int = 50, offset: int = 0, fingerprint: str | None = None, settings: Settings = Depends(get_settings)
):
    store = get_history_store(settings)
    if store is None:
        raise HTTPException(status_code=404, detail="History persistence is disabled on this server.")
    limit = max(1, min(limit, 200))
    items, total = store.list(limit=limit, offset=offset, fingerprint=fingerprint)
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
