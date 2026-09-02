"""Walks a normalized EXPLAIN plan tree into a flat list of PlanNode records."""
from __future__ import annotations

from collections.abc import Generator
from typing import Any

from .context import PlanNode


def get_root_plan(plan: dict[str, Any]) -> dict[str, Any]:
    return plan.get("Plan", plan)


def _node_id(path: str) -> str:
    return path.replace(".", "_").replace("[", "_").replace("]", "")


def walk_plan(
    node: dict[str, Any], path: str = "Plan", parent_id: str | None = None
) -> Generator[tuple[str, str | None, dict[str, Any]], None, None]:
    """Legacy generator interface: (path, parent_id, node) tuples."""
    node_id = _node_id(path)
    yield path, parent_id, node
    for i, child in enumerate(node.get("Plans", []) or []):
        yield from walk_plan(child, f"{path}.Plans[{i}]", node_id)


def flatten_plan(root: dict[str, Any]) -> list[PlanNode]:
    """Flatten the plan tree into PlanNode records, depth-first, root first.

    This is the structure both the rule engine (RuleContext.ancestors) and
    the API layer (parent_id-based tree for the UI) build on.
    """
    out: list[PlanNode] = []

    def _walk(n: dict[str, Any], path: str, parent_id: str | None, depth: int) -> None:
        node_id = _node_id(path)
        out.append(PlanNode(path=path, node_id=node_id, parent_id=parent_id, depth=depth, node=n))
        for i, child in enumerate(n.get("Plans", []) or []):
            _walk(child, f"{path}.Plans[{i}]", node_id, depth + 1)

    _walk(root, "Plan", None, 0)
    return out
