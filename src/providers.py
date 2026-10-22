"""One interface to the model, whoever hosts it: complete() sends the conversation and tools and
returns text, tool calls and token usage in the same shape for every provider.

Model IDs: a plain ID ("claude-opus-5-5") goes to Anthropic; "openrouter:<model-id>" goes to
OpenRouter (OpenAI-compatible chat completions, key from OPENROUTER_API_KEY).

The conversation is kept in a neutral form, and each adapter translates it to its own format:
    {"role": "user", "text": "..."}
    {"role": "assistant", "native": <the reply exactly as the provider sent it>, "tool_calls": [...]}
    {"role": "tool_results", "results": [{"id", "content", "is_error"}]}
"""

import json
import os
import urllib.error
import urllib.request

import anthropic

OPENROUTER_PREFIX = "openrouter:"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# Models that accept Anthropic's server-side refusal fallback in "default" mode.
FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}
MAX_TOKENS = 16000


class ProviderError(Exception):
    """A non-Anthropic provider failed (HTTP error, bad reply)."""


def key_name(model):
    """The environment variable that holds the API key for this model's provider."""
    return "OPENROUTER_API_KEY" if model.startswith(OPENROUTER_PREFIX) else "ANTHROPIC_API_KEY"


def complete(model, system, tools, messages):
    """One model call. Returns {"texts", "tool_calls": [{"id", "name", "input"}], "stop",
    "usage": {"input_tokens", "output_tokens"[, "cost_usd"]}, "native"}.

    stop is "end" (final answer), "tool_use", "refusal", or the provider's own reason otherwise.
    tools are in Anthropic's format (name, description, input_schema); adapters convert them.
    """
    if model.startswith(OPENROUTER_PREFIX):
        return _openrouter(model.removeprefix(OPENROUTER_PREFIX), system, tools, messages)
    return _anthropic(model, system, tools, messages)


# --- Anthropic: the agent's original behaviour ---

def _anthropic_messages(messages):
    out = []
    for m in messages:
        if m["role"] == "user":
            out.append({"role": "user", "content": m["text"]})
        elif m["role"] == "assistant":
            out.append({"role": "assistant", "content": m["native"]})  # thinking blocks kept
        else:
            out.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": r["id"], "content": r["content"],
                 "is_error": r["is_error"]} for r in m["results"]]})
    return out


def _anthropic(model, system, tools, messages):
    fallback = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"} \
        if model in FALLBACK_MODELS else {}
    response = anthropic.Anthropic().beta.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        system=system,
        tools=tools,
        messages=_anthropic_messages(messages),
        output_config={"effort": "medium"},
        **fallback,
    )
    stop = {"end_turn": "end", "tool_use": "tool_use", "refusal": "refusal"}
    return {
        "texts": [b.text for b in response.content if b.type == "text" and b.text.strip()],
        "tool_calls": [{"id": b.id, "name": b.name, "input": b.input}
                       for b in response.content if b.type == "tool_use"],
        "stop": stop.get(response.stop_reason, response.stop_reason),
        "usage": {"input_tokens": response.usage.input_tokens,
                  "output_tokens": response.usage.output_tokens},
        "native": response.content,
    }


# --- OpenRouter: OpenAI-compatible chat completions ---

def openrouter_tools(tools):
    """Anthropic tool definitions -> OpenAI function tools (same name, description and schema)."""
    return [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                              "parameters": t["input_schema"]}} for t in tools]


def openrouter_messages(system, messages):
    out = [{"role": "system", "content": system}]
    for m in messages:
        if m["role"] == "user":
            out.append({"role": "user", "content": m["text"]})
        elif m["role"] == "assistant":
            out.append(m["native"])  # includes its tool_calls, so results can refer to them
        else:
            out += [{"role": "tool", "tool_call_id": r["id"], "content": r["content"]}
                    for r in m["results"]]
    return out


def parse_arguments(text):
    """Tool arguments arrive as a JSON string; anything that isn't a JSON object becomes {}
    (the tool then reports the missing inputs as an error, which the model can correct)."""
    try:
        value = json.loads(text or "{}")
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def parse_openrouter(body):
    """An OpenAI-format response body -> complete()'s return shape."""
    if body.get("error") or not body.get("choices"):
        raise ProviderError(f"OpenRouter returned no answer: {str(body.get('error') or body)[:300]}")
    choice = body["choices"][0]
    message = choice["message"]
    calls = message.get("tool_calls") or []
    reason = choice.get("finish_reason")
    if calls:
        stop = "tool_use"  # some models say "stop" even when they called tools
    else:
        stop = {"stop": "end", "content_filter": "refusal"}.get(reason, reason)
    text = (message.get("content") or "").strip()
    usage = body.get("usage") or {}
    native = {"role": "assistant", "content": message.get("content") or ""}
    if calls:
        native["tool_calls"] = calls
    return {
        "texts": [text] if text else [],
        "tool_calls": [{"id": c["id"], "name": c["function"]["name"],
                        "input": parse_arguments(c["function"].get("arguments"))} for c in calls],
        "stop": stop,
        "usage": {"input_tokens": usage.get("prompt_tokens", 0),
                  "output_tokens": usage.get("completion_tokens", 0),
                  "cost_usd": usage.get("cost")},
        "native": native,
    }


def _openrouter(model, system, tools, messages):
    payload = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "messages": openrouter_messages(system, messages),
        "tools": openrouter_tools(tools),
        "usage": {"include": True},  # ask OpenRouter to report the actual cost
    }
    request = urllib.request.Request(
        OPENROUTER_URL, data=json.dumps(payload).encode(), method="POST",
        headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            body = json.loads(response.read())
    except urllib.error.HTTPError as e:
        raise ProviderError(f"OpenRouter HTTP {e.code}: {e.read()[:300]!r}") from e
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        raise ProviderError(f"OpenRouter request failed: {e}") from e
    return parse_openrouter(body)
