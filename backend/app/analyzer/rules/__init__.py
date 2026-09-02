"""Built-in advisory rules.

Importing this package registers every rule module with
``app.analyzer.registry``. To add a new check: write a new module in this
package with a function decorated ``@node_rule`` or ``@plan_rule`` (see
``registry.py`` for the contract), then import it below. Nothing else needs
to change - ``engine.py`` iterates whatever is registered.
"""
from . import (  # noqa: F401  (imported for side-effect: rule registration)
    access_path,
    cardinality,
    io,
    joins,
    memory,
    subplans,
    text_quality,
)

__all__ = [
    "access_path",
    "cardinality",
    "io",
    "joins",
    "memory",
    "subplans",
    "text_quality",
]
