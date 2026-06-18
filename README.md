# MARS — Multi-Agent Research System (internal lab tool)

MARS takes a research question + your papers + your data and returns a **ranked,
evidence-backed set of research opportunities** — with computed confidence, an
explicit "these are likely dead ends, and here's why" section, and an auditable
trail for every claim. It is built to tell you the **truth** about your question,
not to fill a page.

It runs as a small Streamlit web app on one lab-controlled machine. 3–5 research
assistants use it through a browser; every run is saved locally as evidence.

> Built per `MARS_BUILD_SPEC_v2.md`. v2 replaces the earlier linear-pipeline spec
> with a layered, looping research system (evidence ledger, executed data
> analysis, enforced skepticism, editorial loop).

**New here? Read [CAPABILITIES.md](CAPABILITIES.md) first** — an honest, per-agent
account of what MARS can and can't do (it's also shown on the app's home page).

---

## Why this is different from "ask a chatbot"

A single chatbot is agreeable: it produces something complete-looking and
converges on what you seemed to want. MARS resists that **structurally**:

- **Computed confidence, not fluent confidence.** Every assertion is a claim
  record in an evidence ledger. A deterministic function maps its state →
  High / Medium / Low. Agents never assert their own confidence.
- **Critique is a gate, not a comment.** A direction cannot reach high confidence
  while an unresolved high-severity objection stands — it is capped at low
  ("promising but unvalidated") until evidence answers the objection.
- **A red-team tries to kill the top direction** every pass — finds the prior
  paper that already did it, the confound that defeats it, or a sharper angle.
- **The data agent executes real code** (pandas/numpy/statsmodels/scipy) against
  your dataset in a sandbox, logs **every** specification it runs (anti-p-hacking),
  labels results exploratory, and reports nulls — not just hits.
- **It endorses fewer directions than it generates.** That reduction is the point.

---

## Quick start

```bash
# 1. Install
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Key — the lab Claude service-account key (NOT a personal subscription)
cp .env.example .env
#   ANTHROPIC_API_KEY=sk-ant-...        (lab service account)
#   OPENROUTER_API_KEY=...              (optional; only if an agent uses openrouter)

# 3. (Optional) local model, only if a dataset must stay off the API:
#    install Ollama from ollama.com, then `ollama pull qwen2.5:14b`,
#    and set that agent's provider to `ollama` in config.yaml.

# 4. Run, reachable on the lab network
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

**Point RAs at:** `http://<this-machine-ip>:8501` (find the IP with `ipconfig getifaddr en0`
on macOS or `hostname -I` on Linux). No login — they enter their initials for the
run log. Inputs: a research question, PDF papers, CSV/Excel data, a scoring preset.

---

## How a run works (six layers)

```
Layer 0  Researcher input    question + papers + data + scoring preset
Layer 1  Orchestrator        builds the evidence ledger, scopes each agent's context
Layer 2  Specialists         literature · scout · data-explorer (parallel)
                             then hypothesis · methods · critique(gate) · red-team · checks
Layer 3  Evidence & conflict scores findings, computes confidence, classifies directions
Layer 4  Editorial loop      reads the evidence → iterate (back to L1) or finish
Layer 5  Output              ranked directions, confidence tiers, contested/dead-end, trail
```

