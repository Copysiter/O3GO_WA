"""Settings for external message API service."""
from pydantic import Field
from pydantic_settings import BaseSettings


class MessageSettings(BaseSettings):
    """Configuration for external message API."""
    MESSAGE_API_URL: str = Field(
        'https://campaigner.o3go.ru', json_schema_extra={'env': 'MESSAGE_API_URL'}
    )
    MESSAGE_API_TIMEOUT: int = 30