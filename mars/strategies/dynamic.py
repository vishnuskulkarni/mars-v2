"""Dynamic decomposition strategy — STUB / comparison arm (build spec v2 §9).

The intended dynamic strategy lets an orchestrator agent decide which
specialists to spawn per question (the "Conor's branch" experiment), rather than
running the fixed ARIA set. It is deliberately a stub here: the point of the
`DecompositionStrategy` interface is that this can be filled in later WITHOUT
touching Layers 0/1/3/4/5 (ingest, ledger, scoring, editorial, report).

To keep the system runnable and the comparison harness honest, this stub
currently delegates Layer-2 execution to the ARIA decomposition. Replacing the
body of `run_pass` with an LLM planner that selects a subset of agents is the
only change required to make the dynamic arm real.
"""

from __future__ import annotations

from typing import Dict

from mars.ledger import Ledger
from mars.strategies.aria import ARIAStrategy
from mars.strategies.base import DecompositionStrategy, PipelineContext, ProgressFn


class DynamicStrategy(DecompositionStrategy):
    name = "dynamic"

    def __init__(self):
        # Reuse ARIA's agent-execution + ledger-wiring until a planner is added.
        self._impl = ARIAStrategy()

    def run_pass(self, ledger: Ledger, ctx: PipelineContext, cfg: Dict,
                 pass_num: int, focus: Dict[str, str], emit: ProgressFn = None) -> None:
        # TODO(dynamic): replace with an orchestrator-LLM that plans which agents
        # to spawn for this question, then writes their outputs to the ledger.
        self._impl.run_pass(ledger, ctx, cfg, pass_num, focus, emit)

    def resolve_with_evidence(self, ledger: Ledger, cfg: Dict) -> int:
        return self._impl.resolve_with_evidence(ledger, cfg)
