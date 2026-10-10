from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, create_engine

from api.db.base import Base


def test_migrations_match_the_models(database: str, alembic_config: Config) -> None:
    """The hand-written migrations produce exactly the tables, indexes and constraints in models."""
    engine = create_engine(database)

    def diff(connection: Connection) -> list[object]:
        context = MigrationContext.configure(connection, opts={"compare_server_default": True})
        return compare_metadata(context, Base.metadata)

    with engine.connect() as connection:
        changes = diff(connection)
        head = MigrationContext.configure(connection).get_current_revision()
    engine.dispose()

    assert changes == []
    assert head == ScriptDirectory.from_config(alembic_config).get_current_head()
