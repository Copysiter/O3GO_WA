from typing import Any, Optional
from pydantic import Field, PostgresDsn, ValidationInfo, field_validator
from pydantic_settings import BaseSettings


class DatabaseSettings(BaseSettings):
    POSTGRES_HOST: str = Field(
        'localhost', json_schema_extra={'env': 'POSTGRES_HOST'}
    )
    POSTGRES_PORT: int = Field(
        5432, json_schema_extra={'env': 'POSTGRES_PORT'}
    )
    POSTGRES_USER: str = Field(
        'postgres', json_schema_extra={'env': 'POSTGRES_USER'}
    )
    POSTGRES_PASSWORD: str = Field(
        'postgres', json_schema_extra={'env': 'POSTGRES_PASSWORD'}
    )
    POSTGRES_DB: str = Field(
        'postgres', json_schema_extra={'env': 'POSTGRES_DB'}
    )

    POSTGRES_DSN: Optional[PostgresDsn] = Field(
        'postgresql+asyncpg://postgres:postgres@localhost:5432/postgres',
        json_schema_extra={'env': 'POSTGRES_DSN'}
    )

    @field_validator('POSTGRES_DSN', mode='before')
    def assemble_db_connection(
        cls, v: Optional[str], values: ValidationInfo
    ) -> Any:
        if isinstance(v, str):
            return v
        return PostgresDsn.build(
            scheme='postgresql+asyncpg',
            username=values.data.get('POSTGRES_USER'),
            password=values.data.get('POSTGRES_PASSWORD'),
            host=values.data.get('POSTGRES_SERVER'),
            port=values.data.get('POSTGRES_PORT'),
            path=f'{values.data.get("POSTGRES_DB") or ""}',
        )

    DATABASE_DELETE_ALL: bool = Field(
        False, json_schema_extra={'env': 'DATABASE_DELETE_ALL'}
    )
    DATABASE_CREATE_ALL: bool = Field(
        True, json_schema_extra={'env': 'DATABASE_CREATE_ALL'}
    )
    DATABASE_POOL_SIZE: int = Field(
        50, json_schema_extra={'env': 'DATABASE_POOL_SIZE'}
    )
    DATABASE_MAX_OVERFLOW: int = Field(
        100, json_schema_extra={'env': 'DATABASE_MAX_OVERFLOW'}
    )

    FIRST_SUPERUSER: str = Field(
        'admin', json_schema_extra={'env': 'FIRST_SUPERUSER'}
    )
    FIRST_SUPERUSER_PASSWORD: str = Field(
        'admin', json_schema_extra={'env': 'FIRST_SUPERUSER_PASSWORD'}
    )
