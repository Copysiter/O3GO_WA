"""
Модуль middlewares.logging: Middleware для логирования HTTP-запросов и ответов.
"""

import json
import time
import hashlib
from typing import Any, Dict, Optional, Union

from fastapi import Request, Response
from fastapi.responses import FileResponse, StreamingResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

from atol_logging.context import request_id as ctx_request_id
from app.core.logger import logger, E


def generate_id() -> str:
    """
    Генерация уникального идентификатора запроса.
    """
    return hashlib.sha256(str(time.time()).encode()).hexdigest()[:16]


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware логирует:
    - входящие HTTP-запросы (HTTP_REQUEST)
    - исходящие HTTP-ответы (HTTP_RESPONSE)
    Также добавляет и пробрасывает X-Request-ID.
    """

    async def dispatch(
        self, request: Request, call_next: Any
    ) -> StreamingResponse:
        start_time = time.time()
        client_ip = request.client.host if request.client else "unknown"

        request_id = request.headers.get("X-Request-ID") or generate_id()
        token = ctx_request_id.set(request_id)

        try:
            # Обработка тела запроса
            body_data = await self._parse_body(request)

            logger.info(
                event=E.SYSTEM.API.REQUEST,
                extra={
                    "client_ip": client_ip,
                    "method": request.method,
                    "url": str(request.url),
                    "headers": dict(request.headers),
                    "query_params": dict(request.query_params),
                    "body": body_data,
                },
            )

            # Получение ответа от следующего обработчика
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id

            # Чтение тела ответа
            content = b"".join(
                [chunk async for chunk in response.body_iterator]
            )
            duration_ms = round((time.time() - start_time) * 1000, 2)

            logger.info(
                event=E.SYSTEM.API.RESPONSE,
                extra=self._build_response(response, content, duration_ms),
            )

            return StreamingResponse(
                iter([content]),
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )
        except Exception as e:
            logger.info(
                event=E.SYSTEM.API.ERROR, extra={
                    'error': {'type': type(e).__name__, 'message': str(e)}
                }
            )
        finally:
            ctx_request_id.reset(token)

    async def _parse_body(
        self, request: Request
    ) -> Union[Dict[str, Any], str]:
        """
        Метод для считывания тела запроса.

        Returns:
            Тело запроса или строку с ошибкой.
        """
        try:
            content_type = request.headers.get("content-type", "")
            if "multipart/form-data" in content_type:
                form = await request.form()
                return {
                    key: getattr(value, "filename", value)
                    for key, value in form.items()
                }

            raw_body = await request.body()
            try:
                return json.loads(raw_body)
            except json.JSONDecodeError:
                return raw_body.decode(errors="ignore")

        except Exception as e:
            return f"<error parsing body: {e}>"

    def _build_response(
        self, response: Response, content: bytes, duration_ms: float
    ) -> Dict[str, Any]:
        """
        Метод для формирования словаря с данными для логирования ответа.
        """
        body: Optional[Union[str, Dict[str, Any]]] = None

        if isinstance(response, FileResponse):
            body = {
                "filename": response.filename,
                "content_type": response.media_type,
            }
        elif isinstance(response, (StreamingResponse, RedirectResponse)):
            body = f"<{type(response).__name__} omitted>"
        else:
            try:
                body = json.loads(content)
            except Exception:
                body = content.decode(errors="ignore")

        return {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "body": body,
            "processing_time_ms": duration_ms,
        }
