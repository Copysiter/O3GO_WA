from typing import Union, List
from pydantic import Field
from pydantic_settings import BaseSettings


class AppSettings(BaseSettings):
    PROJECT_NAME: str = Field(
        'cloud_config_service', json_schema_extra={'env': 'PROJECT_NAME'}
    )
    PROJECT_DESCRIPTION: str = Field(
        '', json_schema_extra={'env': 'PROJECT_DESCRIPTION'}
    )
    PROJECT_VERSION: str = Field(
        '0.0.1', json_schema_extra={'env': 'PROJECT_VERSION'}
    )
    PROJECT_ENVIRONMENT: str = Field(
        'dev', json_schema_extra={'env': 'PROJECT_ENVIRONMENT'}
    )
    PROJECT_INSTANCE_ID: Union[str, None] = Field(
        None, json_schema_extra={'env': 'PROJECT_INSTANCE_ID'}
    )
    PROJECT_HOST: str = Field(
        '127.0.0.1', json_schema_extra={'env': 'PROJECT_HOST'}
    )
    PROJECT_PORT: int = Field(
        8080, json_schema_extra={'env': 'PROJECT_PORT'}
    )
    API_VERSION: str = Field(
        '1', json_schema_extra={'env': 'API_VERSION'}
    )
    API_VERSION_PREFIX: str = Field(
        '/api/v1', json_schema_extra={'env': 'API_VERSION_PREFIX'}
    )
    EXT_API_VERSION: str = Field(
        '1', json_schema_extra={'env': 'EXT_EXT_API_VERSION'}
    )
    EXT_API_VERSION_PREFIX: str = Field(
        '/ext/api/v1', json_schema_extra={'env': 'EXT_API_VERSION_PREFIX'}
    )
    BACKEND_CORS_ORIGINS: Union[str, List[str]] = Field(
        '*', json_schema_extra={'env': 'BACKEND_CORS_ORIGINS'}
    )
    ASGI_WORKERS: int = Field(1, json_schema_extra={'env': 'ASGI_WORKERS'})
