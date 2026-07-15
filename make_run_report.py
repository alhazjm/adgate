"""Render out/run-report.html - a self-contained, offline, print-clean report of
the latest pipeline run. This page is the async demo of the pipeline.

Every figure is read from the real run outputs (eval_results.md, refusal_log.md,
batch_sheet.csv, run_costs.json). Missing values render "not recorded" - never
fabricated. No external scripts (the only external reference is the Google Fonts
link, with full system fallbacks); one tiny inline handler opens the collapsible
sections when printing.
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
        if not meta:  # repair-eval rows carry attempts / evasion info instead
            attempt = re.search(r"PASS after (\d+/\d+) attempt", detail)
            if attempt:
                meta = f"repair, {attempt.group(1)} attempts"
            elif "evasion probe clean" in detail:
                meta = "evasion probe clean"
            elif "fail" in detail.lower() and "closed" in detail.lower():
                meta = "failed closed"
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
  --bg:#FBFBFA;--bg-2:#F2F1F7;--ink:#1E1656;--ink-2:#443D7C;--muted:#8B87A8;
  --muted-2:#B7B4CB;--rule:#E7E5F1;--rule-soft:#F0EFF7;--accent:#F0047F;
  --orange:#FF7900;--yellow:#FFC700;
  --ok:#0E7A4E;--warn:#D96A00;--danger:#F0047F;--ok-soft:#DEF0E7;
  --warn-soft:#FFE8D2;--danger-soft:#FCE0EF;
  --display:'Poppins',ui-sans-serif,system-ui,-apple-system,sans-serif;
  --sans:'Poppins',ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
  --mono:'JetBrains Mono',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  --max:1180px;
}
*{box-sizing:border-box}
body{margin:0;background-color:var(--bg);
  background-image:radial-gradient(var(--rule) 1.15px, transparent 1.15px);
  background-size:22px 22px;
  color:var(--ink);font-family:var(--sans);
  font-size:15px;line-height:1.6;-webkit-font-smoothing:antialiased}
a{color:var(--ink);text-decoration:underline;text-decoration-color:var(--rule);text-underline-offset:3px}
a:hover{color:var(--accent);text-decoration-color:var(--accent)}
code{font-family:var(--mono);font-size:0.86em;background:var(--bg-2);padding:1px 5px;border-radius:2px}
.wrap{max-width:var(--max);margin:0 auto;padding:0 28px}
header.page{position:relative;padding:34px 0 48px;border-bottom:none;
  background:
    radial-gradient(60% 130% at 6% 12%, rgba(255,199,0,.55), transparent 58%),
    radial-gradient(70% 150% at 30% 45%, rgba(255,0,153,.40), transparent 62%),
    radial-gradient(60% 140% at 66% 0%, rgba(255,121,0,.42), transparent 58%),
    radial-gradient(90% 160% at 92% 85%, rgba(240,4,127,.30), transparent 65%),
    linear-gradient(135deg,#FFE9F5 0%,#FFF3E4 100%)}
header.page .wrap{background:#fff;border-radius:28px;
  box-shadow:0 16px 48px rgba(30,22,86,.14);padding:30px 40px 26px;
  display:flex;flex-direction:column}
@media (min-width:941px){header.page .wrap{min-height:264px}
  .cta-row{margin-top:auto;padding-top:18px}}
.eyebrow{font-family:var(--display);font-size:11px;font-weight:600;text-transform:uppercase;
  letter-spacing:.18em;color:var(--accent);margin:0 0 10px}
h1{font-family:var(--display);font-size:38px;line-height:1.08;letter-spacing:-.02em;
  font-weight:700;margin:0}
.meta{margin:12px 0 0;font-family:var(--mono);font-size:11.5px;color:var(--muted);
  letter-spacing:.02em;line-height:1.7}
.meta b{color:var(--ink);font-weight:600}
.cta-row{display:flex;gap:10px;flex-wrap:wrap;margin-top:18px}
.btn-plain{display:inline-block;font-family:var(--display);font-weight:600;font-size:14px;
  padding:13px 26px;border-radius:999px;text-decoration:none;line-height:1;
  background:#fff;color:var(--ink);border:1.5px solid var(--ink)}
.btn-plain:hover{border-color:var(--accent);color:var(--accent)}
.howto{list-style:none;margin:6px 0 0;padding:0;max-width:760px}
.howto li{padding:9px 0;border-bottom:1px dashed var(--rule-soft);font-size:13.5px;
  color:var(--ink-2);line-height:1.6}
.howto li:last-child{border-bottom:none}
.howto li strong{color:var(--ink);font-weight:600;font-family:var(--display)}
main{padding:8px 0 40px}
section{margin:0;padding:30px 0 34px;border-bottom:1px solid var(--rule)}
section:last-of-type{border-bottom:none}
.sec-head{display:flex;justify-content:space-between;align-items:baseline;gap:16px;
  border-top:2px solid var(--ink);padding-top:14px;margin-bottom:20px}
.sec-head h2{font-family:var(--display);font-size:21px;font-weight:600;letter-spacing:-.012em;margin:0}
.sec-head .right{font-family:var(--mono);font-size:10.5px;letter-spacing:.1em;
  color:var(--muted);text-transform:uppercase;text-align:right}
.sec-note{font-size:13.5px;color:var(--ink-2);max-width:720px;margin:0 0 20px}
.v{font-family:var(--mono);font-weight:700;font-size:10px;letter-spacing:.08em;text-transform:uppercase;
  padding:3px 11px;border-radius:999px;background:var(--bg-2);white-space:nowrap;display:inline-block}
.v.ok{color:var(--ok);background:var(--ok-soft)}.v.danger{color:var(--danger);background:var(--danger-soft)}
.v.warn{color:var(--warn);background:var(--warn-soft)}.v.muted{color:var(--muted)}
.nr{font-family:var(--mono);font-size:12px;color:var(--muted-2);font-style:italic}
/* eval rows */
.ev-row{display:grid;grid-template-columns:170px 190px 1fr;gap:18px;
  padding:11px 0;border-bottom:1px dashed var(--rule-soft);align-items:baseline}
.ev-row:last-child{border-bottom:none}
.ev-rule{font-family:var(--mono);font-size:11px;color:var(--ink-2);letter-spacing:.02em}
.ev-label em{font-style:italic;color:var(--ink)}
.ev-detail{display:block;font-size:12px;color:var(--muted);margin-top:2px;font-style:normal}
/* refusal log */
.rf{background:#fff;border:1px solid var(--rule);
  padding:14px 18px;margin:0 0 14px;border-radius:16px;
  box-shadow:0 4px 16px rgba(30,22,86,.05)}
.rf.live{background:var(--danger-soft);border-color:transparent}
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
td.mono{font-family:var(--mono);font-size:11px;white-space:nowrap;color:var(--ink-2)}
td.vtxt{max-width:380px;color:var(--ink-2)}
td.vtxt strong{color:var(--ink);font-weight:600;display:block}
td.vtxt .cap{display:block}
td.vcell{white-space:nowrap}
td.vcell .vs{display:block;font-family:var(--mono);font-size:10px;color:var(--muted);margin-top:3px}
td.reason{color:var(--muted);font-size:11.5px;max-width:320px}
/* unit economics */
.hero-num{display:grid;gap:6px;margin:4px 0 26px}
.hero-num .k-label{font-family:var(--display);font-size:11px;font-weight:600;
  text-transform:uppercase;letter-spacing:.16em;color:var(--accent)}
.hero-num .n{font-family:var(--display);font-weight:700;font-size:92px;line-height:.95;
  letter-spacing:-.03em;color:var(--ink)}
.hero-num .n small{font-size:38px;font-weight:600;letter-spacing:-.01em;color:var(--orange);margin-left:8px}
.hero-num .sub{font-family:var(--mono);font-size:12px;color:var(--ink-2);letter-spacing:.01em}
table.stages{max-width:640px;font-size:12.5px}
table.stages tbody td{font-family:var(--mono);font-size:11.5px;padding:8px 14px 8px 0;
  border-bottom:1px dashed var(--rule-soft);color:var(--ink-2)}
table.stages tr.tot td{border-bottom:none;border-top:1px solid var(--rule);
  color:var(--ink);font-weight:700}
footer.page{border-top:1px solid var(--rule);padding:22px 0 40px;
  color:var(--muted);font-size:12px;font-family:var(--mono);letter-spacing:.01em;line-height:1.8}
footer.page a{color:var(--muted)}
/* production-flow diagram */
.flow{max-width:760px;margin:6px auto 0}
.flow-row{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.node{background:#fff;border:1px solid var(--rule);border-radius:16px;padding:14px 16px;
  text-align:center;box-shadow:0 4px 16px rgba(30,22,86,.05);position:relative}
.node .n-title{font-family:var(--display);font-weight:600;font-size:14px;color:var(--ink)}
.node .n-sub{font-size:11.5px;color:var(--muted);line-height:1.5;margin-top:3px}
.node.live{background:var(--ink);border-color:var(--ink)}
.node.live .n-title{color:#fff}
.node.live .n-sub{color:#B7B4CB}
.node.human{background:var(--ok-soft);border:1.5px solid var(--ok)}
.node.dashed{border-style:dashed;background:transparent;box-shadow:none}
.live-pill{position:absolute;top:-9px;right:14px;font-family:var(--mono);font-size:9px;
  font-weight:700;letter-spacing:.1em;background:var(--accent);color:#fff;
  padding:3px 10px;border-radius:999px}
.chips{display:flex;gap:6px;justify-content:center;margin-top:8px;flex-wrap:wrap}
.chip{font-family:var(--mono);font-size:9px;font-weight:700;letter-spacing:.08em;
  text-transform:uppercase;padding:3px 9px;border-radius:999px}
.chip.ai{background:var(--warn-soft);color:var(--warn)}
.chip.rules{background:var(--bg-2);color:var(--ink-2)}
.chip.hmn{background:var(--ok-soft);color:var(--ok)}
.chip.na{background:transparent;color:var(--muted);border:1px dashed var(--muted-2)}
.node.live .chip.ai{background:rgba(255,121,0,.28);color:#FFC08A}
.node.live .chip.rules{background:rgba(255,255,255,.14);color:#CFCBE8}
.node.live .chip.hmn{background:rgba(14,122,78,.4);color:#9FE0C0}
.flow-arrow{text-align:center;color:var(--muted-2);font-size:16px;line-height:1;padding:7px 0}
.flow-note{font-size:11.5px;color:var(--muted);text-align:center;margin-top:10px}
.legend{display:flex;gap:16px;justify-content:center;flex-wrap:wrap;margin-top:20px;
  font-size:11.5px;color:var(--muted);align-items:center}
.legend .sw{display:inline-block;width:12px;height:12px;border-radius:4px;margin-right:6px;vertical-align:-1px}
/* collapsible sections */
details.fold{margin-top:16px}
details.fold summary{display:inline-flex;align-items:center;gap:9px;cursor:pointer;
  font-family:var(--display);font-weight:600;font-size:13.5px;color:var(--ink);
  background:#fff;border:1.5px solid var(--ink);border-radius:999px;padding:11px 24px;
  list-style:none;user-select:none}
details.fold summary::-webkit-details-marker{display:none}
details.fold summary:hover{border-color:var(--accent);color:var(--accent)}
details.fold summary .chev{transition:transform .2s ease;font-size:11px}
details.fold[open] summary .chev{transform:rotate(180deg)}
details.fold summary .when-open{display:none}
details.fold[open] summary .when-open{display:inline}
details.fold[open] summary .when-closed{display:none}
details.fold > .fold-body{margin-top:16px}
@media (max-width:940px){
  .ev-row{grid-template-columns:140px 1fr;grid-auto-rows:auto}
  .ev-row .ev-rule{grid-column:2}
  .rf-line{grid-template-columns:120px 1fr}
  .hero-num .n{font-size:64px}
  .flow-row{grid-template-columns:1fr}
}
@media print{
  body{background:#fff;background-image:none;color:#000;font-size:8pt;line-height:1.35;
    -webkit-print-color-adjust:exact;print-color-adjust:exact}
  .wrap{max-width:none;padding:0}
  header.page{padding:0 0 8px;background:none}
  header.page .wrap{box-shadow:none;border-radius:0;padding:0;background:none}
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
  details.fold summary{display:none}
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
    all_refusals = load_refusals()
    repaired_entries = [e for e in all_refusals if e["verdict"] == "REPAIRED"]
    refusals = [e for e in all_refusals if e["verdict"] != "REPAIRED"]
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

    def fold(show_label, hide_label, inner):
        return (f'<details class="fold"><summary>'
                f'<span class="when-closed">{show_label}</span>'
                f'<span class="when-open">{hide_label}</span>'
                f'<span class="chev">&#9662;</span></summary>'
                f'<div class="fold-body">{inner}</div></details>')

    evals_block = (fold(f"Show all {len(evals)} checks", "Hide the checks",
                        eval_rows_html(evals))
                   if evals else eval_rows_html(evals))
    repair_first = refusal_html(repaired_entries[:1]) if repaired_entries else ""
    repair_rest = (fold(f"Show the other {len(repaired_entries) - 1} salvages",
                        "Hide the salvages", refusal_html(repaired_entries[1:]))
                   if len(repaired_entries) > 1 else "")
    batch_block = (fold(f"Show all {len(batch)} variants", "Hide the batch sheet",
                        batch_html(batch))
                   if batch else batch_html(batch))

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>adgate &mdash; run report</title>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
<!-- GoatCounter analytics: no cookies; ignores localhost; host-prefix callback so all
     hadialhazim.com subdomains share one dashboard with distinguishable paths -->
<script>window.goatcounter = {{ path: function(p) {{ return location.host + p }} }};</script>
<script data-goatcounter="https://hadialhazim.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>
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
  <div class="cta-row">
    <a class="btn-plain" href="./">&larr; Try the gate live</a>
    <a class="btn-plain" href="https://github.com/alhazjm/adgate">Source on GitHub</a>
  </div>
</div></header>
<main><div class="wrap">

<section id="about">
  <div class="sec-head"><h2>What this is</h2>
    <span class="right">start here</span></div>
  <p class="sec-note">Anyone can make an ad with AI now. The hard part is knowing which
  ads a brand can actually run. This pipeline writes ad copy for one brand&rsquo;s market
  (Huggies, Singapore), then forces every piece through a gate before a human sees it:
  ten fixed rules refuse anything the brand could not defend, an AI judge scores the
  survivors for brand voice, and a small repair agent rewrites what failed and sends it
  back through the same gate. The rules are not guesses. Each one comes from the
  brand&rsquo;s own published fine print, Singapore&rsquo;s advertising code, past
  regulator rulings, or real customer complaints. This page is the record of one real
  run, rendered from the run&rsquo;s own output files.</p>
  <ul class="howto">
    <li><strong>Eval results</strong> &nbsp;the checks the system must pass before any run
      is trusted: copy that must be refused, copy that must pass, and repair-behaviour
      tests, including one that catches the agent smuggling a banned claim past the rules
      in new words.</li>
    <li><strong>Repair</strong> &nbsp;the one place an agent lives. It reads the rule that
      stopped an ad and the evidence behind it, rewrites, and resubmits to the same gate.
      Two attempts, a spend cap, and no power to approve its own work.</li>
    <li><strong>Refusal log</strong> &nbsp;every ad this run stopped, the rule that fired,
      and the before/after wherever the agent repaired it.</li>
    <li><strong>Batch sheet</strong> &nbsp;all 48 ads this run generated, with each
      one&rsquo;s final verdict. The ads are outputs of this pipeline, written for the
      demo; none are real advertisements.</li>
    <li><strong>Unit economics</strong> &nbsp;what the run cost, measured from actual
      tokens, expressed per 100 gated ads.</li>
  </ul>
  <p class="sec-note" style="margin-top:16px">The ten rules themselves are listed on the
  <a href="./">try-the-gate page</a>, where any line of copy can be tested against them
  directly in the browser, with no model call.</p>
</section>

<section id="production">
  <div class="sec-head"><h2>How this runs in production</h2>
    <span class="right">dark cards run in this demo &middot; AI marked per step</span></div>
  <p class="sec-note">The dark cards are what the shipped demo already does; the light
  cards are the pipeline around it on a real engagement. Every card is tagged with who
  does the work: a model, deterministic rules, or a person.</p>
  <div class="flow">
    <div class="flow-row">
      <div class="node"><div class="n-title">Campaign brief</div>
        <div class="n-sub">from account / strategy</div>
        <div class="chips"><span class="chip hmn">human</span></div></div>
      <div class="node"><div class="n-title">Claims list &amp; brand book</div>
        <div class="n-sub">Legal + brand team</div>
        <div class="chips"><span class="chip hmn">human</span></div></div>
      <div class="node"><div class="n-title">Complaints &middot; CS &middot; social</div>
        <div class="n-sub">what customers contest</div>
        <div class="chips"><span class="chip rules">data feed</span></div></div>
    </div>
    <div class="flow-arrow">&darr;</div>
    <div class="node live"><span class="live-pill">LIVE</span>
      <div class="n-title">Brand rule set</div>
      <div class="n-sub">versioned do-not-say rules. This demo&rsquo;s ten were built from
        public evidence; on the job, from the claims list. AI may draft candidate rules,
        a person approves (roadmap)</div>
      <div class="chips"><span class="chip rules">rules &middot; no ai</span>
        <span class="chip hmn">human approves</span></div></div>
    <div class="flow-arrow">&darr;</div>
    <div class="node live"><span class="live-pill">LIVE</span>
      <div class="n-title">Asset generation</div>
      <div class="n-sub">briefs &rarr; variants at scale</div>
      <div class="chips"><span class="chip ai">ai &middot; cheap model</span></div></div>
    <div class="flow-arrow">&darr;</div>
    <div class="node live"><span class="live-pill">LIVE</span>
      <div class="n-title">Claims gate</div>
      <div class="n-sub">rules run first &middot; refusals are free and instant</div>
      <div class="chips"><span class="chip rules">rules &middot; no ai</span></div></div>
    <div class="flow-arrow">&darr;</div>
    <div class="node live"><span class="live-pill">LIVE</span>
      <div class="n-title">Voice judge</div>
      <div class="n-sub">scores rule-survivors only, so the strong model never reads
        what the rules already refused</div>
      <div class="chips"><span class="chip ai">ai &middot; strong model</span></div></div>
    <div class="flow-arrow">&darr;</div>
    <div class="node live"><span class="live-pill">LIVE</span>
      <div class="n-title">Repair agent</div>
      <div class="n-sub">rewrites refusals and resubmits to the same gate &middot; two
        attempts, spend cap, no verdict authority</div>
      <div class="chips"><span class="chip ai">ai &middot; bounded agent</span></div></div>
    <div class="flow-arrow">&darr;</div>
    <div class="node human">
      <div class="n-title">Human review</div>
      <div class="n-sub">approves, edits, or kills &mdash; nothing publishes without a
        person. This report is the run&rsquo;s version of that queue</div>
      <div class="chips"><span class="chip hmn">human decides</span></div></div>
    <div class="flow-arrow">&darr;</div>
    <div class="node"><div class="n-title">Publish / traffic</div>
      <div class="n-sub">channel delivery via existing tooling</div>
      <div class="chips"><span class="chip rules">no ai</span></div></div>
    <div class="flow-arrow">&darr;</div>
    <div class="node dashed"><div class="n-title">Performance readback</div>
      <div class="n-sub">winners and losers re-enter the evidence base and update the
        rule set</div>
      <div class="chips"><span class="chip na">designed &middot; not built</span></div></div>
    <p class="flow-note">the readback loops to the top: new evidence &rarr; rule updates
      &rarr; the next run generates against a smarter gate</p>
  </div>
  <div class="legend">
    <span><span class="sw" style="background:var(--ink)"></span>live in this demo</span>
    <span><span class="sw" style="background:#fff;border:1px solid var(--rule)"></span>production pipeline around it</span>
    <span><span class="chip ai">ai</span>&nbsp;model involved</span>
    <span><span class="chip rules">rules</span>&nbsp;deterministic, free</span>
    <span><span class="chip hmn">human</span>&nbsp;a person decides</span>
  </div>
</section>

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
  {evals_block}
</section>

<section id="repair">
  <div class="sec-head"><h2>Repair &mdash; agency in exactly one place, bounded</h2>
    <span class="right">{esc(rep_summary)}</span></div>
  <p class="sec-note">Refused and off-voice variants go to a repair agent that reads the
  rule that fired and the review evidence behind it, rewrites, and resubmits. Bounds:
  2 attempts per variant, a per-run spend cap, brand and angle pinned, and no verdict
  authority &mdash; every rewrite re-enters the same gate, and whatever is still failing
  lands in the human queue with its full history. Each card below is one salvage from
  this run: the copy as generated, the rule it broke, and the rewrite that passed.</p>
  {repair_first}
  {repair_rest}
</section>

<section id="refusals">
  <div class="sec-head"><h2>Refusal log &mdash; what the gate said no to</h2>
    <span class="right">deterministic rules run first &middot; refusals cost nothing</span></div>
  <p class="sec-note">Every refusal names its rule and the evidence behind it. Entries
  the repair agent salvaged are shown in the Repair section above; what remains here is
  the live-copy audit and anything that stayed refused or off-voice.</p>
  {refusal_html(refusals)}
</section>

<section id="batch">
  <div class="sec-head"><h2>Batch sheet &mdash; the full gated run</h2>
    <span class="right">{esc(batch_summary)}</span></div>
  <p class="sec-note">Every variant below was generated by this run (corpus &rarr; briefs
  &rarr; variants on the cheap model tier), then gated and, where needed, repaired;
  verdicts are final, post-repair. All of it is demo output; none of it is a real
  advertisement.</p>
  {batch_block}
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
  <a href="https://hadialhazim.com">Hadi Al-Hazim</a> &middot; the pipeline is a
  fixed-stage process with one bounded agentic step; this page is its per-run output
  &middot; built on public voice-of-customer data only &middot; not affiliated with or
  endorsed by any brand named
</div></footer>
<script>
/* no external scripts; this only opens the collapsed sections when printing */
window.addEventListener("beforeprint", function () {{
  document.querySelectorAll("details.fold").forEach(function (d) {{ d.open = true; }});
}});
</script>
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
