"""Layer 5 — output assembly (build spec v2 §10).

The report is built from the evidence ledger, not from an agent's prose. It
surfaces:
  * endorsed directions, each with its computed confidence tier and per-factor
    score breakdown traceable to ledger records;
  * a contested / flagged / likely-dead-end section with the explicit evidence
    for each negative call (the point of MARS — do not hide these);
  * the executed-analysis trail and the deterministic gate results.

No dependency on the orchestrator (receives the ledger + a meta dict), so there
is no import cycle.
"""

from __future__ import annotations

import html
import os
import re
from typing import Dict, List

from mars.ledger import HIGH, LOW, MEDIUM, Direction, Ledger

_TIER_ICON = {HIGH: "🟢 high", MEDIUM: "🟡 medium", LOW: "🔴 low"}


# --------------------------------------------------------------------------- #
# Markdown
# --------------------------------------------------------------------------- #
def _factor_table(d: Direction, weights: Dict[str, float]) -> str:
    rows = ["| Factor | Value | Weight | Contribution |", "|---|---|---|---|"]
    for f in ("novelty", "feasibility", "datafit", "robustness"):
        v = d.factors.get(f, 0.0)
        w = weights.get(f, 0.0)
        rows.append(f"| {f} | {v:.2f} | {w:.2f} | {v * w:.3f} |")
    rows.append(f"| **score** |  |  | **{d.score:.3f}** |")
    return "\n".join(rows)


def _evidence_lines(d: Direction, ledger: Ledger) -> List[str]:
    lines = []
    for cid in d.supporting_claims:
        c = ledger.claims.get(cid)
        if not c:
            continue
        src = ", ".join(f"{g.type}:{g.ref}" for g in c.grounded_in) or "ungrounded"
        lines.append(f"  - `{c.id}` ({_TIER_ICON.get(c.confidence_tier, c.confidence_tier)}) "
                     f"{c.text}  _[{src}]_")
    return lines or ["  - _(no grounded supporting claims)_"]


def _why_flagged(d: Direction, ledger: Ledger) -> List[str]:
    out = []
    objs = list(d.objections) + [o for cid in d.supporting_claims if cid in ledger.claims
                                 for o in ledger.claims[cid].critique_objections]
    for o in objs:
        state = "resolved" if o.resolved else "OPEN"
        out.append(f"  - objection [{o.by}, {o.severity}, {state}]: {o.text}")
    for cid in d.supporting_claims:
        c = ledger.claims.get(cid)
        if c and c.contradicted_by:
            out.append(f"  - contradicted by: {', '.join(c.contradicted_by)} (claim {c.id})")
    if d.notes.get("null_interesting") is False:
        out.append(f"  - null-interesting check FAILED: {d.notes.get('null_reason', '')}")
    if d.notes.get("so_what") is False:
        out.append(f"  - so-what check FAILED: {d.notes.get('so_what_reason', '')}")
    return out or ["  - _(below endorsement bar on score/confidence)_"]


def assemble_markdown(ledger: Ledger, meta: Dict) -> str:
    weights = meta.get("weights", {})
    directions = ledger.directions_sorted()
    endorsed = [d for d in directions if d.status == "endorsed"]
    contested = [d for d in directions if d.status == "contested"]
    dead = [d for d in directions if d.status == "dead_end"]

    L = []
    L.append("# MARS Research Opportunity Report")
    L.append("")
    L.append(f"**Research question:** {meta.get('question', '')}")
    L.append("")
    L.append(f"- **Run:** `{meta.get('run_id', '')}`  ·  **By:** {meta.get('initials') or 'n/a'}"
             f"  ·  **Generated:** {meta.get('timestamp', '')}")
    L.append(f"- **Strategy:** {meta.get('strategy', 'aria')}  ·  **Scoring preset:** "
             f"{meta.get('preset', 'Balanced')}  ·  **Passes:** {meta.get('passes', 1)}"
             f"  ·  **Model calls:** {meta.get('model_calls', 0)}")
    L.append(f"- **Candidates generated:** {len(directions)}  →  **endorsed:** {len(endorsed)}"
             f"  ·  **contested:** {len(contested)}  ·  **dead-end:** {len(dead)}")
    L.append("")
    L.append("> MARS is built to tell you the truth, not to fill the page. It endorses "
             "fewer directions than it generates and attaches computed doubt to survivors. "
             "Confidence tiers are computed from the evidence ledger, never asserted.")
    L.append("")

    # Endorsed
    L.append("## Endorsed directions")
    if not endorsed:
        L.append("\n_No direction cleared the endorsement bar. The candidates below are "
                 "contested or likely dead ends — see why, and the sharper angles raised._\n")
    for i, d in enumerate(endorsed, 1):
        L += _direction_block(i, d, ledger, weights, endorsed=True)

    # Contested / dead-end — the point
    L.append("## Contested / flagged / likely dead-ends")
    L.append("\n_These are surfaced deliberately, with the evidence for the call._\n")
    if not contested and not dead:
        L.append("_None._")
    for d in contested + dead:
        L.append(f"\n### {'⚠️ contested' if d.status == 'contested' else '⛔ likely dead-end'}: "
                 f"{d.title}")
        L.append(f"- **Direction (`{d.id}`):** {d.statement}")
        L.append(f"- **Confidence:** {_TIER_ICON.get(d.confidence_tier)}  ·  "
                 f"**Score:** {d.score:.3f}  ·  **Flags:** {', '.join(d.flags) or 'none'}")
        L.append("- **Why:**")
        L += _why_flagged(d, ledger)

    # Ledger + analyses + gates
    L.append("\n## Evidence ledger summary")
    tiers = {HIGH: 0, MEDIUM: 0, LOW: 0}
    for c in ledger.claims.values():
        tiers[c.confidence_tier] = tiers.get(c.confidence_tier, 0) + 1
    L.append(f"- Claims: {len(ledger.claims)} (high {tiers[HIGH]} / medium {tiers[MEDIUM]} / "
             f"low {tiers[LOW]})  ·  Directions: {len(ledger.directions)}  ·  "
             f"Executed analyses: {len(ledger.analyses)}")
    L.append(f"- Full audit trail: `ledger.json`  ·  re-runnable analysis code: `analyses/`")

    L.append("\n## Executed analyses (exploratory; every specification logged)")
    if not ledger.analyses:
        L.append("_No dataset analysed._")
    for a in ledger.analyses.values():
        status = "ERROR" if a.error else ("significant" if a.significant else "null / n.s.")
        L.append(f"- `{a.id}` ({a.kind}, n={a.n}, {status}): {a.result_summary or a.error} "
                 f"— code: `analyses/{os.path.basename(a.code_path) if a.code_path else 'n/a'}`")

    L.append("\n## Validation & provenance (deterministic gates)")
    L.append("_Catch fabricated citations and ungrounded numbers before they propagate — "
             "they do not eliminate hallucination._\n")
    for g in meta.get("gate_results", []):
        mark = "✅" if g.passed else "⚠️"
        L.append(f"- {mark} `{g.name}` — {g.detail}")

    if meta.get("decision_log"):
        L.append("\n## Editorial loop")
        for entry in meta["decision_log"]:
            L.append(f"- Pass {entry['pass']}: {entry['reason']}")

    L.append("\n---\n_Runs are saved locally under `runs/`._")
    return "\n".join(L)


