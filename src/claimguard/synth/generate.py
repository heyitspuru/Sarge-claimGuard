"""Synthetic discharge-record generator.

Each record instantiates one clinical template (see templates.py) with
randomized demographics, dates, amounts, and one of three scenarios:
"normal" (fully compliant -> "ready"), "missing_doc" (one required document
dropped -> "rejected"), "vague_dx" (diagnosis text swapped for a vague
placeholder -> "needs_review"). Determinism comes from a single
random.Random(seed) + Faker.seed(seed) pair threaded through the whole run.
"""

import argparse
import json
import random
from datetime import date, timedelta
from pathlib import Path

from faker import Faker

from claimguard.models import AnswerKey, DischargeRecord, Insurance, Patient
from claimguard.synth import templates

# Deliberately non-existent insurer codes. The originals were abbreviations that collided
# with real Indian insurance entities, and this repo publishes invented policy *wordings*
# under whatever name sits here — a reader could reasonably have taken those for real
# policy terms. Names that announce themselves as synthetic cannot be misread, and that
# matches what the rest of the project claims about itself.
INSURERS = [("SYNTH1", "PLANA"), ("SYNTH2", "PLANB"), ("SYNTH3", "PLANC")]
SUM_INSURED_OPTIONS = [500000, 1000000]

# Specialty-appropriate age bands; falls back to DEFAULT_AGE_BAND otherwise.
AGE_BANDS = {
    "ophthalmology": (55, 85),
    "orthopedics": (60, 90),
    "obstetrics": (18, 40),
    "cardiology": (40, 80),
    "endocrinology": (25, 70),
    "neurology": (45, 85),
}
DEFAULT_AGE_BAND = (15, 75)

_SCENARIO_TO_PACKAGING = {
    "normal": "ready",
    "missing_doc": "rejected",
    "vague_dx": "needs_review",
}


def make_record(i: int, rng: random.Random, faker) -> tuple[DischargeRecord, AnswerKey]:
    record_id = f"R{i:04d}"
    template = rng.choice(templates.TEMPLATES)
    weights = template["scenario_weights"]
    scenario = rng.choices(list(weights), weights=list(weights.values()))[0]
    claim_type = rng.choice(template["claim_types"])
    specialty = template["specialty"]

    sex = "F" if specialty == "obstetrics" else rng.choice(["M", "F"])
    lo, hi = AGE_BANDS.get(specialty, DEFAULT_AGE_BAND)
    age = rng.randint(lo, hi)

    admission_date = date.today() - timedelta(days=rng.randint(1, 90))
    discharge_date = admission_date + timedelta(days=rng.randint(1, 8))

    required = templates.REQUIRED_DOCS[claim_type]
    if scenario == "missing_doc":
        drop = rng.choice(required)
        documents = [d for d in required if d != drop]
    else:
        documents = list(required)

    diagnosis_text = (
        rng.choice(templates.VAGUE_DX) if scenario == "vague_dx" else template["diagnosis_text"]
    )

    insurer_id, plan_id = rng.choice(INSURERS)
    sum_insured = rng.choice(SUM_INSURED_OPTIONS)
    band_lo, band_hi = template["claim_band"]
    claimed_amount = rng.randrange(band_lo, band_hi)

    record = DischargeRecord(
        record_id=record_id,
        patient=Patient(
            name=faker.name(),
            age=age,
            sex=sex,
            abha_id=faker.numerify("##-####-####-####"),
        ),
        admission_date=admission_date.isoformat(),
        discharge_date=discharge_date.isoformat(),
        claim_type=claim_type,
        specialty=specialty,
        diagnosis_text=diagnosis_text,
        procedures=list(template["procedures"]),
        medications=list(template["medications"]),
        clinical_notes=rng.choice(template["notes"]),
        documents=documents,
        insurance=Insurance(
            insurer_id=insurer_id,
            plan_id=plan_id,
            policy_number=faker.bothify("POL#######"),
            sum_insured=sum_insured,
            claimed_amount=claimed_amount,
        ),
    )
    answer_key = AnswerKey(
        record_id=record_id,
        icd_codes=template["icd_codes"],
        expected_packaging=_SCENARIO_TO_PACKAGING[scenario],
    )
    return record, answer_key


def generate(n: int, seed: int, out_dir: Path, golden_n: int) -> tuple[int, int]:
    rng = random.Random(seed)
    Faker.seed(seed)
    faker = Faker("en_IN")

    synth_dir = Path(out_dir) / "synthetic"
    golden_dir = Path(out_dir) / "golden"
    synth_dir.mkdir(parents=True, exist_ok=True)
    golden_dir.mkdir(parents=True, exist_ok=True)

    n_syn = 0
    n_gold = 0
    for i in range(n):
        record, answer_key = make_record(i, rng, faker)
        (synth_dir / f"{record.record_id}.json").write_text(
            record.model_dump_json(indent=2), encoding="utf-8"
        )
        n_syn += 1
        if i < golden_n:
            payload = {"record": record.model_dump(), "answer_key": answer_key.model_dump()}
            (golden_dir / f"{record.record_id}.json").write_text(
                json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            n_gold += 1

    return n_syn, n_gold


def _cmd_gen_data(args: argparse.Namespace) -> None:
    n_syn, n_gold = generate(
        n=args.n, seed=args.seed, out_dir=Path(args.out_dir), golden_n=args.golden
    )
    print(f"generated {n_syn} synthetic records, {n_gold} golden records -> {args.out_dir}")


def add_subparser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("gen-data", help="Generate synthetic discharge records")
    p.add_argument("--n", type=int, default=500)
    p.add_argument("--golden", type=int, default=200)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--out-dir", type=str, default="data")
    p.set_defaults(func=_cmd_gen_data)
