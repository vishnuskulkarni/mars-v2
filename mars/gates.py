"""Deterministic validation gates (build spec v2 §11). No LLM in the gate.

These run over the final evidence ledger and catch *format/grounding* failures —
fabricated citations and ungrounded numbers — before they reach the report. They
are SEPARATE from and complementary to the confidence scoring in §6 (which judges
quality/agreement). The honest claim is "catches fabricated citations and
ungrounded numbers before they propagate," NOT "eliminates hallucination."

In v2 the numeric-provenance gate is strong: the Data Explorer's numbers come
from real executed analyses, so every number in a data-grounded claim is checked
against that analysis's recorded numeric outputs / result summary.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Dict, List

_DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", re.IGNORECASE)
_ARXIV_RE = re.compile(r"\barxiv:\s*\d{4}\.\d{4,5}(v\d+)?\b", re.IGNORECASE)
_URL_RE = re.compile(r"https?://[^\s)\]}>\"']+", re.IGNORECASE)
_QUOTE_RE = re.compile(r"[\"“]([^\"“”]{20,400})[\"”]")
_NUM_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")

_SCHOLARLY = ("doi.org", "arxiv.org", "semanticscholar.org", "ncbi.nlm.nih.gov", "pubmed",
              "springer.com", "sciencedirect.com", "nature.com", "jstor.org", "acm.org",
              "ieee", "researchgate.net", "ssrn.com", "biorxiv.org", "medrxiv.org",
              "plos.org", "wiley.com", "tandfonline.com", "sagepub.com", "oup.com",
              "cambridge.org", "mdpi.com", "elsevier.com", ".edu")


@dataclass
class GateResult:
    name: str
    passed: bool
    detail: str
    checked: int = 0
    failed: int = 0
    flagged: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {"name": self.name, "passed": self.passed, "detail": self.detail,
                "checked": self.checked, "failed": self.failed, "flagged": self.flagged[:25]}


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "")).lower().strip()


def _scholarly(url: str) -> bool:
    m = re.match(r"https?://([^/]+)", url, re.IGNORECASE)
    host = m.group(1).lower() if m else ""
    return any(s in host for s in _SCHOLARLY)


# --------------------------------------------------------------------------- #
# Gate 1 — schema conformance
# --------------------------------------------------------------------------- #
def gate_schema(ledger) -> GateResult:
    flagged, checked = [], 0
    for c in ledger.claims.values():
        checked += 1
        if not (c.text and c.text.strip()) or not c.raised_by:
            flagged.append(f"claim {c.id}: missing text/author")
    for d in ledger.directions.values():
        checked += 1
        if not (d.title and d.statement):
            flagged.append(f"direction {d.id}: missing title/statement")
    for a in ledger.analyses.values():
        checked += 1
        if not a.id or not a.kind:
            flagged.append(f"analysis {a.id}: missing id/kind")
    passed = not flagged
    return GateResult("schema_conformance", passed,
                      f"{checked - len(flagged)}/{checked} records well-formed.", checked,
                      len(flagged), flagged)


# --------------------------------------------------------------------------- #
# Gate 2 — citation resolution
# --------------------------------------------------------------------------- #
def gate_citations(ledger, uploaded_titles: List[str], scout_refs: List[str]) -> GateResult:
    titles_norm = [_norm(t) for t in uploaded_titles]
    refs_norm = {_norm(r) for r in scout_refs}
    flagged, checked = [], 0

    for c in ledger.claims.values():
        for g in c.grounded_in:
            checked += 1
            ref, rn = g.ref, _norm(g.ref)
            if g.type == "paper":
                if not any(rn in t or t in rn or _stem(rn) in t for t in titles_norm):
                    flagged.append(f"{c.id}: paper '{ref}' not in uploaded set")
            elif g.type == "external":
                ok = (_DOI_RE.search(ref) or _ARXIV_RE.search(ref)
                      or (_URL_RE.search(ref) and _scholarly(ref)) or rn in refs_norm
                      or any(rn in r or r in rn for r in refs_norm))
                if not ok:
                    flagged.append(f"{c.id}: external ref '{ref}' unresolved")
            elif g.type == "data":
                if ref not in ledger.analyses:
                    flagged.append(f"{c.id}: data ref '{ref}' has no analysis record")

    if checked == 0:
        return GateResult("citation_resolution", True, "No groundings to resolve.", 0, 0)
    passed = not flagged
    detail = f"{checked - len(flagged)}/{checked} groundings resolve to a real source."
    if flagged:
        detail += f" {len(flagged)} unresolved (flagged)."
    return GateResult("citation_resolution", passed, detail, checked, len(flagged), flagged)


def _stem(s: str) -> str:
    return " ".join(s.split()[:6])


# --------------------------------------------------------------------------- #
# Gate 3 — quote grounding
# --------------------------------------------------------------------------- #
def gate_quotes(ledger, source_text: str) -> GateResult:
    source = _norm(source_text)
    quotes = []
    for c in ledger.claims.values():
        for m in _QUOTE_RE.finditer(c.text or ""):
            q = m.group(1)
            if len(q.split()) >= 6:
                quotes.append((c.id, q))
    if not source:
        return GateResult("quote_grounding", True, "No source text to ground against.", 0, 0)
    if not quotes:
        return GateResult("quote_grounding", True, "No attributed quotes to check.", 0, 0)

    flagged = []
    for cid, q in quotes[:40]:
        nq = _norm(q)
        grounded = nq in source
        if not grounded:
            match = SequenceMatcher(None, nq, source, autojunk=False).find_longest_match(0, len(nq), 0, len(source))
            grounded = (match.size / max(1, len(nq))) >= 0.6
        if not grounded:
            flagged.append(f"{cid}: {q[:80]}")
    passed = not flagged
    detail = f"{len(quotes) - len(flagged)}/{len(quotes)} quotes grounded in the uploaded source."
    if flagged:
        detail += f" {len(flagged)} not located (flagged)."
    return GateResult("quote_grounding", passed, detail, len(quotes), len(flagged), flagged)


# --------------------------------------------------------------------------- #
# Gate 4 — numeric provenance (traces to executed analyses)
# --------------------------------------------------------------------------- #
def _traces(raw: str, x: float, numbers: List[float], summary: str) -> bool:
    if raw in (summary or "") or raw.replace(",", "") in (summary or ""):
        return True
    for a in numbers or []:
        try:
            a = float(a)
        except (TypeError, ValueError):
            continue
        if abs(x - a) <= 0.01 * max(1.0, abs(a)) or round(x, 2) == round(a, 2):
            return True
        if abs(x - a * 100) <= 0.01 * max(1.0, abs(a * 100)):  # proportion vs percent
            return True
    return False


def gate_numeric(ledger) -> GateResult:
    flagged, checked = [], 0
    for c in ledger.claims.values():
        data_refs = [g.ref for g in c.grounded_in if g.type == "data"]
        if not data_refs:
            continue
        pooled_numbers, pooled_summary = [], ""
        for ref in data_refs:
            a = ledger.analyses.get(ref)
            if a:
                pooled_numbers += list(a.numbers or [])
                pooled_summary += " " + (a.result_summary or "")
        for raw in _NUM_RE.findall(c.text or ""):
            cleaned = raw.replace(",", "")
            try:
                x = float(cleaned)
            except ValueError:
                continue
            if x == int(x) and abs(x) <= 1:  # skip trivial 0/1
                continue
            checked += 1
            if not _traces(raw, x, pooled_numbers, pooled_summary):
                flagged.append(f"{c.id}: {raw}")
    if checked == 0:
        return GateResult("numeric_provenance", True, "No data-grounded numbers to trace.", 0, 0)
    passed = len(flagged) == 0
    detail = (f"{checked - len(flagged)}/{checked} data-grounded numbers trace to a "
              f"re-runnable analysis's outputs.")
    if flagged:
        detail += f" {len(flagged)} could not be traced (flagged)."
    return GateResult("numeric_provenance", passed, detail, checked, len(flagged), flagged)


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #
def run_all(ledger, source_text: str = "", uploaded_titles=None, scout_references=None) -> List[GateResult]:
    return [
        gate_schema(ledger),
        gate_citations(ledger, uploaded_titles or [], scout_references or []),
        gate_quotes(ledger, source_text),
        gate_numeric(ledger),
    ]
