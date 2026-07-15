"""Stage 3: brief -> N=6 hook/caption/script variants per brief, per line voice.

One client brand (Huggies, Singapore market), four product-line voices. The
line rubrics are built from the brand's own SG register (huggies.com.sg copy +
Huggies.SG Facebook captions, fetched 15 Jul 2026) - warm, reassurance-first,
mum-centric, hug motif everywhere, exclamatory benefit lines on site, emoji-
dense on social. The generator is deliberately NOT shown the do-not-say list -
claims policing is the gate's job, which is exactly what the demo needs to show.
"""

from config import as_list, llm_call, parse_json

N_VARIANTS = 6

BRAND_VOICES = {
    "naturemade": (
        "Huggies Platinum Naturemade (SG; tape + pants + Overnite Pants - the premium "
        "nature-positioned line, the default first diaper in SG maternity hospitals). "
        "Voice: warm, reassurance-first, mum-centric ('mums', British English), the hug "
        "motif everywhere ('Comfort like a Hug', 'We got you, baby'). Gentle nature "
        "language (NatureSoft liner, 'Goodness of Nature') always paired with a concrete "
        "comfort benefit. Short exclamatory benefit lines on site ('Let baby sleep and "
        "play in comfort!'); emoji-warm on social (🌿💕). Never clinical-cold, never "
        "fear-mongering, no mummy-guilt."
    ),
    "airsoft": (
        "Huggies AirSoft Pants (SG; the breathability line - air-ventilation channels, "
        "'10X more airflow'). Voice: practical relief for hot, humid Singapore days - "
        "airflow, lightness, happy active babies. Warm but benefit-forward; speaks to "
        "parents of crawlers/walkers who sweat through everything. Emoji-light, energetic."
    ),
    "black-label": (
        "Huggies Black Label (SG; the premium-of-premium line, launched on Lazada Super "
        "Brand Day). Voice: indulgent-premium in a warm register - 'as soft as a mother's "
        "hug', 'royal treatment', Japan-imported cotton craft story. Emoji-rich on social "
        "(👑✨☁️), retail-moment tie-ins (mega-days, gift sets). Premium without being "
        "cold; the flex is softness craft, never price."
    ),
    "little-swimmers": (
        "Huggies Little Swimmers (SG; disposable swim pants for pool and beach days). "
        "Voice: sunny, playful, splash-forward - condo-pool Saturdays, baby swim classes, "
        "first beach trips. Fun colours and characters, easy on-off praise. The job is "
        "swim-time confidence and containment in water; it is NOT an absorbent diaper "
        "and the voice never talks like one."
    ),
}

VARIANT_SYSTEM = """You are a senior social-first creative copywriter working a global \
baby-care brand's Singapore market (TikTok/Meta-first). Given a brief and a product-line \
voice rubric, write {n} distinct ad variants. Each variant: a scroll-stopping HOOK \
(<=12 words), a CAPTION (1-2 sentences, platform-ready), and a SCRIPT (3 beats for a \
15-30s video, one line each). Spread variants across the audience splits given. Make \
claims punchy and confident. Return ONLY a JSON array of {n} objects:
[{{"hook": "...", "caption": "...", "script": "beat1 | beat2 | beat3", "audience_variant": "..."}}]"""


def gen_variants(brief, n=N_VARIANTS):
    brand = brief["brand"]
    system = VARIANT_SYSTEM.format(n=n)
    user = (
        f"Product-line voice rubric:\n{BRAND_VOICES[brand]}\n\n"
        f"Brief:\n"
        f"- angle_tag: {brief['angle_tag']}\n"
        f"- audience: {brief['audience']}\n"
        f"- hook_direction: {brief['hook_direction']}\n"
        f"- proof_point (verbatim customer quote - you may quote it): {brief['proof_point']}\n"
        f"- formats: {brief.get('format_suggestions', [])}\n\n"
        f"Write the {n} variants JSON."
    )
    raw = as_list(parse_json(llm_call("variants", "gen", system, user, max_tokens=3000)))
    out = []
    for v in raw[:n]:
        v["angle_tag"] = brief["angle_tag"]
        v["brand"] = brand
        out.append(v)
    return out
