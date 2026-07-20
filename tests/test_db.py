import pytest

import claimguard.db as db


@pytest.mark.db
def test_schema_applies_and_vector_ext_present():
    try:
        conn = db.connect()
    except Exception:
        pytest.skip("postgres not reachable")
    db.init_schema(conn)
    n = conn.execute("SELECT count(*) FROM pg_extension WHERE extname='vector'").fetchone()[0]
    assert n == 1
