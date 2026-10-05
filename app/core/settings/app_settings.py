import json
from typing import Annotated, Any, Union, List, Literal
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode

from app.core.utc import UTCDateTime


StatsCoverageName = Literal[
    "lifecycle", "message_events", "account_errors", "session_errors",
]
StatsCoverageStarts = dict[StatsCoverageName, UTCDateTime]


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
    STATS_COVERAGE_STARTS: Annotated[StatsCoverageStarts, NoDecode] = Field(
        default_factory=dict,
        description=(
            "Confirmed audit collection starts by metric group, in RFC 3339. "
            "Omitted groups have unknown coverage; do not infer rollout dates."
        ),
    )

    @field_validator("STATS_COVERAGE_STARTS", mode="before")
    @classmethod
    def decode_stats_coverage(cls, value: Any) -> Any:
        # Do not let an explicit JSON null silently become the field default.
        return json.loads(value) if isinstance(value, str) else value
