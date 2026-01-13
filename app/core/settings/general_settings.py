from fastapi import Depends
from pydantic_settings import SettingsConfigDict
from typing import Annotated

from .app_settings import AppSettings
from .logging_settings import LoggingSettings
from .database_settings import DatabaseSettings
from .security_settings import SecuritySettings
from .message_settings import MessageSettings


class GeneralSettings(
    AppSettings, LoggingSettings, DatabaseSettings, SecuritySettings,
    MessageSettings
):
    """Объединяющий класс настроек приложения"""
    model_config = SettingsConfigDict(
        env_file='.env', env_file_encoding='utf-8', extra='allow'
    )


def get_settings() -> GeneralSettings:
    return GeneralSettings()


Settings = Annotated[GeneralSettings, Depends(get_settings)]
settings = get_settings()
