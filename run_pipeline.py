"""End-to-end pipeline run: corpus -> briefs -> variants -> gate -> repair -> report.

Fixed stages; LLM calls inside three of them (briefs/variants/repair on the cheap
tier, voice judge on the strong tier). The repair stage is the pipeline's one
agentic step: bounded, and its output still has to pass the same gate. Also runs
the live-copy audit: the brand's own published site copy through the gate.
"""

import time

from briefs import make_briefs
from corpus import load_cards
from gate import deterministic_check, gate_all
from repair import repair_all
from report import write_reports

LIVE_COPY = {
    "label": "Huggies SG's own site copy (huggies.com.sg/about-us, captured 15 Jul 2026)",
    "brand": "naturemade",
    "hook": "Discover Why Huggies® Is the Trusted Choice for Moms and Hospitals",
    "caption": "",
    "script": "",
    "rewrite": "Discover why Huggies® is the diaper brand mums trust most* (*Euromonitor "
               "International Limited; Tissue and Hygiene 2023ed, retail value RSP, 2022 "
               "data - the substantiation Huggies Singapore already publishes elsewhere). "
               "Keeps the trust story, drops the unfootnoted hospital reference that SCAP's "
               "medical appendix requires to be fully substantiated and that NAD made "
               "Kimberly-Clark abandon in 2018.",
}


def live_copy_audit():
    hits = deterministic_check(LIVE_COPY)
    if not hits:
        return []
    return [{
        "label": LIVE_COPY["label"],
        "text": (LIVE_COPY["hook"] + " " + LIVE_COPY["caption"]).strip(),
        "verdict": "REFUSED",
        "rule": "; ".join(h[0] for h in hits),
        "reason": " | ".join(h[1] for h in hits),
        "rewrite": LIVE_COPY["rewrite"],
    }]


def main():
    t0 = time.time()
    cards = load_cards()
    print(f"[1/6] corpus: {len(cards)} angle cards")

    briefs = make_briefs(cards)
    print(f"[2/6] briefs: {len(briefs)} generated (cheap tier, batched)")

    from concurrent.futures import ThreadPoolExecutor

    from variants import gen_variants
    with ThreadPoolExecutor(max_workers=4) as ex:
        batches = list(ex.map(gen_variants, briefs))
    all_variants = [v for batch in batches for v in batch]
    print(f"[3/6] variants: {len(all_variants)} generated (cheap tier, batched)")

    gated = gate_all(all_variants)
    n_refused = sum(1 for v in gated if v["verdict"] == "REFUSED")
    n_flag = sum(1 for v in gated if v["verdict"] == "VOICE-FLAG")
    n_pass = sum(1 for v in gated if v["verdict"] == "PASS")
    print(f"[4/6] gate: {n_pass} PASS / {n_refused} REFUSED / {n_flag} VOICE-FLAG "
          f"(deterministic rules free; judge only on survivors)")

    final, repair_stats = repair_all(gated)
    print(f"[5/6] repair: {repair_stats['salvaged']}/{repair_stats['candidates']} salvaged "
          f"in {repair_stats['attempts_total']} attempt(s), "
          f"{repair_stats['human_queue']} to human queue "
          f"(bounded: 2 attempts, US$0.25 cap{', BUDGET HIT' if repair_stats['budget_exhausted'] else ''}) "
          f"| repair spend US${repair_stats['repair_cost_usd']:.4f}")

    extras = live_copy_audit()
    counts, per_100 = write_reports(final, refusal_extras=extras, repair_stats=repair_stats)
    print(f"[6/6] report written to out/ | live-copy audit: "
          f"{'REFUSED (as designed)' if extras else 'no hit'}")
    print(f"cost per 100 gated variants: US${per_100:.2f} | wall time {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
