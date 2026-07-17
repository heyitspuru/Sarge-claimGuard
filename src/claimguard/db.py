from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector

from claimguard.config import get_settings


def connect() -> psycopg.Connection:
    conn = psycopg.connect(get_settings().database_url, autocommit=True)
    register_vector(conn)
    return conn


def init_schema(conn: psycopg.Connection) -> None:
    conn.execute(Path(__file__).resolve().parents[2].joinpath("schema.sql").read_text())
