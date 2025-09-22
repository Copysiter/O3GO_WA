from fastapi import Depends
from pydantic_settings import SettingsConfigDict
from typing import Annotated

from .app_settings import AppSettings
from .logging_settings import LoggingSettings
from .database_settings import DatabaseSettings
from .security_settings import SecuritySettings


class GeneralSettings(
    AppSettings, LoggingSettings, DatabaseSettings, SecuritySettings
):
    """Объединяющий класс настроек приложения"""
    model_config = SettingsConfigDict(
        env_file='.env', env_file_encoding='utf-8', extra='allow'
    )


def get_settings() -> GeneralSettings:
    return GeneralSettings()


Settings = Annotated[GeneralSettings, Depends(get_settings)]
settings = get_settings()
