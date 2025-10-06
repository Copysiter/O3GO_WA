from fastapi import Depends, HTTPException, Security, status
from fastapi.security.api_key import APIKey, APIKeyQuery, APIKeyHeader
from fastapi.security import OAuth2PasswordBearer, HTTPBasic, HTTPBasicCredentials
from jose import jwt
from pydantic import ValidationError

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.core.security import verify_password

# Импорт async_session делаем внутри функции для разрыва circular import

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_VERSION_PREFIX}/auth/access-token"
)
http_basic = HTTPBasic()

api_key_query = APIKeyQuery(name="x_api_key", auto_error=False)
api_key_header = APIKeyHeader(name="X-Api-Key", auto_error=False)


async def get_db() -> AsyncSession:
    from app.adapters.db.session import async_session
    async with async_session() as session:
        yield session


async def get_current_user(
    db: AsyncSession = Depends(get_db), token: str = Depends(reusable_oauth2)
):
    from app import crud, schemas

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        token_data = schemas.TokenPayload(**payload)
    except (jwt.JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Could not validate credentials"
        )
    user = await crud.user.get(db, id=token_data.sub)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


async def get_current_active_user(
    current_user=Depends(get_current_user),
):
    from app import crud

    if not crud.user.is_active(current_user):
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def get_current_active_superuser(
    current_user=Depends(get_current_user),
):
    from app import crud

    if not crud.user.is_superuser(current_user):
        raise HTTPException(status_code=400, detail="The user doesn't have enough privileges")
    return current_user


async def get_basic_auth_user(
    db: AsyncSession = Depends(get_db),
    credentials: HTTPBasicCredentials = Depends(http_basic),
):
    from app import crud
    user = await crud.user.get_by_login(db, login=credentials.username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not crud.user.is_active(user):
        raise HTTPException(status_code=400, detail="Inactive user")
    if not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=401, detail="Incorrect password", headers={"WWW-Authenticate": "Basic"}
        )
    return user


def get_api_key(
    key_query: APIKey = Security(api_key_query), key_header: APIKey = Security(api_key_header)
) -> APIKey:
    if key_query:
        return key_query
    if key_header:
        return key_header
    raise HTTPException(status_code=403, detail="Not authenticated")


async def get_user_by_api_key(
    session: AsyncSession = Depends(get_db), api_key: APIKey = Security(get_api_key)
):
    from app import crud

    try:
        async with session.begin():
            user = await crud.user.get_by(session, ext_api_key=api_key)
            if not user:
                raise HTTPException(status_code=401, detail="Invalid API key")
            return user
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=getattr(e, "status_code", 500), detail=str(e))
