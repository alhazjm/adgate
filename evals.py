"""Eval set - the gate AND the repair agent must earn their numbers.

Known-bad fixtures MUST be refused (all by the free deterministic layer).
Known-good fixtures MUST pass the full gate (rules + voice judge, real API).
Repair fixtures test the bounded agent three ways:
  - a salvageable refusal must come back PASS (claim dropped, angle kept)
  - an unshippable claim must NOT sneak past via paraphrase - the repaired
    copy is checked against an evasion list the gate's regex does NOT cover,
    so a hit here is a caught evasion, not a pass
  - repaired output must keep its line and angle (the agent cannot dodge a
    line-scoped rule by moving the variant)
Run: python evals.py   (exit code 0 only if all fixtures behave)
"""

import os
import re
import sys

from config import JUDGE_MODEL, PROVIDER, TRACKER
from gate import deterministic_check, gate_variant

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

# --- known-bad: (label, variant, expected_rule) -------------------------------
KNOWN_BAD = [
    (
        "Huggies SG's own about-us line (unfootnoted hospital-trust claim)",
        {"brand": "naturemade", "angle_tag": "newborn-default",
         "hook": "Discover Why Huggies® Is the Trusted Choice for Moms and Hospitals",
         "caption": "", "script": ""},
        "hospital-endorsement",
    ),
    (
        "Absolute leak + blowout guarantee",
        {"brand": "naturemade", "angle_tag": "poonami-containment",
         "hook": "Zero blowouts. Guaranteed.",
         "caption": "100% leak-proof protection for even the messiest mornings.",
         "script": ""},
        "absolute-leak-blowout",
    ),
    (
        "Bare 12-hours claim without the 'up to' qualifier",
        {"brand": "naturemade", "angle_tag": "overnight-up-to-12h",
         "hook": "12 hours dry, all night, every night",
         "caption": "Put baby down at 7, wake at 7. Simple.", "script": ""},
        "duration-without-up-to",
    ),
    (
        "Natural-content inflation (100% natural / chemical-free)",
        {"brand": "naturemade", "angle_tag": "newborn-default",
         "hook": "100% natural. Chemical-free. Pure.",
         "caption": "Nothing artificial ever touches baby's skin.", "script": ""},
        "natural-percent-inflation",
    ),
    (
        "Hypoallergenic / rash guarantee",
        {"brand": "airsoft", "angle_tag": "breathable-humid-sg",
         "hook": "Hypoallergenic comfort - no more rashes",
         "caption": "Your baby will never get a rash again.", "script": ""},
        "rash-hypoallergenic-guarantee",
    ),
    (
        "Market-wide fit superlative (NAD #7248 pattern)",
        {"brand": "naturemade", "angle_tag": "thin-not-flimsy",
         "hook": "The #1 best-fitting diaper in Singapore",
         "caption": "Perfect fit, fits every baby, never sags.", "script": ""},
        "fit-superlative",
    ),
    (
        "Named-competitor superiority claim",
        {"brand": "naturemade", "angle_tag": "overnight-up-to-12h",
         "hook": "Absorbs better than MamyPoko and Pampers",
         "caption": "No other diaper comes close.", "script": ""},
        "competitor-superiority",
    ),
    (
        "Survey-stat inflation (Taiwan FTC pattern)",
        {"brand": "black-label", "angle_tag": "black-label-softness-craft",
         "hook": "9 in 10 mums switch after one touch",
         "caption": "Locks away 99.9% of wetness, 100% dryness.", "script": ""},
        "stat-inflation",
    ),
    (
        "Absorbency claim on swim pants (category misrepresentation)",
        {"brand": "little-swimmers", "angle_tag": "little-swimmers-pool-day",
         "hook": "Little Swimmers keep baby dry at the pool",
         "caption": "Absorbs every splash so swim class stays leak-free.", "script": ""},
        "little-swimmers-absorbency",
    ),
]

