"""Patient communication layer — plain-language, multilingual status updates.

DELIBERATELY TEMPLATE-BASED, NOT LLM-GENERATED. Patient-facing bad news is the
one place a stochastic generator is the wrong tool: CLAUDE.md lists "a message
that states bad news in an alarming rather than human-safe way" as a test
failure, not a judgment call. Templates are reviewed once and auditable forever;
a prompt is neither. Cost of the safety property: translations are hand-written,
so adding a language is a PR, not a config flag. That is the correct trade here.

Copy rules every template obeys (enforced by `unsafe_terms`, tested in
tests/test_comms.py):
  1. No alarming/finality words ("denied", "rejected", "failed", "urgent").
  2. Bad news always arrives WITH the next step and who is already handling it.
  3. Never blame or alarm the patient; never imply they must act immediately.
"""

from claimguard.compliance_radar.radar import PREBREACH_MIN
from claimguard.models import Journey, PatientMessage, RadarReport

LANGUAGES = ("en", "hi", "ta")

# event -> {lang: text}. Keep every language in lockstep: a new event needs all
# three, or `build_message` falls back to English rather than emitting a blank.
EVENTS = {
    # Fires at ORDER time, not approval — the whole point of the trigger is that
    # the pharmacy starts preparing while the claim is still moving (spec §6/E).
    "pharmacy_ready": {
        "en": (
            "Your discharge medicines are being prepared now. "
            "The hospital team will tell you when they are ready to collect."
        ),
        "hi": (
            "आपकी छुट्टी की दवाइयाँ अभी तैयार की जा रही हैं। "
            "अस्पताल की टीम आपको बता देगी कि उन्हें कब लेना है।"
        ),
        "ta": (
            "உங்கள் வீட்டுக்குச் செல்லும் மருந்துகள் இப்போது தயாராகி வருகின்றன. "
            "எப்போது பெற்றுக்கொள்ளலாம் என்பதை மருத்துவமனைக் குழு தெரிவிக்கும்."
        ),
    },
    "claim_submitted": {
        "en": (
            "Your claim has been sent to your insurer. "
            "We will message you as soon as there is an update. Nothing is needed from you."
        ),
        "hi": (
            "आपका क्लेम आपकी बीमा कंपनी को भेज दिया गया है। "
            "जैसे ही कोई जानकारी मिलेगी, हम आपको बता देंगे। आपको अभी कुछ नहीं करना है।"
        ),
        "ta": (
            "உங்கள் க்ளெய்ம் காப்பீட்டு நிறுவனத்திற்கு அனுப்பப்பட்டுள்ளது. "
            "தகவல் கிடைத்தவுடன் உங்களுக்குத் தெரிவிப்போம். இப்போது உங்களிடமிருந்து எதுவும் தேவையில்லை."
        ),
    },
    # Internal SLA alert surfaced to the patient as reassurance, never as a warning.
    "sla_prebreach": {
        "en": (
            "Your claim paperwork is still being completed. "
            "The hospital team has it as a priority and is staying with it."
        ),
        "hi": (
            "आपके क्लेम के कागज़ात अभी पूरे किए जा रहे हैं। "
            "अस्पताल की टीम इसे प्राथमिकता पर रखकर देख रही है।"
        ),
        "ta": (
            "உங்கள் க்ளெய்ம் ஆவணங்கள் இன்னும் தயாராகி வருகின்றன. "
            "மருத்துவமனைக் குழு இதற்கு முன்னுரிமை அளித்துக் கவனித்து வருகிறது."
        ),
    },
    "claim_approved": {
        "en": (
            "Good news — your insurer has approved your claim. "
            "The hospital team will walk you through the final paperwork."
        ),
        "hi": (
            "अच्छी खबर — आपकी बीमा कंपनी ने आपका क्लेम मंज़ूर कर दिया है। "
            "अस्पताल की टीम आपको बाकी कागज़ी काम समझा देगी।"
        ),
        "ta": (
            "நல்ல செய்தி — உங்கள் காப்பீட்டு நிறுவனம் க்ளெய்மை ஏற்றுக்கொண்டுள்ளது. "
            "மீதமுள்ள ஆவண நடைமுறைகளை மருத்துவமனைக் குழு விளக்கும்."
        ),
    },
    # "Queried" is the copy the spec singles out (§6 Phase 4 exit criteria):
    # routine framing, someone already handling it, no action asked of the patient.
    "claim_queried": {
        "en": (
            "An update on your claim: your insurer has asked for a few more details "
            "before they finish reviewing it. This is a routine step and the hospital "
            "team is already taking care of it. Nothing is needed from you right now, "
            "and we will message you as soon as there is news."
        ),
        "hi": (
            "आपके क्लेम की जानकारी: समीक्षा पूरी करने से पहले बीमा कंपनी ने कुछ और "
            "विवरण माँगे हैं। यह एक सामान्य प्रक्रिया है और अस्पताल की टीम इसे संभाल रही है। "
            "अभी आपको कुछ करने की ज़रूरत नहीं है, और जानकारी मिलते ही हम आपको बता देंगे।"
        ),
        "ta": (
            "உங்கள் க்ளெய்ம் குறித்த தகவல்: பரிசீலனையை முடிப்பதற்கு முன் காப்பீட்டு நிறுவனம் "
            "சில கூடுதல் விவரங்களைக் கேட்டுள்ளது. இது வழக்கமான நடைமுறை; மருத்துவமனைக் குழு "
            "இதைக் கவனித்து வருகிறது. இப்போது உங்களிடமிருந்து எதுவும் தேவையில்லை, "
            "தகவல் கிடைத்தவுடன் தெரிவிப்போம்."
        ),
    },
    "claim_partial": {
        "en": (
            "An update on your claim: your insurer has covered part of the amount under "
            "your policy. The hospital team is reading their reason against your policy "
            "document and will go through the options with you, including asking them to "
            "look at it again."
        ),
        "hi": (
            "आपके क्लेम की जानकारी: बीमा कंपनी ने आपकी पॉलिसी के तहत राशि का एक हिस्सा "
            "कवर किया है। अस्पताल की टीम उनके कारण को आपकी पॉलिसी के साथ मिलाकर देख रही है "
            "और आपके साथ आगे के विकल्पों पर बात करेगी, जिसमें दोबारा समीक्षा माँगना भी शामिल है।"
        ),
        "ta": (
            "உங்கள் க்ளெய்ம் குறித்த தகவல்: உங்கள் பாலிசியின் கீழ் காப்பீட்டு நிறுவனம் "
            "தொகையின் ஒரு பகுதியை ஈடுசெய்துள்ளது. மருத்துவமனைக் குழு அவர்களின் காரணத்தை "
            "உங்கள் பாலிசியுடன் ஒப்பிட்டுப் பார்த்து, மறுபரிசீலனை கோருவது உட்பட அடுத்த "
            "வழிகளை உங்களுடன் பேசும்."
        ),
    },
    # The hardest copy in the product: honest about the outcome, never final-sounding,
    # and the next step lands in the same breath as the news.
    "claim_rejected": {
        "en": (
            "An update on your claim: your insurer has not covered this claim under your "
            "policy. The hospital team is reviewing their reason against your policy "
            "document and will explain what it means and what can be done next, including "
            "asking them to reconsider. You do not have to sort this out on your own."
        ),
        "hi": (
            "आपके क्लेम की जानकारी: बीमा कंपनी ने इस क्लेम को आपकी पॉलिसी के तहत कवर "
            "नहीं किया है। अस्पताल की टीम उनके कारण को आपकी पॉलिसी के साथ मिलाकर देख रही है "
            "और आपको समझाएगी कि इसका क्या मतलब है और आगे क्या किया जा सकता है, जिसमें "
            "दोबारा समीक्षा माँगना भी शामिल है। यह सब आपको अकेले नहीं संभालना है।"
        ),
        "ta": (
            "உங்கள் க்ளெய்ம் குறித்த தகவல்: உங்கள் பாலிசியின் கீழ் இந்தக் க்ளெய்மை காப்பீட்டு "
            "நிறுவனம் ஈடுசெய்யவில்லை. மருத்துவமனைக் குழு அவர்களின் காரணத்தை உங்கள் "
            "பாலிசியுடன் ஒப்பிட்டுப் பார்த்து, இதன் பொருள் என்ன, அடுத்து என்ன செய்யலாம் "
            "என்பதை விளக்கும் — மறுபரிசீலனை கோருவதும் அதில் அடங்கும். "
            "இதை நீங்கள் தனியாகச் சமாளிக்க வேண்டியதில்லை."
        ),
    },
}

