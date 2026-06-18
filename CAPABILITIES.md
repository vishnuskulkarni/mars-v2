# MARS — Capabilities & Ceilings

**Read this before your first run.** MARS is a research *direction-finding* tool, not an analysis or modeling platform. It is built to help you decide **what is worth pursuing** — not to produce finished results you can drop into a paper. This page is honest about what each agent can and cannot do, so you use MARS for what it's good at and don't expect things it was deliberately not built to do.

## What MARS is for (use it for these)

- Turning a rough question + your papers + your data into a **short list of research directions worth pursuing**, with honest reasons.
- Getting a fast, critical read on **which of your ideas are weak or already done**, and which have a real gap behind them.
- A quick **feasibility check**: can this question even be answered with the data you have?
- Surfacing **alternate angles** you didn't think to ask about.

## What MARS is NOT for (don't expect these)

- It is **not** a replacement for a data scientist or for your own analysis. It does not produce publication-grade results.
- It does **not** run full ML/DS modeling pipelines — no model training, tuning, cross-validation, feature engineering at scale, or deployment.
- It does **not** deliver confirmatory statistical findings. Everything it computes is **exploratory** — a lead to test properly yourself, not a conclusion.
- It is **not** a better general assistant than a frontier chat model for one-off questions. For those, just use the chat model. MARS earns its place when the work needs grounded, reproducible, multi-perspective analysis over data you control.

---

## Why there are ceilings

Two reasons, both deliberate — these are design choices, not bugs:

1. **Model limitations.** Every agent is an LLM. LLMs are strong at reading, structuring, critiquing, and writing code, but they can be confidently wrong, miss context outside what they're given, and cannot truly "know" your field. MARS reduces this with grounding and cross-checks, but it cannot remove it.
2. **Research integrity.** An agent that could run unlimited analyses *and* was rewarded for finding effects would be an automated p-hacking machine — it would eventually find a "significant" result by chance and present noise as a discovery. MARS is deliberately restrained to keep you, the researcher, in control of any analysis that becomes a real claim.

---

## Per-agent: what it can and cannot do

### Orchestrator
- **Can:** plan the run, give each agent only the context it needs, manage the iterate-or-finish loop within a cost ceiling.
- **Cannot:** add knowledge of its own; it only coordinates the other agents.

### Literature agent
- **Can:** read your uploaded papers, extract their claims/methods/findings, and map where the gaps are.
- **Cannot:** read papers you didn't upload; verify a paper's claims are correct; replace a real systematic literature review. It only knows what's in the documents you give it (plus what the Scout finds).

### Literature Scout
- **Can:** search **Semantic Scholar** (an academic paper database) for related work you may have missed, and flag where your "novel" idea already exists.
- **Cannot:** search the general open web; read paywalled or subscription-only full text (it works only from the titles, abstracts, and identifiers Semantic Scholar returns); or guarantee completeness. Absence of a found paper is **not** proof a topic is unexplored.

### Data Explorer / Analyst
- **Can:** write and run **real Python** against your dataset in a sandbox — descriptive stats, distributions, missingness and data-quality checks, correlations, group comparisons (t-test, ANOVA, chi-square), and **small regressions (OLS, logistic, fixed-effects via statsmodels)**, including controlled regressions to check whether an effect survives covariates. It repairs its own code on error and reports nulls.
- **Does not — by design (deliberate guardrails, partly enforced by limits, not just instructions):**
  - Produce **confirmatory or publication-grade** results. Everything is labeled **exploratory**, with n and uncorrected status.
  - Train, tune, or validate ML models, run cross-validation, or build feature pipelines. (Libraries like scikit-learn are present, but the agent is scoped and instructed to exploratory checks, not modeling deliverables.)
  - Decide "the result" for you. It logs **every** specification it runs (anti-p-hacking) so you can see how a lead was found; it does not hand you one cherry-picked regression as an answer.
  - Handle very large datasets or long-running computation — each analysis runs under a short per-analysis timeout and memory cap, so heavy or slow computation is cut off. It's scoped to quick, interpretable checks.
- **Use it to answer:** "is there plausibly signal here worth a proper study?" — not "what's the final estimate?"

### Hypothesis agent
- **Can:** combine literature gaps with what the data can actually support into testable, evidence-tied directions.
- **Cannot:** guarantee a direction is correct or fundable — only that it's grounded in a gap and a data affordance.

### Methods agent
- **Can:** sketch a defensible study/analysis design per direction and flag feasibility problems.
- **Cannot:** replace formal study design, power calculation by a statistician, or IRB/ethics review. Its designs are starting points.

### Critique & Red-team agents
- **Can:** object to weak directions (and **block** them from being endorsed with high confidence), actively try to kill the top idea, and propose better competing angles.
- **Cannot:** catch every flaw. A direction surviving critique is "not obviously broken," not "proven sound."

### Editorial controller
- **Can:** decide whether the work is good enough or needs another pass, bounded by max-passes and a cost ceiling.
- **Cannot:** run forever or guarantee convergence — it will stop and report honestly if the evidence stays thin.

---

## How to read MARS output

- **Confidence tiers are computed, not asserted.** High = grounded + independently corroborated + survived critique. Low = weakly grounded, contradicted, or carrying an open objection — **surfaced as contested, not hidden.**
- **Fewer endorsed directions is the goal**, not a failure. MARS is built to talk you out of weak ideas.
- **Dead-end calls are findings too.** "This is likely already done / not feasible / a confound" is useful output.
- **Every number traces to re-runnable code** in the run's `analyses/` folder. If you want a real result, take that lead and do the analysis properly yourself.

---

## One-line summary

> MARS tells you **what to study and whether your data can support it** — honestly and with its evidence shown. It does not do your statistics, your modeling, or your paper for you. Treat its analysis as **leads to verify**, not results to report.
