
from typing import Optional

from pydantic import BaseModel

from datetime import datetime

from .user import User


class Token(BaseModel):
    access_token: str
    token_type: str
    user: User
    ts: Optional[datetime]


class TokenTest(BaseModel):
    user: User
    ts: Optional[datetime]


class TokenPayload(BaseModel):
    sub: Optional[int] = None