# §9-4: when the patient has died, every template above is wrong — they address the
# patient directly and talk about their discharge and medicines. These replace them
# wholesale for the compassionate path. The recipient is the family, the register is
# quieter, and the claim is never the first thing said.
COMPASSIONATE_EVENTS = {
    "condolence_hold": {
        "en": (
            "We are so sorry for your loss. The hospital team will take care of the "
            "insurance paperwork for you. Nothing is needed from you right now, and "
            "someone will contact you when you are ready."
        ),
        "hi": (
            "आपकी क्षति के लिए हमें गहरा दुःख है। बीमा से जुड़े कागज़ात का काम अस्पताल "
            "की टीम संभाल लेगी। अभी आपको कुछ नहीं करना है; जब आप तैयार होंगे, कोई आपसे "
            "संपर्क करेगा।"
        ),
        "ta": (
            "உங்கள் இழப்பிற்கு நாங்கள் ஆழ்ந்த வருத்தம் தெரிவித்துக் கொள்கிறோம். "
            "காப்பீட்டு ஆவணப் பணிகளை மருத்துவமனைக் குழு கவனித்துக் கொள்ளும். "
            "இப்போது உங்களிடமிருந்து எதுவும் தேவையில்லை; நீங்கள் தயாராகும்போது "
            "எங்களில் ஒருவர் தொடர்பு கொள்வார்."
        ),
    },
    "claim_settled_family": {
        "en": (
            "The hospital team has completed the insurance paperwork on your behalf. "
            "If anything is still outstanding, they will explain it to you directly and "
            "help you through it. Please take the time you need."
        ),
        "hi": (
            "अस्पताल की टीम ने आपकी ओर से बीमा के कागज़ात पूरे कर दिए हैं। यदि कुछ बाकी "
            "रह गया है, तो वे आपको स्वयं समझाएँगे और आपकी मदद करेंगे। आप जितना समय "
            "चाहें, ले सकते हैं।"
        ),
        "ta": (
            "உங்கள் சார்பாக காப்பீட்டு ஆவணப் பணிகளை மருத்துவமனைக் குழு முடித்துள்ளது. "
            "ஏதேனும் நிலுவையில் இருந்தால், அவர்களே உங்களுக்கு விளக்கி உதவுவார்கள். "
            "உங்களுக்குத் தேவையான நேரத்தை எடுத்துக் கொள்ளுங்கள்."
        ),
    },
}