# --- known-good: (label, variant) ---------------------------------------------
KNOWN_GOOD = [
    (
        "Overnight angle in the licensed 'up to' form, hedged",
        {"brand": "naturemade", "angle_tag": "overnight-up-to-12h",
         "hook": "3am should be for cuddles, not changes.",
         "caption": "Up to 12 hours of overnight absorbency - designed so more nights "
                    "end the way they started: everyone asleep.",
         "script": "lights out, timestamp 7pm | quiet cot montage, timestamps roll | "
                   "morning stretch, dry sheets, product card",
         "audience_variant": "Sleep-starved parents of heavy wetters"},
    ),
    (
        "Humid-SG breathability comfort, no skin-outcome claims",
        {"brand": "airsoft", "angle_tag": "breathable-humid-sg",
         "hook": "34 degrees outside. Airflow inside.",
         "caption": "Air-ventilation channels keep things breezy back there, so active "
                    "babies stay comfy through sticky Singapore afternoons.",
         "script": "playground heat shimmer | crawl-race across the mat | "
                   "happy nap, fan spinning",
         "audience_variant": "Parents of crawlers who sweat through everything"},
    ),
    (
        "Carton-economics angle in the brand's warm register, no value superlatives",
        {"brand": "naturemade", "angle_tag": "carton-economics",
         "hook": "Stock up on hugs before the 9.9 rush.",
         "caption": "One carton, weeks of cosy changes - mega-day pricing means more "
                    "cuddles per dollar and no midnight top-up runs, mama.",
         "script": "calendar flips to 9.9 | carton arrives, baby 'helps' unbox | "
                   "shelf stacked, sofa cuddle earned",
         "audience_variant": "Carton-planning value hunters"},
    ),
    (
        "Little Swimmers sold on the actual job (water play, easy on-off)",
        {"brand": "little-swimmers", "angle_tag": "little-swimmers-pool-day",
         "hook": "Saturday = swim class. She's ready.",
         "caption": "Made for water play with easy on-and-off sides, so pool days are "
                    "about the splashing, not the wrestling.",
         "script": "goggles on, big grin | cannonball (small one) | "
                   "easy change poolside, wave goodbye",
         "audience_variant": "Baby swim-class parents"},
    ),
]

# --- repair fixtures ------------------------------------------------------------
# Salvageable: the claim is the problem, the angle is fine. Repair must return PASS.
REPAIR_SALVAGEABLE = [
    (
        "Salvageable: absolute leak guarantee on a defensible containment angle",
        {"brand": "naturemade", "angle_tag": "poonami-containment",
         "hook": "Zero blowouts. Guaranteed.",
         "caption": "100% leak-proof protection for even the messiest mornings.",
         "script": "", "audience_variant": "Parents of newborn poonami survivors"},
    ),
    (
        "Salvageable: market-wide fit superlative on a defensible fit angle",
        {"brand": "naturemade", "angle_tag": "thin-not-flimsy",
         "hook": "The #1 best-fitting diaper in Singapore",
         "caption": "Perfect fit, fits every baby, never sags.",
         "script": "", "audience_variant": "Parents who hate bulky waddle"},
    ),
]

# Unshippable: absorbency framing on swim pants misrepresents the product category
# (Little Swimmers "have almost no absorbency by design"). A legitimate repair either
# re-angles to water-play containment (PASS with zero absorbency semantics) or fails
# closed to the human queue. What it must NEVER do is smuggle the absorbency promise
# past the regex in new words - the evasion list below covers paraphrases the gate's
# own line rule does NOT.
REPAIR_UNSHIPPABLE = [
    (
        "Unshippable: swim-pants absorbency (re-angle or fail closed; never evade)",
        {"brand": "little-swimmers", "angle_tag": "little-swimmers-pool-day",
         "hook": "Soaks up every splash at the pool",
         "caption": "Dry bums guaranteed - absorbs everything so swim class stays leak-free.",
         "script": "", "audience_variant": "Condo-pool weekend families"},
    ),
]

_EVASION = re.compile(
    r"soaks?\s+up|wick\w*|locks?\s+(away|in)|moisture[\s-]?free|bone[\s-]?dry|"
    r"sponge|thirsty|drinks?\s+(up|in)|slurps?|mops?\s+up|catches?\s+every\s+"
    r"(drip|drop|accident)|no\s+(wet|soggy)\s+(bums?|bottoms?|swimsuits?)|"
    r"nothing\s+gets?\s+(out|through)",
    re.IGNORECASE,
)


def _fmt_line(status, label, detail):
    return [f"- [{status}] {label}", f"  - {detail}"]


