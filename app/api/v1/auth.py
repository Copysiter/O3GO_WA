from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Body, Request, Depends, HTTPException, Response, status  # noqa
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import ORJSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

import app.deps as deps
import app.crud as crud, app.models as models, app.schemas as schemas  # noqa
from app.core import security  # noqa
from app.core.settings import settings  # noqa
from app.core.security import get_password_hash  # noqa
from app.core.utils import verify_password_reset_token  # noqa

router = APIRouter()


def get_tokens(user):
    access_token_expires = timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_token_expires = timedelta(
        minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)

    response = ORJSONResponse(content={
        'access_token': security.create_access_token(
            user.id, expires_delta=access_token_expires
        ),
        'token_type': 'bearer',
        'user': {
            'id': user.id,
            'login': user.login,
            'name': user.name,
            'is_active': user.is_active,
            'is_superuser': user.is_superuser
        },
        'ts': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    })
    response.set_cookie(
        key="refresh-token",
        value=security.create_refresh_token(
            user.id, expires_delta=refresh_token_expires
        )
    )
    return response


@router.post('/access-token', response_model=schemas.Token)
async def login_access_token(
    db: AsyncSession = Depends(deps.get_db),
    form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    '''
    OAuth2 compatible token login, get an access token for future requests
    '''
    user = await crud.user.authenticate(
        db, login=form_data.username, password=form_data.password
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail='Incorrect login or password')
    elif not crud.user.is_active(user):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail='Inactive user')
    return get_tokens(user)


@router.post('/refresh-token', response_model=schemas.Token)
async def refresh_token(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    '''
    Refresh token
    '''
    token = request.cookies.get('refresh-token')

    user_id = int(verify_password_reset_token(token))
    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail='Invalid token')
    user = await crud.user.get(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='The user with this ID does not exist in the system.',
        )
    elif not crud.user.is_active(user):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail='Inactive user')
    return get_tokens(user.id)


@router.post('/test-token', response_model=schemas.TokenTest)
async def test_token(
    current_user: models.User = Depends(deps.get_current_user)
) -> Any:
    '''
    Test access token
    '''
    return {
        'user': current_user,
        'ts': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    }
