from fastapi import APIRouter

from . import (
    base, auth, users, androids, versions,
    accounts, sessions, messages, options
)


api_router = APIRouter()

api_router.include_router(
    base.router, prefix='', tags=['Info']
)
api_router.include_router(
    auth.router, prefix='/auth', tags=['Auth']
)
api_router.include_router(
    users.router, prefix='/users', tags=['Users']
)
api_router.include_router(
    androids.router, prefix='/androids', tags=['Android Devices']
)
api_router.include_router(
    versions.router, prefix='/android/versions', tags=['Android App Versions']
)
api_router.include_router(
    accounts.router, prefix='/accounts', tags=['Accounts']
)
api_router.include_router(
    sessions.router, prefix='/sessions', tags=['Sessions']
)
api_router.include_router(
    messages.router, prefix='/messages', tags=['Messages']
)
api_router.include_router(
    options.router, prefix='/options', tags=['Options']
)
