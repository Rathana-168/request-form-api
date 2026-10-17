from dataclasses import dataclass, field
from typing import Any

from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment
from sqlalchemy.ext.asyncio import AsyncSession

_jinja = SandboxedEnvironment(autoescape=False, undefined=StrictUndefined)


@dataclass
class ActionContext:
    db: AsyncSession
    request: Any                      # Request model
    data: dict[str, Any] = field(default_factory=dict)
    event: str = ""
    step_no: int | None = None
    actor: Any | None = None          # User model

    @property
    def template_vars(self) -> dict[str, Any]:
        r = self.request
        return {
            "request": {"id": str(r.id), "request_no": r.request_no,
                        "status": r.status.value, "form_code": r.form.code},
            "requester": {"id": str(r.requester_id), "staff_id": r.requester.staff_id,
                          "name": r.requester.full_name, "email": r.requester.email},
            "actor": {"id": str(self.actor.id), "name": self.actor.full_name} if self.actor else None,
            "data": self.data,
            "step_no": self.step_no,
        }


def render(value: Any, variables: dict[str, Any]) -> Any:
    """Render Jinja templates in strings, recursively through dicts and lists."""
    if isinstance(value, str) and "{{" in value:
        return _jinja.from_string(value).render(**variables)
    if isinstance(value, dict):
        return {k: render(v, variables) for k, v in value.items()}
    if isinstance(value, list):
        return [render(v, variables) for v in value]
    return value