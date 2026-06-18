"""Data execution sandbox (build spec v2 §8).

The Data Explorer agent does not *describe* analysis — it writes Python that is
executed here against the real dataset, and reads the actual output. This module
provides the execution primitive; the plan->write->run->repair loop lives in the
data agent.

Isolation (pragmatic, honest — the threat model is LLM-written analysis code on
lab data on one trusted machine):
  * runs in a subprocess (not in-process), so a crash can't take down the app;
  * a stripped environment with NO API keys (executed code can't exfiltrate the
    lab key);
  * CPU + address-space resource limits and a wall-clock timeout;
  * a light static guard that refuses obviously out-of-scope code (network,
    process spawning, filesystem deletion).
This is not a hardened jail. It does not, on its own, block all network egress.

Each executed analysis is saved as a standalone, re-runnable .py in the run's
`analyses/` folder, and its numeric outputs are captured for the
numeric-provenance gate (§11).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from typing import List, Optional

try:
    import resource  # POSIX only
except ImportError:  # pragma: no cover
    resource = None

_RESULT_MARKER = "__MARS_RESULT__"

# Out-of-scope tokens: this sandbox runs *data analysis*, not I/O or process
# control. Code containing these is rejected before execution.
_FORBIDDEN = re.compile(
    r"\b(subprocess|socket|urllib|requests|httpx|shutil\s*\.\s*rmtree|"
    r"os\s*\.\s*(system|remove|removedirs|rmdir|unlink|popen)|"
    r"__import__\s*\(|eval\s*\(|exec\s*\(|open\s*\([^)]*['\"][wa])\b"
)

_TEMPLATE = '''#!/usr/bin/env python
# MARS exploratory analysis — {aid}: {desc}
# Auto-generated and re-runnable: loads the real dataset and re-executes.
import json, warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
try:
    import scipy            # noqa: F401
    import statsmodels.api as sm   # noqa: F401
    import statsmodels.formula.api as smf  # noqa: F401
except Exception:
    pass

DATA_PATH = {data_path!r}
{loader}

def emit(summary, n=None, numbers=None, significant=None):
    """Agent code calls this once to record structured results to the ledger."""
    print({marker!r} + json.dumps({{
        "summary": str(summary),
        "n": (int(n) if n is not None else None),
        "numbers": [float(x) for x in (numbers or []) if _isnum(x)],
        "significant": (bool(significant) if significant is not None else None),
    }}))

def _isnum(x):
    try:
        float(x); return True
    except Exception:
        return False

# ===== agent analysis code =====
{code}
'''


@dataclass
class ExecResult:
    analysis_id: str
    code_path: str
    ok: bool
    stdout: str = ""
    stderr: str = ""
    error: str = ""
    summary: str = ""
    n: Optional[int] = None
    numbers: List[float] = field(default_factory=list)
    significant: Optional[bool] = None


class DataSandbox:
    def __init__(self, dataset_path: str, analyses_dir: str, timeout: int = 30,
                 mem_limit_mb: int = 1024):
        self.dataset_path = dataset_path
        self.analyses_dir = analyses_dir
        self.timeout = timeout
        self.mem_limit_mb = mem_limit_mb
        os.makedirs(analyses_dir, exist_ok=True)

    def _loader(self) -> str:
        ext = os.path.splitext(self.dataset_path)[1].lower()
        if ext in (".xlsx", ".xls"):
            return "df = pd.read_excel(DATA_PATH)"
        # Auto-detect delimiter (comma/semicolon/tab), matching mars.ingest.
        return ("try:\n"
                "    df = pd.read_csv(DATA_PATH, sep=None, engine='python')\n"
                "    if df.shape[1] == 1: df = pd.read_csv(DATA_PATH)\n"
                "except Exception:\n"
                "    df = pd.read_csv(DATA_PATH)")

    def _limits(self):  # pragma: no cover - POSIX preexec
        if resource is None:
            return None

        def _set():
            try:
                resource.setrlimit(resource.RLIMIT_CPU, (self.timeout + 5, self.timeout + 10))
            except Exception:
                pass
            try:
                soft = self.mem_limit_mb * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (soft, soft))
            except Exception:
                pass

        return _set

    def run(self, code: str, analysis_id: str, description: str = "") -> ExecResult:
        """Execute one analysis. Always writes a re-runnable .py; never raises."""
        code_path = os.path.join(self.analyses_dir, f"{analysis_id}.py")

        if _FORBIDDEN.search(code or ""):
            script = _TEMPLATE.format(aid=analysis_id, desc=description, data_path=self.dataset_path,
                                      loader=self._loader(), marker=_RESULT_MARKER,
                                      code="# REJECTED: out-of-scope operation detected.\n")
            _write(code_path, script)
            return ExecResult(analysis_id, code_path, ok=False,
                              error="Rejected: code contained out-of-scope operations "
                                    "(network/process/filesystem).")

        script = _TEMPLATE.format(aid=analysis_id, desc=description or analysis_id,
                                  data_path=self.dataset_path, loader=self._loader(),
                                  marker=_RESULT_MARKER, code=code)
        _write(code_path, script)

        env = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", ""),
               "PYTHONHASHSEED": "0", "MPLBACKEND": "Agg", "OMP_NUM_THREADS": "2"}
        try:
            proc = subprocess.run(
                [sys.executable, code_path],
                capture_output=True, text=True, timeout=self.timeout,
                cwd=self.analyses_dir, env=env, preexec_fn=self._limits(),
            )
        except subprocess.TimeoutExpired:
            return ExecResult(analysis_id, code_path, ok=False,
                              error=f"Timed out after {self.timeout}s.")
        except Exception as e:
            return ExecResult(analysis_id, code_path, ok=False, error=f"{type(e).__name__}: {e}")

        result = _parse_result(proc.stdout)
        if proc.returncode != 0 and not result:
            return ExecResult(analysis_id, code_path, ok=False, stdout=proc.stdout,
                              stderr=proc.stderr, error=_short_traceback(proc.stderr))

        if result is None:  # ran but didn't call emit(); salvage stdout
            stripped = (proc.stdout or "").strip()
            return ExecResult(analysis_id, code_path, ok=bool(stripped), stdout=proc.stdout,
                              stderr=proc.stderr,
                              summary=stripped[:800] or "(no output)",
                              numbers=_extract_numbers(proc.stdout))
        return ExecResult(
            analysis_id, code_path, ok=True, stdout=proc.stdout, stderr=proc.stderr,
            summary=result.get("summary", "")[:1500], n=result.get("n"),
            numbers=[float(x) for x in result.get("numbers", [])],
            significant=result.get("significant"),
        )


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _write(path: str, text: str) -> None:
    with open(path, "w") as f:
        f.write(text)


def _parse_result(stdout: str):
    last = None
    for line in (stdout or "").splitlines():
        if line.startswith(_RESULT_MARKER):
            try:
                last = json.loads(line[len(_RESULT_MARKER):])
            except json.JSONDecodeError:
                continue
    return last


def _extract_numbers(text: str) -> List[float]:
    out = []
    for tok in re.findall(r"-?\d+\.?\d*", text or ""):
        try:
            out.append(float(tok))
        except ValueError:
            pass
    return out[:50]


def _short_traceback(stderr: str) -> str:
    lines = [ln for ln in (stderr or "").splitlines() if ln.strip()]
    return (lines[-1] if lines else "Unknown execution error")[:300]
