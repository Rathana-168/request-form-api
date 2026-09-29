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


def matches(conditions: list[dict[str, Any]] | None, data: dict[str, Any]) -> bool:
    for rule in conditions or []:
        actual = data.get(rule["field"])
        if hasattr(actual, "value"):  # StrEnum -> its string value
            actual = actual.value
        expected = _coerce(actual, rule["value"])
        try:
            if not OPS[rule["op"]](actual, expected):
                return False
        except TypeError:  # e.g. None > 3
            return False
    return True