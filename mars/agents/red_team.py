from __future__ import annotations

from mars.agents.base import StructuredAgent


class RedTeamAgent(StructuredAgent):
    name = "red_team"
    prompt_file = "red_team.txt"

    def run(self, question: str, top_directions_block: str, scout_block: str,
            analyses_block: str, focus: str = "") -> dict:
        """Return {objections:[...], contradictions:[...], alternatives:[...]}."""
        user = (f"Research question: {question}\n\n"
                f"Top-ranked direction(s) to attack:\n{top_directions_block}\n\n"
                f"Scout external references:\n{scout_block}\n\n"
                f"Executed analyses:\n{analyses_block}")
        if focus:
            user += f"\n\nEditorial focus for this pass: {focus}"
        out = self.ask(user)
        out.setdefault("objections", [])
        out.setdefault("contradictions", [])
        out.setdefault("alternatives", [])
        return out
