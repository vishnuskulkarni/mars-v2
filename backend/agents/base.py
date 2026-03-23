import os
import asyncio
from anthropic import AsyncAnthropic
from backend.config import get_settings
from backend.models import AgentEvent


class BaseAgent:
    def __init__(self, name: str, prompt_file: str):
        self.name = name
        self.system_prompt = self._load_prompt(prompt_file)
        settings = get_settings()
        self.client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.model = settings.CLAUDE_MODEL

    def _load_prompt(self, prompt_file: str) -> str:
        prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", prompt_file)
        with open(prompt_path, "r") as f:
            return f.read()

    async def run(self, context: str, question: str, event_queue: asyncio.Queue) -> str:
        """Run the agent with streaming. Pushes chunk events to the queue. Returns full output."""
        # Signal agent is running
        await event_queue.put(AgentEvent(
            agent=self.name, type="status", content="running", progress=0
        ))

        full_output = ""
        try:
            async with self.client.messages.stream(
                model=self.model,
                max_tokens=4096,
                system=self.system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": f"Research Question: {question}\n\n{context}",
                    }
                ],
            ) as stream:
                async for text in stream.text_stream:
                    full_output += text
                    await event_queue.put(AgentEvent(
                        agent=self.name, type="chunk", content=text
                    ))

            # Signal completion
            await event_queue.put(AgentEvent(
                agent=self.name, type="complete", content=full_output, progress=100
            ))
            return full_output

        except Exception as e:
            error_msg = str(e)
            await event_queue.put(AgentEvent(
                agent=self.name, type="error", content=error_msg
            ))
            return f"[Agent {self.name} error: {error_msg}]"
