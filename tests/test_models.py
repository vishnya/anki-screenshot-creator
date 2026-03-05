import base64
import json

import pytest
import models


def test_encode_image_returns_base64(tiny_png):
    result = models.encode_image(tiny_png)
    decoded = base64.b64decode(result)
    assert decoded[:4] == b"\x89PNG"


def test_encode_image_small_no_resize(tiny_png):
    with open(tiny_png, "rb") as f:
        original_data = f.read()
    original_b64 = base64.standard_b64encode(original_data).decode("utf-8")
    result = models.encode_image(tiny_png)
    assert result == original_b64


def test_parse_cards_valid_json():
    raw = json.dumps({
        "cards": [{"front": "Q", "back": "A", "tags": [], "is_image_card": False}]
    })
    result = models._parse_cards(raw)
    assert len(result) == 1
    assert result[0]["front"] == "Q"


def test_parse_cards_strips_backtick_wrapper():
    raw = '```json\n{"cards": []}\n```'
    result = models._parse_cards(raw)
    assert result == []


def test_parse_cards_empty_cards_key():
    result = models._parse_cards('{"cards": []}')
    assert result == []


def test_parse_cards_invalid_json_shows_response():
    raw = "Sure! Here are some flashcards about biology..."
    with pytest.raises(ValueError, match="Model returned invalid JSON"):
        models._parse_cards(raw)
    # Verify the raw response preview is in the error
    try:
        models._parse_cards(raw)
    except ValueError as e:
        assert "Sure! Here are some flashcards" in str(e)


def test_parse_cards_extracts_json_from_text():
    """Models often wrap valid JSON in explanatory text."""
    raw = 'Here are your flashcards:\n{"cards": [{"front": "Q", "back": "A", "tags": [], "is_image_card": false}]}\nHope that helps!'
    result = models._parse_cards(raw)
    assert len(result) == 1
    assert result[0]["front"] == "Q"


def test_extract_json_returns_none_for_garbage():
    assert models._extract_json("no json here at all") is None


def test_extract_json_returns_none_for_malformed_braces():
    assert models._extract_json("{ broken json {{") is None


def test_build_prompt_no_custom():
    config = {"custom_prompt": ""}
    result = models._build_prompt(config)
    assert result == models.PROMPT_TEMPLATE


def test_build_prompt_with_custom():
    config = {"custom_prompt": "Focus on neuroscience"}
    result = models._build_prompt(config)
    assert "TOPIC FOCUS FOR THIS SESSION:" in result
    assert "Focus on neuroscience" in result


def test_build_prompt_focus_appears_before_json_spec():
    config = {"custom_prompt": "Focus on history"}
    result = models._build_prompt(config)
    focus_pos = result.index("TOPIC FOCUS FOR THIS SESSION:")
    self_check_pos = result.index("SELF-CHECK:")
    json_spec_pos = result.index("Return ONLY valid JSON")
    assert focus_pos < self_check_pos < json_spec_pos
