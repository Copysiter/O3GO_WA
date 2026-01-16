import importlib
import logging
import uvicorn


from fastapi import FastAPI
from fastapi.responses import ORJSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.core.settings import settings
from app.lifespan import lifespan
from app.middlewares.logging import LoggingMiddleware


API_PREFIX = f'/api/v{settings.API_VERSION}'
API_MODULE_PATH = f'app.api.v{settings.API_VERSION}'

EXT_API_PREFIX = f'/ext/api/v{settings.EXT_API_VERSION}'
EXT_API_MODULE_PATH = f'app.api.ext.v{settings.EXT_API_VERSION}'

api_router = importlib.import_module(API_MODULE_PATH).api_router
ext_api_router = importlib.import_module(EXT_API_MODULE_PATH).api_router


def init_app() -> FastAPI:
    """Инициализация и конфигурация экземпляра FastAPI-приложения."""

    app_ = FastAPI(
        title=settings.PROJECT_NAME,
        version=f'v{settings.API_VERSION}',
        docs_url=f'{API_PREFIX}/docs',
        redoc_url=f'{API_PREFIX}/redoc',
        openapi_url=f'{API_PREFIX}/openapi.json',
        default_response_class=ORJSONResponse,
        lifespan=lifespan
    )

    app_.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # app_.add_middleware(LoggingMiddleware)
    app_.include_router(api_router, prefix=API_PREFIX)

    ext_api = FastAPI(
        title=settings.PROJECT_NAME,
        version=f'v{settings.API_VERSION}',
        docs_url=f'{EXT_API_PREFIX}/docs',
        redoc_url=f'{EXT_API_PREFIX}/redoc',
        openapi_url=f'{EXT_API_PREFIX}/openapi.json',
        default_response_class=ORJSONResponse
    )

    # ext_api.add_middleware(LoggingMiddleware)
    ext_api.include_router(ext_api_router, prefix=EXT_API_PREFIX)
    app_.mount('', ext_api)

    return app_


app = init_app()


if __name__ == '__main__':
    uvicorn.run(
        'app.main:app',
        host=settings.PROJECT_HOST, port=settings.PROJECT_PORT,
        workers=settings.ASGI_WORKERS, log_config=None, reload=False,
        proxy_headers=True, forwarded_allow_ips="*"
    )
