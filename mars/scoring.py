"""Direction viability scoring + endorsement classification (build spec v2 §7).

    score = w_novelty·novelty + w_feasibility·feasibility
          + w_datafit·datafit + w_robustness·robustness

Every factor is a 0..1 value DERIVED FROM THE LEDGER, not asserted by an agent:
  novelty     drops as the Scout/Red-team surface prior work or contradictions.
  feasibility comes from the Methods assessment.
  datafit     rises when required variables are confirmed present with adequate n.
  robustness  reflects surviving critique/red-team (unresolved objections hurt it).

Weights are the researcher's per-run priorities (presets in config.yaml). Same
evidence, different ranking — and the per-factor breakdown is shown so the
researcher sees WHY a direction ranked where it did.

Classification then decides which directions are `endorsed` vs `contested` vs
`dead_end`. The design REDUCES endorsements: a direction is endorsed only if it
clears the score bar, is not low-confidence, and carries no blocking flag.
"""

from __future__ import annotations

from typing import Dict

from mars.ledger import LOW, Direction, Ledger

_LEVEL = {"high": 1.0, "medium": 0.6, "low": 0.3}
_SEV_PENALTY = {"high": 0.4, "medium": 0.2, "low": 0.1}


def resolve_weights(cfg: Dict, preset: str = None) -> Dict[str, float]:
    sc = cfg.get("scoring", {})
    presets = sc.get("presets", {})
    name = preset or sc.get("default_preset", "Balanced")
    weights = presets.get(name) or presets.get("Balanced") or {
        "novelty": 0.25, "feasibility": 0.25, "datafit": 0.25, "robustness": 0.25}
    total = sum(weights.values()) or 1.0
    return {k: v / total for k, v in weights.items()}


# --------------------------------------------------------------------------- #
# Factors
# --------------------------------------------------------------------------- #
def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def compute_factors(d: Direction, ledger: Ledger, scout_challenge_count: int) -> Dict[str, float]:
    support = [ledger.claims[c] for c in d.supporting_claims if c in ledger.claims]
    n_contradicted = sum(1 for c in support if c.contradicted_by)
    redteam_objs = [o for o in d.objections if o.by == "red_team"]
    all_objs = list(d.objections) + [o for c in support for o in c.critique_objections]
    unresolved = [o for o in all_objs if not o.resolved]

    novelty = _clamp(1.0 - 0.25 * len(redteam_objs) - 0.15 * n_contradicted
                     - 0.10 * min(scout_challenge_count, 3))
    feasibility = _LEVEL.get((d.notes.get("feasibility") or "").lower(), 0.5)
    datafit = _LEVEL.get((d.notes.get("datafit") or "").lower(), 0.5)
    if d.notes.get("vars_present") is False:
        datafit = min(datafit, 0.3)
    robustness = _clamp(1.0 - sum(_SEV_PENALTY.get((o.severity or "low").lower(), 0.1)
                                  for o in unresolved))
    return {"novelty": round(novelty, 3), "feasibility": round(feasibility, 3),
            "datafit": round(datafit, 3), "robustness": round(robustness, 3)}


def score_directions(ledger: Ledger, weights: Dict[str, float]) -> None:
    """Compute and store factors + weighted score on every direction."""
    scout_challenges = sum(1 for c in ledger.claims.values() if "novelty_challenge" in c.labels)
    for d in ledger.directions.values():
        d.factors = compute_factors(d, ledger, scout_challenges)
        d.score = round(sum(weights.get(f, 0.0) * v for f, v in d.factors.items()), 3)


# --------------------------------------------------------------------------- #
# Classification (endorse / contest / dead-end)
# --------------------------------------------------------------------------- #
def classify_directions(ledger: Ledger, cfg: Dict) -> None:
    """Set direction.flags and direction.status from confidence + score + checks."""
    blocking = cfg.get("confidence", {}).get("blocking_severity", "high")
    min_score = float(cfg.get("scoring", {}).get("endorse_min_score", 0.5))

    for d in ledger.directions.values():
        support = [ledger.claims[c] for c in d.supporting_claims if c in ledger.claims]
        all_objs = list(d.objections) + [o for c in support for o in c.critique_objections]

        flags = []
        if any(o.is_blocking(blocking) for o in all_objs):
            flags.append("blocked")
        if any(c.contradicted_by for c in support):
            flags.append("contradicted")
        if d.notes.get("null_interesting") is False:
            flags.append("null_uninteresting")
        if d.notes.get("so_what") is False:
            flags.append("no_so_what")
        # keep any flags already present (e.g. from prior pass) without duplication
        d.flags = sorted(set(d.flags) | set(flags))

        endorsed = (d.confidence_tier != LOW and d.score >= min_score and not d.flags)
        if endorsed:
            d.status = "endorsed"
        elif ("blocked" in d.flags and d.score < min_score) or \
             ("contradicted" in d.flags and d.confidence_tier == LOW) or \
             ("null_uninteresting" in d.flags and "no_so_what" in d.flags):
            d.status = "dead_end"
        else:
            d.status = "contested"
