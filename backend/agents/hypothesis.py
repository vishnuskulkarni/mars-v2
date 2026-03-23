import asyncio
from backend.agents.base import BaseAgent


class HypothesisAgent(BaseAgent):
    def __init__(self):
        super().__init__("hypothesis", "hypothesis.txt")

    async def run(self, literature_text: str, question: str, event_queue: asyncio.Queue) -> str:
        context = f"Available evidence from literature:\n\n{literature_text}"
        return await super().run(context, question, event_queue)