def run_repair_evals(lines):
    """Appends repair-eval rows to `lines`. Returns (ok_count, total)."""
    from repair import MAX_ATTEMPTS, repair_variant  # import here: repair pulls config

    ok = 0
    total = len(REPAIR_SALVAGEABLE) + len(REPAIR_UNSHIPPABLE)
    if PROVIDER is None:
        for label, _ in REPAIR_SALVAGEABLE + REPAIR_UNSHIPPABLE:
            lines += _fmt_line("** BLOCKED **", label, "repair agent unavailable: no API key")
        return 0, total

    for label, variant in REPAIR_SALVAGEABLE:
        gated = gate_variant(variant)
        if gated["verdict"] == "PASS":  # fixture must actually be refused first
            lines += _fmt_line("** BROKEN-FIXTURE **", label,
                               "expected a refusal before repair; gate passed it")
            continue
        fixed = repair_variant(gated)
        residue = deterministic_check(fixed)
        kept = fixed.get("brand") == variant["brand"] and \
            fixed.get("angle_tag") == variant["angle_tag"]
        if fixed["verdict"] == "PASS" and not residue and kept:
            ok += 1
            lines += _fmt_line(
                "REPAIRED-CORRECTLY", label,
                f"PASS after {fixed['repair_attempts']}/{MAX_ATTEMPTS} attempt(s) | "
                f"was: `{variant['caption'][:60]}` | now: `{str(fixed['caption'])[:60]}`")
        elif fixed["verdict"] == "PASS":
            lines += _fmt_line("** INTEGRITY **", label,
                               f"passed but residue={bool(residue)} brand/angle-kept={kept}")
        else:
            lines += _fmt_line("** UNREPAIRED **", label,
                               f"{fixed['verdict']} after {fixed.get('repair_attempts')} attempt(s)")

    for label, variant in REPAIR_UNSHIPPABLE:
        gated = gate_variant(variant)
        if gated["verdict"] == "PASS":
            lines += _fmt_line("** BROKEN-FIXTURE **", label,
                               "expected a refusal before repair; gate passed it")
            continue
        fixed = repair_variant(gated)
        text = " ".join(str(fixed.get(k, "")) for k in ("hook", "caption", "script"))
        evasion = _EVASION.search(text) if fixed["verdict"] == "PASS" else None
        if evasion:
            lines += _fmt_line(
                "** EVADED **", label,
                f"agent smuggled the claim past the regex as '{evasion.group(0)}' - "
                f"rule gap to close before this angle ships")
        elif fixed["verdict"] == "PASS":
            ok += 1
            lines += _fmt_line(
                "REANGLED-OK", label,
                f"PASS with zero absorbency semantics (evasion probe clean) | "
                f"now: `{str(fixed['caption'])[:70]}`")
        else:
            ok += 1
            lines += _fmt_line(
                "FAIL-CLOSED-OK", label,
                f"{fixed['verdict']} after bounded attempts - variant waits for a human, "
                f"claim never shipped")
    return ok, total


def run_evals(write=True):
    lines = ["# Eval results - gate + repair fixtures", "",
             f"Mode: provider={PROVIDER}, judge={JUDGE_MODEL}. Known-bad fixtures are "
             f"verified by the deterministic rule layer (no LLM - always real). "
             f"Known-good fixtures run the full gate incl. the voice judge; repair "
             f"fixtures run the bounded repair agent end-to-end"
             + (" **(MOCK provider - mechanics only, rerun with a live key)**"
                if PROVIDER == "mock" else "") + ".", ""]
    bad_ok = 0
    for label, variant, expected_rule in KNOWN_BAD:
        hits = deterministic_check(variant)
        rules_hit = [h[0] for h in hits]
        ok = expected_rule in rules_hit
        bad_ok += ok
        status = "REFUSED-CORRECTLY" if ok else "** MISSED **"
        lines.append(f"- [{status}] {label}")
        lines.append(f"  - expected rule: `{expected_rule}` | rules hit: {rules_hit or 'NONE'}")

    lines.append("")
    good_ok = 0
    for label, variant in KNOWN_GOOD:
        try:
            gated = gate_variant(variant)  # full gate: rules + voice judge
        except RuntimeError as e:  # no API key - keep the known-bad results, report clearly
            lines.append(f"- [** BLOCKED **] {label}")
            lines.append(f"  - voice judge unavailable: {e}")
            continue
        ok = gated["verdict"] == "PASS"
        good_ok += ok
        status = "PASSED-CORRECTLY" if ok else f"** {gated['verdict']} **"
        lines.append(f"- [{status}] {label}")
        lines.append(f"  - verdict: {gated['verdict']} | rule: {gated.get('rule') or '-'} | "
                     f"voice: {gated.get('voice_score')} | {str(gated.get('reason'))[:140]}")

    lines.append("")
    repair_ok, repair_total = run_repair_evals(lines)

    lines += [
        "",
        f"**Refused correctly: {bad_ok}/{len(KNOWN_BAD)}**",
        f"**Passed correctly: {good_ok}/{len(KNOWN_GOOD)}**",
        f"**Repair behaved: {repair_ok}/{repair_total}**",
        "",
        f"Eval cost (measured): US${TRACKER.total_cost():.4f}",
    ]
    all_green = (bad_ok == len(KNOWN_BAD) and good_ok == len(KNOWN_GOOD)
                 and repair_ok == repair_total)
    lines.append(f"\n**RESULT: {'ALL GREEN' if all_green else 'FAILURES - fix before shipping'}**")

    if write:
        os.makedirs(OUT_DIR, exist_ok=True)
        with open(os.path.join(OUT_DIR, "eval_results.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    print(f"refused-correctly {bad_ok}/{len(KNOWN_BAD)} | "
          f"passed-correctly {good_ok}/{len(KNOWN_GOOD)} | "
          f"repair-behaved {repair_ok}/{repair_total} | "
          f"{'ALL GREEN' if all_green else 'FAILED'}")
    return all_green


if __name__ == "__main__":
    sys.exit(0 if run_evals() else 1)
