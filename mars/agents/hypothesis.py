from __future__ import annotations

from mars.agents.base import StructuredAgent


class HypothesisAgent(StructuredAgent):
    name = "hypothesis"
    prompt_file = "hypothesis.txt"

    def run(self, question: str, gaps_block: str, claims_block: str,
            signals_block: str, focus: str = "") -> dict:
        """Return {directions:[{title, statement, supporting_claims, rationale}]}."""
        user = (f"Research question: {question}\n\n"
                f"Literature gaps (ledger):\n{gaps_block}\n\n"
                f"Available claims (ledger, cite these ids):\n{claims_block}\n\n"
                f"Data signals/affordances (executed):\n{signals_block}")
        if focus:
            user += f"\n\nEditorial focus for this pass: {focus}"
        out = self.ask(user)
        out.setdefault("directions", [])
        return out
