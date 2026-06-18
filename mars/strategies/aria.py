"""ARIA — the fixed, typed agent set (build spec v2 §4, §9). Default strategy.

One pass:
  Layer 2 parallel block : literature, scout, data-explorer (independent)
  then sequential         : hypothesis -> methods -> critique(gate) -> red-team -> checks
All outputs are written to the shared evidence ledger as claim/direction/objection
records. On refinement passes (pass>1) the agents named in the editorial `focus`
re-run with that focus and add new evidence; objections answered by that new
evidence are then resolved (see resolve_with_evidence).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List

from mars.agents import (ChecksAgent, CritiqueAgent, DataAgent, HypothesisAgent,
                         LiteratureAgent, MethodsAgent, RedTeamAgent, ScoutAgent)
from mars.ledger import Grounding, Ledger, Objection
from mars.strategies.base import DecompositionStrategy, PipelineContext, ProgressFn

_NOVELTY_WORDS = ("already", "prior work", "novel", "been done", "existing", "duplicat", "replicat")


def _g(items) -> List[Grounding]:
    out = []
    for x in items or []:
        if isinstance(x, dict) and x.get("ref"):
            out.append(Grounding(type=x.get("type", "paper"), ref=str(x["ref"]), loc=str(x.get("loc", ""))))
    return out


def _norm_title(t: str) -> str:
    return " ".join((t or "").lower().split())


class ARIAStrategy(DecompositionStrategy):
    name = "aria"

    # ------------------------------------------------------------------ #
    def run_pass(self, ledger: Ledger, ctx: PipelineContext, cfg: Dict,
                 pass_num: int, focus: Dict[str, str], emit: ProgressFn = None) -> None:
        first = pass_num == 1

        # ---- Layer 2 parallel block: literature, scout, data ---------- #
        scout = ScoutAgent()
        tasks = {}
        if first or "literature" in focus:
            tasks["literature"] = lambda: LiteratureAgent().run(
                ctx.question, ctx.papers_text, focus.get("literature", ""))
        if first or "scout" in focus:
            tasks["scout"] = lambda: scout.run(
                ctx.question, ctx.key_terms, ctx.uploaded_titles, focus.get("scout", ""))
        if (first or "data" in focus) and ctx.dataframe is not None and ctx.sandbox is not None:
            ds = cfg.get("data_sandbox", {})
            tasks["data"] = lambda: DataAgent().run(
                ctx.question, ctx.dataframe, ctx.sandbox, gaps_text=self._gaps_block(ledger),
                focus=focus.get("data", ""), max_analyses=int(ds.get("max_analyses_per_pass", 8)),
                max_repair=int(ds.get("max_plan_iterations", 2)) - 1)

        results: Dict[str, dict] = {}
        if tasks:
            for name in tasks:
                _emit(emit, name, "running")
            with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
                futs = {name: pool.submit(fn) for name, fn in tasks.items()}
                for name, fut in futs.items():
                    try:
                        results[name] = fut.result()
                    except Exception as e:
                        results[name] = {"_error": str(e)}
                    _emit(emit, name, "complete")

        if "literature" in results:
            self._apply_literature(ledger, ctx, results["literature"])
        if "scout" in results:
            self._apply_scout(ledger, ctx, scout, results["scout"])
        if "data" in results:
            self._apply_data(ledger, results["data"])

        # ---- Hypothesis -> directions --------------------------------- #
        if first or "hypothesis" in focus:
            _emit(emit, "hypothesis", "running")
            hyp = HypothesisAgent().run(
                ctx.question, self._gaps_block(ledger), self._claims_block(ledger),
                self._signals_block(ledger), focus.get("hypothesis", ""))
            self._apply_directions(ledger, hyp.get("directions", []), "hypothesis")
            _emit(emit, "hypothesis", "complete")

        if not ledger.directions:
            return  # nothing to assess this pass

        # ---- Methods -------------------------------------------------- #
        _emit(emit, "methods", "running")
        schema = results.get("data", {}).get("schema", "") or "(no dataset)"
        methods = MethodsAgent().run(ctx.question, self._directions_block(ledger), schema,
                                     self._analyses_block(ledger), focus.get("methods", ""))
        self._apply_methods(ledger, methods.get("assessments", []))
        _emit(emit, "methods", "complete")

        # ---- Critique (gate) ------------------------------------------ #
        _emit(emit, "critique", "running")
        crit = CritiqueAgent().run(ctx.question, self._directions_block(ledger),
                                   self._analyses_block(ledger), self._claims_block(ledger))
        self._apply_critique(ledger, crit)
        _emit(emit, "critique", "complete")

        # ---- Red-team (targets top directions) ------------------------ #
        _emit(emit, "red_team", "running")
        rt = RedTeamAgent().run(ctx.question, self._top_directions_block(ledger),
                                self._scout_block(ledger), self._analyses_block(ledger))
        self._apply_red_team(ledger, rt)
        _emit(emit, "red_team", "complete")

        # ---- Checks (null / so-what gate) ----------------------------- #
        _emit(emit, "checks", "running")
        chk = ChecksAgent().run(ctx.question, self._directions_block(ledger))
        self._apply_checks(ledger, chk.get("checks", []))
        _emit(emit, "checks", "complete")

    # ------------------------------------------------------------------ #
    # Objection resolution (called by orchestrator on pass>1)
    # ------------------------------------------------------------------ #
    def resolve_with_evidence(self, ledger: Ledger, cfg: Dict) -> int:
        """Resolve non-novelty objections on directions now supported by data
        evidence (datafit confirmed, not contradicted). Returns count resolved."""
        resolved = 0
        for d in ledger.directions.values():
            if d.status == "dead_end":
                continue
            support = [ledger.claims[c] for c in d.supporting_claims if c in ledger.claims]
            datafit_ok = (d.notes.get("datafit") or "").lower() == "high" and d.notes.get("vars_present") is True
            contradicted = any(c.contradicted_by for c in support)
            if not (datafit_ok and not contradicted):
                continue
            for o in d.objections:
                if not o.resolved and not _is_novelty(o.text):
                    o.resolved = True
                    o.resolution = "Resolved: data/methods evidence now confirms the required relationship (by editorial)."
                    resolved += 1
        if resolved:
            ledger.recompute_confidence()
        return resolved

    # ------------------------------------------------------------------ #
    # Apply helpers
    # ------------------------------------------------------------------ #
    def _apply_literature(self, ledger, ctx, out):
        for c in out.get("claims", []):
            if c.get("text"):
                ledger.add_claim(c["text"], "literature", grounded_in=_g(c.get("grounded_in")))
        for gp in out.get("gaps", []):
            if gp.get("text"):
                ledger.add_claim(gp["text"], "literature", grounded_in=_g(gp.get("grounded_in")), labels=["gap"])
        if out.get("key_terms"):
            ctx.key_terms = list(dict.fromkeys((ctx.key_terms or []) + out["key_terms"]))[:8]

    def _apply_scout(self, ledger, ctx, scout, out):
        for r in out.get("external_refs", []):
            if r.get("text"):
                ledger.add_claim(r["text"], "scout", grounded_in=_g(r.get("grounded_in")), labels=["external"])
        for nc in out.get("novelty_challenges", []):
            if nc.get("text"):
                ledger.add_claim(nc["text"], "scout", grounded_in=_g(nc.get("grounded_in")),
                                 labels=["novelty_challenge"])
        ctx.scout_references = scout.references()

    def _apply_data(self, ledger, out):
        for a in out.get("analyses", []):
            labels = ["exploratory"]
            if a.get("significant") is False:
                labels.append("null")
            if a.get("error"):
                labels.append("error")
            ledger.add_analysis(a.get("kind", "analysis"), a.get("description", ""), id=a.get("id"),
                                code_path=a.get("code_path", ""), n=a.get("n"),
                                result_summary=a.get("summary", ""), numbers=a.get("numbers", []),
                                significant=a.get("significant"), error=a.get("error", ""), labels=labels)
            if a.get("ok") and (a.get("summary") or a.get("description")):
                sig_label = "signal" if a.get("significant") else "null"
                ledger.add_claim(a.get("summary") or a.get("description"), "data",
                                 grounded_in=[Grounding("data", a["id"])],
                                 labels=["exploratory", sig_label])

    def _apply_directions(self, ledger, directions, raised_by):
        existing = {_norm_title(d.title) for d in ledger.directions.values()}
        for d in directions:
            title = d.get("title") or d.get("statement", "")[:60]
            if not title or _norm_title(title) in existing:
                continue
            existing.add(_norm_title(title))
            ledger.add_direction(title, d.get("statement", title), raised_by,
                                 supporting_claims=d.get("supporting_claims", []),
                                 notes={"rationale": d.get("rationale", "")})

    def _apply_methods(self, ledger, assessments):
        for a in assessments:
            d = ledger.directions.get(a.get("direction_id", ""))
            if not d:
                continue
            d.notes.update({
                "feasibility": (a.get("feasibility") or "").lower(),
                "datafit": (a.get("datafit") or "").lower(),
                "vars_present": a.get("vars_present"),
                "design_sketch": a.get("design_sketch", ""),
                "required_vars": ", ".join(a.get("required_vars", []) or []),
                "methods_notes": a.get("notes", ""),
            })
            for cid in a.get("corroborates", []) or []:
                ledger.corroborate(cid, "methods")

    def _apply_critique(self, ledger, out):
        for o in out.get("direction_objections", []):
            if o.get("direction_id") and o.get("text"):
                ledger.object_to_direction(o["direction_id"],
                                           Objection("critique", o["text"], o.get("severity", "medium")))
        for o in out.get("claim_objections", []):
            if o.get("claim_id") and o.get("text"):
                ledger.object_to_claim(o["claim_id"],
                                       Objection("critique", o["text"], o.get("severity", "medium")))

    def _apply_red_team(self, ledger, out):
        for o in out.get("objections", []):
            if o.get("direction_id") and o.get("text"):
                ledger.object_to_direction(o["direction_id"],
                                           Objection("red_team", o["text"], o.get("severity", "high")))
        for c in out.get("contradictions", []):
            cid = c.get("claim_id")
            if cid and cid in ledger.claims:
                ledger.contradict(cid, "red_team")
                if c.get("text"):
                    ledger.object_to_claim(cid, Objection("red_team", c["text"], "high"))
        self._apply_directions(ledger, out.get("alternatives", []), "red_team")

    def _apply_checks(self, ledger, checks):
        for c in checks:
            d = ledger.directions.get(c.get("direction_id", ""))
            if not d:
                continue
            d.notes.update({
                "null_interesting": c.get("null_interesting"),
                "null_reason": c.get("null_reason", ""),
                "so_what": c.get("so_what"),
                "so_what_reason": c.get("so_what_reason", ""),
            })

    # ------------------------------------------------------------------ #
    # Ledger -> prompt formatters
    # ------------------------------------------------------------------ #
    def _gaps_block(self, ledger):
        gaps = [c for c in ledger.claims.values() if "gap" in c.labels]
        return "\n".join(f"- {c.id}: {c.text}" for c in gaps) or "(no gaps yet)"

    def _claims_block(self, ledger):
        cs = [c for c in ledger.claims.values() if "gap" not in c.labels]
        return "\n".join(
            f"- {c.id} [{c.raised_by}]: {c.text}"
            + (f" (src: {', '.join(g.ref for g in c.grounded_in)})" if c.grounded_in else "")
            for c in cs) or "(no claims yet)"

    def _signals_block(self, ledger):
        sigs = [c for c in ledger.claims.values()
                if c.raised_by == "data" or "external" in c.labels]
        return "\n".join(f"- {c.id} [{c.raised_by}]: {c.text}" for c in sigs) or "(no data signals yet)"

    def _analyses_block(self, ledger):
        out = []
        for a in ledger.analyses.values():
            status = "ERROR" if a.error else ("sig" if a.significant else "null/NA")
            out.append(f"- {a.id} ({a.kind}, n={a.n}, {status}): {a.result_summary or a.error}")
        return "\n".join(out) or "(no analyses run)"

    def _directions_block(self, ledger):
        out = []
        for d in ledger.directions.values():
            sc = ", ".join(d.supporting_claims) or "none"
            out.append(f"- {d.id}: {d.title} — {d.statement} [supporting: {sc}]")
        return "\n".join(out) or "(no directions yet)"

    def _top_directions_block(self, ledger):
        ranked = sorted(ledger.directions.values(),
                        key=lambda d: (d.score, len(d.supporting_claims)), reverse=True)[:3]
        out = []
        for d in ranked:
            out.append(f"- {d.id}: {d.title} — {d.statement} "
                       f"[supporting: {', '.join(d.supporting_claims) or 'none'}]")
        return "\n".join(out) or "(no directions yet)"

    def _scout_block(self, ledger):
        refs = [c for c in ledger.claims.values() if "external" in c.labels or "novelty_challenge" in c.labels]
        return "\n".join(
            f"- {c.id} [{', '.join(c.labels)}]: {c.text}"
            + (f" ({', '.join(g.ref for g in c.grounded_in)})" if c.grounded_in else "")
            for c in refs) or "(no external references)"


def _emit(emit: ProgressFn, agent: str, status: str) -> None:
    if emit:
        try:
            emit({"type": "agent", "agent": agent, "status": status})
        except Exception:
            pass


def _is_novelty(text: str) -> bool:
    low = (text or "").lower()
    return any(w in low for w in _NOVELTY_WORDS)
