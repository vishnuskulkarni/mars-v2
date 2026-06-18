from __future__ import annotations

from typing import Dict, List

from mars import ingest, jsonutil
from mars.agents.base import StructuredAgent
from mars.data_sandbox import DataSandbox

_REPAIR_SYSTEM = (
    "You fix a single Python data-analysis snippet that failed to run against a "
    "preloaded pandas DataFrame named `df`. Keep it exploratory. It must call "
    "emit(summary=..., n=..., numbers=[...], significant=...) exactly once and use "
    "only real columns. Return ONLY {\"code\": \"<fixed python>\"}."
)


class DataAgent(StructuredAgent):
    name = "data"
    prompt_file = "data.txt"

    def run(self, question: str, df, sandbox: DataSandbox, gaps_text: str = "",
            focus: str = "", max_analyses: int = 8, max_repair: int = 1) -> dict:
        """Plan exploratory analyses, EXECUTE each, repair-once on error, log all.

        Returns {analyses:[...], schema:str}. Every attempted spec is recorded —
        significant, null, or errored — which is the anti-p-hacking trail.
        """
        schema = ingest.schema_brief(df)
        user = (f"Research question: {question}\n\nDataset schema:\n{schema}\n\n"
                f"Literature gaps (for targeting):\n{gaps_text or '(none yet)'}")
        if focus:
            user += f"\n\nEditorial focus for this pass: {focus}"
        plan: List[Dict] = self.ask(user).get("analyses", []) or []

        results: List[Dict] = []
        for i, spec in enumerate(plan[:max_analyses]):
            kind = (spec.get("kind") or "analysis").strip().replace(" ", "_")
            desc = spec.get("description", "")
            code = spec.get("code", "")
            aid = f"exploratory_{kind}_{i + 1:02d}"
            res = sandbox.run(code, aid, desc)

            attempts = 0
            while (not res.ok) and res.error and attempts < max_repair:
                fixed = self._repair(schema, desc, code, res.error)
                if not fixed:
                    break
                code, attempts = fixed, attempts + 1
                res = sandbox.run(code, aid, desc)

            results.append({
                "id": aid, "kind": kind, "description": desc, "code_path": res.code_path,
                "ok": res.ok, "n": res.n, "summary": res.summary, "numbers": res.numbers,
                "significant": res.significant, "error": res.error,
            })
        return {"analyses": results, "schema": schema}

    def _repair(self, schema: str, desc: str, code: str, error: str) -> str:
        user = (f"Dataset schema:\n{schema}\n\nAnalysis goal: {desc}\n\n"
                f"Failing code:\n{code}\n\nError:\n{error}\n\nReturn fixed code as JSON.")
        return jsonutil.call_json(self.name, _REPAIR_SYSTEM, user).get("code", "")
