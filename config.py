"""Provider config + per-stage cost tracking.

Spec default is OpenAI (OPENAI_API_KEY, GEN_MODEL=gpt-5-mini, JUDGE_MODEL=gpt-5.4).
If only ANTHROPIC_API_KEY is present, the pipeline runs on Anthropic instead
(GEN_MODEL=claude-haiku-4-5, JUDGE_MODEL=claude-opus-4-8). Same two-tier shape:
cheap model generates, strong model judges. Override models via GEN_MODEL /
JUDGE_MODEL and prices via *_PRICE_IN / *_PRICE_OUT (USD per 1M tokens).
"""

import json
import os
import re
import threading

# USD per 1M tokens: (input, output). OpenAI gpt-5.4 pricing is an assumption
# (not verifiable from this machine) - override with JUDGE_PRICE_IN/OUT.
PRICES = {
    "gpt-5-mini": (0.25, 2.00),
    "gpt-5.4": (1.25, 10.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-opus-4-8": (5.00, 25.00),
}

if os.environ.get("MOCK_LLM"):
    PROVIDER = "mock"  # mechanics verification only - canned outputs, zero cost
    GEN_MODEL = "mock-gen"
    JUDGE_MODEL = "mock-judge"
elif os.environ.get("OPENAI_API_KEY"):
    # OPENAI_BASE_URL lets any OpenAI-compatible provider serve the pipeline
    # (e.g. Groq https://api.groq.com/openai/v1) - set GEN_MODEL/JUDGE_MODEL to match.
    PROVIDER = "openai"
    GEN_MODEL = os.environ.get("GEN_MODEL", "gpt-5-mini")
    JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "gpt-5.4")
elif os.environ.get("ANTHROPIC_API_KEY"):
    PROVIDER = "anthropic"
    GEN_MODEL = os.environ.get("GEN_MODEL", "claude-haiku-4-5")
    JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "claude-opus-4-8")
else:
    PROVIDER = None  # evals' deterministic layer still runs; LLM stages will raise
    GEN_MODEL = os.environ.get("GEN_MODEL", "gpt-5-mini")
    JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "gpt-5.4")


def _price(model, env_prefix):
    """Returns (in, out) per-1M prices, or None when the model has no known price."""
    p_in = os.environ.get(f"{env_prefix}_PRICE_IN")
    p_out = os.environ.get(f"{env_prefix}_PRICE_OUT")
    if p_in and p_out:
        return float(p_in), float(p_out)
    return PRICES.get(model)


