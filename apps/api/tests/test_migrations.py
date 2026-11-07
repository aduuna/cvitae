import json
import uuid
from collections.abc import Callable

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, create_engine, make_url, text

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


def test_layouts_keep_what_an_ejected_cv_held(
    database: str, alembic_config: Config, create_database: Callable[[str], None]
) -> None:
    """0010 turns an ejected CV's main.typ into its layout and drops `mode` and `source_files`;
    downgrading turns every layout back into an ejected CV."""
    base = make_url(database)
    scratch = base.set(database=f"{base.database}_layouts")
    url = scratch.render_as_string(hide_password=False)
    create_database(url)
    config = Config(alembic_config.config_file_name)
    config.set_main_option("sqlalchemy.url", url)
    config.attributes["configure_logging"] = False
    user, plain, ejected = (str(uuid.uuid4()) for _ in range(3))
    files = json.dumps({"main.typ": "#let x = 1", "data.json": "{}"})

    command.downgrade(config, "base")
    command.upgrade(config, "0009")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO users (id, firebase_uid, email) VALUES (:id, 'u', 'a@b.c')"),
            {"id": user},
        )
        for document, mode, source_files in (
            (plain, "structured", None),
            (ejected, "ejected", files),
        ):
            connection.execute(
                text(
                    "INSERT INTO documents (id, user_id, name, template_id, mode, content, "
                    "source_files) VALUES (:id, :user, 'CV', 'classic', :mode, '{}', "
                    "CAST(:files AS jsonb))"
                ),
                {"id": document, "user": user, "mode": mode, "files": source_files},
            )
            connection.execute(
                text(
                    "INSERT INTO document_versions (id, document_id, number, reason, content, "
                    "source_files) VALUES (:version, :id, 1, 'manual', '{}', "
                    "CAST(:files AS jsonb))"
                ),
                {"version": str(uuid.uuid4()), "id": document, "files": source_files},
            )

    command.upgrade(config, "0010")
    with engine.connect() as connection:
        layouts = connection.execute(
            text("SELECT id::text, layout FROM documents ORDER BY layout NULLS FIRST")
        ).all()
        version_layouts = connection.execute(
            text("SELECT layout FROM document_versions ORDER BY layout NULLS FIRST")
        ).all()
    assert [tuple(row) for row in layouts] == [(plain, None), (ejected, "#let x = 1")]
    assert [tuple(row) for row in version_layouts] == [(None,), ("#let x = 1",)]

    command.downgrade(config, "0009")
    with engine.connect() as connection:
        modes = {
            row[0]: row[1]
            for row in connection.execute(text("SELECT id::text, mode FROM documents"))
        }
        restored = connection.execute(
            text("SELECT source_files FROM documents WHERE id = :id"), {"id": ejected}
        ).scalar_one()
    engine.dispose()
    assert modes == {plain: "structured", ejected: "ejected"}
    assert restored == {"main.typ": "#let x = 1", "data.json": "{}"}
