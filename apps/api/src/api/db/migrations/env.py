"""Alembic environment: runs migrations online over a synchronous psycopg connection."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from api.db import models  # noqa: F401 - registers every table on Base.metadata
from api.db.base import Base
from api.settings import DatabaseSettings


def _url() -> str:
    # Tests pass the URL in the Alembic config; everything else uses the environment.
    configured = context.config.get_main_option("sqlalchemy.url")
    return configured or DatabaseSettings().migration_url


def configure_logging() -> None:
    # The CLI logs progress; tests turn this off so pytest keeps its own logging setup.
    config = context.config
    if config.config_file_name and config.attributes.get("configure_logging", True):
        fileConfig(config.config_file_name, disable_existing_loggers=False)


def run_migrations() -> None:
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


configure_logging()
run_migrations()
