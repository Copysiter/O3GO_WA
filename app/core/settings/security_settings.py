import secrets
from pydantic_settings import BaseSettings


class SecuritySettings(BaseSettings):
    JWT_ALGORITHM: str = 'HS256'
    SECRET_KEY: str = 'Query123456'
    DYNAMIC_SECRET_KEY: str = secrets.token_urlsafe(32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 10
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 30
