from typing import Any


def get_by_path(data: Any, path: str) -> Any:
    """Get a nested value by dot path. Returns None if not found.

    "a.b"        -> data["a"]["b"]
    "items.0.id" -> first item's id
    "items.*.id" -> list of all items' ids
    """
    if not path:
        return None
    return _resolve(data, path.split("."))


# Private functions, do not import to use direct
def _resolve(cur, parts: list[str]):
    if cur is None:
        return None
    if not parts:
        return cur

    head, rest = parts[0], parts[1:]

    if head == "*":
        if not isinstance(cur, list):
            return None
        out = []
        for item in cur:
            v = _resolve(item, rest)
            if v is None:
                continue
            out.extend(v if isinstance(v, list) else [v])
        return out

    if isinstance(cur, dict):
        return _resolve(cur.get(head), rest)

    if isinstance(cur, list) and head.isdigit():
        i = int(head)
        return _resolve(cur[i], rest) if i < len(cur) else None

    return None