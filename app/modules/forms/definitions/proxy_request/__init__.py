from app.modules.forms.definitions.proxy_request.hooks import ProxyRequestHooks
from app.modules.forms.definitions.proxy_request.models import ProxyRequestData
from app.modules.forms.definitions.proxy_request.router import router
from app.modules.forms.definitions.proxy_request.schemas import (
    ProxyRequestCreate,
    ProxyRequestOut,
    ProxyRequestUpdate,
)
from app.modules.forms.plugin import FormDefinition

definition = FormDefinition(
    code="PROXY_REQUEST",
    prefix="PROXY",
    model=ProxyRequestData,
    create_schema=ProxyRequestCreate,
    update_schema=ProxyRequestUpdate,
    read_schema=ProxyRequestOut,
    hooks=ProxyRequestHooks(),
    router=router,
)