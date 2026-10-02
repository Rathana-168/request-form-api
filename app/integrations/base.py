import logging
from typing import Any

import httpx

from app.core.config import ServiceConfig

log = logging.getLogger(__name__)


class ServiceUnavailableError(Exception):
    """The other service is down or returned 5xx. Mapped to a 503 response."""

    def __init__(self, service: str, detail: str):
        super().__init__(f"{service}: {detail}")
        self.service = service
        self.detail = detail


class BaseServiceClient:
    name = "service"

    def __init__(self, config: ServiceConfig):
        self.config = config
        self._client = httpx.AsyncClient(
            base_url=config.url,
            headers={"X-API-Key": config.api_key},
            timeout=config.timeout,
            transport=httpx.AsyncHTTPTransport(retries=config.retries),  # connection errors only
        )

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        try:
            resp = await self._client.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            log.warning("%s %s %s failed: %s", self.name, method, url, exc)
            raise ServiceUnavailableError(self.name, "unreachable") from exc
        if resp.status_code >= 500:
            log.warning("%s %s %s -> %s", self.name, method, url, resp.status_code)
            raise ServiceUnavailableError(self.name, f"error {resp.status_code}")
        return resp

    @staticmethod
    def data(resp: httpx.Response) -> Any:
        """Unwrap the shared APIResponse shape: {status_code, message, data}."""
        return resp.json()["data"]

    async def aclose(self) -> None:
        await self._client.aclose()