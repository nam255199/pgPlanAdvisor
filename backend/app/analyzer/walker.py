
from typing import Any, Dict, Generator, Optional, Tuple


def get_root_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    return plan.get("Plan", plan)


def walk_plan(node: Dict[str, Any], path: str = "Plan", parent_id: Optional[str] = None) -> Generator[Tuple[str, Optional[str], Dict[str, Any]], None, None]:
    node_id = path.replace(".", "_").replace("[", "_").replace("]", "")
    yield path, parent_id, node
    for i, child in enumerate(node.get("Plans", []) or []):
        yield from walk_plan(child, f"{path}.Plans[{i}]", node_id)