The **loop** (Layer 4 → Layer 1) is the core of v2: the editorial controller can
send work back with targeted instructions ("scout broader, the novelty is
contested"; "data agent: test relationship X first"), bounded by a max-pass count
and a model-call cost ceiling so it always terminates.

ARIA (the fixed agent set above) is the default. A `dynamic` strategy is wired
behind the same `DecompositionStrategy` interface so it can be swapped in and
compared on the same machinery — it is currently a stub (`mars/strategies/dynamic.py`).

---

## Configuration — `config.yaml` (no code change needed)

- **Model routing** — which provider/model serves each agent. Default is the lab
  Claude service-account key for everything; reassign any agent to `openrouter`
  (cheap open models) or `ollama` (local) per agent.
- **Confidence thresholds** — e.g. how many independent corroborators a claim needs
  for High; which objection severity blocks.
- **Scoring presets** — Balanced / Novelty-seeking / Feasibility-first. Same
  evidence, different ranking; the per-factor breakdown (novelty, feasibility,
  datafit, robustness) is shown so you see *why* a direction ranked where it did.
- **Editorial bounds** — `max_passes`, `max_agent_calls` (cost ceiling),
  `target_endorsed_directions`.
- **Data sandbox** — per-analysis timeout, max analyses per pass.

`.env` holds only secrets (`ANTHROPIC_API_KEY`, optional `OPENROUTER_API_KEY`).

---

## Run artifacts — `runs/<timestamp>_<initials>/`

Every run is self-contained evidence:

```
runs/2026-06-18_1430_VK/
├── inputs/            uploaded papers + data
├── question.txt
├── report.md          ranked directions + contested/dead-ends + provenance
├── report.pdf         (if reportlab is installed)
├── ledger.json        the full evidence ledger — every claim, direction, objection
├── analyses/          re-runnable .py for every executed analysis (anti-p-hacking trail)
└── manifest.json      who/when, provider+model per agent, gates, passes, status counts
```

---

## What MARS does and does NOT claim

- **Validation gates are deterministic** (no LLM in the gate): schema conformance,
  citation resolution (cited refs resolve to a real id / an uploaded paper),
  quote grounding (quotes appear in the source), and numeric provenance (every
  data number traces to a re-runnable analysis). The honest claim: *they catch
  fabricated citations and ungrounded numbers before they propagate* — they do
  **not** eliminate hallucination.
- **The data agent is exploratory, not confirmatory.** It answers "is there
  plausibly signal worth pursuing," reports n and that results are uncorrected,
  and you stay in the loop for paper-grade analysis.
- **The sandbox** runs analysis code in a subprocess with a stripped environment
  (no API keys), CPU/memory limits, a timeout, and a guard against
  network/process/filesystem operations. It is a pragmatic guard for LLM-written
  analysis code on a trusted lab machine — not a hardened jail.

## Compliance assumption (a lab/PI decision, not a code decision)

MARS sends question, paper text, and dataset content to the configured model
provider. The default is the lab's **Claude service-account API key** (a standard
Anthropic API key owned by the lab — not a personal Claude subscription). The
build assumes the lab's data agreement with Anthropic permits sending lab research
data to the Claude API. **If a given dataset is not cleared for the API, route the
data agent to a local Ollama model in `config.yaml`** — no code change required.

---

## Tests

```bash
python tests/test_ledger.py   # unit-tests the computed-confidence function
python tests/smoke_e2e.py     # offline end-to-end (mock provider; sandbox runs real code)
```

The smoke test needs no API key and verifies the Definition of Done: fewer
endorsed than candidates with evidence for dead-ends, computed confidence +
per-factor breakdowns, real executed analysis with nulls reported, critique
blocking, the editorial loop iterating and terminating, and the full run artifact.

---

## Repository layout

```
app.py                     Streamlit entry point (Layers 0 + 5 surface)
config.yaml                routing + confidence + scoring presets + editorial bounds
mars/
├── orchestrator.py        Layers 0/1/3/4/5 — the loop
├── strategies/            aria.py (default) + dynamic.py (stub) behind DecompositionStrategy
├── agents/                literature, scout, data, hypothesis, methods, critique, red_team, checks
├── prompts/               structured-output prompts (the research IP)
├── ledger.py              claim records + computed confidence (§6)
├── scoring.py             direction viability + endorse/contest/dead-end (§7)
├── editorial.py           iterate-or-finish controller (§2, §4)
├── data_sandbox.py        code-execution loop for the data agent (§8)
├── gates.py               deterministic validation gates (§11)
├── models.py              per-agent provider routing + cost counter (carry-over)
├── ingest.py              PDF / dataset parsing
├── plots.py               dataset visualisations
└── report.py              Layer 5 report assembly + PDF
runs/                      created at runtime (gitignored)
tests/                     ledger unit tests + offline e2e smoke test
```

---

## Legacy v2.1 app (`backend/` + `frontend/`)

The original FastAPI + React prototype still lives in `backend/` and `frontend/`.
It is the predecessor this tool was built from and is **not** the deployment
target. To run it instead, see `scripts/start.sh`. The Streamlit tool above
(`app.py` + `mars/`) is the current internal deployment.

## License

MIT
