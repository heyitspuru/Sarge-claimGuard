"""Back-translation check for the patient-copy catalogs.

`unsafe_terms()` proves a NEGATIVE property (no blocklisted phrase appears). Meaning
drift is a positive property it cannot see, and drift is the one failure class that is
clinically dangerous rather than merely embarrassing. This module closes that gap the
way the field does: translate each non-English string back to English **blind** — the
back-translator never sees the original — then judge the round trip against the source.

Deliberately a ONE-SHOT artifact generator, not a CI gate. The catalogs are static
constants, not runtime-generated output, so there is no drift channel between commits;
a permanent gate would re-prove the same fact forever at real API cost. The recurring
protection is instead `tests/test_translation_artifact.py`, which is offline and fails
if a string changes without being revalidated. See docs/TRANSLATION_VALIDATION.md.

Run: python -m claimguard validate-translations     (~4 provider requests)
"""

import hashlib
import json
from collections.abc import Callable
from pathlib import Path

from claimguard.comms.messages import EVENTS
from claimguard.comms.status import _STAGE_COPY

ARTIFACT = Path("docs/TRANSLATION_BACKCHECK.md")
SIDECAR = Path("data/translation_checked.json")

_BACK_TRANSLATE_SYSTEM = (
    "You are a professional translator producing a BLIND back-translation for clinical "
    "material validation. You will be given numbered strings in a source language. "
    "Render each into plain English as literally as the grammar allows — mirror the "
    "register and word choice actually present, do NOT smooth, improve, or guess at an "
    "intended meaning. Your output is used to detect translation drift, so a clumsy "
    "faithful rendering is far more useful than a fluent approximation."
)

_JUDGE_SYSTEM = (
    "You are validating patient-facing clinical translations. For each pair you receive "
    "the ENGLISH SOURCE and a BLIND BACK-TRANSLATION of the deployed translation. Judge "
    "only whether the round trip preserved MEANING and REGISTER that matter to a patient: "
    "the factual claim, who is doing what next, whether any action is demanded of the "
    "patient, and whether the tone stayed calm and non-alarming. Ignore wording and "
    "grammatical differences that carry no difference in meaning."
)


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def collect_strings() -> list[dict]:
    """Every non-English string with its English source, as flat reviewable rows."""
    rows: list[dict] = []
    for event, by_lang in sorted(EVENTS.items()):
        for lang, text in sorted(by_lang.items()):
            if lang == "en":
                continue
            rows.append({"key": f"event:{event}", "lang": lang, "text": text,
                         "source": by_lang["en"]})
    for stage, by_lang in sorted(_STAGE_COPY.items()):
        for lang, pair in sorted(by_lang.items()):
            if lang == "en":
                continue
            for field, idx in (("happening", 0), ("next_step", 1)):
                rows.append({"key": f"stage:{stage}:{field}", "lang": lang,
                             "text": pair[idx], "source": by_lang["en"][idx]})
    return rows


def back_translate(rows: list[dict], lang: str, llm: Callable) -> list[str]:
    """Blind back-translation of one language's strings — the source is NEVER shown."""
    numbered = "\n".join(f"{i + 1}. {r['text']}" for i, r in enumerate(rows))
    result = llm(
        f"Back-translate these {len(rows)} strings into English.\n\n{numbered}",
        system=_BACK_TRANSLATE_SYSTEM,
        tier="reasoning",
        json_schema={
            "type": "object",
            "properties": {"translations": {"type": "array", "items": {"type": "string"}}},
            "required": ["translations"],
        },
    )
    out = result.get("translations", []) if isinstance(result, dict) else []
    # Pad rather than raise: a short response should degrade to "unchecked" rows in the
    # artifact, not throw away the strings that did come back.
    return list(out) + [""] * (len(rows) - len(out))


