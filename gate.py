"""Stage 4: the gate. Deterministic do-not-say checks FIRST (free), then the LLM
voice judge (strong model) only on survivors.

Every deterministic rule traces to citable evidence: the brand's own published
substantiation footnotes (huggies.com.sg, fetched 15 Jul 2026), Singapore's
Code of Advertising Practice (SCAP, ASAS), published regulator/self-regulator
precedent (NAD 2018 + Case #7248 2024; Taiwan FTC 2017), live US litigation,
and voice-of-customer complaint patterns from public reviews and forums.
Verdicts:
  PASS                     - survived rules and voice judge
  REFUSED(rule, reason)    - deterministic do-not-say hit (costs nothing)
  VOICE-FLAG(reason)       - passed rules, but the judge scored it off-voice
"""

import re
from concurrent.futures import ThreadPoolExecutor

from config import llm_call, parse_json
from variants import BRAND_VOICES

VOICE_PASS_THRESHOLD = 6  # judge score 0-10; >= threshold passes

# ---------------------------------------------------------------- deterministic


def _rx(pattern):
    return re.compile(pattern, re.IGNORECASE)


# (rule_id, lines or None for all, regex, evidence-backed reason)
_REGEX_RULES = [
    (
        "absolute-leak-blowout",
        None,
        _rx(r"leak[\s-]?proof|leak[\s-]?free|100\s*%\s*leak|never\s+leaks?\b|"
            r"zero\s+(leaks?|blowouts?)\b|\bno\s+leaks?\b|won'?t\s+(ever\s+)?leak|"
            r"blowout[\s-]?proof|\bno\s+blowouts?\b|never\s+.{0,12}blowout|"
            r"guaranteed?\s+(leak|blowout|dry)"),
        "Absolute leak/blowout claim - user experience is polarised in public reviews "
        "('leaked all over even though states has side shield guards' vs 'almost never "
        "had a leak', both 2025; SEA: 'Petpet and Huggies both bocor'). The brand's own "
        "SG copy stays hedged ('Superior leak protection'). SCAP 5.1: no misleading by "
        "exaggeration.",
    ),
    (
        "natural-percent-inflation",
        None,
        _rx(r"100\s*%\s*(all[\s-])?natural|all[\s-]natural|purely?\s+natural|"
            r"chemical[\s-]?free|toxin[\s-]?free|\bno\s+chemicals\b|"
            r"nothing\s+artificial|made\s+(entirely\s+)?(of|from)\s+nature\b"),
        "Natural-content inflation - the brand's own Naturemade footnote narrows the "
        "'100% Imported Natural Fibres' headline to a liner that 'contains 1% plant-based "
        "fiber; 100% imported from Europe' (100% attaches to import origin, not fibre "
        "content). SCAP Appendix L bars unqualified environmental claims; US class "
        "actions contest 'plant-based/natural' wipes marketing.",
    ),
    (
        "rash-hypoallergenic-guarantee",
        None,
        _rx(r"hypo[\s-]?allergenic|rash[\s-]?free\b|\bno\s+(more\s+)?rash(es)?\b|"
            r"never\s+.{0,20}rash|stops?\s+rash|prevents?\s+(diaper\s+|nappy\s+)?rash|"
            r"rash[\s-]?proof|dermatologist[\s-]?(approved|recommended)|"
            r"cures?\s+(rash|eczema)|(safe|gentle)\s+for\s+all\s+skin"),
        "Rash/skin-safety guarantee - contested by real users (SG blogger: 'not as "
        "hypoallergenic as it states', rash on size change; 2025 global cluster: 'rash "
        "that almost looked like a chemical burn') and by live US class actions on "
        "'hypoallergenic' (Burns v. K-C 2025; Rojas v. K-C 2026). The only licensed "
        "form is line-specific with its published citation ('breathability clinically "
        "proven to help prevent diaper rash - Akin et al., Pediatric Dermatology, 2001') "
        "- conservative by design: a claims owner may whitelist that exact form.",
    ),
    (
        "hospital-endorsement",
        None,
        _rx(r"\bhospitals?\b|"
            r"trusted\s+by\s+(doctors?|nurses?|p(a)?ediatricians?)|"
            r"(doctors?|p(a)?ediatricians?|midwi(fe|ves))[\s-]?(recommended|approved|choice)"),
        "Hospital/professional endorsement - SCAP medical appendix 4.3 allows hospital/"
        "doctor references in ads only if fully substantiated (peer-review published), "
        "so ANY hospital mention is blocked pending substantiation (conservative by "
        "design); NAD 2018 made Kimberly-Clark drop 'more hospitals than ever are "
        "choosing Huggies' as 'based on assumptions, not facts'. The substantiated SG "
        "trust claim is the Euromonitor mums line, not hospitals.",
    ),
    (
        "fit-superlative",
        None,
        _rx(r"#\s?1\s+(best[\s-]?)?fit(ting)?|best[\s-]?fitting\s+diaper\s+"
            r"(ever|in\s+(sg|singapore)|on\s+the\s+market)|perfect\s+fit\b|"
            r"fits\s+(every|all|any)\s+bab|true[\s-]to[\s-]size|"
            r"never\s+(sags?|gaps?|slips?)"),
        "Market-wide fit superlative - NAD Case #7248 (Feb 2024) recommended "
        "discontinuing '#1 Best Fitting Diaper' (evidence covered one line only, not "
        "the market); public sizing reports directly contradict each other ('runs "
        "smaller than Pampers' vs 'Pampers runs smaller'; SEA: 'actual diaper size is "
        "smaller than the other brands'). Self-scoped phrasing ('our best-fitting') "
        "is the licensed form.",
    ),
    (
        "competitor-superiority",
        None,
        _rx(r"absorbs?\s+(better|more)\s+than|(softest|driest|thinnest|most\s+absorbent|"
            r"best)\s+(diaper|nappy|pants)\s+(ever|in\s+(sg|singapore)|on\s+the\s+market)|"
            r"(beats?|outperforms?)\s+(pampers|mamypoko|merries|drypers|moony|rascal|every)|"
            r"(than|vs\.?)\s+(pampers|mamypoko|merries|drypers|moony|rascal)|"
            r"no\s+other\s+(diaper|nappy|brand)"),
        "Competitor-superiority claim - SG parents rank rivals at or above Huggies on "
        "the exact axes ads would claim ('Mamy Poko absorbs better than Huggies', "
        "KiasuParents; HoneyKids 2026 recommends other brands for overnight); Taiwan's "
        "FTC fined Kimberly-Clark NT$800,000 (2017) over a comparative demo 'not "
        "performed in accordance with normal use'. SCAP 9.3: comparisons must be clear, "
        "fair, same-basis.",
    ),
    (
        "stat-inflation",
        None,
        _rx(r"99\.9\s*%|100\s*%\s*(dry(ness)?|protection|absorb)|"
            r"\b\d{1,3}\s*%\s+of\s+(mums?|moms?|mothers?|parents?)|"
            r"\b\d{1,2}\s+(in|out\s+of)\s+\d{1,2}\s+(mums?|moms?|mothers?|parents?)"),
        "Statistical inflation - the brand's own Panda Pants page says 'Locks Away "
        "99.9%' in the bullet but '99%' in the feature grid ('based on 1st rewet data "
        "of internal testing'); the substantiated ceiling is 99% + footnote. Survey-"
        "style claims echo the Taiwan FTC finding ('90% of mothers are willing to "
        "switch' rested on 21 people at a staged demo). SCAP 5.3: statistics must not "
        "imply greater validity than they have.",
    ),
    (
        "unqualified-clinical-language",
        None,
        _rx(r"clinically\s+proven\s+(safe|to\s+protect|leak)|medical[\s-]?grade|"
            r"scientifically\s+(proven|guaranteed)|lab[\s-]?certified\s+safe|"
            r"therapeutic|heals?\s+(skin|rash)"),
        "Unqualified clinical/scientific language - SCAP 5.3 bars scientific jargon "
        "that implies a basis claims do not possess; the brand's own licensed clinical "
        "claims are narrow and cited (Dermatest 5-Star seal; Akin et al. 2001 for "
        "breathability; zinc-liner claims in the US are fenced 'Not for therapeutic "
        "use'). Anything broader needs substantiation held 'ready for immediate "
        "production' (SCAP Part III 1.1).",
    ),
    (
        "little-swimmers-absorbency",
        ("little-swimmers",),
        _rx(r"absorb\w*|leak[\s-]?(proof|free)|\bno\s+leaks?\b|"
            r"keeps?\s+.{0,20}dry|stays?\s+dry|\bdry\s+(bum|bottom|bab)|"
            r"holds?\s+(pee|urine|liquid|everything)|12\s*h(ou)?rs?"),
        "Absorbency implication for swim pants - Little Swimmers 'have almost no "
        "absorbency by design' (independent absorbency test, Feb 2026: 'leaked on the "
        "first wetting' out of water); the product's job is containment during water "
        "play. Any dryness/absorbency framing for this line misrepresents the product "
        "category. Product-scoped hard rule.",
    ),
]

