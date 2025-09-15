from datetime import datetime, timedelta
from typing import Optional

from jose import jwt

from app.core.settings import settings  # noqa


def generate_password_reset_token(login: str) -> str:
    delta = timedelta(hours=settings.EMAIL_RESET_TOKEN_EXPIRE_HOURS)
    now = datetime.utcnow()
    expires = now + delta
    exp = expires.timestamp()
    encoded_jwt = jwt.encode(
        {'exp': exp, 'sub': login},
        settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt


def verify_password_reset_token(token: str) -> Optional[str]:
    try:
        decoded_token = jwt.decode(
            token, settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return decoded_token['sub']
    except jwt.JWTError:
        return None
