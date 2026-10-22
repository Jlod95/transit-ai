"""The OpenRouter adapter's format conversions, offline (no API call)."""

from src.agent import TOOLS
from src.providers import key_name, openrouter_messages, openrouter_tools, parse_openrouter

CALL = {"id": "call_1", "type": "function",
        "function": {"name": "get_block_distance",
                     "arguments": '{"agency": "halifax", "block_id": "722145", "date": "2026-10-14"}'}}


def test_tools_keep_name_description_and_schema():
    converted = openrouter_tools(TOOLS)
    assert [t["function"]["name"] for t in converted] == [t["name"] for t in TOOLS]
    assert converted[0]["function"]["description"] == TOOLS[0]["description"]
    assert converted[0]["function"]["parameters"] == TOOLS[0]["input_schema"]


def test_tool_call_reply_is_parsed():
    body = {"choices": [{"finish_reason": "tool_calls",
                         "message": {"role": "assistant", "content": None, "tool_calls": [CALL]}}],
            "usage": {"prompt_tokens": 900, "completion_tokens": 40, "cost": 0.0003}}
    r = parse_openrouter(body)
    assert r["stop"] == "tool_use" and r["texts"] == []
    assert r["tool_calls"] == [{"id": "call_1", "name": "get_block_distance",
                                "input": {"agency": "halifax", "block_id": "722145", "date": "2026-10-14"}}]
    assert r["usage"] == {"input_tokens": 900, "output_tokens": 40, "cost_usd": 0.0003}


def test_final_answer_and_bad_arguments():
    final = parse_openrouter({"choices": [{"finish_reason": "stop",
                                           "message": {"role": "assistant", "content": "80.5 km."}}]})
    assert final["stop"] == "end" and final["texts"] == ["80.5 km."]
    bad = {**CALL, "function": {"name": "get_block_distance", "arguments": "{not json"}}
    r = parse_openrouter({"choices": [{"finish_reason": "tool_calls",
                                       "message": {"role": "assistant", "tool_calls": [bad]}}]})
    assert r["tool_calls"][0]["input"] == {}


def test_conversation_becomes_openai_messages():
    reply = parse_openrouter({"choices": [{"finish_reason": "tool_calls",
                                           "message": {"role": "assistant", "tool_calls": [CALL]}}]})
    messages = [{"role": "user", "text": "How far?"},
                {"role": "assistant", "native": reply["native"], "tool_calls": reply["tool_calls"]},
                {"role": "tool_results", "results": [{"id": "call_1", "content": "80.5 km", "is_error": False}]}]
    out = openrouter_messages("SYSTEM", messages)
    assert [m["role"] for m in out] == ["system", "user", "assistant", "tool"]
    assert out[2]["tool_calls"] == [CALL]
    assert out[3] == {"role": "tool", "tool_call_id": "call_1", "content": "80.5 km"}


def test_key_name_follows_the_provider():
    assert key_name("claude-opus-5-5") == "ANTHROPIC_API_KEY"
    assert key_name("openrouter:deepseek/deepseek-v4.1-flash") == "OPENROUTER_API_KEY"
