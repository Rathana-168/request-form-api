from sqlalchemy import event
from sqlalchemy.orm import Session

from app.core.context import current_user_id
from app.db.mixins import AuditMixin


@event.listens_for(Session, "before_flush")
def fill_audit_columns(session: Session, _flush_context, _instances) -> None:
    user_id = current_user_id.get()
    if user_id is None:
        return
    for obj in session.new:
        if isinstance(obj, AuditMixin):
            obj.created_by_id = obj.created_by_id or user_id
            obj.updated_by_id = user_id
    for obj in session.dirty:
        if isinstance(obj, AuditMixin) and session.is_modified(
            obj, include_collections=False
        ):
            obj.updated_by_id = user_id
