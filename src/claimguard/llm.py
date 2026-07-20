"""LLM provider interface. mock = deterministic/offline (all tests); gemini = runtime."""
import hashlib
import json
import time
from functools import lru_cache

from claimguard.config import get_settings

EMBED_DIM = 768

# Free-tier ceiling, confirmed from the provider's own quota error (2026-07-20):
# GenerateRequestsPerDayPerProjectPerModel-FreeTier, quotaValue 20, gemini-2.5-flash.
FREE_TIER_DAILY_GENERATE = 20

# Markers distinguishing "the provider cut us off" from "the call was wrong".
QUOTA_MARKERS = ("429", "RESOURCE_EXHAUSTED", "quota")


def is_quota_error(err: object) -> bool:
    """True when `err` (an exception or message) is provider throttling, not a real fault.

    Callers use this to end cleanly rather than crash: on a free tier, running out of
    daily quota is an expected outcome of a long job, not a bug.
    """
    msg = str(err)
    return any(marker in msg for marker in QUOTA_MARKERS)


def _with_backoff(call, *, tries: int = 4, base: float = 20.0):
    """Retry a Gemini call on 429 rate-limit, honoring the server's retry hint.
    Free-tier RPM is low; a burst eval otherwise dies on the first 429.
    # ponytail: fixed backoff; swap for a token-bucket limiter if throughput matters.
    """
    for attempt in range(tries):
        try:
            return call()
        except Exception as e:  # google.genai.errors.ClientError (429) or transient
            msg = str(e)
            if "429" not in msg and "RESOURCE_EXHAUSTED" not in msg:
                raise
            if attempt == tries - 1:
                raise
            wait = base * (attempt + 1)
            if "retryDelay" in msg:
                import re
                m = re.search(r"retryDelay['\"]?:\s*['\"]?(\d+)", msg)
                if m:
                    wait = min(float(m.group(1)) + 2, 60)
            time.sleep(wait)


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


@lru_cache
def _gemini_client():
    # Reuse one client: constructing a fresh genai.Client per call lets the
    # first instance's cleanup close the shared httpx transport, which breaks
    # any subsequent call ("Cannot send a request, as the client has been closed").
    from google import genai
    return genai.Client(api_key=get_settings().gemini_api_key)


def _gemini_complete(prompt, system, tier, json_schema):
    s = get_settings()
    model = s.model_reasoning if tier == "reasoning" else s.model_fast
    cfg = {"system_instruction": system} if system else {}
    if json_schema:
        cfg |= {"response_mime_type": "application/json"}
        prompt += "\nRespond ONLY with JSON matching this schema:\n" + json.dumps(json_schema)
    resp = _with_backoff(lambda: _gemini_client().models.generate_content(
        model=model, contents=prompt, config=cfg or None))
    return json.loads(resp.text) if json_schema else resp.text


def complete(prompt: str, *, system: str = "", tier: str = "fast",
             json_schema: dict | None = None) -> str | dict:
    if get_settings().llm_provider == "gemini":
        return _gemini_complete(prompt, system, tier, json_schema)
    return _mock_complete(prompt, system, json_schema)


def embed(texts: list[str]) -> list[list[float]]:
    if get_settings().llm_provider == "gemini":
        from google.genai import types
        client = _gemini_client()
        # gemini-embedding-001 defaults to 3072 dims; truncate to EMBED_DIM (768)
        # via Matryoshka output_dimensionality so it matches the pgvector(768) schema.
        res = _with_backoff(lambda: client.models.embed_content(
            model=get_settings().embed_model,
            contents=texts,
            config=types.EmbedContentConfig(output_dimensionality=EMBED_DIM),
        ))
        return [e.values for e in res.embeddings]
    return _mock_embed(texts)
