"""Context objects passed into advisory rules.

Rules should never reach into globals or re-walk the plan themselves - they
receive a fully-populated context object with the current node, its
ancestry, and (for plan-level rules) the flattened list of every node. This
keeps rules pure functions of their input, which makes them trivial to unit
test in isolation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.config import Thresholds


@dataclass
class PlanNode:
    """A single plan node together with the bookkeeping the walker computed."""

    path: str
    node_id: str
    parent_id: str | None
    depth: int
    node: dict[str, Any]


@dataclass
class RuleContext:
    """Everything a per-node rule needs to make a decision."""

    node: dict[str, Any]
    path: str
    node_id: str
    parent_id: str | None
    depth: int
    ancestors: list[dict[str, Any]]
    total_runtime_ms: float
    planning_time_ms: float
    thresholds: Thresholds
    query: str | None = None

    def parent(self) -> dict[str, Any] | None:
        return self.ancestors[-1] if self.ancestors else None


@dataclass
class PlanContext:
    """Everything a whole-plan (aggregate) rule needs."""

    root: dict[str, Any]
    nodes: list[PlanNode]
    total_runtime_ms: float
    planning_time_ms: float
    thresholds: Thresholds
    query: str | None = None
