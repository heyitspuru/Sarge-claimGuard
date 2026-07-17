from pathlib import Path

import pytest

from claimguard import icd

CSV_PATH = Path(__file__).resolve().parents[1] / "data" / "icd" / "icd10.csv"

REQUIRED_CODES = [
    "K35.9", "A90", "A01.0", "I21.9", "E11.1", "H25.9",
    "K40.9", "J18.9", "I63.9", "S72.0", "K80.2", "O82",
]


def _mock_embed(texts: list[str]) -> list[list[float]]:
    """Deterministic stand-in for llm.embed: identical text -> identical vector."""
    import hashlib
    out = []
    for t in texts:
        h = hashlib.sha256(t.encode()).digest()
        out.append([(h[i % 32] * (i + 1) % 1000) / 1000 for i in range(16)])
    return out


def test_load_csv_returns_at_least_60_unique_codes():
    entries = icd.load_csv(CSV_PATH)
    codes = [e.code for e in entries]
    assert len(entries) >= 60
    assert len(codes) == len(set(codes))
    for e in entries:
        assert isinstance(e, icd.IcdEntry)
        assert e.code and e.description


def test_load_csv_contains_all_template_ground_truth_codes():
    entries = icd.load_csv(CSV_PATH)
    codes = {e.code for e in entries}
    for code in REQUIRED_CODES:
        assert code in codes


def test_retriever_returns_k_entries():
    entries = icd.load_csv(CSV_PATH)
    retriever = icd.InMemoryRetriever(entries, _mock_embed)
    results = retriever("fever", k=5)
    assert len(results) == 5
    assert all(isinstance(r, icd.IcdEntry) for r in results)


def test_retriever_ranks_exact_description_match_first():
    entries = icd.load_csv(CSV_PATH)
    target = next(e for e in entries if e.code == "A90")
    retriever = icd.InMemoryRetriever(entries, _mock_embed)
    results = retriever(target.description, k=3)
    assert results[0].code == "A90"


@pytest.mark.db
def test_load_refs_into_db_upserts_icd_codes_and_policy_clauses():
    import claimguard.db as db

    try:
        conn = db.connect()
    except Exception:
        pytest.skip("postgres not reachable")
    db.init_schema(conn)

    icd.load_refs_into_db(conn)

    n_icd = conn.execute("SELECT count(*) FROM icd_codes").fetchone()[0]
    n_clauses = conn.execute("SELECT count(*) FROM policy_clauses").fetchone()[0]
    assert n_icd >= 60
    assert n_clauses >= 30

    row = conn.execute(
        "SELECT description, embedding FROM icd_codes WHERE code = 'A90'"
    ).fetchone()
    assert row is not None
    assert row[0] == "Dengue fever [classical dengue]"
    assert len(row[1]) == 768

    # re-run to confirm upsert (no duplicate rows, no error)
    icd.load_refs_into_db(conn)
    n_icd_again = conn.execute("SELECT count(*) FROM icd_codes").fetchone()[0]
    assert n_icd_again == n_icd
