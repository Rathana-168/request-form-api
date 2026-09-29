from decimal import Decimal

from pydantic import BaseModel

from app.modules.forms.definitions.purchase_request.models import PurchaseRequestData
from app.modules.forms.plugin import FormContext, FormHooks


def _set_total(row: PurchaseRequestData) -> None:
    total = sum((i.qty * Decimal(i.unit_price) for i in row.items), start=Decimal(0))
    row.total = total.quantize(Decimal("0.01"))


class PurchaseHooks(FormHooks):
    async def build(self, ctx: FormContext, data: BaseModel) -> PurchaseRequestData:
        row = await super().build(ctx, data)
        _set_total(row)  # total is computed, never taken from the user
        return row

    async def apply_update(
        self, ctx: FormContext, row: PurchaseRequestData, data: BaseModel, fields: set[str]
    ) -> None:
        await super().apply_update(ctx, row, data, fields)
        if "items" in fields:
            _set_total(row)