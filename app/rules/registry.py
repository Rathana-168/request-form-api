from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError

from app.rules.context import ActionContext

Handler = Callable[[ActionContext, BaseModel], Awaitable[None]]


class ActionError(Exception):
    """Raised by an action. In a sync action it rolls back the user's action."""


@dataclass(frozen=True)
class ActionSpec:
    type: str
    params: type[BaseModel]
    handler: Handler
    is_async: bool
    forms: frozenset[str] | None
    description: str


_REGISTRY: dict[str, ActionSpec] = {}


def register_action(type_: str, *, params: type[BaseModel], is_async: bool,
                    forms: list[str] | None = None, description: str = ""):
    def decorator(fn: Handler) -> Handler:
        if type_ in _REGISTRY:
            raise RuntimeError(f"Action type '{type_}' is registered twice")
        _REGISTRY[type_] = ActionSpec(type_, params, fn, is_async,
                                      frozenset(forms) if forms else None, description)
        return fn
    return decorator


def get_action(type_: str) -> ActionSpec | None:
    return _REGISTRY.get(type_)


def list_actions(form_code: str | None = None) -> list[ActionSpec]:
    return [s for s in _REGISTRY.values()
            if form_code is None or s.forms is None or form_code in s.forms]


def validate_actions(actions: list[dict], form_code: str) -> list[str]:
    """Called when a rule is saved. Returns a list of error messages."""
    if not actions:
        return ["at least one action is required"]
    errors = []
    for i, a in enumerate(actions):
        spec = _REGISTRY.get(a.get("type", ""))
        if spec is None:
            errors.append(f"actions[{i}]: unknown type '{a.get('type')}'")
        elif spec.forms and form_code not in spec.forms:
            errors.append(f"actions[{i}]: '{spec.type}' is not allowed for {form_code}")
        else:
            try:
                spec.params.model_validate(a.get("params", {}))
            except ValidationError as e:
                err = e.errors()[0]
                loc = ".".join(map(str, err["loc"]))
                msg = err["msg"].removeprefix("Value error, ")
                errors.append(f"actions[{i}]{'.' + loc if loc else ''}: {msg}")
    return errors