def _direction_block(i, d: Direction, ledger, weights, endorsed) -> List[str]:
    L = [f"\n### {i}. {d.title}  —  {_TIER_ICON.get(d.confidence_tier)}"]
    L.append(f"- **Direction (`{d.id}`):** {d.statement}")
    if d.notes.get("rationale"):
        L.append(f"- **Rationale:** {d.notes['rationale']}")
    if d.notes.get("design_sketch"):
        L.append(f"- **Design sketch:** {d.notes['design_sketch']}")
    if d.notes.get("required_vars"):
        L.append(f"- **Required variables:** {d.notes['required_vars']} "
                 f"(present: {d.notes.get('vars_present')})")
    L.append(f"- **Score breakdown:**\n\n{_factor_table(d, weights)}")
    L.append("- **Supporting evidence:**")
    L += _evidence_lines(d, ledger)
    open_objs = [o for o in d.objections if not o.resolved]
    if open_objs:
        L.append("- **Open objections (capping confidence):**")
        for o in open_objs:
            L.append(f"  - [{o.by}, {o.severity}] {o.text}")
    return L


# --------------------------------------------------------------------------- #
# PDF (best-effort)
# --------------------------------------------------------------------------- #
def _inline(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`(.+?)`", r'<font face="Courier">\1</font>', text)
    return text


def markdown_to_pdf(markdown_text: str, out_path: str) -> bool:
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import (ListFlowable, ListItem, Paragraph,
                                        SimpleDocTemplate, Spacer)
    except Exception:
        return False
    try:
        styles = getSampleStyleSheet()
        body = ParagraphStyle("Body", parent=styles["Normal"], fontSize=10, leading=14)
        doc = SimpleDocTemplate(out_path, pagesize=letter, leftMargin=0.9 * inch,
                                rightMargin=0.9 * inch, topMargin=0.9 * inch, bottomMargin=0.9 * inch)
        flow, bullets = [], []

        def flush():
            if bullets:
                flow.append(ListFlowable(list(bullets), bulletType="bullet", leftIndent=14))
                bullets.clear()

        for raw in (markdown_text or "").splitlines():
            line = raw.rstrip()
            if not line.strip():
                flush(); flow.append(Spacer(1, 5)); continue
            if re.match(r"^\s*\|", line) or line.strip() == "---" or line.startswith(">"):
                continue
            h = re.match(r"^(#{1,4})\s+(.*)", line)
            if h:
                flush()
                lvl = len(h.group(1))
                flow.append(Paragraph(_inline(h.group(2)),
                                      styles["Title"] if lvl == 1 else styles[f"Heading{min(lvl,4)}"]))
                continue
            b = re.match(r"^\s*[-*]\s+(.*)", line)
            if b:
                bullets.append(ListItem(Paragraph(_inline(b.group(1)), body))); continue
            flush(); flow.append(Paragraph(_inline(line), body))
        flush()
        doc.build(flow)
        return os.path.exists(out_path)
    except Exception:
        return False
