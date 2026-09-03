# Changelog

## Unreleased

### Added

- **Concrete `CREATE INDEX` suggestions**: `seq_scan_expensive` and
  `ineffective_index_scan` now extract likely column names out of the
  node's `Filter`/`Index Cond` (best-effort, unverified - always review
  before running) and attach a `ddl_suggestion` to the finding, rendered
  as a copyable SQL block in the UI and in Markdown exports.
- **Plan-only (no `ANALYZE`) awareness**: a new `plan_only_no_analyze`
  finding fires when a pasted plan has no actual execution stats, so a
  quiet report doesn't get mistaken for a clean bill of health.
- **Query fingerprinting**: saved analyses are grouped by a normalized
  hash of the query text (literals stripped), so repeated runs of "the
  same" query can be found via `GET /api/v1/history?fingerprint=...` and
  the History panel now shows a runtime-trend sparkline per query.
- **Plan comparison**: `POST /api/v1/compare` analyzes a baseline and a
  current plan and returns a structural, node-by-node diff (time/row
  deltas, matched/added/removed nodes) plus findings that newly appeared
  or resolved between the two - with a "Compare" tab in the UI.
- **`auto_explain` log ingestion**: `POST /api/v1/analyze/batch` splits a
  pasted `auto_explain` log excerpt into its individual `duration: ... ms
  plan:` entries and analyzes all of them at once - a "Batch Log" tab in
  the UI, worst-runtime-first.
- **Flame/icicle cost-time view**: a new "Flame" tab renders the plan as
  a proportional, click-to-inspect icicle chart (hand-rolled SVG/CSS, no
  new dependency) instead of only a linear tree/table.
- **CI regression gate**: a `pgplanadvisor` console script (`app/cli.py`)
  runs the same rule engine against a plan file with no server required,
  exits non-zero on a severity threshold or a runtime regression versus
  a `--baseline` plan - for use as a CI check.
- Backend tests for all of the above (`test_sql_conditions.py`,
  `test_fingerprint.py`, `test_compare.py`, `test_ingest.py`,
  `test_cli.py`, plus additions to `test_rules.py`, `test_api.py`,
  `test_history.py`).

### Fixed

- `parse_text_explain` used to default a missing `Execution Time:`/`Planning
  Time:` line to `0.0` instead of leaving it absent, which made
  `plan_only_no_analyze` (above) unable to ever fire for text-format
  `EXPLAIN` input without `ANALYZE` - it always looked like it had actual
  stats. Now `None` when the line isn't present, matching how
  `Query Identifier` already behaved.
- `compare_plans`' runtime-delta percentage is mathematically undefined
  when the baseline's runtime is `0` (e.g. a plan-only baseline); this
  used to fall through to `verdict="unchanged"`, silently hiding a real
  regression from both the API and the CLI's `--baseline` gate. Now
  treated as `"regressed"` whenever the current plan has a measurable
  runtime.
- `POST /api/v1/analyze/batch` now caps the number of plan entries
  processed per request (`PGPA_MAX_BATCH_ENTRIES`, default 200) instead
  of running the full rule engine over an unbounded number of log
  entries in one synchronous request.

## 2.0.0

A professionalization pass over the original v1 project: same purpose and
stack (FastAPI + React/Vite), substantially reworked internals.

### Added

- Pluggable rule engine (`app/analyzer/registry.py`): rules are
  independently-registered, independently-testable functions instead of
  one monolithic `analyze_rules()`. See `ARCHITECTURE.md`.
- Six new advisory rules: `ineffective_index_scan`, `missing_parallelism`,
  `buffer_cache_hit_ratio` (whole-plan), `nested_loop_row_explosion`,
  `correlated_subquery_repeated`, plus concrete `work_mem` sizing
  suggestions on the existing sort/hash spill rules.
- Configurable thresholds for every rule (`PGPA_*` env vars via
  `app/config.py`), instead of hardcoded literals.
- Optional API key auth (`PGPA_API_KEY`), off by default.
- In-memory rate limiting, on by default (`PGPA_RATE_LIMIT_*`).
- Optional SQLite-backed analysis history (`PGPA_HISTORY_ENABLED`):
  save/list/get/delete past analyses, export any of them as Markdown.
- Request correlation IDs (`X-Request-ID`) and structured logging.
- Versioned API (`/api/v1/...`); `/health` stays unversioned.
- Markdown report export, both ad-hoc (`POST /api/v1/analyze/export`) and
  from saved history.
- 45 backend tests (parser, rules - unit and end-to-end, engine, API,
  history, security, rate limiting) and 21 frontend tests (format/sort
  helpers, settings persistence, API error handling), up from 1.
- CI (GitHub Actions): ruff, mypy, pytest+coverage, ESLint, Vitest, Vite
  build, Docker image builds.
- History panel, Settings (API key) panel, and a Markdown export button in
  the frontend.

### Fixed

- The text-`EXPLAIN` parser's `Buffers:` line parsing only matched
  `"shared read="` as a literal substring, which real Postgres output
  rarely contains - Postgres writes the qualifier once
  (`shared hit=500 read=12000`), so `Shared Read Blocks` (and other
  second-and-later metrics in a group) silently came back as 0. Rewritten
  as a qualifier-aware token parser.
- `parse_plan` now raises a clear, typed `PlanParseError` (surfaced as an
  HTTP 400 with a helpful message) instead of silently returning a
  near-empty synthetic plan for unparseable input.

### Changed

- `requirements.txt` versions are now mirrored by `pyproject.toml` as the
  source of truth for the package + dev tooling.
- Findings now carry a stable `rule_id` and sort by severity rank first,
  then score (previously score-only).
