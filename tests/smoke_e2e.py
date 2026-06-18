"""Offline end-to-end smoke test (build spec v2 build-order step 9 + §14).

No API key needed: mars.models.complete is replaced with a deterministic mock,
and the Scout's network search is stubbed. The DATA SANDBOX STILL EXECUTES REAL
CODE against a real CSV, so this exercises the genuine analysis path.

Verifies the Definition of Done:
  * fewer endorsed directions than candidates, with evidence for dead-end calls
  * computed confidence tiers + per-factor score breakdown traceable to ledger
  * the data agent executes real analysis, logs every spec, labels exploratory,
    reports nulls
  * critique can block a direction from reaching high confidence
  * ARIA runs end-to-end; artifacts include ledger.json + re-runnable analysis code
  * the editorial loop iterates when the bar isn't met, and terminates at a bound

Run:  python tests/smoke_e2e.py
"""

import json
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from mars import models, orchestrator  # noqa: E402
from mars.agents import scout as scout_mod  # noqa: E402

QUOTE = "Time pressure reduces idea diversity in collaborative ideation"


# --------------------------------------------------------------------------- #
# Fixtures: a real PDF and a real CSV with a true linear relationship
# --------------------------------------------------------------------------- #
def make_pdf(path: str):
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(path)
    c.drawString(72, 720, QUOTE + ".")
    c.drawString(72, 700, "Prior studies measured ideation under deadline conditions.")
    c.save()


def make_csv(path: str):
    rng = np.random.default_rng(1)
    n = 240
    pressure = rng.normal(5, 2, n)
    diversity = -1.5 * pressure + rng.normal(0, 3, n) + 40   # real negative relationship
    noise = rng.normal(0, 1, n)
    pd.DataFrame({"time_pressure": pressure, "idea_diversity": diversity, "noise": noise}).to_csv(path, index=False)


# --------------------------------------------------------------------------- #
# Deterministic mock provider
# --------------------------------------------------------------------------- #
def _ids(text, prefix):
    return re.findall(rf"\b{prefix}_\d+\b", text or "")


