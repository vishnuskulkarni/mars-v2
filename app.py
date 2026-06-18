"""MARS — internal research tool (Streamlit entry point), build spec v2.

Run:  streamlit run app.py --server.address 0.0.0.0 --server.port 8501
RAs open http://<this-machine-ip>:8501

Single-page flow: research question + papers (PDF) + data (CSV/XLSX) + initials +
a scoring preset, then Run. MARS executes the layered, looping research system
(evidence ledger, executed data analysis, critique/red-team, editorial loop) and
returns RANKED directions with computed confidence + per-factor breakdowns, an
explicit contested/dead-end section, and a per-claim evidence drill-down. Every
run is saved under ./runs/.
"""

from __future__ import annotations

import os
import queue
import re
import threading
from datetime import datetime
from pathlib import Path

import streamlit as st

from mars import models, orchestrator, scoring, strategies
from mars.ledger import HIGH, LOW, MEDIUM

RUNS_DIR = Path(__file__).resolve().parent / "runs"
CAPABILITIES_PATH = Path(__file__).resolve().parent / "CAPABILITIES.md"
TUTORIAL_PATH = Path(__file__).resolve().parent / "TUTORIAL.md"
AGENT_LABELS = {
    "literature": "Literature", "scout": "Literature Scout", "data": "Data Explorer (executes)",
    "hypothesis": "Hypothesis", "methods": "Methods", "critique": "Critique (gate)",
    "red_team": "Red-team", "checks": "Null / so-what checks",
}
ICON = {"pending": "⚪", "running": "🔵", "complete": "✅", "error": "🔴"}
TIER = {HIGH: "🟢 High", MEDIUM: "🟡 Medium", LOW: "🔴 Low"}
STATUS_BADGE = {"endorsed": "✅ endorsed", "contested": "⚠️ contested", "dead_end": "⛔ likely dead-end",
                "candidate": "• candidate"}

st.set_page_config(page_title="MARS — Research Tool", page_icon="🛰️", layout="wide")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _initials(s: str) -> str:
    return (re.sub(r"[^A-Za-z0-9]", "", s or "").upper()[:8]) or "RA"


def _providers_in_use() -> set:
    try:
        return {r.provider for r in models.describe_routing().values()}
    except Exception:
        return set()


def _missing_keys(providers: set) -> list:
    miss = []
    if "anthropic" in providers and not os.getenv("ANTHROPIC_API_KEY", "").strip():
        miss.append("ANTHROPIC_API_KEY (lab Claude service account)")
    if "openrouter" in providers and not os.getenv("OPENROUTER_API_KEY", "").strip():
        miss.append("OPENROUTER_API_KEY")
    return miss


def _save_uploads(files, dest: Path, exts: set) -> list:
    dest.mkdir(parents=True, exist_ok=True)
    paths = []
    for f in files or []:
        if Path(f.name).suffix.lower() in exts:
            (dest / f.name).write_bytes(f.getbuffer())
            paths.append(str(dest / f.name))
    return paths


def _board(states: dict) -> str:
    return "  \n".join(f"{ICON.get(states.get(n, 'pending'), '⚪')} **{AGENT_LABELS[n]}** — "
                       f"{states.get(n, 'pending')}" for n in orchestrator.AGENT_ORDER)


# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.subheader("Model routing")
    st.caption("Per-agent provider/model from `config.yaml` (edit to reassign — no code change).")
    try:
        for name, route in models.describe_routing().items():
            st.markdown(f"- **{AGENT_LABELS.get(name, name)}** → `{route.provider}`·`{route.model}`")
    except Exception as e:
        st.error(f"config.yaml: {e}")
    if st.button("↻ Reload config.yaml"):
        models.reload_config()
        st.rerun()
    st.divider()
    st.subheader("Past runs")
    if RUNS_DIR.exists():
        for rd in sorted([p for p in RUNS_DIR.iterdir() if p.is_dir()], reverse=True)[:15]:
            qf = rd / "question.txt"
            st.markdown(f"- `{rd.name}` — {(qf.read_text()[:55] + '…') if qf.exists() else ''}")
    else:
        st.caption("No runs yet.")


# --------------------------------------------------------------------------- #
# Header + inputs
# --------------------------------------------------------------------------- #
st.title("🛰️ MARS — Multi-Agent Research System")
st.markdown("MARS tells you the **truth** about your question: which directions are worth pursuing, "
            "which are likely dead ends and **why**, with computed confidence and an auditable "
            "evidence trail. It endorses **fewer** directions than it generates — that is the point.")

# Welcome + capabilities — collapsed by default so they don't crowd the page.
# Both render live from their markdown files, so editing the file updates the panel.
with st.expander("👋 New to MARS? Start here", expanded=False):
    try:
        st.markdown(TUTORIAL_PATH.read_text())
    except Exception:
        st.caption("TUTORIAL.md not found — see the repo for the getting-started guide.")
