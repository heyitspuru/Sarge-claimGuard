"""Patient-facing "what's happening / what's next" view.

Same template discipline as messages.py — the patient never sees generated prose.
Internal stage names (summary/code/package/submit) mean nothing to a patient, so
each one maps to a plain sentence about their claim, not about our pipeline.
"""

from claimguard.comms.messages import OUTCOME_EVENT, build_message, plan_notifications
from claimguard.compliance_radar.radar import DISCHARGE_SLA_MIN, STAGE_ORDER
from claimguard.models import Journey, PatientStatus, RadarReport

# stage -> {lang: (what's happening, what's next)}
_STAGE_COPY = {
    "order": {
        "en": ("Your discharge has been started.",
               "Your care team is preparing your summary and your medicines."),
        "hi": ("आपकी छुट्टी की प्रक्रिया शुरू हो गई है।",
               "आपकी टीम आपका सारांश और दवाइयाँ तैयार कर रही है।"),
        "ta": ("உங்கள் டிஸ்சார்ஜ் நடைமுறை தொடங்கிவிட்டது.",
               "உங்கள் சுருக்கமும் மருந்துகளும் தயாராகி வருகின்றன."),
    },
    "summary": {
        "en": ("Your discharge summary is being written up.",
               "Next, your treatment details are prepared for your insurer."),
        "hi": ("आपका डिस्चार्ज सारांश तैयार किया जा रहा है।",
               "इसके बाद, आपके इलाज का विवरण बीमा कंपनी के लिए तैयार किया जाएगा।"),
        "ta": ("உங்கள் டிஸ்சார்ஜ் சுருக்கம் தயாராகி வருகிறது.",
               "அடுத்து, சிகிச்சை விவரங்கள் காப்பீட்டு நிறுவனத்திற்குத் தயாரிக்கப்படும்."),
    },
    "code": {
        "en": ("Your treatment details are being prepared for your insurer.",
               "Next, your claim is put together and checked."),
        "hi": ("आपके इलाज का विवरण बीमा कंपनी के लिए तैयार किया जा रहा है।",
               "इसके बाद, आपका क्लेम तैयार करके जाँचा जाएगा।"),
        "ta": ("சிகிச்சை விவரங்கள் காப்பீட்டு நிறுவனத்திற்குத் தயாராகி வருகின்றன.",
               "அடுத்து, உங்கள் க்ளெய்ம் தயாரிக்கப்பட்டு சரிபார்க்கப்படும்."),
    },
    "package": {
        "en": ("Your claim is being put together and checked.",
               "Next, it goes to your insurer."),
        "hi": ("आपका क्लेम तैयार करके जाँचा जा रहा है।",
               "इसके बाद, यह आपकी बीमा कंपनी को भेजा जाएगा।"),
        "ta": ("உங்கள் க்ளெய்ம் தயாரிக்கப்பட்டு சரிபார்க்கப்படுகிறது.",
               "அடுத்து, அது காப்பீட்டு நிறுவனத்திற்கு அனுப்பப்படும்."),
    },
    "submit": {
        "en": ("Your claim is with your insurer.",
               "They are reviewing it. We will message you as soon as there is news."),
        "hi": ("आपका क्लेम आपकी बीमा कंपनी के पास है।",
               "वे इसकी समीक्षा कर रहे हैं। जानकारी मिलते ही हम आपको बता देंगे।"),
        "ta": ("உங்கள் க்ளெய்ம் காப்பீட்டு நிறுவனத்திடம் உள்ளது.",
               "அவர்கள் பரிசீலித்து வருகின்றனர். தகவல் கிடைத்தவுடன் தெரிவிப்போம்."),
    },
    "decision": {
        "en": ("Your insurer has responded on your claim.",
               "Your hospital team is going through it and will explain what happens next."),
        "hi": ("आपकी बीमा कंपनी ने आपके क्लेम पर जवाब दिया है।",
               "अस्पताल की टीम इसे देख रही है और आगे की प्रक्रिया समझाएगी।"),
        "ta": ("உங்கள் க்ளெய்ம் குறித்து காப்பீட்டு நிறுவனம் பதிலளித்துள்ளது.",
               "மருத்துவமனைக் குழு அதைப் பார்த்து, அடுத்து என்ன என்பதை விளக்கும்."),
    },
}


def _copy(stage: str, language: str) -> tuple[str, str]:
    by_lang = _STAGE_COPY[stage]
    return by_lang.get(language) or by_lang["en"]


def patient_status(
    journey: Journey,
    report: RadarReport,
    *,
    language: str = "en",
    now_minutes: int | None = None,
    outcome: str | None = None,
) -> PatientStatus:
    """Where the claim is right now, in the patient's words and language.

    `now_minutes` defaults to the end of the journey (the whole timeline has run).
    Pass an earlier value to see what the patient would have been told mid-claim.
    """
    at = {s.stage: s.at_minutes for s in journey.stages}
    end = max(at.values()) if at else 0
    now = end if now_minutes is None else now_minutes

    reached = [s for s in STAGE_ORDER if s in at and at[s] <= now]
    stage = reached[-1] if reached else "order"
    upcoming = [s for s in STAGE_ORDER if s in at and at[s] > now]

    happening, next_step = _copy(stage, language)
    # ETA is to the next real handoff; once the insurer has responded there is
    # nothing left for us to promise a time on.
    eta = at[upcoming[0]] - now if upcoming else None

    # After a decision the generic "next" line is replaced by the outcome copy,
    # so the patient never sees a vaguer message than the one they were sent.
    if stage == "decision" and outcome in OUTCOME_EVENT:
        next_step = build_message(journey.record_id, OUTCOME_EVENT[outcome], language, at[stage]).text

    return PatientStatus(
        record_id=journey.record_id,
        language=language,
        stage=stage,
        happening=happening,
        next_step=next_step,
        eta_min=eta,
        sla_min=DISCHARGE_SLA_MIN,
        elapsed_min=now,
        messages=plan_notifications(journey, report, language=language, outcome=outcome),
    )
