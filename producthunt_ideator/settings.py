import enum
from pathlib import Path
from tempfile import gettempdir
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from yarl import URL

TEMP_DIR = Path(gettempdir())


class LogLevel(str, enum.Enum):
    """Possible log levels."""

    NOTSET = "NOTSET"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    FATAL = "FATAL"


class Settings(BaseSettings):
    """
    Application settings.

    These parameters can be configured
    with environment variables.
    """

    host: str = "127.0.0.1"
    port: int = 8000
    # quantity of workers for uvicorn
    workers_count: int = 1
    # Enable uvicorn reloading
    reload: bool = False
    # Whether to use instructor package for structured outputs
    instructor: bool = True

    # Current environment
    environment: str = "dev"

    post_limit: int = 3

    log_level: LogLevel = LogLevel.INFO
    # Variables for the database
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "producthunt_ideator"
    db_pass: str = "producthunt_ideator"
    db_base: str = "admin"
    db_echo: bool = False

    # Variables for Redis
    redis_host: str = "producthunt_ideator-redis"
    redis_port: int = 6379
    redis_user: Optional[str] = None
    redis_pass: Optional[str] = None
    redis_base: Optional[int] = None

    # Variables for Celery
    celery_db: int = 0
    celery_broker_connection_retry: bool = True

    gpt_model: str
    openai_api_key: str
    azure_openai_endpoint: str

    producthunt_client_id: str
    producthunt_client_secret: str

    wordpress_url: str
    wordpress_user: str
    wordpress_password: str

    @property
    def db_url(self) -> URL:
        """
        Assemble database URL from settings.

        :return: database URL.
        """
        return URL.build(
            scheme="postgresql+asyncpg",
            host=self.db_host,
            port=self.db_port,
            user=self.db_user,
            password=self.db_pass,
            path=f"/{self.db_base}",
        )

    @property
    def redis_url(self) -> URL:
        """
        Assemble REDIS URL from settings.

        :return: redis URL.
        """
        path = ""
        if self.redis_base is not None:
            path = f"/{self.redis_base}"
        return URL.build(
            scheme="redis",
            host=self.redis_host,
            port=self.redis_port,
            user=self.redis_user,
            password=self.redis_pass,
            path=path,
        )

    @property
    def celery_broker_url(self) -> str:
        """
        Assemble Celery broker URL from settings.

        :return: Celery broker URL.
        """
        return "/".join(
            [
                str(self.redis_url),
                str(self.celery_db),
            ],
        )

    @property
    def celery_result_backend(self) -> str:
        """
        Assemble Celery result backend URL from settings.

        :return: Celery result backend URL.
        """
        return self.celery_broker_url

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="PRODUCTHUNT_IDEATOR_",
        env_file_encoding="utf-8",
    )


settings = Settings()
