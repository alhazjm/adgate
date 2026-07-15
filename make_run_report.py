"""Render out/run-report.html - a self-contained, offline, print-clean report of
the latest pipeline run. This page is the async demo of the pipeline.

Every figure is read from the real run outputs (eval_results.md, refusal_log.md,
batch_sheet.csv, run_costs.json). Missing values render "not recorded" - never
fabricated. Zero JavaScript; the only external reference is the Google Fonts
link (full system fallbacks, so the page reads fine offline).
"""

import csv
import html
import json
import os
import re
import time

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
OUT_HTML = os.path.join(OUT_DIR, "run-report.html")

NR = "not recorded"


def esc(x):
    return html.escape(str(x), quote=True)


# ------------------------------------------------------------------ load data

def load_costs():
    p = os.path.join(OUT_DIR, "run_costs.json")
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        d["_run_date"] = time.strftime("%d %b %Y, %H:%M", time.localtime(os.path.getmtime(p)))
        return d
    except (OSError, ValueError):
        return {}


def load_models():
    try:
        with open(os.path.join(OUT_DIR, "batch_sheet.md"), encoding="utf-8") as f:
            m = re.search(r"Provider: (\S+) \| gen model: (\S+) \| judge model: (\S+)", f.read())
        return m.groups() if m else (NR, NR, NR)
    except OSError:
        return (NR, NR, NR)


