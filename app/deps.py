from fastapi import Depends, HTTPException, Security, status
from fastapi.security.api_key import APIKey, APIKeyQuery, APIKeyHeader
from fastapi.security import ( # noqa
    OAuth2PasswordBearer, HTTPBasic, HTTPBasicCredentials  # noqa
)  # noqa
from jose import jwt
from pydantic import ValidationError

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.core.security import verify_password
from app.adapters.db.session import async_session

import app.crud as crud
import app.models as models
import app.schemas as schemas


reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f'{settings.API_VERSION_PREFIX}/auth/access-token'
)

http_basic = HTTPBasic()

api_key_query = APIKeyQuery(name='x_api_key', auto_error=False)
api_key_header = APIKeyHeader(name='X-Api-Key', auto_error=False)


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session


async def get_current_user(
    db: AsyncSession = Depends(get_db), token: str = Depends(reusable_oauth2)
) -> models.User:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        token_data = schemas.TokenPayload(**payload)
    except (jwt.JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Could not validate credentials',
        )
    user = await crud.user.get(db, id=token_data.sub)
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    return user


async def get_current_active_user(
    current_user: models.User = Depends(get_current_user),
) -> models.User:
    if not crud.user.is_active(current_user):
        raise HTTPException(status_code=400, detail='Inactive user')
    return current_user


async def get_current_active_superuser(
    current_user: models.User = Depends(get_current_user),
) -> models.User:
    if not crud.user.is_superuser(current_user):
        raise HTTPException(
            status_code=400, detail='The user doesn\'t have enough privileges'
        )
    return current_user


async def get_basic_auth_user(
    db: AsyncSession = Depends(get_db),
    credentials: HTTPBasicCredentials = Depends(http_basic)
) -> models.User:
    user = await crud.user.get_by_login(db, login=credentials.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail='User not found'
        )
    if not crud.user.is_active(user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail='Inactive user'
        )
    if not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Incorrect password',
            headers={"WWW-Authenticate": "Basic"},
        )
    return user


def get_api_key(
    key_query: APIKey = Security(api_key_query),
    key_header: APIKey = Security(api_key_header)
) -> APIKey:
    if key_query:
        return key_query
    if key_header:
        return key_header
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail='Not authenticated'
    )


async def get_user_by_api_key(
    session: AsyncSession = Depends(get_db),
    api_key: APIKey = Security(get_api_key)
) -> bool:
    try:
        async with session.begin():
            user = await crud.user.get_by(session, ext_api_key=api_key)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail='Invalid API key'
                )
            return user
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=getattr(e, 'status_code', 500), detail=str(e)
        )