def mock_complete(agent_name, system, prompt, *, json_mode=False):
    models._increment_calls()  # keep cost accounting realistic

    if agent_name == "literature":
        return json.dumps({
            "claims": [
                {"text": f'The paper states: "{QUOTE}".',
                 "grounded_in": [{"type": "paper", "ref": "smith2021", "loc": "p1"}]},
                {"text": "Deadline conditions have been studied in ideation.",
                 "grounded_in": [{"type": "paper", "ref": "smith2021", "loc": "p1"}]},
            ],
            "gaps": [{"text": "No quantitative dataset has linked time pressure to diversity.",
                      "grounded_in": [{"type": "paper", "ref": "smith2021", "loc": "p1"}]}],
            "key_terms": ["time pressure", "idea diversity", "ideation"],
        })

    if agent_name == "scout":
        if 'MODE "queries"' in prompt:
            return json.dumps({"queries": ["time pressure idea diversity"]})
        return json.dumps({
            "external_refs": [{"text": "A related ideation study.",
                               "grounded_in": [{"type": "external", "ref": "10.1000/abcd1234", "loc": ""}]}],
            "novelty_challenges": [{"text": "Some prior work has already linked deadlines to ideation breadth.",
                                    "grounded_in": [{"type": "external", "ref": "arXiv:2101.00001", "loc": ""}]}],
        })

    if agent_name == "data":
        if "fix" in (system or "").lower():  # repair path (shouldn't be needed)
            return json.dumps({"code": "emit(summary='noop', n=int(len(df)), numbers=[1.0])"})
        return json.dumps({"analyses": [
            {"kind": "ols", "description": "OLS idea_diversity ~ time_pressure",
             "code": ("import statsmodels.formula.api as smf\n"
                      "m = smf.ols('idea_diversity ~ time_pressure', data=df).fit()\n"
                      "b = m.params['time_pressure']; p = m.pvalues['time_pressure']\n"
                      "emit(summary=f'OLS beta={b:.3f}, p={p:.4g}, R2={m.rsquared:.3f}', "
                      "n=int(m.nobs), numbers=[round(b,3), round(p,4), round(m.rsquared,3)], "
                      "significant=bool(p<0.05))")},
            {"kind": "corr", "description": "Correlation noise vs idea_diversity (null check)",
             "code": ("from scipy import stats\n"
                      "r,p = stats.pearsonr(df['noise'], df['idea_diversity'])\n"
                      "emit(summary=f'Pearson r={r:.3f}, p={p:.3g}', n=len(df), "
                      "numbers=[round(r,3), round(p,3)], significant=bool(p<0.05))")},
            {"kind": "feasibility", "description": "Variables present with adequate n",
             "code": ("cols=['time_pressure','idea_diversity']\n"
                      "nn=int(df[cols].dropna().shape[0])\n"
                      "emit(summary=f'Required vars present, complete n={nn}', n=nn, numbers=[nn], significant=None)")},
        ]})

    if agent_name == "hypothesis":
        # distinct supporting claim per direction (dedup, preserve order)
        seen = []
        for x in _ids(prompt, "c"):
            if x not in seen:
                seen.append(x)
        c = seen + [""] * 6
        return json.dumps({"directions": [
            {"title": "Time pressure lowers idea diversity", "statement": "Does time pressure causally reduce idea diversity?",
             "supporting_claims": [x for x in [c[1]] if x], "rationale": "Gap + confirmed negative OLS signal."},
            {"title": "Diversity moderates output quality", "statement": "Does idea diversity mediate output quality under pressure?",
             "supporting_claims": [x for x in [c[2]] if x], "rationale": "Lit gap + data affordance."},
            {"title": "Noise predicts diversity", "statement": "Does the noise variable predict diversity?",
             "supporting_claims": [x for x in [c[3]] if x], "rationale": "Speculative; likely a confound."},
            {"title": "Deadline framing effect", "statement": "Does framing a deadline change diversity independent of real pressure?",
             "supporting_claims": [x for x in [c[4]] if x], "rationale": "Exploratory framing angle."},
        ]})

    if agent_name == "methods":
        ds = _ids(prompt, "d")
        cs = _ids(prompt, "c")
        assess = []
        plan = {"d_01": ("high", "high", True), "d_02": ("high", "high", True),
                "d_03": ("low", "low", False), "d_04": ("medium", "medium", True)}
        for d in ds:
            feas, fit, present = plan.get(d, ("medium", "medium", True))
            assess.append({"direction_id": d, "feasibility": feas, "datafit": fit,
                           "required_vars": ["time_pressure", "idea_diversity"], "vars_present": present,
                           "design_sketch": "OLS with controls; n>=200.", "notes": "Exploratory only.",
                           "corroborates": cs[:2]})
        return json.dumps({"assessments": assess})

    if agent_name == "critique":
        return json.dumps({
            "direction_objections": [
                {"direction_id": "d_03", "text": "The data cannot support this; noise is random by construction.",
                 "severity": "high"}],
            "claim_objections": [],
        })

    if agent_name == "red_team":
        # Target the weak direction by STABLE id; propose a sharper alternative.
        return json.dumps({
            "objections": [{"direction_id": "d_03", "text": "This is a confound (noise is random by construction), not a finding.",
                            "severity": "high"}],
            "contradictions": [],
            "alternatives": [{"title": "Pressure x expertise interaction",
                              "statement": "Does expertise buffer the pressure effect on diversity?",
                              "rationale": "A sharper, less-studied angle than the targeted direction."}],
        })

    if agent_name == "checks":
        ds = _ids(prompt, "d")
        checks = []
        for d in ds:
            if d == "d_03":  # the confound direction fails BOTH gates -> dead-end
                checks.append({"direction_id": d, "null_interesting": False,
                               "null_reason": "Only interesting if the (artefactual) effect appears.",
                               "so_what": False, "so_what_reason": "A noise correlation tells us nothing."})
            elif d == "d_04":  # fails one gate -> contested, not dead
                checks.append({"direction_id": d, "null_interesting": False,
                               "null_reason": "Only interesting if the effect is present.",
                               "so_what": True, "so_what_reason": "Minor relevance to collaboration design."})
            else:
                checks.append({"direction_id": d, "null_interesting": True, "null_reason": "A null is informative.",
                               "so_what": True, "so_what_reason": "Bears on collaboration design."})
        return json.dumps({"checks": checks})

    return "{}"


