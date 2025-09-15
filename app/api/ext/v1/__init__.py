from fastapi import APIRouter

from . import messages, account

api_router = APIRouter()

api_router.include_router(
    messages.router, prefix='/messages', tags=['Messages']
)
api_router.include_router(
    account.router, prefix='/account', tags=['Account']
)
