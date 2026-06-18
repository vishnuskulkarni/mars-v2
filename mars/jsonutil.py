"""Robust JSON extraction for agent responses + a json-mode call helper.

Agents are asked to return a single JSON object. Models sometimes wrap it in
prose or markdown fences; this extracts the object tolerantly and retries once
with an explicit repair instruction if parsing fails.
"""

from __future__ import annotations

import json
from typing import Optional

from mars import models


def extract_json(text: str) -> Optional[dict]:
    """Pull the first balanced JSON object out of `text`. None if none parses."""
    if not text:
        return None
    # Direct parse first.
    try:
        obj = json.loads(text.strip())
        return obj if isinstance(obj, dict) else None
    except (json.JSONDecodeError, ValueError):
        pass
    # Strip ```json fences.
    fenced = text
    if "```" in fenced:
        parts = fenced.split("```")
        for p in parts:
            p = p.strip()
            if p.lower().startswith("json"):
                p = p[4:].strip()
            if p.startswith("{"):
                obj = _try_balanced(p)
                if obj is not None:
                    return obj
    # Scan for the first balanced {...}.
    return _try_balanced(text)


def _try_balanced(text: str) -> Optional[dict]:
    start = text.find("{")
    if start < 0:
        return None
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(text[start:i + 1])
                    return obj if isinstance(obj, dict) else None
                except (json.JSONDecodeError, ValueError):
                    return None
    return None


def call_json(agent_name: str, system: str, user: str, retries: int = 1) -> dict:
    """Call the model in json mode and return a parsed dict (or {} on failure)."""
    out = models.complete(agent_name, system, user, json_mode=True)
    obj = extract_json(out)
    if obj is not None:
        return obj
    for _ in range(retries):
        repair = (user + "\n\nYour previous reply did not parse as JSON. "
                  "Reply again with ONLY a single valid JSON object.")
        out = models.complete(agent_name, system, repair, json_mode=True)
        obj = extract_json(out)
        if obj is not None:
            return obj
    return {}
