import pytest


@pytest.mark.db
def test_schema_applies_and_vector_ext_present(db_conn):
    n = db_conn.execute(
        "SELECT count(*) FROM pg_extension WHERE extname='vector'").fetchone()[0]
    assert n == 1
