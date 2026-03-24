import os
import json
import asyncio
import httpx
from backend.config import get_settings
from backend.models import AgentEvent


class BaseAgent:
    def __init__(self, name: str, prompt_file: str):
        self.name = name
        self.system_prompt = self._load_prompt(prompt_file)
        self.settings = get_settings()

    def _load_prompt(self, prompt_file: str) -> str:
        prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", prompt_file)
        with open(prompt_path, "r") as f:
            return f.read()

    async def run(self, context: str, question: str, event_queue: asyncio.Queue) -> str:
        """Run the agent with streaming. Pushes chunk events to the queue. Returns full output."""
        await event_queue.put(AgentEvent(
            agent=self.name, type="status", content="running", progress=0
        ))

        if self.settings.LLM_PROVIDER == "ollama":
            return await self._run_ollama(context, question, event_queue)
        else:
            return await self._run_anthropic(context, question, event_queue)

    async def _run_ollama(self, context: str, question: str, event_queue: asyncio.Queue) -> str:
        """Stream response from Ollama API."""
        full_output = ""
        url = f"{self.settings.OLLAMA_BASE_URL}/api/chat"
        payload = {
            "model": self.settings.OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"Research Question: {question}\n\n{context}"},
            ],
            "stream": True,
        }

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
                async with client.stream("POST", url, json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        chunk = data.get("message", {}).get("content", "")
                        if chunk:
                            full_output += chunk
                            await event_queue.put(AgentEvent(
                                agent=self.name, type="chunk", content=chunk
                            ))

                        if data.get("done", False):
                            break

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

    async def _run_anthropic(self, context: str, question: str, event_queue: asyncio.Queue) -> str:
        """Stream response from Anthropic Claude API."""
        from anthropic import AsyncAnthropic

        full_output = ""
        try:
            client = AsyncAnthropic(api_key=self.settings.ANTHROPIC_API_KEY)
            async with client.messages.stream(
                model=self.settings.CLAUDE_MODEL,
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
