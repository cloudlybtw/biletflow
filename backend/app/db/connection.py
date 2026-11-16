"""Provider URL normalization and explicit certificate-verified PostgreSQL TLS."""

import ssl

from sqlalchemy.engine import make_url


def connection_options(database_url, ssl_mode="disable", ca_file=None):
    url = make_url(database_url)
    if url.drivername not in {"postgres", "postgresql", "postgresql+asyncpg"}:
        raise ValueError("DATABASE_URL must be PostgreSQL.")
    url = url.set(drivername="postgresql+asyncpg")
    query = dict(url.query)
    requested = query.pop("sslmode", None)
    # asyncpg does not accept libpq's sslmode as a connection keyword.
    if requested and requested != ssl_mode:
        raise ValueError("DATABASE_SSL_MODE must match the URL sslmode.")
    if "ssl" in query:
        raise ValueError("Use DATABASE_SSL_MODE instead of a URL ssl parameter.")
    url = url.set(query=query)
    if ssl_mode == "disable":
        options = {"ssl": False}
    elif ssl_mode == "verify-full":
        options = {"ssl": ssl.create_default_context(cafile=str(ca_file) if ca_file else None)}
    else:
        raise ValueError("Use disable locally or verify-full for hosted PostgreSQL.")
    return url, options
