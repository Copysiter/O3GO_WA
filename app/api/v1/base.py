from fastapi import APIRouter

from core.settings import settings  # noqa


router = APIRouter()


@router.get('/')
async def root_handler():
    return {'version': f'v{settings.API_VERSION}'}