# Conditional rule: "12 hours" without the brand's own "up to" qualifier. The SG
# substantiation footnote reads "Based on research on average urination rate of
# babies per 12hrs" - a usage model, not a wear test - so the licensed form is
# "up to 12 hours", never bare "12 hours dry" or absolutes like "all night, every
# night". (AU reviews of a redesigned line: old ones "would last the whole night
# (12-13 hours)", new ones "barely last 5-8 hours" - duration absolutes age badly.)
_TWELVE_HOURS = _rx(r"\b(1[0-2])\s*[\s-]?h(ou)?rs?\b|\ball\s+night,?\s+every\s+night|"
                    r"dry\s+all\s+(the\s+)?(night|time)|through\s+the\s+night,?\s+"
                    r"(guaranteed|every)")
_UP_TO = _rx(r"up\s+to\s+(1[0-2])\s*[\s-]?h(ou)?rs?")

_TWELVE_HOURS_REASON = (
    "Duration claim without the 'up to' qualifier - the brand's own footnote bases "
    "'Up To 12 Hours***' on 'research on average urination rate of babies per 12hrs' "
    "(a usage model, not a wear test), and public reviews contest unconditional "
    "duration ('barely last 5-8 hours' after a redesign). SCAP 5.1: omission of a "
    "material qualifier misleads. Licensed form: 'up to 12 hours'."
)


