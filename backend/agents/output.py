import asyncio
from typing import Dict
from backend.agents.base import BaseAgent


class OutputAgent(BaseAgent):
    def __init__(self):
        super().__init__("output", "output.txt")

    async def run(self, agent_outputs: Dict[str, str], question: str, event_queue: asyncio.Queue) -> str:
        context = (
            f"Literature Agent Output:\n{agent_outputs.get('literature', 'N/A')}\n\n"
            f"Data Agent Output:\n{agent_outputs.get('data', 'N/A')}\n\n"
            f"Hypothesis Agent Output:\n{agent_outputs.get('hypothesis', 'N/A')}\n\n"
            f"Methods Agent Output:\n{agent_outputs.get('methods', 'N/A')}\n\n"
            f"Scout Agent Output:\n{agent_outputs.get('scout', 'N/A')}\n\n"
            f"Critique Agent Output:\n{agent_outputs.get('critique', 'N/A')}\n\n"
            f"Synthesis Agent Output:\n{agent_outputs.get('synthesis', 'N/A')}"
        )
        return await super().run(context, question, event_queue)
