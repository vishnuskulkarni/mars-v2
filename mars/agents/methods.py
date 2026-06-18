from __future__ import annotations

from mars.agents.base import StructuredAgent


class MethodsAgent(StructuredAgent):
    name = "methods"
    prompt_file = "methods.txt"

    def run(self, question: str, directions_block: str, schema: str,
            analyses_block: str, focus: str = "") -> dict:
        """Return {assessments:[{direction_id, feasibility, datafit, ...}]}."""
        user = (f"Research question: {question}\n\n"
                f"Candidate directions:\n{directions_block}\n\n"
                f"Dataset schema:\n{schema}\n\n"
                f"Executed analyses:\n{analyses_block}")
        if focus:
            user += f"\n\nEditorial focus for this pass: {focus}"
        out = self.ask(user)
        out.setdefault("assessments", [])
        return out
