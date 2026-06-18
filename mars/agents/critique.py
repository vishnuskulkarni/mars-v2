from __future__ import annotations

from mars.agents.base import StructuredAgent


class CritiqueAgent(StructuredAgent):
    name = "critique"
    prompt_file = "critique.txt"

    def run(self, question: str, directions_block: str, analyses_block: str,
            claims_block: str, focus: str = "") -> dict:
        """Return {direction_objections:[...], claim_objections:[...]} — the gate."""
        user = (f"Research question: {question}\n\n"
                f"Candidate directions (with supporting claim ids):\n{directions_block}\n\n"
                f"Executed analyses:\n{analyses_block}\n\n"
                f"Literature/scout claims:\n{claims_block}")
        if focus:
            user += f"\n\nEditorial focus for this pass: {focus}"
        out = self.ask(user)
        out.setdefault("direction_objections", [])
        out.setdefault("claim_objections", [])
        return out
