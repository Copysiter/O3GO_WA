"""HTTP-клиент для внешнего API сообщений."""
import httpx
from typing import Optional

from app.core.settings import settings
from app.core.logger import logger, E
from .schemas import GetNextMessageResponse, SetMessageStatusResponse


class MessageService:
    """Сервис для взаимодействия с внешним API сообщений."""

    def __init__(self):
        self.base_url = settings.MESSAGE_API_URL
        self.timeout = settings.MESSAGE_API_TIMEOUT

    async def get_next_message(
        self,
        device: str,
        api_key: str,
        status: str = "sent"
    ) -> Optional[GetNextMessageResponse]:
        """
        Получить следующее сообщение для отправки.

        Args:
            device: ID устройства
            api_key: API ключ для аутентификации
            status: Фильтр статуса сообщения (по умолчанию: "sent")

        Returns:
            GetNextMessageResponse или None если нет доступных сообщений
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/ext/api/v1/messages/next",
                    params={
                        "device": device,
                        "status": status
                    },
                    headers={"X-Api-Key": api_key}
                )
                response.raise_for_status()
                data = response.json()

                if not data:
                    logger.info(
                        f"No messages available for device {device}",
                        event=E.EXTERNAL.SERVICE.RESPONSE
                    )
                    return None

                return GetNextMessageResponse(**data)

            except httpx.HTTPStatusError as e:
                logger.error(
                    f"Message API HTTP error: {e.response.status_code}, "
                    f"device={device}",
                    event=E.EXTERNAL.SERVICE.FAILURE
                )
                return None
            except httpx.TimeoutException:
                logger.error(
                    f"Message API timeout for device {device}",
                    event=E.EXTERNAL.SERVICE.ERROR
                )
                return None
            except Exception as e:
                logger.exception(
                    f"Unexpected error calling message API "
                    f"(get_next_message): {e}",
                    event=E.EXTERNAL.SERVICE.ERROR
                )
                return None

    async def set_message_status(
        self,
        message_id: int,
        status: str,
        api_key: str,
        src_addr: Optional[str] = None
    ) -> Optional[SetMessageStatusResponse]:
        """
        Обновить статус сообщения.

        Args:
            message_id: ID сообщения
            status: Новый статус (delivered/undelivered/failed)
            api_key: API ключ для аутентификации
            src_addr: Адрес источника (опционально)

        Returns:
            SetMessageStatusResponse или None если не удалось обновить
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                params = {
                    "id": message_id,
                    "status": status
                }
                if src_addr:
                    params["src_addr"] = src_addr

                response = await client.get(
                    f"{self.base_url}/ext/api/v1/messages/status",
                    params=params,
                    headers={"X-Api-Key": api_key}
                )
                response.raise_for_status()
                data = response.json()

                return SetMessageStatusResponse(**data)

            except httpx.HTTPStatusError as e:
                logger.error(
                    f"Message API HTTP error: {e.response.status_code}, "
                    f"message_id={message_id}, status={status}",
                    event=E.EXTERNAL.SERVICE.FAILURE
                )
                return None
            except httpx.TimeoutException:
                logger.error(
                    f"Message API timeout for message_id={message_id}",
                    event=E.EXTERNAL.SERVICE.ERROR
                )
                return None
            except Exception as e:
                logger.exception(
                    f"Unexpected error calling message API "
                    f"(set_message_status): {e}",
                    event=E.EXTERNAL.SERVICE.ERROR
                )
                return None