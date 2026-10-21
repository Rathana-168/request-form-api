import uuid

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin
from app.modules.users.models import User


class Attachment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "attachments"

    file_name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size: Mapped[int] = mapped_column(BigInteger)
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    uploaded_by: Mapped[User | None] = relationship(lazy="selectin")
    request_id: Mapped[uuid.UUID | None] = mapped_column(
            ForeignKey("requests.id", ondelete="SET NULL"), index=True
        )