"""Live end-to-end run against the real Anthropic API (uses the key in .env).
Uses the student-performance sample (one review paper + the math CSV).
Run:  python tests/live_run.py
"""

import os
import shutil
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mars import orchestrator  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, "data", "301d0885-890f-4857-8783-6cb07006fa85")
QUESTION = ("Which student-level factors most affect final academic performance (G3), "
            "and which research directions are most worth pursuing with this dataset?")

run_id = datetime.now().strftime("%Y-%m-%d_%H%M") + "_TEST"
run_dir = os.path.join(REPO, "runs", run_id)
inputs = os.path.join(run_dir, "inputs")
os.makedirs(inputs, exist_ok=True)

pdf = "FactorsAffectingStudentsAcademicPerformanceAreview.pdf"
csv = "student-mat.csv"
shutil.copy(os.path.join(SRC, pdf), os.path.join(inputs, pdf))
shutil.copy(os.path.join(SRC, csv), os.path.join(inputs, csv))
open(os.path.join(run_dir, "question.txt"), "w").write(QUESTION)
lit_paths = [os.path.join(inputs, pdf)]
data_paths = [os.path.join(inputs, csv)]


def prog(ev):
    t = ev.get("type")
    if t == "phase":
        print("PHASE:", ev["phase"], flush=True)
    elif t == "agent":
        print(f"   agent {ev['agent']}: {ev['status']}", flush=True)
    elif t == "decision":
        print(f"DECISION pass {ev.get('pass_num')}: "
              f"{'FINISH' if ev['finish'] else 'ITERATE'} — {ev['reason']}", flush=True)
    elif t == "info":
        print("INFO:", ev.get("message"), flush=True)
    elif t == "error":
        print("ERROR:", ev.get("message"), flush=True)


print(f"RUN {run_id} starting (live API)…", flush=True)
res = orchestrator.run(QUESTION, lit_paths, data_paths, run_dir, initials="TEST",
                       preset="Balanced", strategy_name="aria", progress=prog)

L = res.ledger
ds = list(L.directions.values()) if L else []
by = {}
for d in ds:
    by[d.status] = by.get(d.status, 0) + 1
print("\n===== RESULT =====", flush=True)
print("error:", res.error)
print(f"duration: {res.duration_seconds}s · passes: {res.passes} · model_calls: {res.model_calls}")
print(f"claims: {len(L.claims)} · directions: {len(ds)} · analyses: {len(L.analyses)}")
print("directions_by_status:", by)
print("\nDIRECTIONS:")
for d in sorted(ds, key=lambda d: d.score, reverse=True):
    print(f"  [{d.status:9}] {d.confidence_tier:6} score={d.score:.2f}  {d.title}")
print("\nEXECUTED ANALYSES:")
for a in L.analyses.values():
    st = "ERROR" if a.error else ("sig" if a.significant else "null/NA")
    print(f"  {a.id} ({a.kind}, n={a.n}, {st}): {(a.result_summary or a.error)[:90]}")
print("\nGATES:")
for g in res.gate_results:
    print(f"  {'PASS' if g.passed else 'FLAG'} {g.name}: {g.detail}")
print("\nARTIFACTS in", run_dir, ":", sorted(os.listdir(run_dir)))
print("LIVE RUN COMPLETE", flush=True)
