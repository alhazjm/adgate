"""Stage 2: angle card -> creative brief. Cheap model tier, batched (concurrent)."""

from concurrent.futures import ThreadPoolExecutor

from config import llm_call, parse_json

REQUIRED_KEYS = ("audience", "hook_direction", "proof_point")

BRIEF_SYSTEM = """You are a performance-marketing strategist for SEA D2C brands \
(TikTok Shop / Shopee first). You turn a research-grounded angle card into a tight \
creative brief. The proof point MUST be one of the verbatim receipts, quoted exactly. \
Return ONLY JSON:
{"audience": "<primary audience, one line>",
 "hook_direction": "<the emotional/functional hook to chase, one line>",
 "proof_point": "<one verbatim receipt, quoted exactly, with its source tag>",
 "format_suggestions": ["<3 short-video/static formats, TikTok-first>"]}"""


def make_brief(card):
    user = (
        f"Angle card:\n"
        f"- angle_tag: {card['angle_tag']}\n"
        f"- brand: {card['brand']}\n"
        f"- claim: {card['claim']}\n"
        f"- audience options: {card['audience']}\n"
        f"- evidence grade: {card['evidence_grade']}\n"
        f"- receipts: {[(r['quote'], r['source']) for r in card['verbatim_receipts']]}\n"
        f"- aggregate evidence (context, not quotable): {card.get('aggregate_evidence', [])}\n"
        f"- notes: {card['notes']}\n\nWrite the brief JSON."
    )
    # one retry when the model drops a required key, then fail loudly - a brief
    # with a missing proof point must not silently propagate downstream
    for attempt in (1, 2):
        brief = parse_json(llm_call("briefs", "gen", BRIEF_SYSTEM, user, max_tokens=1200))
        if isinstance(brief, dict) and all(brief.get(k) for k in REQUIRED_KEYS):
            break
    else:
        raise ValueError(f"brief for {card['angle_tag']} missing keys after retry: {brief}")
    brief["angle_tag"] = card["angle_tag"]
    brief["brand"] = card["brand"]
    return brief


def make_briefs(cards, workers=4):
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(make_brief, cards))