# --------------------------------------------------------------------------- #
# Run
# --------------------------------------------------------------------------- #
def main():
    tmp = tempfile.mkdtemp(prefix="mars_smoke_")
    inputs = os.path.join(tmp, "run", "inputs")
    os.makedirs(inputs, exist_ok=True)
    pdf = os.path.join(inputs, "smith2021.pdf")
    csv = os.path.join(inputs, "ideation.csv")
    make_pdf(pdf)
    make_csv(csv)
    Path(tmp, "run", "question.txt").write_text("Does time pressure reduce idea diversity?")

    # Patch the provider + the scout's network search (stay fully offline).
    models.complete = mock_complete
    scout_mod.ScoutAgent._search = lambda self, q: [
        {"title": "Deadlines and ideation", "abstract": "We study deadlines.", "year": 2021,
         "url": "https://doi.org/10.1000/abcd1234", "externalIds": {"DOI": "10.1000/abcd1234"}}]

    run_dir = os.path.join(tmp, "run")
    res = orchestrator.run("Does time pressure reduce idea diversity?", [pdf], [csv], run_dir,
                           initials="VK", preset="Balanced", strategy_name="aria")

    L = res.ledger
    directions = list(L.directions.values())
    endorsed = [d for d in directions if d.status == "endorsed"]
    dead = [d for d in directions if d.status == "dead_end"]

    print(f"  passes={res.passes} model_calls={res.model_calls} error={res.error}")
    print(f"  candidates={len(directions)} endorsed={len(endorsed)} "
          f"contested={sum(1 for d in directions if d.status=='contested')} dead_end={len(dead)}")
    print(f"  claims={len(L.claims)} analyses={len(L.analyses)}")

    assert res.error is None, f"pipeline errored: {res.error}"

    # 1. fewer endorsed than candidates, with at least one endorsed and one dead-end
    assert len(directions) >= 4, "expected several candidate directions"
    assert 0 < len(endorsed) < len(directions), "endorsed must be a nonempty proper subset"
    assert len(dead) >= 1, "expected at least one dead-end"
    print("  ok  fewer endorsed than candidates, with a dead-end")

    # 2. computed confidence + per-factor breakdown on every direction
    for d in directions:
        assert d.confidence_tier in ("high", "medium", "low")
        assert set(d.factors) == {"novelty", "feasibility", "datafit", "robustness"}, d.factors
        assert 0.0 <= d.score <= 1.0
    print("  ok  computed confidence tiers + per-factor breakdown present")

    # 3. data agent executed real analysis, logged specs, labelled exploratory, reported a null
    assert len(L.analyses) >= 2, "expected executed analyses"
    ols = next((a for a in L.analyses.values() if a.kind == "ols"), None)
    assert ols and ols.numbers and ols.n == 240, f"OLS analysis missing/incomplete: {ols}"
    assert abs(ols.numbers[0] + 1.5) < 0.6, f"OLS did not recover the true slope: {ols.numbers}"
    assert all("exploratory" in a.labels for a in L.analyses.values()), "analyses must be labelled exploratory"
    assert any(a.significant is False for a in L.analyses.values()), "a null result should be reported"
    print(f"  ok  data executed (OLS beta={ols.numbers[0]}, n={ols.n}); nulls reported; labelled exploratory")

    # 4. critique blocked a direction from reaching high confidence
    blocked = [d for d in directions if any(o.by == "critique" and o.severity == "high"
                                            for o in d.objections)]
    assert blocked, "critique should have raised a high-severity (blocking) objection"
    assert all(d.confidence_tier == "low" for d in blocked), "blocked direction must be capped at low"
    print("  ok  critique blocked a direction (capped at low confidence)")

    # 5. artifacts: ledger.json + re-runnable analysis code + manifest
    assert os.path.exists(os.path.join(run_dir, "ledger.json")), "ledger.json missing"
    led = json.load(open(os.path.join(run_dir, "ledger.json")))
    assert led["counts"]["claims"] and led["counts"]["directions"] and led["counts"]["analyses"]
    code_files = list(Path(run_dir, "analyses").glob("*.py"))
    assert code_files, "no re-runnable analysis code saved"
    assert os.path.exists(os.path.join(run_dir, "report.md")), "report.md missing"
    man = json.load(open(os.path.join(run_dir, "manifest.json")))
    assert man["schema_version"] == 2 and man["model_routing"] and man["gates"]
    assert man["directions_by_status"].get("endorsed", 0) == len(endorsed)
    print(f"  ok  artifacts: ledger.json, {len(code_files)} analysis .py, report.md, manifest.json")

    # 6. gates ran (deterministic) and provenance/citation/quote checks are present
    names = {g.name for g in res.gate_results}
    assert {"schema_conformance", "citation_resolution", "quote_grounding", "numeric_provenance"} <= names
    numeric = next(g for g in res.gate_results if g.name == "numeric_provenance")
    assert numeric.checked > 0, "numeric provenance should have checked data-grounded numbers"
    print(f"  ok  gates ran: {sorted(names)} (numeric checked {numeric.checked} numbers)")

    # 7. editorial loop: iterates when the bar is raised, and terminates at the bound
    orig_get_config = models.get_config
    cfg2 = json.loads(json.dumps(orig_get_config()))  # deep copy
    cfg2["editorial"]["target_endorsed_directions"] = 5  # unreachable -> must iterate
    models.get_config = lambda: cfg2
    try:
        run_dir2 = os.path.join(tmp, "run2")
        os.makedirs(os.path.join(run_dir2, "inputs"), exist_ok=True)
        res2 = orchestrator.run("Q?", [pdf], [csv], run_dir2, initials="VK",
                                preset="Balanced", strategy_name="aria")
    finally:
        models.get_config = orig_get_config
    assert res2.passes > 1, f"editorial loop should iterate when bar unmet (passes={res2.passes})"
    assert res2.passes <= cfg2["editorial"]["max_passes"] + 1, "loop must terminate at the bound"
    assert res2.decision_log[-1]["finish"] is True
    print(f"  ok  editorial loop iterated to {res2.passes} passes then stopped at the bound")

    print("\nALL E2E SMOKE CHECKS PASSED")


if __name__ == "__main__":
    main()