def judge_equivalence(rows: list[dict], backs: list[str], llm: Callable) -> list[dict]:
    """Score each round trip. Returns one verdict dict per row, order preserved."""
    pairs = "\n\n".join(
        f"{i + 1}.\nENGLISH SOURCE: {r['source']}\nBACK-TRANSLATION: {b or '(missing)'}"
        for i, (r, b) in enumerate(zip(rows, backs))
    )
    result = llm(
        f"Judge these {len(rows)} round trips.\n\n{pairs}",
        system=_JUDGE_SYSTEM,
        tier="reasoning",
        json_schema={
            "type": "object",
            "properties": {"verdicts": {"type": "array", "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "equivalent": {"type": "boolean"},
                    "severity": {"type": "string"},  # none | minor | major
                    "note": {"type": "string"},
                },
                "required": ["index", "equivalent", "severity", "note"],
            }}},
            "required": ["verdicts"],
        },
    )
    verdicts = result.get("verdicts", []) if isinstance(result, dict) else []
    by_index = {v.get("index"): v for v in verdicts if isinstance(v, dict)}
    # Unjudged rows are reported as unknown, never silently as passing.
    return [by_index.get(i + 1, {"equivalent": None, "severity": "unchecked",
                                 "note": "no verdict returned"})
            for i in range(len(rows))]


def _flag(verdict: dict) -> str:
    severity = (verdict.get("severity") or "").lower()
    if verdict.get("equivalent") is None:
        return "UNCHECKED"
    if severity == "major":
        return "DRIFT — review"
    if severity == "minor":
        return "minor"
    return "ok"


def render_artifact(checked: list[dict]) -> str:
    langs = sorted({r["lang"] for r in checked})
    drift = [r for r in checked if r["flag"].startswith("DRIFT")]
    unchecked = [r for r in checked if r["flag"] == "UNCHECKED"]

    out = [
        "# Translation back-check",
        "",
        "Blind back-translation of every non-English patient-facing string, judged against",
        "its English source. Generated by `python -m claimguard validate-translations`.",
        "",
        "**What this does and does not establish.** It detects *meaning drift* — the",
        "dangerous failure class. It does **not** establish warmth, register, dignity or",
        "reading level, because the judge is itself a model and is not a native speaker.",
        "This is a screen that raises the floor, never a sign-off. Real-world use still",
        "requires WHO-style validation with human forward/back translators and patient",
        "cognitive interviews — see `docs/TRANSLATION_VALIDATION.md`.",
        "",
        f"- Strings checked: **{len(checked)}** across {', '.join(langs)}",
        f"- Flagged for human review: **{len(drift)}**",
        f"- Unchecked (no verdict returned): **{len(unchecked)}**",
        "",
    ]
    if drift:
        out += ["## Flagged for human review first", ""]
        for r in drift:
            out += [f"- `{r['key']}` ({r['lang']}) — {r['note']}"]
        out += [""]

    for lang in langs:
        out += [f"## {lang}", "",
                "| key | English source | blind back-translation | verdict |",
                "|---|---|---|---|"]
        for r in (x for x in checked if x["lang"] == lang):
            src = r["source"].replace("|", "\\|")
            back = (r["back"] or "_(none)_").replace("|", "\\|")
            out += [f"| `{r['key']}` | {src} | {back} | {r['flag']} |"]
        out += [""]
    return "\n".join(out)


def run_backcheck(llm: Callable, *, artifact: Path = ARTIFACT,
                  sidecar: Path = SIDECAR) -> dict:
    """Back-translate, judge, and write both the review artifact and the hash sidecar."""
    rows = collect_strings()
    checked: list[dict] = []
    for lang in sorted({r["lang"] for r in rows}):
        subset = [r for r in rows if r["lang"] == lang]
        backs = back_translate(subset, lang, llm)
        verdicts = judge_equivalence(subset, backs, llm)
        for row, back, verdict in zip(subset, backs, verdicts):
            checked.append(row | {"back": back, "flag": _flag(verdict),
                                  "note": verdict.get("note", "")})

    artifact = Path(artifact)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(render_artifact(checked), encoding="utf-8")

    sidecar = Path(sidecar)
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(json.dumps({
        "_note": "sha256 of every validated string; tests/test_translation_artifact.py "
                 "fails if a catalog string changes without re-running the back-check.",
        "hashes": {f"{r['lang']}:{r['key']}": text_hash(r["text"]) for r in checked},
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "checked": len(checked),
        "flagged": sum(1 for r in checked if r["flag"].startswith("DRIFT")),
        "unchecked": sum(1 for r in checked if r["flag"] == "UNCHECKED"),
        "artifact": str(artifact),
        "sidecar": str(sidecar),
    }
