# Architecture

pgPlanAdvisor is a small, focused service: parse a PostgreSQL `EXPLAIN`
plan, run it through a set of advisory rules, and return findings plus a
visualizable plan tree. This document describes how the pieces fit
together and why they're shaped the way they are.

## Request flow

```
EXPLAIN output (JSON or text)
        │
        ▼
  app/analyzer/parser.py    - normalizes into {"Plan": {...}, "Execution Time": ..., ...}
        │
        ▼
  app/analyzer/walker.py    - flattens the plan tree into PlanNode records (path, parent, depth)
        │
        ▼
  app/analyzer/engine.py    - for each node, builds a RuleContext and runs every registered rule;
        │                     also runs whole-plan (aggregate) rules once
        ▼
  app/analyzer/registry.py  - the rule registry: node_rule / plan_rule decorators, run_node_rules /
        │                     run_plan_rules. Rules live in app/analyzer/rules/*.py
        ▼
  app/models.AnalyzeResponse - findings, node summaries (for the tree/table UI), recommendations,
                                a DBA checklist, and the normalized plan JSON
```

`app/routes.py` exposes this as `POST /api/v1/analyze`, wraps parse errors
as clean 400s, and optionally persists the result (`app/db.py`) or renders
it as Markdown (`app/analyzer/report.py`).

## The rule engine

The advisory logic is not one large function - it's a set of small,
independent, unit-testable rules registered with a decorator:

```python
# app/analyzer/rules/access_path.py
@node_rule
def seq_scan_expensive(ctx: RuleContext) -> Finding | None:
    ...
```

Two kinds of rules:

- **Node rules** (`@node_rule`) run once per plan node and see that node,
  its ancestors, and the whole-plan runtime. Most checks are node rules:
  "this Seq Scan looks expensive", "this Sort spilled to disk".
- **Plan rules** (`@plan_rule`) run once for the whole plan and see every
  node at once. Used for checks that only make sense in aggregate, like
  buffer cache hit ratio (a single node's read count is noisy; the sum
  across the whole plan is a much more reliable signal).

Why this shape:

- **Adding a check never touches existing code.** Write a new function in
  `app/analyzer/rules/`, decorate it, import the module from
  `app/analyzer/rules/__init__.py`. `engine.py` iterates whatever's
  registered - it has no knowledge of individual rules.
- **Every rule is a pure function of its input**, so it's testable in
  isolation without spinning up the parser or the API:

  ```python
  def test_seq_scan_expensive_fires_for_large_scan():
      finding = seq_scan_expensive(make_ctx({"Node Type": "Seq Scan", ...}))
      assert finding.rule_id == "seq_scan_expensive"
  ```

  See `tests/test_rule_units.py` for more, and `tests/test_rules.py` for
  end-to-end (parse → analyze) tests against realistic fixture plans in
  `tests/fixtures/`.
- **One bad rule can't take down analysis.** `registry.run_node_rules` /
  `run_plan_rules` catch and log exceptions per-rule rather than letting
  one bug 500 the whole `/analyze` call.
