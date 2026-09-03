# pgPlanAdvisor

[![CI](https://github.com/nam255199/pgPlanAdvisor/actions/workflows/ci.yml/badge.svg)](https://github.com/nam255199/pgPlanAdvisor/actions/workflows/ci.yml)

**pgPlanAdvisor** is a PostgreSQL `EXPLAIN` plan advisor for DBAs. Paste
the output of

```sql
EXPLAIN (ANALYZE, BUFFERS, VERBOSE, FORMAT JSON)
SELECT ...;
```

and get back a bottleneck summary, a DBA checklist, an expensive-node
table, a visual plan tree, and a set of findings with evidence and
concrete remediation steps (index suggestions, `work_mem` sizing, "this
is a correlated subquery, rewrite it as a JOIN", and more) - each backed
by an independently-testable rule. See [`ARCHITECTURE.md`](ARCHITECTURE.md)
for the full rule catalog and how the rule engine is put together.

Text `EXPLAIN` output is also accepted (best-effort parsing), but `FORMAT
JSON` is strongly recommended: it round-trips exactly, where text parsing
is necessarily an approximation.

## Features

- **Bottleneck detection** across access paths, cardinality estimates,
  memory spills, physical I/O, join strategy, and correlated subqueries -
  see the [rule catalog](ARCHITECTURE.md#rule-catalog).
- **Plan tree visualizer** with per-node timing, row estimates, buffers,
  and conditions, plus a **Flame/icicle view** showing proportionally
  where execution time actually goes.
- **Concrete `CREATE INDEX` suggestions** on access-path findings, not
  just prose - best-effort, always review before running.
- **Plan comparison**: paste a baseline and current plan and get a
  node-by-node diff plus findings that newly appeared or resolved.
- **`auto_explain` log ingestion**: paste a captured log excerpt and
  analyze every plan in it at once, worst-runtime-first.
- **Markdown report export** - paste into a ticket or runbook, with or
  without server-side history enabled.
- **Optional analysis history** (SQLite-backed): save, browse, and
  re-open past analyses, grouped by a query fingerprint with a
  runtime-trend sparkline.
- **CI regression gate**: a `pgplanadvisor` console script runs the rule
  engine against a plan file with no server needed, and can fail a build
  on severity or a runtime regression vs. a baseline.
- **Configurable rule thresholds** via environment variables - tune
  sensitivity without forking the analyzer.
- **Optional API key auth** and **rate limiting** for shared/hosted
  deployments.
- Versioned JSON API (`/api/v1`), request correlation IDs, structured
  logging.

## Quickstart: Docker Compose

```bash
git clone https://github.com/nam255199/pgPlanAdvisor.git
cd pgPlanAdvisor
docker compose up --build
```

- UI: <http://localhost:5173>
- API docs (Swagger UI): <http://localhost:8000/docs>
- Health check: `curl http://localhost:8000/health`

Running on a remote server over SSH:

```bash
ssh -L 5173:localhost:5173 -L 8000:localhost:8000 your_user@your_server
```

then open `http://localhost:5173` locally.

To enable saved history, set `PGPA_HISTORY_ENABLED=true` before starting
(see [Configuration](#configuration)):

```bash
PGPA_HISTORY_ENABLED=true docker compose up --build
```

## Quickstart: local development (no Docker)

```bash
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

## Configuration

Every setting is an environment variable, prefixed `PGPA_`, all optional
(see `backend/.env.example`). Service-level settings (`app/config.py`
`Settings`):

| Variable | Default | Purpose |
|---|---|---|
| `PGPA_LOG_LEVEL` | `INFO` | Log verbosity |
| `PGPA_LOG_JSON` | `false` | JSON-formatted logs (for log aggregators) instead of plain text |
| `PGPA_CORS_ORIGINS` | `["*"]` | Allowed CORS origins, as a JSON array |
| `PGPA_MAX_PLAN_BYTES` | `5000000` | Reject larger plan payloads with a 413 |
| `PGPA_MAX_BATCH_ENTRIES` | `200` | Cap on plans processed per `POST /api/v1/analyze/batch` request |
| `PGPA_API_KEY` | unset | If set, requires a matching `X-API-Key` header on `/api/v1/*` |
| `PGPA_RATE_LIMIT_ENABLED` | `true` | Enable the in-memory rate limiter |
| `PGPA_RATE_LIMIT_REQUESTS` / `PGPA_RATE_LIMIT_WINDOW_SECONDS` | `60` / `60` | N requests per window per client IP |
| `PGPA_HISTORY_ENABLED` | `false` | Enable SQLite-backed saved-analysis history |
| `PGPA_HISTORY_DB_PATH` | `./data/pgplanadvisor.db` | SQLite file location |
| `PGPA_HISTORY_MAX_ROWS` | `500` | Oldest rows are trimmed beyond this |

Rule thresholds (`app/config.py` `Thresholds`, also `PGPA_`-prefixed, e.g.
`PGPA_SEQ_SCAN_MIN_ROWS=5000`) - see the class docstring in
`backend/app/config.py` for the full list and defaults.

## API

All endpoints are under `/api/v1` except `/health`. Full interactive docs
at `/docs` (Swagger) or `/redoc` once the backend is running.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `POST` | `/api/v1/analyze` | Analyze a plan; `{"plan": ..., "query": "...", "save": false, "label": null}` |
| `POST` | `/api/v1/analyze/export` | Analyze and return a Markdown report directly |
| `POST` | `/api/v1/compare` | Compare a `baseline` and `current` plan (both shaped like `/analyze`'s body); returns a node-by-node diff |
| `POST` | `/api/v1/analyze/batch` | Analyze every plan found in a pasted `auto_explain` log excerpt; `{"log_text": "...", "save": false}` |
| `GET` | `/api/v1/history` | List saved analyses (404 if history is disabled); optional `?fingerprint=` filter |
| `GET` | `/api/v1/history/{id}` | Fetch one saved analysis |
| `DELETE` | `/api/v1/history/{id}` | Delete one saved analysis |
| `GET` | `/api/v1/history/{id}/export` | Saved analysis as a Markdown file |

`plan` accepts EXPLAIN JSON (object, or the `[{...}]` array psql/JSON
output produces), a JSON string, or text EXPLAIN output.

## CI regression gate

Installed as the `pgplanadvisor` console script, `app/cli.py` runs the
same rule engine directly against a plan file - no server required:

```bash
pip install -e ".[dev]"   # or just ".", the CLI has no extra deps
pgplanadvisor path/to/plan.json --fail-on-severity high
pgplanadvisor current.json --baseline previous.json --max-regression-pct 10
```

Exits non-zero if a finding at or above `--fail-on-severity` is present,
or (with `--baseline`) if total runtime regressed by more than
`--max-regression-pct`. Example GitHub Actions step:

```yaml
- name: Check plan quality
  run: |
    pip install -e ".[dev]"
    pgplanadvisor ci/queries/checkout.explain.json --fail-on-severity high
  working-directory: backend
```

## Testing

```bash
# Backend: 45 tests (parser, rules, engine, API, history, auth, rate limiting)
cd backend
pip install -e ".[dev]"
ruff check app tests   # lint
mypy app                # type-check
pytest --cov=app        # tests + coverage

# Frontend: 21 tests (format/sort helpers, settings, API error handling)
cd frontend
npm install
npm run lint
npm run test
npm run build
```

CI (`.github/workflows/ci.yml`) runs all of the above plus a Docker image
build for both services on every push/PR.

## Logging

Containers write structured logs to stdout (captured by Docker's `json-file`
driver, rotated at 20MB × 5 files) and additionally to `./logs/backend/` and
`./logs/frontend/` on the host via bind mounts. Every request gets a short
correlation ID, echoed as the `X-Request-ID` response header and attached
to that request's log lines - useful when someone reports "my analyze call
failed" and you need to find it in the logs.

```bash
docker compose logs -f              # all services
./scripts/logs.sh backend           # just backend
tail -f logs/backend/backend.log    # host-side log file
```

Containers use `restart: unless-stopped`, so they survive SSH disconnects
and restart after a host reboot unless explicitly stopped
(`docker compose down`).

## Architecture

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the request flow, the
pluggable rule engine design, the full rule catalog, and the reasoning
behind a few scope decisions (SQLite over Postgres for history, in-memory
over Redis for rate limiting).

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md), particularly "Adding a new
advisory rule" - the rule engine is designed so that's a small,
self-contained change.

## Roadmap

Shipped: pluggable rule engine, advisory rules (including `CREATE INDEX`
suggestions and plan-only-input awareness), configurable thresholds,
optional auth/rate limiting, optional saved history (with query
fingerprinting and trend view), Markdown export, plan comparison,
`auto_explain` log batch ingestion, a flame/icicle cost view, a CI
regression-gate CLI, versioned API, structured logging, CI, and a large
test suite.

Still open:

- `pg_stat_statements` integration (pull top queries from a live instance
  rather than only pasted EXPLAIN output)
- Index recommendation simulation (`HypoPG`-style hypothetical indexes)
- PDF export (Markdown export is available today)
- Kubernetes manifests
- Multi-instance-safe rate limiting (Redis-backed) for horizontally-scaled deployments
