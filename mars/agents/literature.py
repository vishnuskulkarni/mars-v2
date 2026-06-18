from __future__ import annotations

from mars.agents.base import StructuredAgent


class LiteratureAgent(StructuredAgent):
    name = "literature"
    prompt_file = "literature.txt"

    def run(self, question: str, papers_text: str, focus: str = "") -> dict:
        """Return {claims:[...], gaps:[...], key_terms:[...]} grounded in papers."""
        user = f"Research question: {question}\n\n"
        if focus:
            user += f"Editorial focus for this pass: {focus}\n\n"
        user += f"Uploaded papers:\n\n{papers_text}"
        out = self.ask(user)
        out.setdefault("claims", [])
        out.setdefault("gaps", [])
        out.setdefault("key_terms", [])
        return out