- **Thresholds are configuration, not magic numbers.** Every numeric
  threshold (e.g. "how many rows removed by a filter counts as
  'expensive'") lives in `app/config.py`'s `Thresholds` class and is
  overridable via `PGPA_*` environment variables, so an operator can tune
  sensitivity for their workload without forking the analyzer.

## Rule catalog

| Rule ID | Category | What it flags |
|---|---|---|
| `seq_scan_expensive` | Access path | A sequential scan reading/discarding a lot of rows, or with heavy physical reads |
| `ineffective_index_scan` | Access path | An index/bitmap scan whose residual `Filter` throws away most of what it read |
| `missing_parallelism` | Parallelism | A large, slow scan that ran without parallel workers |
| `cardinality_estimate_error` | Cardinality | Planner row estimate off by 10x+ from actual rows |
| `buffer_cache_hit_ratio` | I/O (plan-level) | Low shared-buffer hit ratio summed across the whole plan |
| `sort_spill` | Memory | A `Sort` that spilled to disk (external merge); includes a concrete `work_mem` suggestion |
| `hash_spill` | Memory | A `Hash`/`HashAggregate` that spilled (batches > 1); includes a `work_mem` suggestion |
| `heavy_physical_io` | I/O | A node with a large number of physical block reads |
| `nested_loop_row_explosion` | Join strategy | The inner side of a Nested Loop re-executed thousands of times (plan-level N+1) |
| `correlated_subquery_repeated` | Query shape | A `SubPlan`/correlated subquery re-evaluated once per outer row |
| `text_explain_detected` | Input quality | Informational: input was text `EXPLAIN`, not `FORMAT JSON` |
| `plan_only_no_analyze` | Input quality | Informational: plan has no actual execution stats (`EXPLAIN` without `ANALYZE`) - most other findings are skipped, not "clean" |

`seq_scan_expensive` and `ineffective_index_scan` additionally attach a
best-effort `ddl_suggestion` (a `CREATE INDEX ...` statement) built by
`rules/sql_conditions.py`'s regex extraction of column names out of the
node's `Filter`/`Index Cond` string - there's no real SQL parser here, so
treat it as a starting point, not a verified fact.

## Plan comparison

`app/analyzer/compare.py`'s `compare_plans(baseline, current, thresholds)`
takes two already-`analyze()`'d plans and matches nodes by `path` (the
right notion of "the same node" for two runs of the same query shape).
It's exposed via `POST /api/v1/compare` and reused by `app/cli.py`'s
`--baseline` flag. A path that only exists on one side is reported as
`added`/`removed` rather than force-matched to something else.

## `auto_explain` log ingestion

`app/analyzer/ingest.py` splits a pasted `auto_explain` log excerpt on its
`duration: <ms> ms  plan:` marker lines and hands each entry's body
straight to the existing `parser.parse_plan` (which already handles both
JSON and text-EXPLAIN bodies) - no new plan-format parsing was needed,
only finding where each entry starts and ends. Exposed via `POST
/api/v1/analyze/batch`.

## CLI / CI regression gate

`app/cli.py` (installed as the `pgplanadvisor` console script) calls
`analyzer.engine.analyze()` directly - no HTTP server involved - so a CI
pipeline or shell script can gate on plan quality without standing up the
API. `--fail-on-severity` gates on the worst finding severity;
`--baseline <file>` additionally runs `compare_plans` and can fail on a
runtime regression past `--max-regression-pct` (default: the
`compare_regression_pct` threshold, 10%).

## Why SQLite for history, not Postgres

History persistence (`app/db.py`) is optional (`PGPA_HISTORY_ENABLED`) and
uses the stdlib `sqlite3` module rather than a Postgres table or an ORM.
This is a deliberate scope call: history is a small local lookup table
(saved analyses, not application data), pgPlanAdvisor shouldn't need its
*own* Postgres instance just to remember your last 500 analyses, and
`sqlite3` needs no extra dependency or migration tooling. If you need
shared, multi-instance history, point `PGPA_HISTORY_DB_PATH` at a shared
volume, or swap `HistoryStore` for a real database - the interface is a
single small class.

## Why an in-memory rate limiter, not Redis

`app/middleware.py`'s `InMemoryRateLimiter` is a fixed-window, per-process
limiter. pgPlanAdvisor is meant to be self-hosted by a team or a single
DBA, not run as a multi-tenant SaaS behind a fleet of replicas - so a
Redis-backed distributed limiter would be more infrastructure than the
problem calls for. If you do run multiple backend replicas behind a load
balancer without session affinity, either accept a looser effective limit
(N requests per replica) or swap in a shared-store limiter.

## Frontend

The frontend is a small React + Vite app (`frontend/src/`). API access is
centralized in `lib/api.js` (versioned endpoints, auth header injection,
consistent error handling via `ApiError`); formatting/sorting logic that
doesn't need React lives in `lib/format.js` so it's unit-testable with
Vitest without mounting components. `lib/settings.js` wraps `localStorage`
for the couple of per-browser preferences (API key, save-by-default).
