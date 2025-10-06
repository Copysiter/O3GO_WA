from __future__ import annotations

from enum import IntEnum


class AccountStatus(IntEnum):
    BANNED    = -1
    AVAILABLE = 0
    ACTIVE    = 1
    PAUSED    = 2


class MessageStatus(IntEnum):
    WAITING     = -1
    CREATED     = 0
    SENT        = 1
    DELIVERED   = 2
    UNDELIVERED = 3
    FAILED      = 4
