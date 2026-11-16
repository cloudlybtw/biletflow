"""Run versioned SQL migrations as a separate release step; never print the DSN."""

import argparse
import os
import shutil
from pathlib import Path

from app.core.config import get_settings
from app.db.connection import connection_options


def migration_command(settings, executable):
    url, _ = connection_options(
        settings.database_url, settings.database_ssl_mode, settings.database_ssl_ca_file
    )
    query = dict(url.query)
    query["sslmode"] = settings.database_ssl_mode
    if settings.database_ssl_ca_file:
        query["sslrootcert"] = str(settings.database_ssl_ca_file)
    dsn = url.set(drivername="postgresql", query=query).render_as_string(hide_password=False)
    return [
        executable,
        "-path",
        str(Path(__file__).resolve().parents[2] / "migrations"),
        "-database",
        dsn,
        "up",
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm-up",
        action="store_true",
        required=True,
        help="Confirm non-destructive forward migrations for the configured database",
    )
    parser.parse_args()
    executable = shutil.which("migrate")
    if not executable:
        raise SystemExit(
            "golang-migrate is not installed; use the production image or local Compose migration service."
        )
    command = migration_command(get_settings(), executable)
    os.execv(executable, command)


if __name__ == "__main__":
    main()
