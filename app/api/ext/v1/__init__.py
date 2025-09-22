from fastapi import APIRouter

from . import message, session

api_router = APIRouter()

api_router.include_router(
    message.router, prefix='/messages', tags=['Messages']
)
api_router.include_router(
    session.router, prefix='/session', tags=['Account']
)
