from dataclasses import dataclass, fields


@dataclass
class Status:
    @classmethod
    def name(cls, value):
        for field in fields(cls):
            if getattr(cls, field.name) == value:
                return field.name
        return None


@dataclass
class AccountStatus(Status):
    BANNED: int = -1
    AVAILABLE: int = 0
    ACTIVE: int = 1
    PAUSED: int = 2


@dataclass
class MessageStatus(Status):
    WAITING: int = -1
    CREATED: int = 0
    SENT: int = 1
    DELIVERED: int = 2
    UNDELIVERED: int = 3
    FAILED: int = 4
