# Contributing

## Adding a new advisory rule

This is the most common contribution, so it gets its own walkthrough. Say
you want to flag `Materialize` nodes that get rescanned a huge number of
times.

1. Pick (or create) a module in `backend/app/analyzer/rules/` - this fits
   in `memory.py` or a new `materialize.py`, your call.
2. Write a function taking a `RuleContext` and returning a `Finding` or
   `None`, decorated `@node_rule` (or `@plan_rule` for whole-plan checks):

   ```python
   from app.analyzer.context import RuleContext
   from app.analyzer.registry import node_rule
   from app.models import Finding, Severity

   @node_rule
   def materialize_rescanned_heavily(ctx: RuleContext) -> Finding | None:
       node = ctx.node
       if node.get("Node Type") != "Materialize":
           return None
       loops = node.get("Actual Loops", 1)
       if loops < ctx.thresholds.materialize_min_loops:  # add this to Thresholds in config.py
           return None
       return Finding(
           rule_id="materialize_rescanned_heavily",
           severity=Severity.MEDIUM,
           category="Memory",
           title=f"Materialize rescanned {loops:g} times",
           node_path=ctx.path,
           score=loops,
           evidence=[...],
           recommendation="...",
           checks=["..."],
       )
   ```

3. If you added a new threshold, put it on `Thresholds` in
   `backend/app/config.py` with a sensible default - this makes it
   overridable via `PGPA_<NAME>` without any other code changes.
4. Register the module by importing it in
   `backend/app/analyzer/rules/__init__.py` (skip this if you added to an
   existing module).
5. Add a fixture plan under `backend/tests/fixtures/` that triggers it,
   plus a test in `tests/test_rules.py` (end-to-end via `analyze()`) and/or
   `tests/test_rule_units.py` (calling your function directly). See
   existing tests for the pattern.
6. Add a row to the rule catalog table in `ARCHITECTURE.md`.

Every rule must be safe to run on arbitrary/malformed plan input -
`registry.py` catches exceptions per-rule, but a rule that throws on every
plan is still a rule that never fires. Use `fnum()`/`.get()` (see
`app/analyzer/rules/helpers.py`) rather than assuming a field is present.

## Local development

```bash
# backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload

# in another terminal: frontend
cd frontend
npm install
npm run dev
```

## Before opening a PR

```bash
cd backend && ruff check app tests && mypy app && pytest
cd frontend && npm run lint && npm run test && npm run build
```

CI (`.github/workflows/ci.yml`) runs the same checks plus a Docker image
build for both services.

## Code style

- Backend: [ruff](https://docs.astral.sh/ruff/) for lint/format, mypy for
  type-checking (`pyproject.toml` has both configs). Type hints are
  expected on new public functions.
- Frontend: ESLint (flat config, `eslint.config.js`) + Prettier
  (`.prettierrc.json`).
- Keep rule modules small and focused - one concern per module, one check
  per function.
