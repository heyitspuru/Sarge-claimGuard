"""ICD-10 reference subset + in-memory semantic retriever.

# ponytail: 60-code subset sized to the template universe; swap in full WHO
# table when the coder must generalize beyond the synthetic corpus.
"""

import csv
import math
from pathlib import Path
from typing import Callable, NamedTuple

from claimguard import coverage
from claimguard.llm import embed

ICD_CSV_PATH = Path(__file__).resolve().parents[2] / "data" / "icd" / "icd10.csv"
POLICIES_DIR = Path(__file__).resolve().parents[2] / "data" / "policies"
BATCH_SIZE = 50


class IcdEntry(NamedTuple):
    code: str
    description: str


def load_csv(path: str | Path) -> list[IcdEntry]:
    with open(path, encoding="utf-8", newline="") as f:
        return [IcdEntry(row["code"], row["description"]) for row in csv.DictReader(f)]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class InMemoryRetriever:
    """Cosine-similarity retriever over a fixed set of IcdEntry, embedded once at init."""

    def __init__(self, entries: list[IcdEntry],
                 embed_fn: Callable[[list[str]], list[list[float]]]):
        self.entries = entries
        self.embed_fn = embed_fn
        self._vectors = embed_fn([e.description for e in entries])

    def __call__(self, query: str, k: int = 5) -> list[IcdEntry]:
        q_vec = self.embed_fn([query])[0]
        ranked = sorted(
            zip(self.entries, self._vectors),
            key=lambda pair: _cosine(q_vec, pair[1]),
            reverse=True,
        )
        return [entry for entry, _ in ranked[:k]]


def _batches(seq: list, size: int):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def _upsert_icd_codes(conn, entries: list[IcdEntry]) -> None:
    for batch in _batches(entries, BATCH_SIZE):
        vectors = embed([e.description for e in batch])
        for entry, vec in zip(batch, vectors):
            conn.execute(
                "INSERT INTO icd_codes (code, description, embedding) VALUES (%s, %s, %s) "
                "ON CONFLICT (code) DO UPDATE SET "
                "description = EXCLUDED.description, embedding = EXCLUDED.embedding",
                (entry.code, entry.description, vec),
            )


def _upsert_policy_clauses(conn, policies: list[dict]) -> None:
    from psycopg.types.json import Jsonb

    clauses = [(p, c) for p in policies for c in p["clauses"]]
    for batch in _batches(clauses, BATCH_SIZE):
        vectors = embed([c["text"] for _, c in batch])
        for (policy, clause), vec in zip(batch, vectors):
            conn.execute(
                "INSERT INTO policy_clauses "
                "(clause_id, insurer_id, plan_id, clause_type, clause_text, structured, "
                "embedding) VALUES (%s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (clause_id) DO UPDATE SET "
                "clause_text = EXCLUDED.clause_text, structured = EXCLUDED.structured, "
                "embedding = EXCLUDED.embedding",
                (clause["clause_id"], policy["insurer_id"], policy["plan_id"],
                 clause["clause_type"], clause["text"], Jsonb(clause["structured"]), vec),
            )


def load_refs_into_db(conn) -> None:
    """Embed the ICD-10 subset and all policy clauses in batches of 50, upserting both."""
    _upsert_icd_codes(conn, load_csv(ICD_CSV_PATH))
    _upsert_policy_clauses(conn, coverage.load_policies(POLICIES_DIR))
