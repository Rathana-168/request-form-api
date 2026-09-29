from app.modules.forms.definitions.purchase_request.hooks import PurchaseHooks
from app.modules.forms.definitions.purchase_request.models import PurchaseRequestData
from app.modules.forms.definitions.purchase_request.schemas import (
    PurchaseCreate,
    PurchaseOut,
    PurchaseUpdate,
)
from app.modules.forms.plugin import FormDefinition

definition = FormDefinition(
    code="PURCHASE_REQUEST",
    prefix="PR",
    model=PurchaseRequestData,
    create_schema=PurchaseCreate,
    update_schema=PurchaseUpdate,
    read_schema=PurchaseOut,
    hooks=PurchaseHooks(),
)