from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector

from claimguard.config import get_settings


def connect() -> psycopg.Connection:
    conn = psycopg.connect(get_settings().database_url, autocommit=True)
    # register_vector() resolves the `vector` type OID, so the extension must already
    # exist. Locally it does — compose mounts schema.sql as a Postgres init script — but
    # against a bare server (a CI service container, which cannot mount files) connect()
    # would fail before init_schema() ever got the chance to create it. Idempotent.
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    register_vector(conn)
    return conn


def init_schema(conn: psycopg.Connection) -> None:
    conn.execute(Path(__file__).resolve().parents[2].joinpath("schema.sql").read_text())
