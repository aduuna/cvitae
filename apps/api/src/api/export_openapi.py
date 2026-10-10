"""Write the OpenAPI schema to a file (or stdout) without a server or a database.

uv run --package api python -m api.export_openapi apps/web/src/lib/api/openapi.json
"""

import json
import os
import sys
from pathlib import Path
from typing import Any


def openapi_schema() -> dict[str, Any]:
    # api.main builds an app from the environment on import; the schema needs no real settings.
    os.environ.update(ENV="test", AUTH_MODE="dev", DATABASE_URL="postgresql+psycopg://unused")
    from api.main import app

    return app.openapi()


def main(argv: list[str]) -> None:
    text = json.dumps(openapi_schema(), indent=2) + "\n"
    if len(argv) > 1:
        Path(argv[1]).write_text(text)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main(sys.argv)
