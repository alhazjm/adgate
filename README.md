# adgate

> **Provenance & intent.** All data here is public — the brand's own published
> site copy and substantiation footnotes, Singapore's advertising code and
> published regulator decisions, and customer reviews from public marketplaces,
> forums and archives. The system's purpose is protective: it stops ad copy
> from carrying claims the substantiation doesn't cover or that real customers
> contest, before spend amplifies them. Nothing in this repository is internal
> to any company; adgate is not affiliated with or endorsed by Huggies,
> Kimberly-Clark or any brand named, and everything the pipeline generates is
> synthetic demo output, never a real advertisement. Happy to take this
> repository private on request.

A gated ad-creative pipeline with **one bounded agentic stage**, built as a
working case study on a global baby-care brand's Singapore market (Huggies SG,
four product lines). Evidence in → angles → briefs → variants → a deterministic
claims-and-voice gate that refuses → a repair agent that rewrites refusals and
resubmits → humans decide.

Plain Python, no framework. The path is fixed and testable; the pipeline has
agency in exactly one place — repair, where the next step depends on what the
gate found — and that agency is bounded four ways:

1. **attempts** — 2 rewrites per variant, then stop
2. **spend** — a per-run budget for the repair stage, checked before every call
3. **verdicts** — the repair model's output has no verdict field; every rewrite
   re-enters `gate_variant()`, and only the gate decides
4. **fail-closed** — anything still failing lands in the human queue with its
   full repair history, never silently dropped

**Measured, not estimated:** the included run in `out/` generated and gated 48
variants for **US$0.351** in model spend (**US$0.73 per 100 gated variants**,
repair included) — a cheap model generates and repairs, the strong judge reads
only rule-survivors. The gate refused 12 variants and voice-flagged 3; the
repair agent salvaged **15/15 in 17 attempts for US$0.0248**, with zero left in
the human queue this run. The eval suite went **9/9 known-bad refused, 4/4
known-good passed, 3/3 repair fixtures behaved**; one known-bad fixture is the
brand's own live site copy — an unfootnoted hospital-trust line — which the
gate refused on a code-and-precedent-backed rule and rewrote to the form the
brand's own published substantiation supports. `out/run-report.html` renders
the whole run as one static page.

## What makes the rules interesting

The ten do-not-say rules don't come from imagination — each traces to citable
evidence of a specific kind:

- **the brand's own footnotes**: the SG site's "100% Imported Natural Fibres"
  headline resolves, in its own feature grid, to a liner that "contains 1%
  plant-based fiber; 100% imported from Europe" — the 100% attaches to import
  origin, not fibre content. "Up To 12 Hours" rests on "research on average
  urination rate of babies per 12hrs" (a usage model, not a wear test). One
  page says "99.9%" in the bullet and "99%" in the grid.
- **the code**: Singapore's Code of Advertising Practice (ASAS/SCAP) — no
  misleading by "inaccuracy, ambiguity, exaggeration, omission"; objective
  claims substantiated and "ready for immediate production"; hospital/doctor
  references only if fully substantiated; unqualified environmental claims
  barred (Appendix L).