def load_evals():
    """Returns (rows, refused_line, passed_line). Row: (status, label, detail)."""
    try:
        with open(os.path.join(OUT_DIR, "eval_results.md"), encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return [], NR, NR
    rows = []
    for m in re.finditer(r"^- \[([A-Z -]+)\] (.+)\n  - (.+)$", text, re.M):
        rows.append((m.group(1).strip(), m.group(2).strip(), m.group(3).strip()))
    refused = re.search(r"Refused correctly: (\d+/\d+)", text)
    passed = re.search(r"Passed correctly: (\d+/\d+)", text)
    repaired = re.search(r"Repair behaved: (\d+/\d+)", text)
    return (rows, (refused.group(1) if refused else NR),
            (passed.group(1) if passed else NR),
            (repaired.group(1) if repaired else NR))


def load_refusals():
    """Returns list of dicts: {title, verdict, fields:[(k,v)...]} from refusal_log.md."""
    try:
        with open(os.path.join(OUT_DIR, "refusal_log.md"), encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return []
    entries = []
    for block in re.split(r"\n(?=## )", text):
        if not block.startswith("## "):
            continue
        lines = block.splitlines()
        title = lines[0][3:].strip()
        fields = []
        for line in lines[1:]:
            m = re.match(r"- ([a-z ]+): (.*)", line)
            if m:
                fields.append((m.group(1).strip(), m.group(2).strip()))
        verdict = next((v for k, v in fields if k == "verdict"), None)
        if verdict is None:
            for tag in ("REPAIRED", "HUMAN-QUEUE", "VOICE-FLAG"):
                if tag in title:
                    verdict = tag
                    break
            else:
                verdict = "REFUSED"
        entries.append({"title": title, "verdict": verdict, "fields": fields})
    return entries


def load_batch():
    p = os.path.join(OUT_DIR, "batch_sheet.csv")
    try:
        with open(p, encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    except OSError:
        return []


# --------------------------------------------------------------------- render

VERDICT_CLASS = {"PASS": "ok", "REFUSED": "danger", "VOICE-FLAG": "warn",
                 "REFUSED-CORRECTLY": "danger", "PASSED-CORRECTLY": "ok",
                 "BLOCKED": "warn", "MISSED": "warn",
                 "REPAIRED": "ok", "REPAIRED-CORRECTLY": "ok", "REANGLED-OK": "ok",
                 "FAIL-CLOSED-OK": "ok", "HUMAN-QUEUE": "warn",
                 "EVADED": "danger", "UNREPAIRED": "warn",
                 "BROKEN-FIXTURE": "warn", "INTEGRITY": "warn"}


def vclass(verdict):
    return VERDICT_CLASS.get(str(verdict).strip("* "), "muted")


def fmt_usd(x, dp=2):
    try:
        return f"US${float(x):.{dp}f}"
    except (TypeError, ValueError):
        return NR


def eval_rows_html(rows):
    if not rows:
        return f'<p class="nr">{NR}</p>'
    out = []
    for status, label, detail in rows:
        detail = re.sub(r"`([^`]+)`", r"<code>\1</code>", esc(detail))
        rule = re.search(r"expected rule: <code>([^<]+)</code>", detail)
        rule_txt = rule.group(1) if rule else ""
        voice = re.search(r"voice: (\d+\.?\d*)", detail)
        meta = rule_txt or (f"voice {voice.group(1)}/10" if voice else "")
        out.append(
            f'<div class="ev-row">'
            f'<span class="v {vclass(status)}">{esc(status)}</span>'
            f'<span class="ev-rule">{esc(meta)}</span>'
            f'<span class="ev-label"><em>{esc(label)}</em>'
            f'<span class="ev-detail">{detail}</span></span>'
            f'</div>')
    return "\n".join(out)


def refusal_html(entries):
    if not entries:
        return f'<p class="nr">{NR}</p>'
    out = []
    for e in entries:
        cls = vclass(e["verdict"])
        live = e["title"].startswith("[LIVE-COPY AUDIT]")
        rows = []
        for k, v in e["fields"]:
            if k == "verdict":
                continue
            label = {"text": "live caption", "hook": "hook", "caption": "caption",
                     "rule": "rule", "reason": "reason",
                     "suggested rewrite": "suggested rewrite"}.get(k, k)
            val = esc(v)
            klass = "q" if k in ("text", "hook", "caption") else "r"
            if k == "rule":
                val = f"<code>{val}</code>"
                klass = "rule"
            rows.append(f'<div class="rf-line {klass}"><span class="k">{esc(label)}</span>'
                        f'<span>{val}</span></div>')
        out.append(
            f'<article class="rf {cls}{" live" if live else ""}">'
            f'<div class="rf-head"><span class="v {cls}">{esc(e["verdict"])}</span>'
            f'<span class="rf-title">{esc(e["title"])}</span></div>'
            + "\n".join(rows) + "</article>")
    return '<div class="rf-list">' + "\n".join(out) + "</div>"


def batch_html(rows):
    if not rows:
        return f'<p class="nr">{NR}</p>'
    body = []
    for r in rows:
        verdict = r.get("verdict", "")
        voice = r.get("voice_score", "")
        voice_txt = f'<span class="vs">voice {voice}</span>' if voice not in ("", "None") else ""
        variant = (f'<strong>{esc(r.get("hook", ""))}</strong>'
                   f'<span class="cap">{esc(r.get("caption", ""))}</span>')
        body.append(
            f'<tr class="{vclass(verdict)}">'
            f'<td class="mono">{esc(r.get("angle_tag", ""))}</td>'
            f'<td class="mono">{esc(r.get("brand", ""))}</td>'
            f'<td class="vtxt">{variant}</td>'
            f'<td class="vcell"><span class="v {vclass(verdict)}">{esc(verdict)}</span>{voice_txt}</td>'
            f'<td class="reason"><span class="rsn">{esc(r.get("reason", ""))}</span></td></tr>')
    return (
        '<div class="scroll-x"><table class="batch">'
        '<thead><tr><th>angle tag</th><th>brand</th><th>variant</th>'
        '<th>verdict</th><th>reason</th></tr></thead>'
        f'<tbody>{"".join(body)}</tbody></table></div>')


def stages_html(costs):
    stages = costs.get("stages") or {}
    if not stages:
        return f'<p class="nr">{NR}</p>'
    rows = "".join(
        f'<tr><td>{esc(name)}</td><td>{d.get("calls", NR)}</td>'
        f'<td>{d.get("input_tokens", NR):,}</td><td>{d.get("output_tokens", NR):,}</td>'
        f'<td>{fmt_usd(d.get("cost_usd"), 4)}</td></tr>'
        for name, d in stages.items())
    total = fmt_usd(costs.get("total_cost_usd"), 4)
    return ('<table class="stages"><thead><tr><th>stage</th><th>calls</th>'
            '<th>tokens in</th><th>tokens out</th><th>cost</th></tr></thead>'
            f'<tbody>{rows}<tr class="tot"><td>total (measured)</td><td></td><td></td>'
            f'<td></td><td>{total}</td></tr></tbody></table>')


CSS = """
:root{
  --bg:#FAF4EE;--bg-2:#F1E7DC;--ink:#1B1210;--ink-2:#3A2C27;--muted:#8B776C;
  --muted-2:#AC9C90;--rule:#E6D8CB;--rule-soft:#EFE5D9;--accent:#C20D2E;
  --ok:#1F6B4A;--warn:#B0641C;--danger:#C20D2E;--ok-soft:#DCEAE1;
  --warn-soft:#F4E5CF;--danger-soft:#F6DAD9;
  --display:'Archivo','Inter Tight',ui-sans-serif,system-ui,-apple-system,sans-serif;
  --sans:'Inter Tight',ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
  --mono:'JetBrains Mono',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  --max:1180px;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);
  font-size:15.5px;line-height:1.55;-webkit-font-smoothing:antialiased}
a{color:var(--ink);text-decoration:underline;text-decoration-color:var(--rule);text-underline-offset:3px}
a:hover{color:var(--accent);text-decoration-color:var(--accent)}
code{font-family:var(--mono);font-size:0.86em;background:var(--bg-2);padding:1px 5px;border-radius:2px}
.wrap{max-width:var(--max);margin:0 auto;padding:0 28px}
header.page{border-bottom:1px solid var(--rule);padding:26px 0 22px}
.eyebrow{font-family:var(--mono);font-size:10.5px;font-weight:700;text-transform:uppercase;
  letter-spacing:.16em;color:var(--accent);margin:0 0 9px}
h1{font-family:var(--display);font-size:36px;line-height:1;letter-spacing:-.028em;
  font-weight:800;margin:0}
.meta{margin:12px 0 0;font-family:var(--mono);font-size:11.5px;color:var(--muted);
  letter-spacing:.02em;line-height:1.7}
.meta b{color:var(--ink);font-weight:600}
main{padding:8px 0 40px}
section{margin:0;padding:30px 0 34px;border-bottom:1px solid var(--rule)}
section:last-of-type{border-bottom:none}
.sec-head{display:flex;justify-content:space-between;align-items:baseline;gap:16px;
  border-top:2px solid var(--ink);padding-top:14px;margin-bottom:20px}
.sec-head h2{font-family:var(--display);font-size:21px;font-weight:700;letter-spacing:-.018em;margin:0}
.sec-head .right{font-family:var(--mono);font-size:10.5px;letter-spacing:.1em;
  color:var(--muted);text-transform:uppercase;text-align:right}
.sec-note{font-size:13.5px;color:var(--ink-2);max-width:720px;margin:0 0 20px}
.v{font-family:var(--mono);font-weight:700;font-size:10.5px;letter-spacing:.08em;text-transform:uppercase}
.v.ok{color:var(--ok)}.v.danger{color:var(--danger)}.v.warn{color:var(--warn)}.v.muted{color:var(--muted)}
.nr{font-family:var(--mono);font-size:12px;color:var(--muted-2);font-style:italic}
/* eval rows */
.ev-row{display:grid;grid-template-columns:170px 190px 1fr;gap:18px;
  padding:11px 0;border-bottom:1px dashed var(--rule-soft);align-items:baseline}
.ev-row:last-child{border-bottom:none}
.ev-rule{font-family:var(--mono);font-size:11px;color:var(--ink-2);letter-spacing:.02em}
.ev-label em{font-style:italic;color:var(--ink)}
.ev-detail{display:block;font-size:12px;color:var(--muted);margin-top:2px;font-style:normal}
/* refusal log */
.rf{background:var(--bg-2);border-left:3px solid var(--danger);padding:14px 18px;
  margin:0 0 14px;border-radius:0 2px 2px 0}
.rf.warn{border-left-color:var(--warn)}
.rf.live{background:var(--danger-soft)}
.rf-head{display:flex;gap:14px;align-items:baseline;flex-wrap:wrap;margin-bottom:8px}
.rf-title{font-family:var(--display);font-weight:700;font-size:14.5px;letter-spacing:-.01em}
.rf-line{display:grid;grid-template-columns:150px 1fr;gap:12px;padding:3px 0;
  font-size:13px;line-height:1.5;align-items:baseline}
.rf-line .k{font-family:var(--mono);font-size:10px;text-transform:uppercase;
  letter-spacing:.12em;color:var(--muted);font-weight:600}
.rf-line.q span:last-child{font-family:var(--display);font-style:italic;color:var(--ink)}
.rf-line.r span:last-child{color:var(--ink-2)}
/* batch table */
.scroll-x{overflow-x:auto}
table{border-collapse:collapse;width:100%}
table.batch{min-width:820px;font-size:12.5px}
table.batch thead th, table.stages thead th{font-family:var(--mono);font-size:10px;
  text-transform:uppercase;letter-spacing:.12em;color:var(--muted);font-weight:600;
  text-align:left;padding:8px 14px 8px 0;border-bottom:2px solid var(--ink)}
table.batch tbody tr{border-bottom:1px dashed var(--rule)}
table.batch tbody td{padding:10px 14px 10px 0;vertical-align:top;line-height:1.45}
table.batch tbody tr td:first-child{padding-left:10px;position:relative}
table.batch tbody tr td:first-child::before{content:"";position:absolute;left:0;top:8px;
  bottom:8px;width:3px;border-radius:1px;background:var(--muted-2)}
table.batch tbody tr.ok td:first-child::before{background:var(--ok)}
table.batch tbody tr.danger td:first-child::before{background:var(--danger)}
table.batch tbody tr.warn td:first-child::before{background:var(--warn)}
td.mono{font-family:var(--mono);font-size:11px;white-space:nowrap;color:var(--ink-2)}
td.vtxt{max-width:380px;color:var(--ink-2)}
td.vtxt strong{color:var(--ink);font-weight:600;display:block}
td.vtxt .cap{display:block}
td.vcell{white-space:nowrap}
td.vcell .vs{display:block;font-family:var(--mono);font-size:10px;color:var(--muted);margin-top:3px}
td.reason{color:var(--muted);font-size:11.5px;max-width:320px}
/* unit economics */
.hero-num{display:grid;gap:6px;margin:4px 0 26px}
.hero-num .k-label{font-family:var(--mono);font-size:10.5px;font-weight:600;
  text-transform:uppercase;letter-spacing:.14em;color:var(--muted)}
.hero-num .n{font-family:var(--display);font-weight:800;font-size:92px;line-height:.95;
  letter-spacing:-.04em;color:var(--ink)}
.hero-num .n small{font-size:38px;font-weight:700;letter-spacing:-.02em;color:var(--muted);margin-left:8px}
.hero-num .sub{font-family:var(--mono);font-size:12px;color:var(--ink-2);letter-spacing:.01em}
table.stages{max-width:640px;font-size:12.5px}
table.stages tbody td{font-family:var(--mono);font-size:11.5px;padding:8px 14px 8px 0;
  border-bottom:1px dashed var(--rule-soft);color:var(--ink-2)}
table.stages tr.tot td{border-bottom:none;border-top:1px solid var(--rule);
  color:var(--ink);font-weight:700}
footer.page{border-top:1px solid var(--rule);padding:22px 0 40px;
  color:var(--muted);font-size:12px;font-family:var(--mono);letter-spacing:.01em;line-height:1.8}
footer.page a{color:var(--muted)}
@media (max-width:940px){
  .ev-row{grid-template-columns:140px 1fr;grid-auto-rows:auto}
  .ev-row .ev-rule{grid-column:2}
  .rf-line{grid-template-columns:120px 1fr}
  .hero-num .n{font-size:64px}
}
@media print{
  body{background:#fff;color:#000;font-size:8pt;line-height:1.35;
    -webkit-print-color-adjust:exact;print-color-adjust:exact}
  .wrap{max-width:none;padding:0}
  header.page{padding:0 0 8px}
  h1{font-size:19pt}
  .meta{margin-top:4px;font-size:6.5pt;line-height:1.5}
  main{padding:0}
  section{page-break-inside:auto;padding:8px 0 10px}
  .sec-head{padding-top:6px;margin-bottom:7px}
  .sec-head h2{font-size:11pt}
  .sec-head .right{font-size:6pt}
  .sec-note{font-size:7pt;margin-bottom:7px}
  .v{font-size:6pt}
  .ev-row{grid-template-columns:100px 125px 1fr;gap:10px;padding:2px 0}
  .ev-rule{font-size:6.5pt}
  .ev-label{font-size:7.5pt}
  .ev-detail{font-size:6pt}
  .rf-list{column-count:2;column-gap:14px}
  .rf{break-inside:avoid;page-break-inside:avoid;padding:4px 8px;margin-bottom:4px}
  .rf-head{margin-bottom:1px}
  .rf-title{font-size:7pt}
  .rf-line{grid-template-columns:70px 1fr;gap:7px;padding:0.5px 0;font-size:6pt}
  .rf-line .k{font-size:5pt}
  table.batch{min-width:0;font-size:5.5pt}
  table.batch thead th{font-size:5pt;padding:2px 6px 2px 0}
  table.batch tbody td{padding:1.5px 6px 1.5px 0;line-height:1.25}
  td.vtxt .cap,td.reason .rsn{display:-webkit-box;-webkit-line-clamp:2;
    -webkit-box-orient:vertical;overflow:hidden}
  table.batch tbody tr td:first-child{padding-left:5px}
  td.mono{font-size:5.5pt}
  td.vcell .vs{font-size:5.5pt}
  td.vtxt,td.reason{max-width:none}
  td.reason{font-size:5.5pt}
  .hero-num{margin:2px 0 10px}
  .hero-num .n{font-size:28pt}
  .hero-num .n small{font-size:12pt}
  .hero-num .sub{font-size:6.5pt}
  table.stages{font-size:6.5pt}
  table.stages thead th{padding:2px 8px 2px 0;font-size:5.5pt}
  table.stages tbody td{padding:1.5px 8px 1.5px 0;font-size:6.5pt}
  footer.page{padding:6px 0;font-size:6pt;line-height:1.5}
  a{text-decoration:none;color:inherit}
  .scroll-x{overflow-x:visible}
}
"""


def build():
    costs = load_costs()
    provider, gen_model, judge_model = load_models()
    evals, refused, passed, repaired = load_evals()
    refusals = load_refusals()
    batch = load_batch()

    run_date = costs.get("_run_date", NR)
    n_gated = costs.get("variants_gated", NR)
    per100 = costs.get("cost_per_100_gated_variants_usd")
    per100_txt = fmt_usd(per100) if per100 is not None else NR
    total_txt = fmt_usd(costs.get("total_cost_usd"), 4)
    n_refused = sum(1 for r in batch if r.get("verdict") == "REFUSED")
    n_flag = sum(1 for r in batch if r.get("verdict") == "VOICE-FLAG")
    n_pass = sum(1 for r in batch if r.get("verdict") == "PASS")
    n_queue = sum(1 for r in batch if r.get("verdict") == "HUMAN-QUEUE")
    n_repaired = sum(1 for r in batch if str(r.get("repaired", "")) == "True")
    batch_summary = (f"{len(batch)} variants · {n_pass} pass ({n_repaired} repaired) · "
                     f"{n_refused} refused · {n_flag} voice-flag · "
                     f"{n_queue} human-queue") if batch else NR

    rep = costs.get("repair") or {}
    rep_summary = ((f"{rep.get('salvaged', NR)}/{rep.get('candidates', NR)} salvaged · "
                    f"{rep.get('human_queue', NR)} to human queue · "
                    f"repair spend {fmt_usd(rep.get('repair_cost_usd'), 4)}")
                   if rep else NR)

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>adgate &mdash; run report</title>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@600;700;800&family=Inter+Tight:wght@400;500;600&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<header class="page"><div class="wrap">
  <p class="eyebrow">adgate &middot; SG baby-care case study</p>
  <h1>Pipeline run report</h1>
  <p class="meta">run <b>{esc(run_date)}</b> &middot; provider <b>{esc(provider)}</b>
   &middot; gen <b>{esc(gen_model)}</b> / judge <b>{esc(judge_model)}</b><br>
   stages: corpus &rarr; briefs &rarr; variants &rarr; gate (deterministic rules, then voice judge)
   &rarr; bounded repair agent &rarr; report
   &middot; every figure on this page is read from the run&rsquo;s output files</p>
</div></header>
<main><div class="wrap">

<section id="evals">
  <div class="sec-head"><h2>Eval results &mdash; the gate earns its numbers</h2>
    <span class="right">refused correctly {esc(refused)} &middot; passed correctly {esc(passed)}
      &middot; repair behaved {esc(repaired)}</span></div>
  <p class="sec-note">Known-bad fixtures must be refused by the deterministic rule layer
  (no model involved); known-good fixtures must survive the full gate including the
  strong-model voice judge. The first row is the brand&rsquo;s own published site copy.
  Repair fixtures run the bounded agent end-to-end &mdash; a salvageable refusal must come
  back PASS, and an unshippable claim must never sneak past as a paraphrase (the evasion
  probe checks wordings the gate&rsquo;s own regex does not cover).</p>
  {eval_rows_html(evals)}
</section>

<section id="repair">
  <div class="sec-head"><h2>Repair &mdash; agency in exactly one place, bounded</h2>
    <span class="right">{esc(rep_summary)}</span></div>
  <p class="sec-note">Refused and off-voice variants go to a repair agent that reads the
  rule that fired and the review evidence behind it, rewrites, and resubmits. Bounds:
  2 attempts per variant, a per-run spend cap, brand and angle pinned, and no verdict
  authority &mdash; every rewrite re-enters the same gate, and whatever is still failing
  lands in the human queue with its full history. Repaired entries below show the
  before/after.</p>
</section>

<section id="refusals">
  <div class="sec-head"><h2>Refusal log &mdash; what the gate said no to</h2>
    <span class="right">deterministic rules run first &middot; refusals cost nothing</span></div>
  <p class="sec-note">Every refusal names its rule and the review evidence behind it.
  Amber entries passed the claims rules but were flagged off-voice by the judge.</p>
  {refusal_html(refusals)}
</section>

<section id="batch">
  <div class="sec-head"><h2>Batch sheet &mdash; the full gated run</h2>
    <span class="right">{esc(batch_summary)}</span></div>
  {batch_html(batch)}
</section>

<section id="economics">
  <div class="sec-head"><h2>Unit economics &mdash; measured, never estimated</h2>
    <span class="right">actual tokens &times; prices</span></div>
  <div class="hero-num">
    <span class="k-label">measured cost per 100 gated variants</span>
    <p class="n">{esc(per100_txt)}<small>per 100</small></p>
    <span class="sub">{esc(n_gated)} variants gated for {esc(total_txt)} in model spend
      &middot; {esc(gen_model)} generates, {esc(judge_model)} judges survivors only</span>
  </div>
  {stages_html(costs)}
</section>

</div></main>
<footer class="page"><div class="wrap">
  Hadi Al-Hazim &middot; the pipeline is a fixed-stage process with one bounded agentic
  step; this page is its per-run output &middot; built on public voice-of-customer data only
  &middot; not affiliated with or endorsed by any brand named
</div></footer>
</body>
</html>"""

    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(page)
    # sibling copy for the static site, so the try-the-gate page can link ./run-report.html
    site_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "site")
    if os.path.isdir(site_dir):
        with open(os.path.join(site_dir, "run-report.html"), "w", encoding="utf-8") as f:
            f.write(page)
    print(f"wrote {OUT_HTML} ({os.path.getsize(OUT_HTML)/1024:.0f} KB, "
          f"{len(evals)} eval rows, {len(refusals)} refusal entries, {len(batch)} batch rows)")


if __name__ == "__main__":
    build()