# Advocacy narrative (see advocacy.py). Resolved-then-reported with a visible seam: an
# immediate lead so the patient is never left in silence, then the full story — naming
# the real clause — once the appeal is actually filed.
ADVOCACY_EVENTS = {
    # The lead. Sent the moment a decision lands, before we know how it will go.
    "advocacy_reviewing": {
        "en": (
            "Your insurer has come back with a question about part of your claim. "
            "Your hospital team is already checking it against your policy — this is a "
            "normal step and it is being handled for you. Nothing is needed from you, "
            "and we will tell you what we find."
        ),
        "hi": (
            "आपके क्लेम के एक हिस्से को लेकर बीमा कंपनी ने सवाल उठाया है। अस्पताल की "
            "टीम इसे आपकी पॉलिसी के साथ मिलाकर देख रही है — यह एक सामान्य प्रक्रिया है "
            "और इसे आपके लिए संभाला जा रहा है। आपको कुछ नहीं करना है; जो पता चलेगा, "
            "हम आपको बताएँगे।"
        ),
        "ta": (
            "உங்கள் க்ளெய்மின் ஒரு பகுதி குறித்து காப்பீட்டு நிறுவனம் கேள்வி "
            "எழுப்பியுள்ளது. மருத்துவமனைக் குழு அதை உங்கள் பாலிசியுடன் ஒப்பிட்டுப் "
            "பார்த்து வருகிறது — இது வழக்கமான நடைமுறை, உங்களுக்காக இது "
            "கவனிக்கப்படுகிறது. உங்களிடமிருந்து எதுவும் தேவையில்லை; தெரிந்தவுடன் "
            "தெரிவிப்போம்."
        ),
    },
    # The full story. Names the real clause the appeal rests on.
    "advocacy_filed": {
        "en": (
            "We have written back to your insurer on your behalf. Their decision applied "
            "a limit in your policy that we do not think applies to your treatment, and "
            "we have asked them to look again — pointing to the part of your own policy "
            "that provides cover. We will tell you as soon as they reply."
        ),
        "hi": (
            "हमने आपकी ओर से बीमा कंपनी को जवाब भेज दिया है। उनके फैसले में पॉलिसी की "
            "एक सीमा लगाई गई है, जो हमारे विचार से आपके इलाज पर लागू नहीं होती, इसलिए "
            "हमने उन्हें दोबारा देखने के लिए कहा है — आपकी अपनी पॉलिसी के उस हिस्से का "
            "हवाला देते हुए जो कवर देता है। उनका जवाब आते ही हम आपको बताएँगे।"
        ),
        "ta": (
            "உங்கள் சார்பாக காப்பீட்டு நிறுவனத்திற்கு நாங்கள் பதில் அனுப்பியுள்ளோம். "
            "அவர்களின் முடிவில் பாலிசியில் உள்ள ஒரு வரம்பு பயன்படுத்தப்பட்டுள்ளது; அது "
            "உங்கள் சிகிச்சைக்குப் பொருந்தாது என்று நாங்கள் கருதுகிறோம். எனவே உங்கள் "
            "பாலிசியில் பாதுகாப்பு அளிக்கும் பகுதியைச் சுட்டிக்காட்டி, மறுபரிசீலனை "
            "செய்யக் கோரியுள்ளோம். அவர்கள் பதிலளித்தவுடன் தெரிவிப்போம்."
        ),
    },
    # The honest no. Hardest to write, and the one that makes the others credible.
    "advocacy_no_valid_appeal": {
        "en": (
            "We have gone through your policy carefully. On this point your insurer is "
            "applying a term that genuinely is part of your policy, so challenging it "
            "would not be honest and would not help you. Your hospital team will go "
            "through what this means for you and what options are left — you will not "
            "be left to work it out alone."
        ),
        "hi": (
            "हमने आपकी पॉलिसी को ध्यान से देखा है। इस बिंदु पर बीमा कंपनी जो शर्त लगा "
            "रही है, वह वास्तव में आपकी पॉलिसी का हिस्सा है, इसलिए उसे चुनौती देना न तो "
            "सही होगा और न ही इससे आपको कोई लाभ होगा। अस्पताल की टीम आपको समझाएगी कि "
            "इसका आपके लिए क्या मतलब है और आगे क्या विकल्प बचे हैं — यह सब आपको अकेले "
            "नहीं सुलझाना पड़ेगा।"
        ),
        "ta": (
            "உங்கள் பாலிசியை நாங்கள் கவனமாகப் பரிசீலித்தோம். இந்த விஷயத்தில் காப்பீட்டு "
            "நிறுவனம் பயன்படுத்தும் விதி உண்மையிலேயே உங்கள் பாலிசியின் ஒரு பகுதி; "
            "எனவே அதை எதிர்ப்பது நேர்மையாகவும் இருக்காது, உங்களுக்கு உதவவும் செய்யாது. "
            "இதன் பொருள் என்ன, இன்னும் என்ன வழிகள் உள்ளன என்பதை மருத்துவமனைக் குழு "
            "உங்களுடன் பேசும் — இதை நீங்கள் தனியாகச் சமாளிக்க வேண்டியதில்லை."
        ),
    },
}

