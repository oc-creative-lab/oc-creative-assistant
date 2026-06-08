"""Helpers for plain-JSON structured output fallback."""

import pytest

from app.llm.provider import _extract_json_object, _strip_json_fence


def test_strip_json_fence():
    raw = '```json\n{"primary": "structure"}\n```'
    assert _strip_json_fence(raw) == '{"primary": "structure"}'


def test_extract_json_object_from_fenced_block():
    data = _extract_json_object('```\n{"reasoning": "x", "summary": "y"}\n```')
    assert data["reasoning"] == "x"


def test_extract_json_object_raises_when_missing():
    with pytest.raises(ValueError, match="No JSON object"):
        _extract_json_object("not json at all")
