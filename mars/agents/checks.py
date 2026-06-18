from __future__ import annotations

from mars.agents.base import StructuredAgent


class ChecksAgent(StructuredAgent):
    name = "checks"
    prompt_file = "checks.txt"

    def run(self, question: str, directions_block: str) -> dict:
        """Null-interesting + so-what gate. Return {checks:[{direction_id, ...}]}."""
        user = (f"Research question: {question}\n\n"
                f"Directions to check:\n{directions_block}")
        out = self.ask(user)
        out.setdefault("checks", [])
        return out
