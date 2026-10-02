from app.core.config import get_settings
from app.integrations.base import BaseServiceClient
from app.integrations.file_service.client import FileServiceClient

file_service = FileServiceClient(get_settings().FILE_SERVICE)

ALL_CLIENTS: list[BaseServiceClient] = [file_service]


async def close_all_client_services() -> None:
    for client in ALL_CLIENTS:
        await client.aclose()