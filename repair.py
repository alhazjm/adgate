"""Stage 4.5: the bounded repair agent.

This is the ONE place the pipeline has agency: what happens next depends on what
the gate found (which rule fired, what the judge said). Everything else stays a
fixed, testable path. The agency is bounded four ways:

  1. attempts   - MAX_ATTEMPTS rewrites per variant, then stop
  2. spend      - REPAIR_BUDGET_USD per run for this stage alone, checked
                  before every model call
  3. verdicts   - the repair model's output has NO verdict field; every rewrite
                  goes back through gate_variant(), and only the gate decides
  4. fail-closed- anything not PASS after the caps lands in the human queue
                  with its full repair history attached, never silently dropped

The repair prompt sees the rule that fired and the evidence-backed reason, so
the rewrite is targeted at the actual violation rather than a blind retry.
"""

from concurrent.futures import ThreadPoolExecutor

from config import TRACKER, llm_call, parse_json
from gate import gate_variant
from variants import BRAND_VOICES

MAX_ATTEMPTS = 2
REPAIR_BUDGET_USD = 0.25  # per-run ceiling for the repair stage alone

_COPY_KEYS = ("hook", "caption", "script", "audience_variant")

REPAIR_SYSTEM = """You are a senior copywriter fixing an ad variant that a compliance \
gate refused. You get the variant, the rule(s) it broke with the customer-review \
evidence behind each rule, and the brand voice rubric. Rewrite the variant so it keeps \
its angle, audience and energy but drops the offending claim ENTIRELY - in any wording, \
synonym or implication, not just the flagged phrase. Concrete, honest phrasing beats \
vague hedging. Never introduce new absolute claims ("100%", "never", "guaranteed"), \
superlatives, origin claims, health guarantees, overnight/duration promises, or \
star-rating citations. Return ONLY JSON:
{"hook": "...", "caption": "...", "script": "beat1 | beat2 | beat3", "audience_variant": "..."}"""


def _repair_spent():
    return TRACKER.stages.get("repair", {}).get("cost_usd", 0.0)


def _repair_prompt(variant):
    return (
        f"Brand voice rubric:\n{BRAND_VOICES[variant['brand']]}\n\n"
        f"Refused variant:\n"
        f"- hook: {variant.get('hook')}\n"
        f"- caption: {variant.get('caption')}\n"
        f"- script: {variant.get('script')}\n"
        f"- audience_variant: {variant.get('audience_variant')}\n\n"
        f"Gate verdict: {variant['verdict']}\n"
        f"Rule(s) fired: {variant.get('rule')}\n"
        f"Reason (cites the review evidence): {variant.get('reason')}\n\n"
        f"Rewrite it. Return the JSON only."
    )


def repair_variant(gated):
    """Takes one gate-annotated variant with verdict REFUSED or VOICE-FLAG.
    Returns the final variant: repaired-and-PASSed, or the original annotated
    as human-queue with its repair history. Never raises on a bad model
    response - a failed attempt is just a consumed attempt."""
    original = dict(gated)
    current = dict(gated)
    history = []

    for attempt in range(1, MAX_ATTEMPTS + 1):
        if _repair_spent() >= REPAIR_BUDGET_USD:
            history.append({"attempt": attempt, "outcome": "SKIPPED-BUDGET",
                            "detail": f"repair stage spend reached US${REPAIR_BUDGET_USD}"})
            break
        try:
            raw = parse_json(llm_call("repair", "gen", REPAIR_SYSTEM,
                                      _repair_prompt(current), max_tokens=1500))
            if isinstance(raw, list):
                raw = raw[0] if raw else {}
            rewrite = {k: str(raw.get(k, "")) for k in _COPY_KEYS}
            if not rewrite["hook"] and not rewrite["caption"]:
                raise ValueError("rewrite missing hook and caption")
        except (ValueError, KeyError, TypeError) as e:
            history.append({"attempt": attempt, "outcome": "BAD-RESPONSE", "detail": str(e)})
            continue

        # brand/angle are pinned from the original - the agent cannot move a
        # variant to a different brand or angle to dodge a brand-scoped rule
        rewrite["brand"] = original["brand"]
        rewrite["angle_tag"] = original.get("angle_tag", "")

        regated = gate_variant(rewrite)
        history.append({"attempt": attempt, "outcome": regated["verdict"],
                        "detail": regated.get("reason", ""), "hook": rewrite["hook"],
                        "caption": rewrite["caption"]})
        if regated["verdict"] == "PASS":
            regated.update(
                repaired=True, repair_attempts=attempt,
                repaired_from_rule=original.get("rule", ""),
                original_hook=original.get("hook", ""),
                original_caption=original.get("caption", ""),
                repair_history=history,
            )
            return regated
        current = regated  # next attempt sees the newest violation, not the stale one

    final = dict(original)
    final.update(
        verdict="HUMAN-QUEUE", repaired=False,
        repair_attempts=sum(1 for h in history if h["outcome"] != "SKIPPED-BUDGET"),
        repaired_from_rule=original.get("rule", ""),
        original_hook=original.get("hook", ""),
        original_caption=original.get("caption", ""),
        repair_history=history,
        reason=(f"unrepaired after {len(history)} attempt(s); original refusal: "
                f"{original.get('reason', '')}"),
    )
    return final


def repair_all(gated, workers=4):
    """Runs repair on every REFUSED/VOICE-FLAG variant. Returns (variants, stats)
    with input order preserved; PASS variants go through untouched."""
    idx_to_fix = [i for i, v in enumerate(gated) if v["verdict"] in ("REFUSED", "VOICE-FLAG")]
    out = list(gated)
    if idx_to_fix:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            fixed = list(ex.map(lambda i: repair_variant(gated[i]), idx_to_fix))
        for i, v in zip(idx_to_fix, fixed):
            out[i] = v

    salvaged = sum(1 for i in idx_to_fix if out[i].get("repaired"))
    stats = {
        "candidates": len(idx_to_fix),
        "salvaged": salvaged,
        "human_queue": len(idx_to_fix) - salvaged,
        "attempts_total": sum(out[i].get("repair_attempts", 0) for i in idx_to_fix),
        "budget_exhausted": any(
            h.get("outcome") == "SKIPPED-BUDGET"
            for i in idx_to_fix for h in out[i].get("repair_history", [])),
        "repair_cost_usd": round(_repair_spent(), 6),
    }
    return out, stats