OUTCOME_EVENT = {
    "approved": "claim_approved",
    "queried": "claim_queried",
    "partial": "claim_partial",
    "rejected": "claim_rejected",
}

# Words that make a patient feel judged, panicked, or out of options. Per-language
# because you cannot lint Hindi copy with an English blocklist.
_UNSAFE = {
    # Phrases, not bare words, where the bare word has innocent uses: "final
    # paperwork" is fine, "the decision is final" is not.
    "en": (
        "denied", "denial", "rejected", "rejection", "failed", "failure", "invalid",
        "problem", "urgent", "immediately", "unfortunately", "sorry", "you must",
        "your fault", "no longer", "cannot be", "is final", "nothing more can",
    ),
    "hi": ("अस्वीकार", "इनकार", "खारिज", "समस्या", "तुरंत", "दुर्भाग्य", "असफल", "गलती"),
    "ta": ("நிராகரி", "மறுக்க", "பிரச்சனை", "உடனடி", "துரதிர்ஷ்ட", "தோல்வி", "தவறு"),
}


# Register is context-dependent, and a single blocklist gets this wrong. "Sorry" in
# claim copy is corporate deflection ("Sorry, your claim was denied"); in condolence
# copy it is basic decency and its ABSENCE would be the defect. These terms are
# therefore permitted only on the compassionate path.
_CONDOLENCE_ALLOWED = {
    "en": {"sorry"},
    "hi": set(),
    "ta": set(),
}


