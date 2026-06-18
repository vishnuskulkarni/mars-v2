"""DecompositionStrategy interface (build spec v2 §9).

Layer 2 (which specialists run, and how they are decomposed) sits behind this
interface so a `dynamic` strategy can replace the fixed `aria` one WITHOUT
touching Layers 0/1/3/4/5. The shared machinery — evidence ledger, scoring,
editorial loop, report — is identical for both, so the two can be compared
fairly on the same question and same infrastructure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import pandas as pd

from mars.data_sandbox import DataSandbox
from mars.ledger import Ledger

ProgressFn = Optional[Callable[[dict], None]]


@dataclass
class PipelineContext:
    """Layer 0 inputs + scoped resources, built once by the orchestrator."""

    question: str
    papers_text: str
    uploaded_titles: str
    literature_files: List[str]
    data_files: List[str]
    dataframe: Optional[pd.DataFrame]
    sandbox: Optional[DataSandbox]
    run_dir: str
    key_terms: List[str] = field(default_factory=list)
    scout_references: List[str] = field(default_factory=list)


class DecompositionStrategy:
    name = "base"

    def run_pass(self, ledger: Ledger, ctx: PipelineContext, cfg: Dict,
                 pass_num: int, focus: Dict[str, str], emit: ProgressFn = None) -> None:
        """Run one Layer-2 pass: dispatch specialists and write to the ledger.

        Implementations MUST NOT compute confidence/scores or decide iteration —
        that is the orchestrator's shared Layer 3/4 responsibility.
        """
        raise NotImplementedError
