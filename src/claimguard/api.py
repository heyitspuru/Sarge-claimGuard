import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from claimguard.comms import LANGUAGES, patient_status
from claimguard.compliance_radar import radar

app = FastAPI(title="ClaimGuard")

# CORS for the Vite dev server (frontend/).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

_GOLDEN = Path(__file__).resolve().parents[2] / "data" / "golden"

_BASELINE = {
    "preauth_sla_min": radar.PREAUTH_SLA_MIN,
    "discharge_sla_min": radar.DISCHARGE_SLA_MIN,
    "prebreach_min": radar.PREBREACH_MIN,
}


def _record_index() -> dict[str, str]:
    """record_id -> claim_type for the golden set; falls back to synthetic ids."""
    idx: dict[str, str] = {}
    if _GOLDEN.exists():
        for f in sorted(_GOLDEN.glob("*.json"))[:50]:
            g = json.loads(f.read_text(encoding="utf-8"))
            rec = g.get("record", {})
            idx[rec.get("record_id", f.stem)] = rec.get("claim_type", "cashless")
    if not idx:
        idx = {f"R{i:04d}": ("cashless" if i % 2 else "reimbursement") for i in range(30)}
    return idx


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index():
    return ("<h1>ClaimGuard API</h1><p>Compliance Radar endpoints: "
            "<code>/radar/journeys</code>, <code>/radar/journey/{record_id}</code>. "
            "Patient view: <code>/patient/{record_id}?lang=en|hi|ta</code>. "
            "Dashboard: run the Vite app in <code>frontend/</code>.</p>")


@app.get("/radar/journeys")
def radar_journeys():
    """Summary report per synthetic journey (labeled synthetic)."""
    reports = [
        radar.analyze(radar.generate_journey(rid, ctype)).model_dump()
        for rid, ctype in _record_index().items()
    ]
    reports.sort(key=lambda r: r["pre_submission_delay_min"], reverse=True)
    return {"synthetic": True, "baseline": _BASELINE, "journeys": reports}


@app.get("/radar/journey/{record_id}")
def radar_journey(record_id: str):
    claim_type = _record_index().get(record_id)
    if claim_type is None:
        raise HTTPException(status_code=404, detail=f"unknown record_id {record_id}")
    journey = radar.generate_journey(record_id, claim_type)
    return {
        "synthetic": True,
        "journey": journey.model_dump(),
        "report": radar.analyze(journey).model_dump(),
        "baseline": _BASELINE,
    }


@app.get("/patient/{record_id}")
def patient_view(record_id: str, lang: str = "en", outcome: str | None = None,
                 at: int | None = None):
    """What the patient sees: plain-language status, ETA, and the messages sent."""
    claim_type = _record_index().get(record_id)
    if claim_type is None:
        raise HTTPException(status_code=404, detail=f"unknown record_id {record_id}")
    if lang not in LANGUAGES:
        raise HTTPException(status_code=400,
                            detail=f"unsupported lang {lang}; supported: {list(LANGUAGES)}")
    journey = radar.generate_journey(record_id, claim_type)
    report = radar.analyze(journey)
    status = patient_status(journey, report, language=lang, now_minutes=at, outcome=outcome)
    return {"synthetic": True, "languages": list(LANGUAGES), "status": status.model_dump()}