- **precedent**: NAD 2018 (Kimberly-Clark dropped "more hospitals than ever
  are choosing Huggies" — "based on assumptions, not facts"); NAD Case #7248,
  Feb 2024 ("#1 Best Fitting Diaper" discontinued); Taiwan FTC 2017 (NT$800,000
  fine over a staged comparative demo); live US class actions on
  "hypoallergenic".
- **voice of customer**: polarised leak reports, contested sizing, a 2025
  rash-complaint cluster, SG parents ranking rivals at parity on overnight
  hold — all from public reviews, forums and archives, provenance-graded
  (fetched / cached / snippet) in `corpus.py`.

**Conservative by design:** rules match banned phrasings even inside quoted
customer reviews, and any hospital mention is blocked pending substantiation.
A claims-list owner can whitelist specific licensed forms later (e.g. the
brand's own cited breathability claim, Akin et al., Pediatric Dermatology 2001).

## Files

| file | stage |
|---|---|
| `corpus.py` | angle cards from the public-evidence sweep (verbatim receipts, provenance grades — embedded) |
| `briefs.py` | angle card → creative brief (cheap model tier) |
| `variants.py` | brief → 6 hook/caption/script variants per product-line voice + audience split (cheap tier) |
| `gate.py` | deterministic do-not-say rules FIRST (free) → LLM voice judge on survivors (strong tier) |
| `repair.py` | **the bounded repair agent** — reads the rule that fired and the evidence behind it, rewrites, resubmits to the same gate |
| `report.py` | batch sheet (CSV + MD), refusal log with before/after repairs, measured cost per 100 gated variants |
| `evals.py` | known-bad MUST be refused + known-good MUST pass + repair fixtures (salvageable, unshippable, evasion probe) |
| `run_pipeline.py` | one runner: end-to-end + live-copy audit (the brand's own published copy through the gate) |
| `make_run_report.py` | renders `out/` into a single static HTML run report |
| `site/index.html` | try-the-gate page: the ten rules ported to client-side JS — paste a caption, get the verdict and the evidence (no model, no cost) |
| `config.py` | provider selection + per-stage token/cost tracking |

The engine (fixed stages, gate-then-judge, bounded repair, measured costs) is
brand-agnostic and reused from an earlier private case study of mine; this
repository points it at a new market, a new evidence base and a new ruleset.

## How to run

```
# 1. evals must be green first (gate + repair fixtures)
python evals.py

# 2. full run (8 angle cards -> 48 variants -> gate -> repair -> out/)
python run_pipeline.py

# 3. render the run report
python make_run_report.py
```

Outputs land in `out/`. This repo ships a real run's artifacts so the numbers
are inspectable without a key.

## Providers (env)

The pipeline auto-detects what's available:

| env | provider | default models (gen / judge) |
|---|---|---|
| `OPENAI_API_KEY` (+optional `OPENAI_BASE_URL` for compatible APIs) | OpenAI | `gpt-5-mini` / `gpt-5.4` |
| `ANTHROPIC_API_KEY` | Anthropic | `claude-haiku-4-5` / `claude-opus-4-8` |
| `MOCK_LLM=1` | mock | canned outputs, zero cost |

Override with `GEN_MODEL` / `JUDGE_MODEL`; prices (USD per 1M tokens) with
`GEN_PRICE_IN/OUT`, `JUDGE_PRICE_IN/OUT`. The shipped run used Anthropic
(haiku generates and repairs, opus judges).

## The repair stage — scale AND refine, without self-approval

Refused and off-voice variants go to `repair.py`. The repair prompt sees the
exact rule that fired and the evidence behind it, so the rewrite is targeted,
not a blind retry. Product line and angle are pinned — the agent cannot dodge
a line-scoped rule by moving the variant. The repair evals encode the failure
mode that matters:

- a **salvageable** refusal (bad claim, good angle) must come back PASS with
  the claim gone in any wording;
- an **unshippable** claim (absorbency framing on swim pants that "have almost
  no absorbency by design") must either be legitimately re-angled to the
  product's real job or fail closed to the human queue — and the repaired copy
  is checked against an **evasion list of paraphrases the gate's own regex
  does not cover** ("soaks up", "wicks away", "bone dry"). An evasion hit
  fails the eval: it means the agent smuggled the claim past the letter of
  the rules, which is a rule gap to close, not a pass.

## What's mock vs real

- **Always real:** the deterministic gate (regex rules — no LLM, no cost), the
  eval fixtures, the live-copy audit, all report mechanics, the `site/` page.
- **Real with a live key:** briefs, variants, voice judge, repair, the measured
  cost line (actual tokens × prices, never estimated).
- **`MOCK_LLM=1`:** canned outputs for mechanics verification — the cost line
  reads $0 and reports are labeled provider=mock.
- **Performance readback** (winners/losers re-entering the corpus as evidence)
  is designed but requires ad-account access — the loop's right edge.