def unsafe_terms(text: str, language: str = "en", context: str = "claim") -> list[str]:
    """Alarming terms found in `text`. Empty list == safe to send.

    The copy contract in one callable so the templates, the tests, and anything
    that ever extends the catalog all check the same rule. `context="condolence"`
    switches to the bereavement register — see `_CONDOLENCE_ALLOWED`.
    """
    low = text.lower()
    allowed = _CONDOLENCE_ALLOWED.get(language, set()) if context == "condolence" else set()
    return [t for t in _UNSAFE.get(language, ())
            if t.lower() in low and t.lower() not in allowed]


def build_message(record_id: str, event: str, language: str, at_minutes: int) -> PatientMessage:
    """One templated message. Unknown language degrades to English rather than blank."""
    for candidate in (EVENTS, COMPASSIONATE_EVENTS, ADVOCACY_EVENTS):
        if event in candidate:
            by_lang = candidate[event]
            break
    else:
        raise KeyError(f"unknown patient comms event: {event}")
    text = by_lang.get(language) or by_lang["en"]
    return PatientMessage(
        record_id=record_id,
        event=event,
        language=language if language in by_lang else "en",
        text=text,
        at_minutes=at_minutes,
    )


def plan_notifications(
    journey: Journey,
    report: RadarReport,
    *,
    language: str = "en",
    outcome: str | None = None,
    disposition: str = "discharged",
) -> list[PatientMessage]:
    """The messages a patient receives across one claim journey, in send order.

    Trigger moments (the part Phase 4's exit criteria actually test):
      - pharmacy_ready at the ORDER handoff, never gated on approval
      - sla_prebreach at the 120-min mark, only when submission is still pending then
      - claim_submitted when the claim actually leaves for the insurer
      - outcome copy at the insurer's decision
    """
    at = {s.stage: s.at_minutes for s in journey.stages}
    rid = journey.record_id

    # §9-4: the standard sequence is addressed to the patient and talks about their
    # discharge medicines. Sending any of it after a death would be a serious harm, so
    # the compassionate path replaces the schedule entirely rather than filtering it.
    if disposition == "deceased":
        msgs = [build_message(rid, "condolence_hold", language, at.get("order", 0))]
        if "decision" in at:
            msgs.append(build_message(rid, "claim_settled_family", language, at["decision"]))
        return msgs

    msgs = [build_message(rid, "pharmacy_ready", language, at.get("order", 0))]

    submit_at = at.get("submit")
    # Alert fires at the pre-breach mark itself, not when submission finally lands —
    # an early warning delivered late is not a warning.
    if submit_at is not None and submit_at >= PREBREACH_MIN:
        msgs.append(build_message(rid, "sla_prebreach", language, PREBREACH_MIN))
    if submit_at is not None:
        msgs.append(build_message(rid, "claim_submitted", language, submit_at))

    if outcome and "decision" in at:
        event = OUTCOME_EVENT.get(outcome)
        if event is None:
            raise KeyError(f"unknown claim outcome: {outcome}")
        msgs.append(build_message(rid, event, language, at["decision"]))

    return sorted(msgs, key=lambda m: m.at_minutes)


def advocacy_messages(record_id: str, decision_at: int, state: str, *,
                      language: str = "en", filed_after_min: int = 90,
                      ) -> list[PatientMessage]:
    """The advocacy track: a lead when the decision lands, the full story once filed.

    The gap between the two is the design, not an accident. It is the window in which
    the patient holds "someone is on this" rather than either silence or bad news.
    """
    if state == "none":
        return []

    msgs = [build_message(record_id, "advocacy_reviewing", language, decision_at)]
    if state in ("filed", "no_valid_appeal"):
        msgs.append(build_message(record_id, f"advocacy_{state}", language,
                                   decision_at + filed_after_min))
    return msgs