def _variant_text(variant):
    return " ".join(str(variant.get(k, ""))
                    for k in ("hook", "caption", "script", "audience_variant"))


def deterministic_check(variant):
    """Returns list of (rule_id, reason) violations. Free - no LLM."""
    brand = variant.get("brand", "")
    text = _variant_text(variant)
    hits = []
    for rule_id, lines, rx, reason in _REGEX_RULES:
        if lines and brand not in lines:
            continue
        m = rx.search(text)
        if m:
            hits.append((rule_id, f"matched '{m.group(0)}' - {reason}"))
    # duration conditional: a 10-12 hour / all-night claim is licensed only in its
    # "up to" form (little-swimmers is already covered by its harder line rule)
    if brand != "little-swimmers":
        m = _TWELVE_HOURS.search(text)
        if m and not _UP_TO.search(text):
            hits.append(("duration-without-up-to",
                         f"matched '{m.group(0)}' - {_TWELVE_HOURS_REASON}"))
    return hits


# ----------------------------------------------------------------- voice judge

JUDGE_SYSTEM = """You are the brand-voice judge in a creative QA gate. Score how \
on-voice an ad variant is for its product line, 0-10 (10 = indistinguishable from the \
brand's best copy; below 6 = off-voice). Judge VOICE ONLY (register, tone, audience fit, \
platform fit) - claims compliance is checked elsewhere. Return ONLY JSON: \
{"score": <0-10>, "reason": "<one sentence>"}"""


def voice_judge(variant):
    brand = variant["brand"]
    user = (
        f"Product-line voice rubric:\n{BRAND_VOICES[brand]}\n\n"
        f"Variant:\n- hook: {variant.get('hook')}\n- caption: {variant.get('caption')}\n"
        f"- script: {variant.get('script')}\n- audience_variant: {variant.get('audience_variant')}\n\n"
        f"Score it."
    )
    # one retry on a malformed judge response, then fail CLOSED (flag, don't crash):
    # a single bad response must not lose a whole paid run
    for attempt in (1, 2):
        try:
            result = parse_json(
                llm_call("gate-voice-judge", "judge", JUDGE_SYSTEM, user, max_tokens=1000))
            return float(result["score"]), str(result["reason"])
        except (ValueError, KeyError, TypeError) as e:
            last_err = e
    return 0.0, f"judge response unparseable after retry ({last_err}) - failing closed"


# ------------------------------------------------------------------- full gate


def gate_variant(variant, skip_judge=False):
    """Returns the variant annotated with verdict / rule / reason / voice_score."""
    v = dict(variant)
    hits = deterministic_check(variant)
    if hits:
        v["verdict"] = "REFUSED"
        v["rule"] = "; ".join(h[0] for h in hits)
        v["reason"] = " | ".join(h[1] for h in hits)
        v["voice_score"] = None
        return v
    if skip_judge:
        v.update(verdict="PASS", rule="", reason="deterministic rules passed (judge skipped)",
                 voice_score=None)
        return v
    score, reason = voice_judge(variant)
    if score >= VOICE_PASS_THRESHOLD:
        v.update(verdict="PASS", rule="", reason=f"on-voice ({score:.0f}/10): {reason}",
                 voice_score=score)
    else:
        v.update(verdict="VOICE-FLAG", rule="voice", reason=f"({score:.0f}/10) {reason}",
                 voice_score=score)
    return v


def gate_all(variants, workers=6):
    """Deterministic checks run inline (free); surviving variants hit the judge
    concurrently. Order of the input list is preserved."""
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(gate_variant, variants))
