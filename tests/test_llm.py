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
