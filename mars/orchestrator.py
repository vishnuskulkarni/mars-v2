"""Orchestrator — Layers 0/1/3/4/5 (build spec v2 §2).

Holds the central loop: a DecompositionStrategy runs a Layer-2 pass (writing the
shared evidence ledger); the orchestrator then recomputes confidence, scores +
classifies directions (Layer 3), and asks the editorial controller whether to
iterate or finish (Layer 4). On finish it runs the deterministic gates and
assembles the report (Layer 5), persisting report.md/.pdf, ledger.json,
analyses/, and manifest.json into the run folder.

Layers 0/1/3/4/5 are identical regardless of which strategy decomposes Layer 2,
so ARIA and the dynamic arm can be compared on the same machinery.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, List, Optional

from mars import editorial, gates, ingest, models, report, scoring, strategies
from mars.data_sandbox import DataSandbox
from mars.ledger import Ledger
from mars.strategies.base import PipelineContext

AGENT_ORDER = ["literature", "scout", "data", "hypothesis", "methods", "critique", "red_team", "checks"]
ProgressFn = Optional[Callable[[dict], None]]


@dataclass
class RunResult:
    run_id: str
    run_dir: str
    question: str
    initials: str
    preset: str
    strategy: str
    started_at: str
    finished_at: str = ""
    duration_seconds: float = 0.0
    passes: int = 0
    model_calls: int = 0
    ledger: Optional[Ledger] = None
    weights: Dict[str, float] = field(default_factory=dict)
    gate_results: List = field(default_factory=list)
    decision_log: List[Dict] = field(default_factory=list)
    report_markdown: str = ""
    report_md_path: str = ""
    report_pdf_path: Optional[str] = None
    manifest: Dict = field(default_factory=dict)
    had_errors: bool = False
    error: Optional[str] = None


def _emit(progress: ProgressFn, **event) -> None:
    if progress:
        try:
            progress(event)
        except Exception:
            pass


def run(question: str, literature_files: List[str], data_files: List[str], run_dir: str,
        initials: str = "", preset: str = "Balanced", strategy_name: str = "aria",
        progress: ProgressFn = None) -> RunResult:
    run_id = os.path.basename(run_dir.rstrip("/"))
    cfg = models.get_config()
    models.reset_calls()
    t0 = time.perf_counter()
    result = RunResult(run_id=run_id, run_dir=run_dir, question=question, initials=initials,
                       preset=preset, strategy=strategy_name,
                       started_at=datetime.now().isoformat(timespec="seconds"))

    try:
        # ---- Layer 0: ingest + scoped resources -------------------------- #
        _emit(progress, type="phase", phase="Reading inputs")
        papers_text = ingest.parse_all_pdfs(literature_files)
        df = ingest.load_first_dataframe(data_files)
        uploaded_titles = [_title(p) for p in literature_files]
        sandbox = None
        if df is not None and data_files:
            ds_path = next((p for p in data_files if ingest.load_dataframe(p) is not None), data_files[0])
            sandbox = DataSandbox(ds_path, os.path.join(run_dir, "analyses"),
                                  timeout=int(cfg.get("data_sandbox", {}).get("exec_timeout_seconds", 30)))

        ctx = PipelineContext(
            question=question, papers_text=papers_text,
            uploaded_titles="\n".join(uploaded_titles) or "No papers uploaded.",
            literature_files=literature_files, data_files=data_files,
            dataframe=df, sandbox=sandbox, run_dir=run_dir,
        )

        # ---- Layer 1: strategy + ledger --------------------------------- #
        strategy = strategies.get_strategy(strategy_name)
        ledger = Ledger(cfg)
        result.ledger = ledger
        weights = scoring.resolve_weights(cfg, preset)
        result.weights = weights

        # ---- The loop (Layers 2 -> 3 -> 4) ------------------------------ #
        max_passes = int(cfg.get("editorial", {}).get("max_passes", 3))
        decision = None
        pass_num = 0
        while pass_num < max_passes + 1:
            pass_num += 1
            focus = decision.focus if decision else {}
            label = "gathering evidence" if pass_num == 1 else "refining (editorial loop)"
            _emit(progress, type="phase", phase=f"Pass {pass_num} — {label}")

            strategy.run_pass(ledger, ctx, cfg, pass_num, focus, progress)

            # Layer 3 — evidence & conflict
            ledger.recompute_confidence()
            if pass_num > 1 and hasattr(strategy, "resolve_with_evidence"):
                n = strategy.resolve_with_evidence(ledger, cfg)
                if n:
                    _emit(progress, type="info", message=f"Resolved {n} objection(s) with new evidence")
            scoring.score_directions(ledger, weights)
            scoring.classify_directions(ledger, cfg)

            # Layer 4 — editorial
            decision = editorial.decide(ledger, cfg, pass_num)
            result.decision_log.append({"pass": pass_num, "finish": decision.finish,
                                        "reason": decision.reason, "focus": list(decision.focus)})
            _emit(progress, type="decision", finish=decision.finish, reason=decision.reason,
                  pass_num=pass_num)
            if decision.finish:
                break

        result.passes = pass_num
        result.model_calls = models.calls()

        # ---- Layer 5: gates + report + artifacts ------------------------ #
        _emit(progress, type="phase", phase="Validating + assembling report")
        result.gate_results = gates.run_all(
            ledger, source_text=papers_text, uploaded_titles=uploaded_titles,
            scout_references=ctx.scout_references)

        meta = {"question": question, "initials": initials, "run_id": run_id,
                "timestamp": result.started_at, "strategy": strategy_name, "preset": preset,
                "weights": weights, "passes": result.passes, "model_calls": result.model_calls,
                "gate_results": result.gate_results, "decision_log": result.decision_log}
        result.report_markdown = report.assemble_markdown(ledger, meta)
        _persist(result, ledger, cfg)

    except Exception as e:
        result.error = f"{type(e).__name__}: {e}"
        result.had_errors = True
        _emit(progress, type="error", message=result.error)
        try:
            _persist(result, result.ledger, cfg) if result.ledger else None
        except Exception:
            pass

    result.duration_seconds = round(time.perf_counter() - t0, 2)
    result.finished_at = datetime.now().isoformat(timespec="seconds")
    _write_manifest(result, cfg)
    _emit(progress, type="done", had_errors=result.had_errors, error=result.error)
    return result


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #
def _persist(result: RunResult, ledger: Ledger, cfg: Dict) -> None:
    os.makedirs(result.run_dir, exist_ok=True)
    result.report_md_path = os.path.join(result.run_dir, "report.md")
    with open(result.report_md_path, "w") as f:
        f.write(result.report_markdown)
    with open(os.path.join(result.run_dir, "ledger.json"), "w") as f:
        json.dump(ledger.to_dict(), f, indent=2, default=str)
    pdf_path = os.path.join(result.run_dir, "report.pdf")
    if report.markdown_to_pdf(result.report_markdown, pdf_path):
        result.report_pdf_path = pdf_path


def _write_manifest(result: RunResult, cfg: Dict) -> None:
    ledger = result.ledger
    directions = list(ledger.directions.values()) if ledger else []
    status_counts = {}
    for d in directions:
        status_counts[d.status] = status_counts.get(d.status, 0) + 1

    try:
        routing = {n: {"provider": r.provider, "model": r.model}
                   for n, r in models.describe_routing().items()}
    except Exception:
        routing = {}

    gate_summary = [g.to_dict() for g in result.gate_results]
    analyses = []
    if ledger:
        for a in ledger.analyses.values():
            analyses.append({"id": a.id, "kind": a.kind, "n": a.n,
                             "significant": a.significant, "error": bool(a.error),
                             "code": f"analyses/{os.path.basename(a.code_path)}" if a.code_path else None})

    manifest = {
        "schema_version": 2,
        "tool": {"name": "MARS internal research tool", "package": "mars", "version": "2.0.0"},
        "run_id": result.run_id,
        "timestamp": result.started_at,
        "finished_at": result.finished_at,
        "initials": result.initials,
        "research_question": result.question,
        "strategy": result.strategy,
        "scoring_preset": result.preset,
        "scoring_weights": result.weights,
        "passes": result.passes,
        "model_calls": result.model_calls,
        "duration_seconds": result.duration_seconds,
        "default_provider": cfg.get("default_provider", "anthropic"),
        "model_routing": routing,
        "inputs": {
            "literature": [os.path.basename(p) for p in _inputs(result, {".pdf"})],
            "data": [os.path.basename(p) for p in _inputs(result, {".csv", ".xlsx", ".xls"})],
        },
        "ledger": {
            "file": "ledger.json",
            "claims": len(ledger.claims) if ledger else 0,
            "directions": len(directions),
            "analyses": len(ledger.analyses) if ledger else 0,
        },
        "directions_by_status": status_counts,
        "endorsed_vs_candidates": f"{status_counts.get('endorsed', 0)}/{len(directions)}",
        "analyses": analyses,
        "gates": gate_summary,
        "editorial_loop": result.decision_log,
        "report": {
            "markdown": os.path.basename(result.report_md_path) if result.report_md_path else None,
            "pdf": os.path.basename(result.report_pdf_path) if result.report_pdf_path else None,
        },
        "had_errors": result.had_errors,
        "error": result.error,
    }
    result.manifest = manifest
    try:
        with open(os.path.join(result.run_dir, "manifest.json"), "w") as f:
            json.dump(manifest, f, indent=2, default=str)
    except Exception:
        pass


def _title(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0].replace("_", " ").replace("-", " ")


def _inputs(result: RunResult, exts: set) -> List[str]:
    d = os.path.join(result.run_dir, "inputs")
    if not os.path.isdir(d):
        return []
    return [os.path.join(d, f) for f in sorted(os.listdir(d)) if os.path.splitext(f)[1].lower() in exts]
