import asyncio
from backend.agents.base import BaseAgent


class LiteratureAgent(BaseAgent):
    def __init__(self):
        super().__init__("literature", "literature.txt")

    async def run(self, literature_text: str, question: str, event_queue: asyncio.Queue) -> str:
        context = f"Literature provided:\n\n{literature_text}"
        return await super().run(context, question, event_queue)