class CostTracker:
    """Accumulates token usage and USD cost per pipeline stage."""

    def __init__(self):
        self._lock = threading.Lock()
        self.stages = {}  # stage -> {calls, input_tokens, output_tokens, cost_usd}
        self.unpriced_models = set()  # models with no price entry - cost understated

    def add(self, stage, model, input_tokens, output_tokens):
        tier = "JUDGE" if model == JUDGE_MODEL else "GEN"
        prices = _price(model, tier)
        if prices is None and PROVIDER != "mock":
            with self._lock:
                self.unpriced_models.add(model)
            prices = (0.0, 0.0)
        elif prices is None:
            prices = (0.0, 0.0)
        cost = input_tokens / 1e6 * prices[0] + output_tokens / 1e6 * prices[1]
        with self._lock:
            s = self.stages.setdefault(
                stage, {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
            )
            s["calls"] += 1
            s["input_tokens"] += input_tokens
            s["output_tokens"] += output_tokens
            s["cost_usd"] += cost

    def total_cost(self):
        return sum(s["cost_usd"] for s in self.stages.values())

    def summary(self):
        return {"stages": self.stages, "total_cost_usd": round(self.total_cost(), 6),
                "unpriced_models": sorted(self.unpriced_models)}


TRACKER = CostTracker()

_client = None
_client_lock = threading.Lock()


def _get_client():
    global _client
    with _client_lock:
        return _get_client_locked()


def _get_client_locked():
    global _client
    if _client is not None:
        return _client
    if PROVIDER == "openai":
        from openai import OpenAI

        base_url = os.environ.get("OPENAI_BASE_URL")
        _client = OpenAI(base_url=base_url) if base_url else OpenAI()
    elif PROVIDER == "anthropic":
        import anthropic

        _client = anthropic.Anthropic()
    else:
        raise RuntimeError("No OPENAI_API_KEY or ANTHROPIC_API_KEY in environment.")
    return _client


_MOCK_BRIEF = ('{"audience": "mock audience", "hook_direction": "mock hook direction", '
               '"proof_point": "mock verbatim receipt [mock source]", '
               '"format_suggestions": ["talking head", "UGC demo", "text-on-screen"]}')


def _mock_response(stage, tier):
    if tier == "judge":
        return '{"score": 7, "reason": "MOCK JUDGE - mechanics verification only"}'
    if stage == "briefs":
        return _MOCK_BRIEF
    if stage == "repair":
        return ('{"hook": "Mock repaired hook", '
                '"caption": "Mock repaired caption - hedged, compliant, claim dropped.", '
                '"script": "beat one | beat two | beat three", '
                '"audience_variant": "mock audience"}')
    # variants: 5 clean + 1 that must trip the deterministic gate, so the
    # refusal path is exercised even in mock mode
    variants = [
        {"hook": f"Mock hook {i}", "caption": f"Mock caption {i} - hedged, compliant.",
         "script": "beat one | beat two | beat three", "audience_variant": "mock audience"}
        for i in range(1, 6)
    ]
    variants.append({"hook": "Mock banned hook", "caption": "100% leak-proof, guaranteed.",
                     "script": "a | b | c", "audience_variant": "mock audience"})
    return json.dumps(variants)


def llm_call(stage, tier, system, user, max_tokens=2000):
    """One LLM call. tier: 'gen' or 'judge'. Returns response text; logs usage."""
    model = JUDGE_MODEL if tier == "judge" else GEN_MODEL
    if PROVIDER == "mock":
        TRACKER.add(stage, model, 0, 0)
        return _mock_response(stage, tier)
    client = _get_client()
    if PROVIDER == "openai":
        # reasoning-tier models spend from max_completion_tokens on hidden
        # reasoning; give headroom so visible content isn't starved to empty
        resp = client.chat.completions.create(
            model=model,
            max_completion_tokens=max(max_tokens, 4000),
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        )
        TRACKER.add(stage, model, resp.usage.prompt_tokens, resp.usage.completion_tokens)
        content = resp.choices[0].message.content
        if not content:
            raise ValueError(
                f"empty completion from {model} (finish_reason="
                f"{resp.choices[0].finish_reason}) - likely reasoning tokens consumed "
                f"the budget; raise max_completion_tokens")
        return content
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    TRACKER.add(stage, model, resp.usage.input_tokens, resp.usage.output_tokens)
    return "".join(b.text for b in resp.content if b.type == "text")


def parse_json(text):
    """Parse a JSON object/array out of an LLM response (tolerates code fences and
    prose wrapping; the scanner is string-literal-aware so braces inside quoted
    values don't truncate the slice)."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    first = min((i for i in (text.find("{"), text.find("[")) if i != -1), default=-1)
    if first != -1:
        opener = text[first]
        closer = "}" if opener == "{" else "]"
        depth, in_string, escaped = 0, False, False
        for i in range(first, len(text)):
            ch = text[i]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    return json.loads(text[first : i + 1])
    raise ValueError(f"No JSON found in response: {text[:200]}")


def as_list(parsed):
    """Coerce a parse_json result to a list of dicts - models sometimes wrap the
    array in an object like {"variants": [...]}."""
    if isinstance(parsed, dict):
        for v in parsed.values():
            if isinstance(v, list):
                parsed = v
                break
        else:
            parsed = [parsed]
    if not isinstance(parsed, list):
        raise ValueError(f"expected a JSON array, got {type(parsed).__name__}")
    return [x for x in parsed if isinstance(x, dict)]
