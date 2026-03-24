import asyncio
import json
import re
import httpx
from backend.agents.base import BaseAgent
from backend.models import AgentEvent


class ScoutAgent(BaseAgent):
    def __init__(self):
        super().__init__("scout", "scout.txt")

    async def run(self, paper_titles: str, question: str, event_queue: asyncio.Queue) -> str:
        """Two-phase agent: generate queries via LLM, search APIs, then assess results via LLM."""
        await event_queue.put(AgentEvent(
            agent=self.name, type="status", content="running", progress=0
        ))

        try:
            # Phase 1: Ask LLM to generate search queries
            query_context = (
                f"Uploaded paper titles:\n{paper_titles}\n\n"
                "Generate 3-5 diverse search queries to find related papers."
            )
            query_output = await self._call_llm(query_context, question)

            await event_queue.put(AgentEvent(
                agent=self.name, type="chunk", content="Generating search queries...\n\n"
            ))

            # Parse queries from LLM output
            queries = self._extract_queries(query_output)
            if not queries:
                queries = [question]  # Fallback to research question itself

            # Phase 2: Search Semantic Scholar
            all_papers = []
            for q in queries:
                await event_queue.put(AgentEvent(
                    agent=self.name, type="chunk", content=f"Searching: {q}\n"
                ))
                papers = await self._search_semantic_scholar(q)
                all_papers.extend(papers)
                await asyncio.sleep(1)  # Rate limiting

            # Deduplicate
            seen_titles = set()
            unique_papers = []
            for p in all_papers:
                title_lower = p.get("title", "").lower().strip()
                if title_lower and title_lower not in seen_titles:
                    seen_titles.add(title_lower)
                    unique_papers.append(p)

            if not unique_papers:
                result = "No additional papers found via Semantic Scholar."
                await event_queue.put(AgentEvent(
                    agent=self.name, type="complete", content=result, progress=100
                ))
                return result

            # Phase 3: Send results to LLM for assessment
            papers_text = "\n\n".join(
                f"Title: {p.get('title', 'N/A')}\n"
                f"Authors: {', '.join(a.get('name', '') for a in p.get('authors', [])[:3])}\n"
                f"Year: {p.get('year', 'N/A')}\n"
                f"Citations: {p.get('citationCount', 'N/A')}\n"
                f"Abstract: {(p.get('abstract') or 'No abstract')[:500]}\n"
                f"URL: {p.get('url', 'N/A')}"
                for p in unique_papers[:20]
            )

            assess_context = (
                f"Uploaded paper titles:\n{paper_titles}\n\n"
                f"Search results ({len(unique_papers)} papers found):\n\n{papers_text}\n\n"
                "Now assess these papers for relevance and produce your scout report."
            )

            full_output = ""
            if self.settings.LLM_PROVIDER == "ollama":
                full_output = await self._stream_ollama(assess_context, question, event_queue)
            else:
                full_output = await self._stream_anthropic(assess_context, question, event_queue)

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

    async def _call_llm(self, context: str, question: str) -> str:
        """Non-streaming LLM call for query generation."""
        if self.settings.LLM_PROVIDER == "ollama":
            url = f"{self.settings.OLLAMA_BASE_URL}/api/chat"
            payload = {
                "model": self.settings.OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": f"Research Question: {question}\n\n{context}"},
                ],
                "stream": False,
            }
            async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                return resp.json().get("message", {}).get("content", "")
        else:
            from anthropic import AsyncAnthropic
            client = AsyncAnthropic(api_key=self.settings.ANTHROPIC_API_KEY)
            msg = await client.messages.create(
                model=self.settings.CLAUDE_MODEL,
                max_tokens=1024,
                system=self.system_prompt,
                messages=[{"role": "user", "content": f"Research Question: {question}\n\n{context}"}],
            )
            return msg.content[0].text

    async def _stream_ollama(self, context: str, question: str, event_queue: asyncio.Queue) -> str:
        """Streaming Ollama call for assessment phase."""
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
                        await event_queue.put(AgentEvent(agent=self.name, type="chunk", content=chunk))
                    if data.get("done", False):
                        break
        return full_output

    async def _stream_anthropic(self, context: str, question: str, event_queue: asyncio.Queue) -> str:
        """Streaming Anthropic call for assessment phase."""
        from anthropic import AsyncAnthropic
        full_output = ""
        client = AsyncAnthropic(api_key=self.settings.ANTHROPIC_API_KEY)
        async with client.messages.stream(
            model=self.settings.CLAUDE_MODEL,
            max_tokens=4096,
            system=self.system_prompt,
            messages=[{"role": "user", "content": f"Research Question: {question}\n\n{context}"}],
        ) as stream:
            async for text in stream.text_stream:
                full_output += text
                await event_queue.put(AgentEvent(agent=self.name, type="chunk", content=text))
        return full_output

    async def _search_semantic_scholar(self, query: str) -> list:
        """Search Semantic Scholar API. Falls back to empty list on failure."""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
                resp = await client.get(
                    "https://api.semanticscholar.org/graph/v1/paper/search",
                    params={
                        "query": query,
                        "limit": 5,
                        "fields": "title,abstract,year,authors,citationCount,url",
                    },
                )
                if resp.status_code == 200:
                    return resp.json().get("data", [])
        except Exception:
            pass
        return []

    def _extract_queries(self, llm_output: str) -> list:
        """Extract search queries from LLM output JSON block."""
        # Try to find JSON block
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', llm_output, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                return data.get("queries", [])
            except json.JSONDecodeError:
                pass
        # Try raw JSON
        try:
            data = json.loads(llm_output)
            return data.get("queries", [])
        except (json.JSONDecodeError, ValueError):
            pass
        return []
