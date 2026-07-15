# Eval results - gate + repair fixtures

Mode: provider=anthropic, judge=claude-opus-4-8. Known-bad fixtures are verified by the deterministic rule layer (no LLM - always real). Known-good fixtures run the full gate incl. the voice judge; repair fixtures run the bounded repair agent end-to-end.

- [REFUSED-CORRECTLY] Huggies SG's own about-us line (unfootnoted hospital-trust claim)
  - expected rule: `hospital-endorsement` | rules hit: ['hospital-endorsement']
- [REFUSED-CORRECTLY] Absolute leak + blowout guarantee
  - expected rule: `absolute-leak-blowout` | rules hit: ['absolute-leak-blowout']
- [REFUSED-CORRECTLY] Bare 12-hours claim without the 'up to' qualifier
  - expected rule: `duration-without-up-to` | rules hit: ['duration-without-up-to']
- [REFUSED-CORRECTLY] Natural-content inflation (100% natural / chemical-free)
  - expected rule: `natural-percent-inflation` | rules hit: ['natural-percent-inflation']
- [REFUSED-CORRECTLY] Hypoallergenic / rash guarantee
  - expected rule: `rash-hypoallergenic-guarantee` | rules hit: ['rash-hypoallergenic-guarantee']
- [REFUSED-CORRECTLY] Market-wide fit superlative (NAD #7248 pattern)
  - expected rule: `fit-superlative` | rules hit: ['fit-superlative']
- [REFUSED-CORRECTLY] Named-competitor superiority claim
  - expected rule: `competitor-superiority` | rules hit: ['competitor-superiority']
- [REFUSED-CORRECTLY] Survey-stat inflation (Taiwan FTC pattern)
  - expected rule: `stat-inflation` | rules hit: ['stat-inflation']
- [REFUSED-CORRECTLY] Absorbency claim on swim pants (category misrepresentation)
  - expected rule: `little-swimmers-absorbency` | rules hit: ['absolute-leak-blowout', 'little-swimmers-absorbency']

- [PASSED-CORRECTLY] Overnight angle in the licensed 'up to' form, hedged
  - verdict: PASS | rule: - | voice: 6.0 | on-voice (6/10): The warm, reassurance-first overnight angle fits well, but it says 'parents' rather than the brand's signature 'mums', drop
- [PASSED-CORRECTLY] Humid-SG breathability comfort, no skin-outcome claims
  - verdict: PASS | rule: - | voice: 9.0 | on-voice (9/10): Nails the SG-heat-relief angle with breathable airflow benefit, energetic active-baby imagery, and warm-but-practical regis
- [PASSED-CORRECTLY] Carton-economics angle in the brand's warm register, no value superlatives
  - verdict: PASS | rule: - | voice: 8.0 | on-voice (8/10): The hug motif ('Stock up on hugs', 'more cuddles'), warm mum-centric tone, and cosy sofa-cuddle imagery are strongly on-voi
- [PASSED-CORRECTLY] Little Swimmers sold on the actual job (water play, easy on-off)
  - verdict: PASS | rule: - | voice: 9.0 | on-voice (9/10): Sunny, splash-forward energy with baby swim-class specificity, easy on-off praise, and containment-in-water focus that neve

- [REPAIRED-CORRECTLY] Salvageable: absolute leak guarantee on a defensible containment angle
  - PASS after 1/2 attempt(s) | was: `100% leak-proof protection for even the messiest mornings.` | now: `Huggies Platinum Naturemade's NatureSoft liner and our signa`
- [REPAIRED-CORRECTLY] Salvageable: market-wide fit superlative on a defensible fit angle
  - PASS after 1/2 attempt(s) | was: `Perfect fit, fits every baby, never sags.` | now: `Snug comfort that moves with your baby—no bulk, no sag.`
- [REANGLED-OK] Unshippable: swim-pants absorbency (re-angle or fail closed; never evade)
  - PASS with zero absorbency semantics (evasion probe clean) | now: `Built for water play with secure fit and side shields. Your little one`

**Refused correctly: 9/9**
**Passed correctly: 4/4**
**Repair behaved: 3/3**

Eval cost (measured): US$0.0360

**RESULT: ALL GREEN**