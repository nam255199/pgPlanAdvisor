"""A tiny pluggable rule registry.

pgPlanAdvisor's advisory logic is implemented as small, independent
"rules" instead of one large function. Each rule is a plain callable
decorated with :func:`node_rule` (runs once per plan node) or
:func:`plan_rule` (runs once for the whole plan, for cross-node checks like
buffer cache hit ratio).

Why a registry instead of one big ``analyze()`` function:

* New checks are added by writing a new function and decorating it - no
  other file needs to change. See ``analyzer/rules/__init__.py`` for the
  import that registers the built-in rule modules.
* Every rule is independently unit-testable: call it with a hand-built
  :class:`~app.analyzer.context.RuleContext` and assert on the returned
  :class:`~app.models.Finding` (or ``None``).
* A misbehaving rule can't take down the others - exceptions are caught,
  logged, and skipped so one bad check never breaks analysis of the plan.
"""
from __future__ import annotations

import logging
from collections.abc import Callable

from app.models import Finding

from .context import PlanContext, RuleContext

logger = logging.getLogger("pgplanadvisor.rules")

RuleResult = Finding | list[Finding] | None
NodeRule = Callable[[RuleContext], RuleResult]
PlanRule = Callable[[PlanContext], RuleResult]

_NODE_RULES: list[NodeRule] = []
_PLAN_RULES: list[PlanRule] = []


def node_rule(fn: NodeRule) -> NodeRule:
    """Register a function as a per-node advisory rule."""
    _NODE_RULES.append(fn)
    return fn


def plan_rule(fn: PlanRule) -> PlanRule:
    """Register a function as a whole-plan (aggregate) advisory rule."""
    _PLAN_RULES.append(fn)
    return fn


def registered_node_rules() -> list[NodeRule]:
    return list(_NODE_RULES)


def registered_plan_rules() -> list[PlanRule]:
    return list(_PLAN_RULES)


def _normalize(result: RuleResult) -> list[Finding]:
    if not result:
        return []
    if isinstance(result, list):
        return [f for f in result if f is not None]
    return [result]


def run_node_rules(ctx: RuleContext) -> list[Finding]:
    findings: list[Finding] = []
    for rule in _NODE_RULES:
        try:
            findings.extend(_normalize(rule(ctx)))
        except Exception:  # noqa: BLE001 - a bad rule must not break analysis
            logger.exception("Rule %s raised while evaluating node %s", getattr(rule, "__name__", rule), ctx.path)
    return findings


def run_plan_rules(ctx: PlanContext) -> list[Finding]:
    findings: list[Finding] = []
    for rule in _PLAN_RULES:
        try:
            findings.extend(_normalize(rule(ctx)))
        except Exception:  # noqa: BLE001
            logger.exception("Plan rule %s raised", getattr(rule, "__name__", rule))
    return findings


def clear_registry_for_testing() -> None:
    """Test helper: reset the registry (used when tests register fakes)."""
    _NODE_RULES.clear()
    _PLAN_RULES.clear()
