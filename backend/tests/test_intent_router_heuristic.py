"""Intent router heuristics: project/story questions must not stay on small_talk."""

from app.agents.nodes.intent_router import (
    _coerce_substantive_intent,
    _guess_intent_from_message,
    _looks_like_project_query,
)
from app.agents.schemas import IntentClassification


def test_detects_chinese_story_visibility():
    assert _looks_like_project_query("你好 看得到这个故事吗")


def test_detects_english_plot_inventory():
    assert _looks_like_project_query("hi, what plot beats have I written so far")


def test_pure_greeting_is_not_project_query():
    assert not _looks_like_project_query("Hello")


def test_coerce_overrides_small_talk_for_story_question():
    intent = IntentClassification(
        primary="small_talk",
        confidence=0.9,
        reasoning="greeting",
    )
    out = _coerce_substantive_intent(intent, "你好 看得到这个故事吗")
    assert out.primary == "research"
    assert out.confidence >= 0.85


def test_guess_structure_for_character_creation():
    out = _guess_intent_from_message("I want to create a character named Linda")
    assert out is not None
    assert out.primary == "structure"


def test_guess_inspiration_for_story_idea():
    out = _guess_intent_from_message(
        "I want to write a story where character Lucy does a fight with a bee"
    )
    assert out is not None
    assert out.primary == "inspiration"


def test_coerce_overrides_small_talk_for_character_creation():
    intent = IntentClassification(primary="small_talk", confidence=0.9, reasoning="greeting")
    out = _coerce_substantive_intent(intent, "I want to create a character named Linda")
    assert out.primary == "structure"
