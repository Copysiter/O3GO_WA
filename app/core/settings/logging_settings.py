from typing import Optional, Union, Literal, Dict
from pydantic import Field
from pydantic_settings import BaseSettings


class LoggingSettings(BaseSettings):
    LOG_NAME: str = Field('fastapi', json_schema_extra={'env': 'LOG_NAME'})
    LOG_LEVEL: str = Field('DEBUG', json_schema_extra={'env': 'LOG_LEVEL'})
    LOG_STDOUT: bool = Field(True, json_schema_extra={'env': 'LOG_STDOUT'})
    LOG_PATH: Union[str, None] = Field(
        None, json_schema_extra={'env': 'LOG_PATH'}
    )
    LOG_ROTATION_TYPE: Optional[Literal['size', 'time']] = Field(
        None, json_schema_extra={'env': 'LOG_ROTATION_TYPE'}
    )
    LOG_ROTATION_MAX_BYTES: int = Field(
        10 * 1024 * 1024, json_schema_extra={'env': 'LOG_ROTATION_MAX_BYTES'}
    )
    LOG_ROTATION_WHEN: str = Field(
        'midnight', json_schema_extra={'env': 'LOG_ROTATION_WHEN'}
    )
    LOG_ROTATION_INTERVAL: int = Field(1, json_schema_extra={
        'env': 'LOG_ROTATION_INTERVAL'}
                                       )
    LOG_BACKUP_COUNT: int = Field(
        10, json_schema_extra={'env': 'LOG_BACKUP_COUNT'}
    )
    LOG_ENABLED_LOGGERS: Union[Dict[str, str], None] = Field(
        None, json_schema_extra={'env': 'LOG_ENABLED_LOGGERS'}
    )
