"""Structured agent base (build spec v2).

Agents return parsed JSON (claim records / directions / objections), not prose.
The ARIA strategy applies those structures to the evidence ledger, so agents
stay pure and testable. Inference is routed through mars.models via jsonutil.
"""

from __future__ import annotations

from pathlib import Path

from mars import jsonutil

_PROMPTS = Path(__file__).resolve().parent.parent / "prompts"


class StructuredAgent:
    name: str = "agent"
    prompt_file: str = ""

    def __init__(self):
        self.system = (_PROMPTS / self.prompt_file).read_text() if self.prompt_file else ""

    def ask(self, user: str) -> dict:
        """One json-mode call returning a parsed dict ({} on failure)."""
        return jsonutil.call_json(self.name, self.system, user)
