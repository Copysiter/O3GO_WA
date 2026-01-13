from fastapi import APIRouter

from .android import android, options, account as android_account
from . import message, session, account

api_router = APIRouter()

# Универсальный роутер для аккаунтов
api_router.include_router(
    account.router, prefix='/account', tags=['Account']
)
api_router.include_router(
    session.router, prefix='/session', tags=['Account Session']
)
api_router.include_router(
    message.router, prefix='/messages', tags=['Account Messages']
)

# Роутер для Android устройств
api_router.include_router(
    android.router, prefix='/android/device', tags=['Android Device']
)
api_router.include_router(
    options.router, prefix='/androids', tags=['Android Options']
)
api_router.include_router(
    android_account.router, prefix='/android/account', tags=['Android Account']
)