with st.expander("📋 What MARS can and can't do (optional, recommended before your first run)", expanded=False):
    try:
        st.markdown(CAPABILITIES_PATH.read_text())
    except Exception:
        st.caption("CAPABILITIES.md not found — see the repo for capabilities and ceilings.")

providers = _providers_in_use()
missing = _missing_keys(providers)
if missing:
    st.warning("Missing credentials: " + ", ".join(missing) + ". Add them to `.env` before running.")

with st.container(border=True):
    question = st.text_area("Research question", height=90,
                            placeholder="e.g. Does time pressure reduce idea diversity in collaborative ideation?")
    c1, c2 = st.columns(2)
    lit_files = c1.file_uploader("Papers (PDF)", type=["pdf"], accept_multiple_files=True)
    data_files = c2.file_uploader("Data (CSV / Excel)", type=["csv", "xlsx", "xls"],
                                  accept_multiple_files=True)
    c3, c4, c5 = st.columns([2, 2, 1])
    initials = c3.text_input("Your name / initials (run log)", max_chars=40)
    sc_cfg = models.get_config().get("scoring", {})
    presets = list(sc_cfg.get("presets", {"Balanced": {}}))
    preset = c4.selectbox("Scoring preset", presets,
                          index=presets.index(sc_cfg.get("default_preset", presets[0]))
                          if sc_cfg.get("default_preset", presets[0]) in presets else 0,
                          help="Same evidence, different ranking. Shown per-factor in the results.")
    strat = c5.selectbox("Strategy", strategies.strategy_names(), index=0,
                         help="ARIA = fixed agent set (default). dynamic = experimental stub.")
    run_clicked = st.button("Run analysis", type="primary", use_container_width=True)


# --------------------------------------------------------------------------- #
# Execute
# --------------------------------------------------------------------------- #
def _execute(question, lit_files, data_files, initials, preset, strat):
    run_id = f"{datetime.now().strftime('%Y-%m-%d_%H%M')}_{_initials(initials)}"
    run_dir = RUNS_DIR / run_id
    inputs = run_dir / "inputs"
    lit_paths = _save_uploads(lit_files, inputs, {".pdf"})
    data_paths = _save_uploads(data_files, inputs, {".csv", ".xlsx", ".xls"})
    (run_dir / "question.txt").write_text(question)

    q: queue.Queue = queue.Queue()
    holder: dict = {}

    def worker():
        holder["result"] = orchestrator.run(question, lit_paths, data_paths, str(run_dir),
                                             initials=initials, preset=preset,
                                             strategy_name=strat, progress=q.put)
        q.put({"type": "_done"})

    threading.Thread(target=worker, daemon=True).start()

    states = {n: "pending" for n in orchestrator.AGENT_ORDER}
    with st.status("Starting…", expanded=True) as status:
        board = st.empty()
        board.markdown(_board(states))
        while True:
            ev = q.get()
            t = ev.get("type")
            if t == "_done":
                break
            if t == "phase":
                status.update(label=ev["phase"])
            elif t == "agent":
                states[ev["agent"]] = ev["status"]
                board.markdown(_board(states))
            elif t == "decision":
                status.write(("🏁 " if ev["finish"] else "🔁 ") + ev["reason"])
            elif t == "info":
                status.write(f"✓ {ev.get('message')}")
            elif t == "error":
                status.write(f"🔴 {ev.get('message')}")
        res = holder.get("result")
        if res and not res.error:
            status.update(label=f"Done in {res.duration_seconds:.0f}s · "
                                f"{res.passes} pass(es) · {res.model_calls} model calls",
                          state="complete")
        else:
            status.update(label="Finished with errors", state="error")
    return res


if run_clicked:
    if not question.strip():
        st.error("Please enter a research question.")
    elif not initials.strip():
        st.error("Please enter your name / initials.")
    elif missing:
        st.error("Cannot run: missing provider credentials (see warning above).")
    else:
        st.session_state["result"] = _execute(question, lit_files, data_files, initials, preset, strat)


# --------------------------------------------------------------------------- #
# Results
# --------------------------------------------------------------------------- #
def _factor_bar(d):
    return " · ".join(f"{f}={d.factors.get(f, 0):.2f}" for f in ("novelty", "feasibility", "datafit", "robustness"))


