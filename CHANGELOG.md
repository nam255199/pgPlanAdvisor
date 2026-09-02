# Changelog

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
