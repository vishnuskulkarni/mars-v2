from __future__ import annotations

import time
from typing import Dict, List

import requests

from mars.agents.base import StructuredAgent

_SEMANTIC_SCHOLAR = "https://api.semanticscholar.org/graph/v1/paper/search"


class ScoutAgent(StructuredAgent):
    name = "scout"
    prompt_file = "scout.txt"

    def __init__(self):
        super().__init__()
        self.found_papers: List[Dict] = []

    def run(self, question: str, key_terms: List[str], uploaded_titles: str, focus: str = "") -> dict:
        """Generate queries -> real Semantic Scholar search -> assess.

        Returns {external_refs:[...], novelty_challenges:[...], found_papers:[...]}.
        """
        # Phase 1 — queries.
        q_user = (f'MODE "queries"\nResearch question: {question}\n'
                  f"Key terms: {', '.join(key_terms) if key_terms else '(none)'}\n"
                  f"Uploaded paper titles:\n{uploaded_titles}")
        if focus:
            q_user += f"\nEditorial focus: {focus}"
        queries = self.ask(q_user).get("queries") or ([" ".join(key_terms)] if key_terms else [question])

        # Phase 2 — real search.
        papers: List[Dict] = []
        for query in queries[:5]:
            papers.extend(self._search(query))
            time.sleep(1)
        seen, unique = set(), []
        for p in papers:
            t = (p.get("title") or "").lower().strip()
            if t and t not in seen:
                seen.add(t)
                unique.append(p)
        self.found_papers = unique
        if not unique:
            return {"external_refs": [], "novelty_challenges": [], "found_papers": []}

        # Phase 3 — assess.
        listing = "\n\n".join(
            f"Title: {p.get('title','N/A')}\n"
            f"Year: {p.get('year','N/A')} | Citations: {p.get('citationCount','N/A')}\n"
            f"Identifier: {self._identifier(p)}\n"
            f"Abstract: {(p.get('abstract') or 'No abstract')[:400]}"
            for p in unique[:20]
        )
        a_user = (f'MODE "assess"\nResearch question: {question}\n\n'
                  f"Retrieved papers ({len(unique)}):\n\n{listing}")
        out = self.ask(a_user)
        out.setdefault("external_refs", [])
        out.setdefault("novelty_challenges", [])
        out["found_papers"] = unique
        return out

    def references(self) -> List[str]:
        """Real identifiers/URLs retrieved this run (for the citation gate)."""
        refs = []
        for p in self.found_papers:
            if p.get("url"):
                refs.append(p["url"])
            ext = p.get("externalIds") or {}
            if ext.get("DOI"):
                refs.append(ext["DOI"])
            if ext.get("ArXiv"):
                refs.append(f"arXiv:{ext['ArXiv']}")
        return refs

    @staticmethod
    def _identifier(p: Dict) -> str:
        ext = p.get("externalIds") or {}
        if ext.get("DOI"):
            return ext["DOI"]
        if ext.get("ArXiv"):
            return f"arXiv:{ext['ArXiv']}"
        return p.get("url", "N/A")

    def _search(self, query: str) -> List[Dict]:
        try:
            resp = requests.get(
                _SEMANTIC_SCHOLAR,
                params={"query": query, "limit": 5,
                        "fields": "title,abstract,year,authors,citationCount,url,externalIds"},
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json().get("data", []) or []
        except Exception:
            pass
        return []
