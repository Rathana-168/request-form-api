"""Step conditions: [{"field": "days", "op": "gt", "value": 3}] - every rule must match."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

OPS = {
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
    "gt": lambda a, b: a > b,
    "gte": lambda a, b: a >= b,
    "lt": lambda a, b: a < b,
    "lte": lambda a, b: a <= b,
    "in": lambda a, b: a in b,
    "not_in": lambda a, b: a not in b,
}


def _coerce(actual: Any, expected: Any) -> Any:
    """Make the JSON value comparable with the form value (dates, decimals, enums)."""
    if isinstance(expected, list):
        return [_coerce(actual, v) for v in expected]
    if isinstance(actual, datetime) and isinstance(expected, str):
        return datetime.fromisoformat(expected)
    if isinstance(actual, date) and isinstance(expected, str):
        return date.fromisoformat(expected)
    if isinstance(actual, Decimal) and isinstance(expected, int | float | str):
        return Decimal(str(expected))
    return expected


def matches(conditions: list[Any] | dict[str, Any] | None, data: dict[str, Any]) -> bool:
    if not conditions:          # None / [] / {} = no condition: the step always runs
        return True
    return _node(conditions, data)


def _node(node: list[Any] | dict[str, Any], data: dict[str, Any]) -> bool:
    if isinstance(node, list):                     # list  -> AND
        return all(_node(n, data) for n in node)
    if "all" in node:                              # {"all": [...]} -> AND
        return all(_node(n, data) for n in node["all"])
    if "any" in node:                              # {"any": [...]} -> OR
        return any(_node(n, data) for n in node["any"])
    return _rule(node, data)                       # otherwise it's a single rule


def _rule(rule: dict[str, Any], data: dict[str, Any]) -> bool:
    actual = data.get(rule["field"])
    if hasattr(actual, "value"):  # StrEnum -> its string value
        actual = actual.value
    expected = _coerce(actual, rule["value"])
    try:
        return bool(OPS[rule["op"]](actual, expected))
    except TypeError:  # e.g. None > 3
        return False


def rule_fields(node: list[Any] | dict[str, Any] | None) -> list[str]:
    """Every field a condition tree refers to (for validation)."""
    if not node:
        return []
    if isinstance(node, list):
        return [f for n in node for f in rule_fields(n)]
    if "all" in node or "any" in node:
        return rule_fields(node.get("all") or node.get("any"))
    return [node["field"]]
