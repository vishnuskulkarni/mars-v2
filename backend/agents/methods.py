import asyncio
from backend.agents.base import BaseAgent


class MethodsAgent(BaseAgent):
    def __init__(self):
        super().__init__("methods", "methods.txt")

    async def run(self, data_summary: str, question: str, event_queue: asyncio.Queue) -> str:
        context = f"Dataset summary:\n\n{data_summary}"
        return await super().run(context, question, event_queue)
