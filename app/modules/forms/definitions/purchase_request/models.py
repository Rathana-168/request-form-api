import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import UUIDMixin
from app.modules.forms.plugin import FormDataMixin


class PurchaseRequestData(FormDataMixin, Base):
    __tablename__ = "form_purchase_requests"

    supplier: Mapped[str] = mapped_column(String(150))
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2))  # computed in hooks.build
    items: Mapped[list["PurchaseItem"]] = relationship(
        cascade="all, delete-orphan", lazy="raise", order_by="PurchaseItem.line_no"
    )
    approver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))


class PurchaseItem(UUIDMixin, Base):
    __tablename__ = "form_purchase_request_items"

    parent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("form_purchase_requests.id", ondelete="CASCADE"), index=True
    )
    line_no: Mapped[int]
    description: Mapped[str] = mapped_column(String(255))
    qty: Mapped[int]
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))