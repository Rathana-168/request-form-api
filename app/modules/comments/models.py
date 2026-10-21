import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin
from app.modules.attachments.models import Attachment
from app.modules.users.models import User

comment_attachments = Table(
    "request_comment_attachments", Base.metadata,
    Column("comment_id", ForeignKey("request_comments.id", ondelete="CASCADE"), primary_key=True),
    Column("attachment_id", ForeignKey("attachments.id", ondelete="CASCADE"), primary_key=True),
)


class RequestComment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "request_comments"
    __table_args__ = (
        CheckConstraint("char_length(body) > 0", name="body_not_empty"),
        Index("ix_request_comments_request_created", "request_id", "created_at"),
        Index("ix_request_comments_parent_created", "parent_id", "created_at"),
    )

    request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("requests.id", ondelete="CASCADE")
    )
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    on_behalf_of_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")  # set when a proxy comments
    )
    body: Mapped[str] = mapped_column(Text)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    author: Mapped[User | None] = relationship(foreign_keys=[author_id], lazy="selectin")
    on_behalf_of: Mapped[User | None] = relationship(
        foreign_keys=[on_behalf_of_id], lazy="selectin"
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("request_comments.id", ondelete="CASCADE")
    )
    attachments: Mapped[list[Attachment]] = relationship(secondary=comment_attachments, lazy="selectin")