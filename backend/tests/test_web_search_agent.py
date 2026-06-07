"""Web search wiring for agent external-fact queries."""

from app.agents.tools import make_project_tools
from app.agents.web_query import looks_like_web_query, prefetch_web_search, resolve_web_search_enabled


def test_resolve_web_search_on():
    assert resolve_web_search_enabled("hello", "on") is True


def test_resolve_web_search_off():
    assert resolve_web_search_enabled("江苏7月份会不会下雨", "off") is False


def test_resolve_web_search_auto():
    assert resolve_web_search_enabled("江苏7月份会不会下雨", "auto") is True
    assert resolve_web_search_enabled("项目里有哪些情节", "auto") is False


def test_web_search_tool_returns_answer():
    tools = make_project_tools("test-project")
    web_tool = next(t for t in tools if t.name == "web_search")
    raw = web_tool.invoke({"query": "Shanghai weather today", "top_k": 2})
    assert "[ERROR]" not in raw
    assert "answer" in raw


def test_web_search_tool_omitted_when_disabled():
    tools = make_project_tools("test-project", include_web_search=False)
    assert all(t.name != "web_search" for t in tools)


def test_detects_chinese_weather_query():
    assert looks_like_web_query("江苏7月份会不会下雨")


def test_skips_pure_project_enumeration():
    assert not looks_like_web_query("项目里有哪些情节节点")


def test_prefetch_returns_answer():
    result = prefetch_web_search("Shanghai weather today", top_k=2)
    assert result is not None
    assert len(result.fallback_answer) > 5
    assert isinstance(result.sources, list)
