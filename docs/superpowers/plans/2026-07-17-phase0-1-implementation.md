# ClaimGuard Phase 0+1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Foundations (scaffold, synthetic data, eval harness) + thin discharge→claim pipeline that turns a synthetic record into a validated NHCX-shaped submission, fully audited.

**Architecture:** Pure-function agents (Summarizer→Coder→Packager→Submitter) chained by a plain-Python orchestrator with retries + audit log. LLM behind a provider interface (`gemini` runtime / `mock` tests). Postgres+pgvector via Docker Compose. Static data (records, policies, ICD table) generated at build time.

**Tech Stack:** Python 3.11, FastAPI, pydantic v2, pydantic-settings, psycopg3, pgvector, Faker, google-genai, fhir.resources (R4), pytest, ruff, Docker Compose.

## Global Constraints

- Python `>=3.11`; all code under `src/claimguard/`; tests under `tests/`.
- **No real patient data, ever.** Synthetic only (CLAUDE.md prime directive 3).
- All tests run offline with the `mock` provider — CI needs no API key, no Docker. DB-dependent tests carry `@pytest.mark.db` and skip when Postgres is unreachable.
- Low-confidence ICD codes are **never** silently submitted (test failure per CLAUDE.md).
- Malformed/missing-document claims are rejected **pre-submission** (test failure per CLAUDE.md).
- Submitter contains **no LLM calls** and is idempotent.
- Ponytail rules: minimal code, deliberate shortcuts marked `# ponytail: <ceiling>, <upgrade path>`.
- Task runner is `python -m claimguard <cmd>` (no make). Windows host: use forward-slash paths in code; commit from repo root `C:\Users\bhara\Desktop\claimGuard`.
- Commit after every task (message style: `feat: ...` / `test: ...` / `docs: ...`).
- Design system for any future UI: `design-system/claimguard/MASTER.md` (not used in this plan's tasks).

**Execution waves:** Tasks 1–3 sequential (foundation). Wave 1 parallel: Tasks 4, 5, 6, 7 (+8 after 5). Task 9 gates Phase 0. Wave 2 parallel: Tasks 10+11, 12, 13. Task 14–15 sequential, gate Phase 1.

---

### Task 1: Scaffold + config

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `.env.example`, `src/claimguard/__init__.py`, `src/claimguard/config.py`, `tests/__init__.py`, `tests/test_config.py`

**Interfaces:**
- Produces: `claimguard.config.get_settings() -> Settings` with fields `llm_provider` ("mock"|"gemini", default "mock"), `gemini_api_key: str = ""`, `model_reasoning: str = "gemini-2.0-flash"`, `model_fast: str = "gemini-2.0-flash"`, `embed_model: str = "text-embedding-004"`, `database_url: str = "postgresql://claimguard:claimguard@localhost:5432/claimguard"`, `data_dir: str = "data"`.

- [ ] **Step 1: Write files**

`pyproject.toml`:
```toml
[project]
name = "claimguard"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi", "uvicorn[standard]", "pydantic>=2", "pydantic-settings",
  "psycopg[binary]", "pgvector", "faker", "google-genai", "fhir.resources>=7", "httpx",
]

[project.optional-dependencies]
dev = ["pytest", "ruff"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.ruff]
line-length = 100

[tool.pytest.ini_options]
markers = ["db: requires a reachable postgres"]
```

`.gitignore`:
```
__pycache__/
*.egg-info/
.env
.venv/
data/synthetic/
!data/synthetic/sample/
.pytest_cache/
.ruff_cache/
```

`.env.example`:
```
LLM_PROVIDER=mock
GEMINI_API_KEY=
DATABASE_URL=postgresql://claimguard:claimguard@localhost:5432/claimguard
```

`src/claimguard/config.py`:
```python
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    llm_provider: str = "mock"
    gemini_api_key: str = ""
    model_reasoning: str = "gemini-2.0-flash"
    model_fast: str = "gemini-2.0-flash"
    embed_model: str = "text-embedding-004"
    database_url: str = "postgresql://claimguard:claimguard@localhost:5432/claimguard"
    data_dir: str = "data"

    model_config = {"env_file": ".env"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

`src/claimguard/__init__.py` and `tests/__init__.py`: empty files.

`tests/test_config.py`:
```python
from claimguard.config import get_settings


def test_defaults_are_mock_provider():
    s = get_settings()
    assert s.llm_provider in ("mock", "gemini")
    assert s.data_dir == "data"
```

- [ ] **Step 2: Create venv, install, run test**

Run (repo root): `python -m venv .venv && .venv/Scripts/pip install -e .[dev] && .venv/Scripts/python -m pytest tests/test_config.py -v`
Expected: PASS.

- [ ] **Step 3: Commit** — `git add -A && git commit -m "feat: scaffold package, config, tooling"`

---

### Task 2: LLM provider interface

**Files:**
- Create: `src/claimguard/llm.py`, `tests/test_llm.py`

**Interfaces:**
- Produces: `complete(prompt: str, *, system: str = "", tier: str = "fast", json_schema: dict | None = None) -> str | dict` and `embed(texts: list[str]) -> list[list[float]]` (768-dim). Provider chosen by `get_settings().llm_provider`.

- [ ] **Step 1: Write the failing tests**

`tests/test_llm.py`:
```python
from claimguard import llm


def test_mock_complete_returns_string():
    out = llm.complete("hello", tier="fast")
    assert isinstance(out, str) and out


def test_mock_complete_json_schema_returns_conformant_minimal_dict():
    schema = {
        "type": "object",
        "properties": {
            "codes": {"type": "array", "items": {"type": "string"}},
            "note": {"type": "string"},
            "score": {"type": "number"},
        },
        "required": ["codes", "note"],
    }
    out = llm.complete("code this", json_schema=schema)
    assert out == {"codes": [], "note": ""}


def test_mock_embed_deterministic_768():
    a = llm.embed(["dengue fever"])
    b = llm.embed(["dengue fever"])
    assert len(a[0]) == 768 and a == b
```

- [ ] **Step 2: Run to verify fail** — `pytest tests/test_llm.py -v` → FAIL (no module `llm`).

- [ ] **Step 3: Implement**

`src/claimguard/llm.py`:
```python
"""LLM provider interface. mock = deterministic/offline (all tests); gemini = runtime."""
import hashlib
import json

from claimguard.config import get_settings

EMBED_DIM = 768


def _min_instance(schema: dict):
    t = schema.get("type", "object")
    if t == "object":
        return {k: _min_instance(v) for k, v in schema.get("properties", {}).items()
                if k in schema.get("required", [])}
    return {"array": [], "string": "", "number": 0, "integer": 0, "boolean": False}.get(t, None)


def _mock_complete(prompt, system, json_schema):
    if json_schema:
        return _min_instance(json_schema)
    return f"[mock:{hashlib.sha1((system + prompt).encode()).hexdigest()[:8]}]"


def _mock_embed(texts):
    out = []
    for t in texts:
        h = hashlib.sha256(t.encode()).digest()
        out.append([(h[i % 32] * (i + 1) % 1000) / 1000 for i in range(EMBED_DIM)])
    return out


def _gemini_client():
    from google import genai
    return genai.Client(api_key=get_settings().gemini_api_key)


def _gemini_complete(prompt, system, tier, json_schema):
    s = get_settings()
    model = s.model_reasoning if tier == "reasoning" else s.model_fast
    cfg = {"system_instruction": system} if system else {}
    if json_schema:
        cfg |= {"response_mime_type": "application/json"}
        prompt += "\nRespond ONLY with JSON matching this schema:\n" + json.dumps(json_schema)
    resp = _gemini_client().models.generate_content(model=model, contents=prompt, config=cfg or None)
    return json.loads(resp.text) if json_schema else resp.text


def complete(prompt: str, *, system: str = "", tier: str = "fast",
             json_schema: dict | None = None) -> str | dict:
    if get_settings().llm_provider == "gemini":
        return _gemini_complete(prompt, system, tier, json_schema)
    return _mock_complete(prompt, system, json_schema)


def embed(texts: list[str]) -> list[list[float]]:
    if get_settings().llm_provider == "gemini":
        client = _gemini_client()
        res = client.models.embed_content(model=get_settings().embed_model, contents=texts)
        return [e.values for e in res.embeddings]
    return _mock_embed(texts)
```

- [ ] **Step 4: Run tests** — `pytest tests/test_llm.py -v` → PASS.
- [ ] **Step 5: Commit** — `git commit -am "feat: llm provider interface (mock + gemini)"`

---

### Task 3: Domain models

**Files:**
- Create: `src/claimguard/models.py`, `tests/test_models.py`

**Interfaces:**
- Produces (all pydantic BaseModel, exact field names):
  - `Patient(name: str, age: int, sex: str, abha_id: str)`
  - `Insurance(insurer_id: str, plan_id: str, policy_number: str, sum_insured: int, claimed_amount: int)`
  - `DischargeRecord(record_id: str, patient: Patient, admission_date: str, discharge_date: str, claim_type: Literal["cashless","reimbursement"], specialty: str, diagnosis_text: str, procedures: list[str], medications: list[str], clinical_notes: str, documents: list[str], insurance: Insurance)`
  - `AnswerKey(record_id: str, icd_codes: list[str], expected_packaging: Literal["ready","rejected","needs_review"])`
  - `DischargeSummary(record_id: str, primary_diagnosis: str, secondary_diagnoses: list[str], procedures: list[str], medications: list[str], admission_course: str, source_fields: dict[str, str])`
  - `CodedDiagnosis(icd_code: str, description: str, confidence: float, needs_review: bool)`
  - `ClaimPackage(record_id: str, status: Literal["ready","rejected","needs_review"], fhir_claim: dict | None = None, rejection_reasons: list[str] = [])`
  - `SubmissionResult(record_id: str, submission_id: str, status: str, outcome: str | None = None)`

- [ ] **Step 1: Write failing test**

`tests/test_models.py`:
```python
from claimguard.models import ClaimPackage, DischargeRecord, Insurance, Patient


def _record(**kw):
    base = dict(
        record_id="R0001",
        patient=Patient(name="Asha Rao", age=34, sex="F", abha_id="12-3456-7890-0001"),
        admission_date="2026-07-01", discharge_date="2026-07-04",
        claim_type="cashless", specialty="general_surgery",
        diagnosis_text="Acute appendicitis", procedures=["Laparoscopic appendectomy"],
        medications=["Inj Ceftriaxone 1g IV BD"], clinical_notes="Uneventful recovery.",
        documents=["discharge_summary", "final_bill", "preauth_form", "id_proof"],
        insurance=Insurance(insurer_id="INS1", plan_id="P1", policy_number="POL123",
                            sum_insured=500000, claimed_amount=80000),
    )
    return DischargeRecord(**(base | kw))


def test_record_roundtrip_json():
    r = _record()
    assert DischargeRecord.model_validate_json(r.model_dump_json()) == r


def test_claim_type_validated():
    import pytest
    with pytest.raises(Exception):
        _record(claim_type="cash")


def test_package_defaults():
    p = ClaimPackage(record_id="R1", status="rejected", rejection_reasons=["missing preauth_form"])
    assert p.fhir_claim is None
```

- [ ] **Step 2: Run to fail** — `pytest tests/test_models.py -v` → FAIL.
- [ ] **Step 3: Implement** `src/claimguard/models.py` with exactly the classes/fields in the Interfaces block (plain `BaseModel`s, `Literal` types as shown, defaults as shown).
- [ ] **Step 4: Run** — PASS. **Step 5: Commit** — `git commit -am "feat: domain models"`

---

### Task 4: Docker Compose, schema, db helper, FastAPI health  *(Wave 1 — parallel)*

**Files:**
- Create: `docker-compose.yml`, `Dockerfile`, `schema.sql`, `src/claimguard/db.py`, `src/claimguard/api.py`, `tests/test_api.py`, `tests/test_db.py`

**Interfaces:**
- Produces: `db.connect()` → psycopg connection (registers pgvector); `db.init_schema(conn)` executes `schema.sql`; FastAPI `app` with `GET /health` → `{"status":"ok"}` and `GET /` → placeholder HTML.

- [ ] **Step 1: Write failing API test**

`tests/test_api.py`:
```python
from fastapi.testclient import TestClient

from claimguard.api import app


def test_health():
    assert TestClient(app).get("/health").json() == {"status": "ok"}


def test_placeholder_page():
    r = TestClient(app).get("/")
    assert r.status_code == 200 and "ClaimGuard" in r.text
```

- [ ] **Step 2: Implement**

`schema.sql`:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS claims (
  record_id text PRIMARY KEY, status text NOT NULL, package jsonb,
  created_at timestamptz DEFAULT now(), updated_at timestamptz DEFAULT now());
CREATE TABLE IF NOT EXISTS audit_log (
  id bigserial PRIMARY KEY, record_id text NOT NULL, step text NOT NULL,
  status text NOT NULL, detail jsonb, created_at timestamptz DEFAULT now());
CREATE TABLE IF NOT EXISTS icd_codes (
  code text PRIMARY KEY, description text NOT NULL, embedding vector(768));
CREATE TABLE IF NOT EXISTS policy_clauses (
  clause_id text PRIMARY KEY, insurer_id text NOT NULL, plan_id text NOT NULL,
  clause_type text NOT NULL, clause_text text NOT NULL, structured jsonb,
  embedding vector(768));
CREATE TABLE IF NOT EXISTS handoff_timestamps (
  id bigserial PRIMARY KEY, record_id text NOT NULL, handoff text NOT NULL,
  at timestamptz DEFAULT now());
-- ponytail: consent/erasure are no-op interfaces on synthetic data; real DPDP impl is product-stage
CREATE TABLE IF NOT EXISTS consents (
  record_id text PRIMARY KEY, granted boolean NOT NULL DEFAULT true, withdrawn_at timestamptz);
```

`src/claimguard/db.py`:
```python
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
```

`src/claimguard/api.py`:
```python
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="ClaimGuard")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index():
    # ponytail: placeholder page; real dashboard is Phase 3 (React + shadcn per design system)
    return "<h1>ClaimGuard</h1><p>API up. Dashboard arrives in Phase 3.</p>"
```

`tests/test_db.py`:
```python
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
```

`Dockerfile`:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .
COPY schema.sql ./
CMD ["uvicorn", "claimguard.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

`docker-compose.yml`:
```yaml
services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: claimguard
      POSTGRES_PASSWORD: claimguard
      POSTGRES_DB: claimguard
    ports: ["5432:5432"]
    volumes:
      - ./schema.sql:/docker-entrypoint-initdb.d/schema.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U claimguard"]
      interval: 5s
      retries: 10
  api:
    build: .
    environment:
      DATABASE_URL: postgresql://claimguard:claimguard@db:5432/claimguard
      LLM_PROVIDER: mock
    ports: ["8000:8000"]
    depends_on:
      db:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "python -c \"import urllib.request as u;u.urlopen('http://localhost:8000/health')\""]
      interval: 10s
      retries: 5
```

- [ ] **Step 3: Run** — `pytest tests/test_api.py tests/test_db.py -v` → API tests PASS, db test PASS or SKIP.
- [ ] **Step 4: Verify compose** — `docker compose up -d --build` then `docker compose ps` → both healthy; `docker compose down`. If Docker Desktop isn't running, note it in the task report instead of failing the task.
- [ ] **Step 5: Commit** — `git commit -am "feat: compose stack, db schema, api health"`

---

### Task 5: Synthetic templates + generator + gen-data CLI  *(Wave 1 — parallel)*

**Files:**
- Create: `src/claimguard/synth/__init__.py`, `src/claimguard/synth/templates.py`, `src/claimguard/synth/generate.py`, `src/claimguard/__main__.py`, `tests/test_generate.py`

**Interfaces:**
- Consumes: `claimguard.models` (Task 3).
- Produces:
  - `templates.TEMPLATES: list[dict]` — each dict has keys `specialty, diagnosis_text, procedures, medications, notes (list[str] variants, some Hinglish), icd_codes (list[str]), claim_types (list[str]), scenario_weights (dict[str,float])`.
  - `templates.REQUIRED_DOCS: dict[str, list[str]]` — `{"cashless": ["discharge_summary","final_bill","preauth_form","id_proof"], "reimbursement": ["discharge_summary","final_bill","payment_receipts","claim_form","id_proof"]}` (Packager, Task 12, imports this).
  - `generate.make_record(i: int, rng: random.Random, faker) -> tuple[DischargeRecord, AnswerKey]` — scenarios: `"normal"` (expected_packaging "ready"), `"missing_doc"` (one required doc removed → "rejected"), `"vague_dx"` (diagnosis_text replaced by vague text → "needs_review").
  - `generate.generate(n: int, seed: int, out_dir: Path, golden_n: int) -> tuple[int, int]` — writes `data/synthetic/{record_id}.json` (record only) and `data/golden/{record_id}.json` (`{"record": ..., "answer_key": ...}`) for the first `golden_n` records; returns counts.
  - CLI: `python -m claimguard gen-data --n 500 --golden 200 --seed 7`.

- [ ] **Step 1: Write `templates.py`** — 12 templates. This is the Claude-generated clinical content; ground truth ICD codes are embedded per template so the golden set is answer-key-by-construction (template-level clinical verification instead of per-record hand-checking — note this honestly in the module docstring). The 12 templates (specialty / dx / ICD):
  1. general_surgery / Acute appendicitis, lap appendectomy / `K35.9`
  2. internal_medicine / Dengue fever with warning signs / `A90`
  3. internal_medicine / Enteric (typhoid) fever / `A01.0`
  4. cardiology / Acute myocardial infarction, PTCA + stent / `I21.9`
  5. endocrinology / Type 2 DM with ketoacidosis / `E11.1`
  6. ophthalmology / Senile cataract, phaco + IOL / `H25.9`
  7. general_surgery / Inguinal hernia, mesh repair / `K40.9`
  8. pulmonology / Community-acquired pneumonia / `J18.9`
  9. neurology / Cerebral infarction (ischemic stroke) / `I63.9`
  10. orthopedics / Fracture neck of femur, hemiarthroplasty / `S72.0`
  11. general_surgery / Cholelithiasis, lap cholecystectomy / `K80.2`
  12. obstetrics / Delivery by emergency LSCS / `O82`

  Each template gets 2–3 clinically plausible note variants; at least 4 templates include one code-switched Hinglish variant (e.g. "Patient ko admission ke time tez bukhar tha, platelets gir rahe the, IV fluids diye gaye"). `scenario_weights` default `{"normal": 0.7, "missing_doc": 0.15, "vague_dx": 0.15}`. Vague replacement texts live in `templates.VAGUE_DX = ["Fever under evaluation, ?viral ?bacterial", "Abdominal pain, cause unclear, obs.", "Generalised weakness, w/u ongoing"]`.

- [ ] **Step 2: Write failing tests**

`tests/test_generate.py`:
```python
import random
from pathlib import Path

from faker import Faker

from claimguard.synth import generate, templates


def test_templates_shape():
    assert len(templates.TEMPLATES) >= 12
    for t in templates.TEMPLATES:
        assert t["icd_codes"] and t["diagnosis_text"] and t["notes"]


def test_make_record_deterministic_and_scenarios_covered():
    fk = Faker("en_IN")
    keys = set()
    for i in range(60):
        rec, key = generate.make_record(i, random.Random(i), fk)
        assert rec.record_id == key.record_id
        keys.add(key.expected_packaging)
    assert keys == {"ready", "rejected", "needs_review"}


def test_missing_doc_scenario_actually_missing(tmp_path: Path):
    n_syn, n_gold = generate.generate(50, seed=7, out_dir=tmp_path, golden_n=50)
    assert n_syn == 50 and n_gold == 50
    import json
    rejected = [json.loads(p.read_text()) for p in (tmp_path / "golden").glob("*.json")
                if json.loads(p.read_text())["answer_key"]["expected_packaging"] == "rejected"]
    assert rejected
    for g in rejected:
        req = templates.REQUIRED_DOCS[g["record"]["claim_type"]]
        assert not set(req) <= set(g["record"]["documents"])
```

- [ ] **Step 3: Run to fail**, then implement `generate.py` + `__main__.py` (argparse subcommands `gen-data`; `eval` and `load-refs` slots added by Tasks 8/7). Seed both `random.Random(seed)` and `Faker.seed(seed)`. Record IDs `R{i:04d}`. Faker `en_IN` for names; ABHA id `fk.numerify('##-####-####-####')`; dates within last 90 days; `claimed_amount` = rng.randrange in template-appropriate band ≤ `sum_insured` (500000 or 1000000).
- [ ] **Step 4: Run tests** — PASS. Then generate for real: `python -m claimguard gen-data --n 500 --golden 200 --seed 7` → verify counts; commit a 5-record sample to `data/synthetic/sample/` (rest is gitignored), full golden set is committed.
- [ ] **Step 5: Commit** — `git commit -am "feat: synthetic data engine (12 clinical templates, 500 records, 200 golden)"`

---

### Task 6: Policy corpus + loader  *(Wave 1 — parallel)*

**Files:**
- Create: `data/policies/ins_star_secure.json`, `data/policies/ins_medicare_plus.json`, `data/policies/ins_arogya_kavach.json`, `src/claimguard/coverage.py`, `tests/test_coverage.py`

**Interfaces:**
- Produces: `coverage.load_policies(policies_dir: Path) -> list[dict]` (validated clause dicts); `coverage.clause_ids(policies) -> set[str]`. Each policy JSON: `{"insurer_id", "insurer_name", "plan_id", "plan_name", "clauses": [{"clause_id", "clause_type": "coverage"|"exclusion"|"sub_limit"|"waiting_period", "text", "structured": {...}}]}`. Clause IDs stable and globally unique, format `{insurer_id}-{plan_id}-C{nn}` — **Phase 2's Negotiator grounds citations against exactly these IDs.**

- [ ] **Step 1: Write the three policy files.** Each insurer ≥ 10 clauses mixing types. Content is Claude-generated synthetic Indian health-insurance prose, e.g. a sub_limit clause: `{"clause_id": "STAR-SEC1-C04", "clause_type": "sub_limit", "text": "Room rent, boarding and nursing expenses shall be limited to 1% of the Sum Insured per day, subject to a maximum of Rs. 7,500 per day.", "structured": {"category": "room_rent", "limit_pct_si_per_day": 1.0, "cap_inr_per_day": 7500}}`. Include: room-rent sub-limits, cataract caps, 24-month waiting periods (hernia, cataract), 30-day initial waiting period, maternity waiting period, dental/cosmetic exclusions, pre-existing disease exclusions, ambulance cover, pre/post hospitalization cover, co-pay clauses.
- [ ] **Step 2: Failing test** — `load_policies` returns 3 policies, ≥30 clauses total, all clause_ids unique, all clause_types in the allowed set.
- [ ] **Step 3: Implement `coverage.py`** (json load + validation ~25 lines). Run → PASS.
- [ ] **Step 4: Commit** — `git commit -am "feat: synthetic policy corpus (3 insurers) + loader"`

---

### Task 7: ICD-10 reference + retriever  *(Wave 1 — parallel)*

**Files:**
- Create: `data/icd/icd10.csv`, `src/claimguard/icd.py`, `tests/test_icd.py`
- Modify: `src/claimguard/__main__.py` (add `load-refs` subcommand)

**Interfaces:**
- Consumes: `llm.embed`, `db.connect`.
- Produces: `icd.load_csv(path) -> list[IcdEntry]` (`IcdEntry = NamedTuple(code: str, description: str)`); `icd.InMemoryRetriever(entries, embed_fn)` with `__call__(query: str, k: int = 5) -> list[IcdEntry]` (cosine over embeddings); `icd.load_refs_into_db(conn)` (embeds + upserts icd_codes and policy_clauses). Coder (Task 11) consumes any `Callable[[str, int], list[IcdEntry]]`.

- [ ] **Step 1: Write `data/icd/icd10.csv`** — header `code,description`; ~60 rows: the 12 template codes plus ~48 clinically adjacent distractors (sibling codes in the same categories: K35.2, K35.3, A91, A01.1, I21.0, I21.4, E11.9, E11.5, H25.0, H25.1, K40.3, J18.0, J18.1, J44.1, I63.5, S72.1, S72.3, K80.0, K80.1, O80, O81, plus commons: E78.5, I10, N18.5, N39.0, R50.9, J06.9, K29.7, M54.5, D64.9, B34.9 ... to ~60). `# ponytail: 60-code subset sized to the template universe; swap in full WHO table when coder must generalize.`
- [ ] **Step 2: Failing tests** — CSV loads ≥60 unique codes; `InMemoryRetriever` with mock embed returns k entries and, given an exact description as the query, ranks its code first (cosine of identical mock vectors = 1.0).
- [ ] **Step 3: Implement `icd.py`** — pure-python cosine for InMemoryRetriever (~30 lines); `load_refs_into_db` embeds in batches of 50 and upserts. Run tests → PASS (db path covered by `@pytest.mark.db` test that skips without Postgres).
- [ ] **Step 4: Commit** — `git commit -am "feat: ICD-10 reference subset + retriever"`

---

### Task 8: Eval harness  *(Wave 1 — after Task 5)*

**Files:**
- Create: `src/claimguard/eval/__init__.py`, `src/claimguard/eval/metrics.py`, `src/claimguard/eval/runner.py`, `tests/test_eval.py`
- Modify: `src/claimguard/__main__.py` (add `eval` subcommand)

**Interfaces:**
- Consumes: golden dir layout from Task 5.
- Produces:
  - `metrics.code_credit(pred: str, true: str) -> float` — 1.0 exact, 0.5 same 3-char category (`pred[:3] == true[:3]`), else 0.0.
  - `metrics.hierarchical_f1(pred: list[str], true: list[str]) -> float` — precision = mean over preds of best credit vs any true; recall = mean over trues of best credit vs any pred; F1 = harmonic mean (0.0 when either side empty).
  - `runner.run_eval(golden_dir: Path, pipeline: Callable[[dict], dict] | None = None) -> dict` — pipeline maps a record dict → `{"icd_codes": list[str], "packaging": str}`. Returns `{"n": int, "coding_f1": float, "packaging_validity": float, "grounding_rate": None}` (grounding armed in Phase 2). `pipeline=None` → all-zero predictions (empty codes, packaging "ready").
  - `runner.print_report(report: dict) -> None` — plain-text table.
  - CLI: `python -m claimguard eval [--golden data/golden]`.

- [ ] **Step 1: Failing tests** — `code_credit("K35.9","K35.9")==1.0`, `code_credit("K35.2","K35.9")==0.5`, `code_credit("A90","K35.9")==0.0`; `hierarchical_f1([],["A90"])==0.0`; `run_eval` on a tmp golden dir with 2 fabricated golden files and `pipeline=None` returns `n==2, coding_f1==0.0` and `packaging_validity` equal to the fraction whose expected_packaging is "ready".
- [ ] **Step 2: Implement** (~60 lines total). Run → PASS.
- [ ] **Step 3: End-to-end zero run** — `python -m claimguard eval` against real `data/golden` prints report with `coding_f1 0.000`. Paste output into the task report.
- [ ] **Step 4: Commit** — `git commit -am "feat: eval harness (hierarchical F1, packaging validity)"`

---

### Task 9: NHCX access doc + Phase 0 exit gate

**Files:**
- Create: `docs/NHCX_ACCESS.md`, `tests/test_phase0_exit.py`

- [ ] **Step 1: Write `docs/NHCX_ACCESS.md`** — states: NHCX (live since June 2024, FHIR-based) sandbox access at `hcxsbx.abdm.gov.in` requires organization-level onboarding via NHA; individuals cannot perform live end-to-end submission. Therefore ClaimGuard ships a **deterministic FHIR/NHCX simulator** (Task 13) and labels every submission as simulated. Real submission is product-stage (see PROJECT_SPEC §14).
- [ ] **Step 2: Write gate test**

`tests/test_phase0_exit.py`:
```python
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(not (ROOT / "data/golden").exists(), reason="run gen-data first")
def test_golden_set_size_and_keys():
    files = list((ROOT / "data/golden").glob("*.json"))
    assert len(files) >= 200
    g = json.loads(files[0].read_text())
    assert {"record", "answer_key"} <= g.keys()


def test_eval_cli_runs():
    out = subprocess.run([sys.executable, "-m", "claimguard", "eval"],
                         capture_output=True, text=True, cwd=ROOT)
    assert out.returncode == 0 and "coding_f1" in out.stdout


def test_nhcx_doc_exists():
    assert (ROOT / "docs/NHCX_ACCESS.md").read_text().lower().count("simulator") >= 1
```

- [ ] **Step 3: Run the full suite** — `pytest -v` → all green (db tests may skip). This is the Phase 0 gate.
- [ ] **Step 4: Commit** — `git commit -am "docs+test: NHCX access reality check, phase 0 exit gate"`

---

### Task 10: Summarizer  *(Wave 2 — parallel)*

**Files:**
- Create: `src/claimguard/agents/__init__.py`, `src/claimguard/agents/summarizer.py`, `tests/test_summarizer.py`

**Interfaces:**
- Consumes: `DischargeRecord`, `DischargeSummary`, `llm.complete` signature.
- Produces: `summarize(record: DischargeRecord, llm=llm.complete) -> DischargeSummary`.

- [ ] **Step 1: Failing tests** — with an injected fake llm returning `{"primary_diagnosis": "Acute appendicitis", "secondary_diagnoses": [], "procedures": ["Laparoscopic appendectomy"], "medications": ["Inj Ceftriaxone 1g IV BD"], "admission_course": "Admitted with RIF pain; surgery day 1; uneventful recovery."}`: result is a `DischargeSummary` with `record_id == record.record_id` and `source_fields` mapping every output key to the record field names fed into the prompt (e.g. `"primary_diagnosis": "diagnosis_text"`). Second test: fake llm returning a dict with an invented extra key → extra key ignored, model still validates.
- [ ] **Step 2: Implement** — build prompt from record fields (`diagnosis_text`, `procedures`, `medications`, `clinical_notes`, dates), `tier="reasoning"`, json_schema for the five output fields, system prompt: *"You are a clinical summarizer. Use ONLY facts present in the record. Never invent findings, dates, or treatments."* `source_fields` is the fixed mapping `{"primary_diagnosis": "diagnosis_text", "secondary_diagnoses": "diagnosis_text", "procedures": "procedures", "medications": "medications", "admission_course": "clinical_notes"}`.
- [ ] **Step 3: Run** → PASS. **Step 4: Commit** — `git commit -am "feat: summarizer agent"`

---

### Task 11: Coder (RAG, confidence, flagging)  *(Wave 2 — parallel, after 10 in same agent lane)*

**Files:**
- Create: `src/claimguard/agents/coder.py`, `tests/test_coder.py`

**Interfaces:**
- Consumes: `DischargeSummary`, `CodedDiagnosis`, retriever `Callable[[str, int], list[IcdEntry]]`, `llm.complete` signature.
- Produces: `assign_codes(summary: DischargeSummary, retrieve, llm=llm.complete, threshold: float = 0.7) -> list[CodedDiagnosis]`.

- [ ] **Step 1: Failing tests** (inject fake retriever returning fixed candidates and fake llm):
  - llm returns `{"codes": [{"icd_code": "K35.9", "confidence": 0.92}]}` → one `CodedDiagnosis` with `needs_review is False`, description filled from retrieval candidates.
  - llm returns confidence 0.4 → `needs_review is True`.
  - llm returns a code **not in the retrieved candidates** → that code is dropped (never emit unretrieved codes) and, if nothing remains, fall back to top candidate with `confidence=0.5, needs_review=True`.
  - llm returns `{"codes": []}` → same top-candidate fallback with `needs_review=True`.
- [ ] **Step 2: Implement** — query = `summary.primary_diagnosis` (+ secondaries appended); retrieve k=5; prompt lists candidates `code — description`; json_schema `{"codes":[{"icd_code","confidence"}]}`; system: *"Assign ICD-10 codes ONLY from the candidate list. Report your confidence honestly."* Filter to candidates; below `threshold` → `needs_review=True`. `# ponytail: single-query retrieval; per-secondary-diagnosis queries when multi-morbidity accuracy matters.`
- [ ] **Step 3: Run** → PASS. **Step 4: Commit** — `git commit -am "feat: RAG coder with confidence flagging"`

---

### Task 12: Packager (rules + FHIR validation)  *(Wave 2 — parallel)*

**Files:**
- Create: `src/claimguard/agents/packager.py`, `tests/test_packager.py`

**Interfaces:**
- Consumes: `DischargeRecord`, `DischargeSummary`, `list[CodedDiagnosis]`, `ClaimPackage`, `templates.REQUIRED_DOCS`.
- Produces: `package(record, summary, codes) -> ClaimPackage`. Rules, in order: (1) missing required docs → `status="rejected"`, reasons `["missing document: X", ...]`; (2) empty codes → `rejected`, reason `"no ICD codes assigned"`; (3) any `needs_review` code → `status="needs_review"`, reason `"low-confidence code: X"`; (4) else build + validate FHIR R4 Claim → `status="ready"`, `fhir_claim` set.

- [ ] **Step 1: Failing tests** — four tests, one per rule, using the Task 3 `_record()` helper pattern (copy it into this test file — do not import across test modules): missing `preauth_form` → rejected with exact reason; no codes → rejected; one low-confidence code → needs_review and `fhir_claim is None`; happy path → ready and `fhir_claim["resourceType"] == "Claim"` with the ICD code present in `diagnosis`.
- [ ] **Step 2: Implement** — build via `fhir.resources.claim.Claim` with: `status="active"`, `type` CodeableConcept `institutional`, `use="claim"`, `patient` display reference, `created` = discharge_date, `provider` display reference, `priority` CodeableConcept `normal`, `insurance` `[{sequence:1, focal:True, coverage: display ref to policy_number}]`, `diagnosis` = one entry per code (`diagnosisCodeableConcept` with `system="http://hl7.org/fhir/sid/icd-10"`), `supportingInfo` = one entry per document (category `info`, valueString doc name). `fhir_claim = claim.model_dump(mode="json", exclude_none=True)`. Pydantic validation of the Claim model **is** the NHCX-shape gate. `# ponytail: NHCX profile checks = FHIR R4 base validation; add NHCX-specific profile constraints when targeting the real sandbox.`
- [ ] **Step 3: Run** → PASS. **Step 4: Commit** — `git commit -am "feat: packager with pre-submission rejection + FHIR validation"`

---

### Task 13: Submitter simulator  *(Wave 2 — parallel)*

**Files:**
- Create: `src/claimguard/agents/submitter.py`, `tests/test_submitter.py`

**Interfaces:**
- Consumes: `ClaimPackage`, `SubmissionResult`.
- Produces: `submit(package: ClaimPackage, store: dict) -> SubmissionResult`. Deterministic, **no LLM**. Raises `ValueError` unless `package.status == "ready"`. Idempotent: same `record_id` → identical result object from `store`. Simulated adjudication: `h = int(hashlib.sha1(record_id.encode()).hexdigest(), 16) % 10` → 0–6 `"approved"`, 7–8 `"partial"`, 9 `"rejected"`; `submission_id = f"SIM-{record_id}"`; `status="adjudicated"`.

- [ ] **Step 1: Failing tests** — non-ready package raises ValueError; two calls with same package return equal results and store has one entry; outcome distribution over 100 fabricated ready packages contains all three outcomes.
- [ ] **Step 2: Implement** (~20 lines). Run → PASS. **Step 3: Commit** — `git commit -am "feat: deterministic NHCX submission simulator"`

---

### Task 14: Orchestrator + audit log

**Files:**
- Create: `src/claimguard/orchestrator.py`, `tests/test_orchestrator.py`

**Interfaces:**
- Consumes: all four agents, `handoff_timestamps` concept (audit events double as radar timestamps).
- Produces:
  - `AuditEvent = dict` with keys `record_id, step, status ("start"|"ok"|"error"), detail (dict)`.
  - `PipelineDeps(llm, retrieve, store: dict, audit: Callable[[dict], None])` (dataclass).
  - `run_claim(record: DischargeRecord, deps: PipelineDeps) -> dict` returning `{"record_id", "final_status" ("adjudicated"|"rejected"|"needs_review"|"error"), "icd_codes": list[str], "packaging": str, "outcome": str | None}`. Steps: summarize → assign_codes → package → (submit only when ready). Each step: audit `start`, run with **one retry** on exception, audit `ok` (detail = compact result) or `error` then final_status "error". Non-ready package short-circuits with its status; every path is fully audited.

- [ ] **Step 1: Failing tests** — with fake deps (list-appending audit): happy path yields `final_status="adjudicated"` and audit sequence `summarize:start, summarize:ok, code:start, code:ok, package:start, package:ok, submit:start, submit:ok`; missing-doc record stops at package with `final_status="rejected"` and **no** submit events; a summarizer that throws once then succeeds → retried, final ok, audit shows one `error` then `ok`; a summarizer that always throws → `final_status="error"`.
- [ ] **Step 2: Implement** (~70 lines). `# ponytail: linear step list; LangGraph only if Phase 2 negotiation loop outgrows it.`
- [ ] **Step 3: Run** → PASS. **Step 4: Commit** — `git commit -am "feat: plain-python orchestrator with retries + audit"`

---

### Task 15: Integration, edge-case tests, Phase 1 gate, README

**Files:**
- Create: `tests/integration/test_pipeline.py`, `tests/edge_cases/test_case_01_cashless_vs_reimbursement.py`, `tests/edge_cases/test_case_05_missing_document.py`, `tests/edge_cases/test_case_06_low_confidence_code.py`, `README.md`
- Modify: `src/claimguard/eval/runner.py` (wire real pipeline), `src/claimguard/__main__.py` (`eval --pipeline` flag)

**Interfaces:**
- Consumes: everything above.
- Produces: `runner.make_pipeline(retrieve, llm) -> Callable[[dict], dict]` adapting `run_claim` to the eval contract (`{"icd_codes", "packaging"}`); `python -m claimguard eval --pipeline` runs the golden set through the real pipeline.

- [ ] **Step 1: Integration test** — load 3 records from `data/golden` (one per scenario, found via answer keys), build `PipelineDeps` with `icd.InMemoryRetriever` over the real CSV + a scripted fake llm (returns template-correct summarizer/coder JSON keyed by prompt content), run `run_claim`: ready-record reaches `adjudicated`, missing-doc → `rejected` before submit, vague-dx → `needs_review`. Assert the audit trail is replayable (every step has start + terminal event, ordered).
- [ ] **Step 2: Edge-case tests** (§9 cases 1, 5, 6) — case 1: cashless and reimbursement records demand different `REQUIRED_DOCS` sets and both pass packaging when complete; case 5: missing/misnamed document caught pre-submission (misnamed = `"final_bil"` in documents → rejected); case 6: low-confidence code never reaches submitter (assert store stays empty). `# ponytail: remaining §9 cases land with their phases (2/3/4).`
- [ ] **Step 3: Wire eval** — `make_pipeline` + CLI flag; run `python -m claimguard eval --pipeline` with mock provider; report prints (F1 will be near zero on mock — expected; mechanism is what's gated). Add to README: with `LLM_PROVIDER=gemini` + key, the same command produces real numbers; paste whichever numbers were produced into README honestly labeled.
- [ ] **Step 4: Write README.md** — honest story (what it is, what it is not — quote the honesty contract), quickstart (`venv`, `pip install -e .[dev]`, `docker compose up -d`, `python -m claimguard gen-data`, `pytest`, `python -m claimguard eval --pipeline`), architecture sketch, phase status table (0 ✅, 1 ✅, 2–5 pending), known limitations (mock-eval numbers, 60-code ICD subset, simulator not real NHCX).
- [ ] **Step 5: Phase 1 gate** — full `pytest -v` green; run `ruff check src tests` clean. Commit — `git commit -am "feat: integration + edge-case tests, eval pipeline, README (phase 1 gate)"`

---

## Self-review notes

- Spec coverage: scaffold(1), llm(2), models(3), compose/db/api(4), synth+CLI(5), policies(6), ICD+retriever(7), eval(8), NHCX doc+gate(9), agents(10–13), orchestrator(14), integration/edges/README/gate(15). Frontend, Negotiator, Radar, comms: explicitly out of scope per spec.
- Type consistency: `IcdEntry`, `REQUIRED_DOCS`, `ClaimPackage.status` values ("ready"/"rejected"/"needs_review"), eval pipeline contract `{"icd_codes","packaging"}` are each defined once and referenced by exact name in consuming tasks.
- Real-numbers eval (Gemini) is a documented runtime step, not a task dependency — nothing blocks on the API key.
