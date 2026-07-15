"""Stage 6: batch sheet (CSV + readable MD), refusal log, repair log,
unit-economics line."""

import csv
import json
import os

from config import GEN_MODEL, JUDGE_MODEL, PROVIDER, TRACKER

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

COLUMNS = ["variant_id", "angle_tag", "brand", "audience_variant", "hook", "caption",
           "script", "verdict", "rule", "voice_score", "reason",
           "repaired", "repair_attempts", "repaired_from_rule",
           "original_hook", "original_caption"]


def _rows(gated):
    rows = []
    for i, v in enumerate(gated, 1):
        rows.append({
            "variant_id": f"V{i:03d}",
            "angle_tag": v.get("angle_tag", ""),
            "brand": v.get("brand", ""),
            "audience_variant": v.get("audience_variant", ""),
            "hook": v.get("hook", ""),
            "caption": v.get("caption", ""),
            "script": v.get("script", ""),
            "verdict": v.get("verdict", ""),
            "rule": v.get("rule", ""),
            "voice_score": v.get("voice_score", ""),
            "reason": v.get("reason", ""),
            "repaired": v.get("repaired", ""),
            "repair_attempts": v.get("repair_attempts", ""),
            "repaired_from_rule": v.get("repaired_from_rule", ""),
            "original_hook": v.get("original_hook", ""),
            "original_caption": v.get("original_caption", ""),
        })
    return rows


def cost_lines(n_gated):
    """Per-stage cost table + the unit-economics line, from measured usage."""
    s = TRACKER.summary()
    total = s["total_cost_usd"]
    per_100 = (total / n_gated * 100) if n_gated else 0.0
    lines = [f"Provider: {PROVIDER} | gen model: {GEN_MODEL} | judge model: {JUDGE_MODEL}", ""]
    lines.append(f"{'stage':<18}{'calls':>6}{'in_tok':>10}{'out_tok':>10}{'cost_usd':>12}")
    for stage, d in s["stages"].items():
        lines.append(f"{stage:<18}{d['calls']:>6}{d['input_tokens']:>10}"
                     f"{d['output_tokens']:>10}{d['cost_usd']:>12.4f}")
    lines.append(f"{'TOTAL':<18}{'':>6}{'':>10}{'':>10}{total:>12.4f}")
    lines.append("")
    lines.append(f"UNIT ECONOMICS: cost per 100 gated variants = "
                 f"US${per_100:.2f} (measured: {n_gated} variants gated for US${total:.4f})")
    if s.get("unpriced_models"):
        lines.append(f"WARNING: no price entry for {s['unpriced_models']} - the cost line "
                     f"UNDERSTATES real spend. Set GEN/JUDGE_PRICE_IN/OUT env vars.")
    return lines, per_100


def _md_cell(value, width=None):
    """Make any value safe inside a markdown table cell."""
    text = str(value).replace("|", "/").replace("\n", " ").replace("\r", " ")
    return text[:width] if width else text


def write_reports(gated, refusal_extras=None, repair_stats=None):
    """gated: final variants (post-gate, post-repair).
    refusal_extras: extra refusal-log entries (e.g. the live-copy audit).
    repair_stats: dict from repair.repair_all()."""
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = _rows(gated)

    # utf-8-sig: BOM so Excel-on-Windows opens emoji-bearing copy correctly
    with open(os.path.join(OUT_DIR, "batch_sheet.csv"), "w", newline="",
              encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)

    counts = {}
    for r in rows:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    n_repaired = sum(1 for r in rows if r["repaired"] is True or r["repaired"] == "True")
    lines, per_100 = cost_lines(len(rows))

    md = ["# Batch sheet - pipeline run", "",
          f"**Verdicts:** {len(rows)} variants -> " +
          ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())) +
          (f" ({n_repaired} of the PASSes repaired by the bounded agent)" if n_repaired else ""),
          "",
          "| id | angle | brand | audience | hook | verdict | rule | voice | repaired | reason |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        repaired_txt = (f"yes ({r['repair_attempts']} att, was {r['repaired_from_rule']})"
                        if r["repaired"] is True or r["repaired"] == "True" else "")
        md.append("| {vid} | {angle} | {brand} | {aud} | {hook} | {verdict} | "
                  "{rule} | {vs} | {rep} | {reason} |".format(
                      vid=_md_cell(r["variant_id"]),
                      angle=_md_cell(r["angle_tag"]),
                      brand=_md_cell(r["brand"]),
                      aud=_md_cell(r["audience_variant"], 30),
                      hook=_md_cell(r["hook"], 60),
                      verdict=_md_cell(r["verdict"]),
                      rule=_md_cell(r["rule"]),
                      vs=r["voice_score"],
                      rep=_md_cell(repaired_txt, 40),
                      reason=_md_cell(r["reason"], 110)))
    md += ["", "## Cost (measured)", "", "```", *lines, "```", ""]
    with open(os.path.join(OUT_DIR, "batch_sheet.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    # refusal log: everything that is not a clean first-pass PASS tells its story
    refusals = [r for r in rows if r["verdict"] in ("REFUSED", "VOICE-FLAG", "HUMAN-QUEUE")]
    repaired_rows = [r for r in rows
                     if r["repaired"] is True or r["repaired"] == "True"]
    rl = ["# Refusal log", "",
          "Every refusal cites the deterministic rule and the review evidence behind it. "
          "Repaired entries show the before/after; HUMAN-QUEUE entries exhausted their "
          "bounded repair attempts and wait for a person.", ""]
    for extra in refusal_extras or []:
        rl += [f"## [LIVE-COPY AUDIT] {extra['label']}", f"- text: \"{extra['text']}\"",
               f"- verdict: {extra['verdict']}", f"- rule: {extra['rule']}",
               f"- reason: {extra['reason']}",
               f"- suggested rewrite: {extra.get('rewrite', 'n/a')}", ""]
    for r in repaired_rows:
        rl += [f"## {r['variant_id']} ({r['angle_tag']}, {r['brand']}) - "
               f"REPAIRED -> PASS after {r['repair_attempts']} attempt(s)",
               f"- original hook: {r['original_hook']}",
               f"- original caption: {r['original_caption']}",
               f"- rule broken: {r['repaired_from_rule']}",
               f"- repaired hook: {r['hook']}", f"- repaired caption: {r['caption']}", ""]
    for r in refusals:
        rl += [f"## {r['variant_id']} ({r['angle_tag']}, {r['brand']}) - {r['verdict']}",
               f"- hook: {r['hook']}", f"- caption: {r['caption']}",
               f"- rule: {r['rule']}", f"- reason: {r['reason']}", ""]
    if not refusals and not repaired_rows and not refusal_extras:
        rl.append("(no refusals this run)")
    with open(os.path.join(OUT_DIR, "refusal_log.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(rl))

    payload = {**TRACKER.summary(), "cost_per_100_gated_variants_usd": round(per_100, 4),
               "variants_gated": len(rows)}
    if repair_stats:
        payload["repair"] = repair_stats
    with open(os.path.join(OUT_DIR, "run_costs.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    return counts, per_100