def _direction_card(d, ledger, expanded):
    badge = STATUS_BADGE.get(d.status, d.status)
    with st.container(border=True):
        st.markdown(f"**{d.title}** — {TIER.get(d.confidence_tier)} · score **{d.score:.2f}** · {badge}")
        st.caption(f"`{d.id}` · {d.statement}")
        st.caption(f"Factors: {_factor_bar(d)}")
        if d.notes.get("design_sketch"):
            st.markdown(f"_Design:_ {d.notes['design_sketch']}")
        open_objs = [o for o in d.objections if not o.resolved]
        if open_objs:
            st.markdown("**Open objections (capping confidence):**")
            for o in open_objs:
                st.markdown(f"- [{o.by}, {o.severity}] {o.text}")
        if d.flags:
            st.markdown(f"**Flags:** {', '.join(d.flags)}")
            if d.notes.get("null_interesting") is False:
                st.caption(f"null-interesting failed: {d.notes.get('null_reason','')}")
            if d.notes.get("so_what") is False:
                st.caption(f"so-what failed: {d.notes.get('so_what_reason','')}")
        with st.expander("Evidence drill-down (per claim)", expanded=expanded):
            if not d.supporting_claims:
                st.caption("No grounded supporting claims.")
            for cid in d.supporting_claims:
                c = ledger.claims.get(cid)
                if not c:
                    continue
                src = ", ".join(f"{g.type}:{g.ref}" for g in c.grounded_in) or "ungrounded"
                st.markdown(f"- `{c.id}` {TIER.get(c.confidence_tier)} — {c.text}")
                st.caption(f"raised by {c.raised_by} · grounded in {src} · "
                           f"corroborated by {', '.join(c.corroborated_by) or 'none'}"
                           + (f" · contradicted by {', '.join(c.contradicted_by)}" if c.contradicted_by else ""))


res = st.session_state.get("result")
if res is not None:
    st.divider()
    if res.error:
        st.error(f"Pipeline error: {res.error}")
    ledger = res.ledger
    directions = ledger.directions_sorted() if ledger else []
    endorsed = [d for d in directions if d.status == "endorsed"]
    contested = [d for d in directions if d.status == "contested"]
    dead = [d for d in directions if d.status == "dead_end"]

    st.success(f"Run `{res.run_id}` saved to `runs/{res.run_id}/` · {res.passes} pass(es) · "
               f"{res.model_calls} model calls · preset {res.preset} · strategy {res.strategy}")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Candidates", len(directions))
    m2.metric("Endorsed", len(endorsed))
    m3.metric("Contested", len(contested))
    m4.metric("Likely dead-end", len(dead))
    st.caption("MARS reduces endorsed directions and attaches computed doubt — fewer-than-candidates "
               "is the designed outcome, not a bug.")

    st.subheader("Endorsed directions")
    if not endorsed:
        st.info("No direction cleared the bar this run. See contested / dead-ends below for why, "
                "and the sharper angles the red-team raised.")
    for d in endorsed:
        _direction_card(d, ledger, expanded=True)

    if contested or dead:
        st.subheader("Contested / flagged / likely dead-ends")
        st.caption("Surfaced deliberately, with the evidence for each call.")
        for d in contested + dead:
            _direction_card(d, ledger, expanded=False)

    # Executed analyses
    if ledger and ledger.analyses:
        st.subheader("Executed analyses (exploratory; every specification logged)")
        for a in ledger.analyses.values():
            status = "🔴 error" if a.error else ("📈 significant" if a.significant else "➖ null / n.s.")
            with st.container(border=True):
                st.markdown(f"`{a.id}` · {a.kind} · n={a.n} · {status}")
                st.caption(a.result_summary or a.error or "")
                if a.code_path and os.path.exists(a.code_path):
                    with st.expander("re-runnable code"):
                        st.code(Path(a.code_path).read_text(), language="python")

    # Gates
    st.subheader("Validation & provenance (deterministic gates)")
    for g in res.gate_results:
        (st.success if g.passed else st.warning)(f"`{g.name}` — {g.detail}")

    # Full report + downloads
    with st.expander("Full report (markdown)"):
        st.markdown(res.report_markdown)

    st.subheader("Download")
    d1, d2, d3 = st.columns(3)
    d1.download_button("⬇ Report (Markdown)", res.report_markdown,
                       file_name=f"mars-report-{res.run_id}.md", mime="text/markdown",
                       use_container_width=True)
    ledger_path = Path(res.run_dir) / "ledger.json"
    if ledger_path.exists():
        d2.download_button("⬇ Evidence ledger (JSON)", ledger_path.read_bytes(),
                           file_name=f"mars-ledger-{res.run_id}.json", mime="application/json",
                           use_container_width=True)
    if res.report_pdf_path and os.path.exists(res.report_pdf_path):
        with open(res.report_pdf_path, "rb") as fh:
            d3.download_button("⬇ Report (PDF)", fh.read(), file_name=f"mars-report-{res.run_id}.pdf",
                               mime="application/pdf", use_container_width=True)
    else:
        d3.caption("PDF unavailable (install reportlab).")

st.divider()
st.caption("Runs are saved locally under `./runs/` (inputs, report, ledger.json, analyses/, manifest.json). "
           "No data leaves this host except agent calls to the configured model provider(s).")
