
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.models import AnalyzeRequest, AnalyzeResponse
from app.analyzer.engine import analyze

app = FastAPI(
    title="pgPlanAdvisor",
    description="PostgreSQL EXPLAIN ANALYZE advisor with bottleneck detection and plan tree visualization.",
    version="0.2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "app": "pgPlanAdvisor"}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze_endpoint(req: AnalyzeRequest):
    try:
        return analyze(req.plan, req.query)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
