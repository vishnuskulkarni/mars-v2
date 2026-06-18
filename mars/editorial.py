"""Editorial controller — Layer 4 (build spec v2 §2, §4).

Reads the evidence state after a pass and decides: iterate (loop back to Layer 1
with refined, targeted instructions) or finish. The loop is what separates v2
from a one-shot pipeline; it is bounded by a max-pass count and a cost ceiling
(model calls), so it always terminates.

The decision is deterministic (a function of ledger state + bounds), and the
refinement focus is templated from which directions still carry unresolved
objections / weak datafit / contested novelty. This keeps the controller
debuggable rather than being another opaque LLM.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

from mars import models
from mars.ledger import LOW, Ledger


@dataclass
class EditorialDecision:
    finish: bool
    reason: str
    focus: Dict[str, str] = field(default_factory=dict)   # per-agent instructions


def decide(ledger: Ledger, cfg: Dict, pass_num: int) -> EditorialDecision:
    ed = cfg.get("editorial", {})
    max_passes = int(ed.get("max_passes", 3))
    max_calls = int(ed.get("max_agent_calls", 60))
    target = int(ed.get("target_endorsed_directions", 2))
    resolve_first = bool(ed.get("resolve_objections_before_finish", True))

    directions = list(ledger.directions.values())
    endorsed = [d for d in directions if d.status == "endorsed"]
    live = [d for d in directions if d.status != "dead_end"]
    open_objs = ledger.open_objections()
    calls = models.calls()

    # ---- hard stops --------------------------------------------------- #
    if not directions:
        return EditorialDecision(True, "No candidate directions to evaluate.")
    if pass_num >= max_passes:
        return EditorialDecision(True, f"Reached max passes ({max_passes}).")
    if calls >= max_calls:
        return EditorialDecision(True, f"Reached cost ceiling ({calls}/{max_calls} model calls).")

    # ---- bar cleared -------------------------------------------------- #
    open_on_live = [o for o in open_objs if any(o.target in (d.id, *d.supporting_claims) for d in live)]
    if len(endorsed) >= target and (not resolve_first or not open_on_live):
        return EditorialDecision(True, f"{len(endorsed)} directions cleared the bar.")
    if not live:
        return EditorialDecision(True, "All directions are dead ends; nothing left to strengthen.")

    # ---- iterate with targeted focus ---------------------------------- #
    return EditorialDecision(False, _iterate_reason(endorsed, target, open_on_live),
                             focus=_build_focus(ledger))


def _iterate_reason(endorsed, target, open_on_live) -> str:
    bits = []
    if len(endorsed) < target:
        bits.append(f"only {len(endorsed)}/{target} directions endorsed")
    if open_on_live:
        bits.append(f"{len(open_on_live)} unresolved objection(s) on live directions")
    return "Iterating: " + (", ".join(bits) or "evidence below bar") + "."


def _build_focus(ledger: Ledger) -> Dict[str, str]:
    """Templated refinement instructions per agent, derived from weak spots."""
    contested, low_datafit, novelty_contested = [], [], []
    for d in ledger.directions.values():
        if d.status == "dead_end":
            continue
        objs = [o for o in (list(d.objections) +
                [o for c in d.supporting_claims if c in ledger.claims
                 for o in ledger.claims[c].critique_objections]) if not o.resolved]
        if objs:
            contested.append((d, objs))
        if (d.notes.get("datafit") or "").lower() == "low" or d.notes.get("vars_present") is False:
            low_datafit.append(d)
        if any(o.by == "red_team" for o in objs):
            novelty_contested.append(d)

    focus: Dict[str, str] = {}
    if novelty_contested:
        names = "; ".join(f"{d.title}" for d in novelty_contested[:3])
        focus["scout"] = (f"Search specifically whether these directions are already addressed by "
                          f"prior work, to settle contested novelty: {names}.")
    if low_datafit:
        names = "; ".join(f"{d.title} ({d.statement})" for d in low_datafit[:3])
        focus["data"] = (f"Test whether the variables these directions need exist and relate, "
                         f"before they can be trusted: {names}.")
    if contested:
        items = "; ".join(f"{d.title}: " + " | ".join(o.text for o in objs[:2])
                          for d, objs in contested[:3])
        focus["hypothesis"] = (f"Strengthen, sharpen, or drop directions with unresolved objections; "
                               f"consider red-team alternatives. Open objections — {items}")
        focus["methods"] = "Re-assess feasibility/datafit for contested directions against the data."
    return focus
