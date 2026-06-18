"""Model-routing layer.

Every agent asks this layer for a completion via `complete(agent_name, ...)`.
The layer looks up the provider+model assigned to that agent in config.yaml and
dispatches to the matching backend (anthropic | openrouter | ollama), returning
the text response.

Design goals (see MARS_BUILD_SPEC.md §3):
  * One `complete()` signature; three thin adapter functions.
  * Per-agent provider assignment, set in config.yaml, reversible without code.
  * The provider+model that actually served each agent is recorded in the run
    manifest (the orchestrator calls `route_for()` for this).

Default is the lab Claude service-account key (`ANTHROPIC_API_KEY` in .env) for
every agent. OpenRouter and Ollama are wired but only used if an agent is
reassigned to them in config.yaml.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

import yaml
from dotenv import load_dotenv

# Repo root = parent of this package directory.
_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _ROOT / "config.yaml"

# Load .env once at import so the API keys are available process-wide.
load_dotenv(_ROOT / ".env")

VALID_PROVIDERS = ("anthropic", "openrouter", "ollama")


@dataclass(frozen=True)
class ModelRoute:
    """Which provider+model serves a given agent. Recorded in the manifest."""

    provider: str
    model: str


class ModelError(RuntimeError):
    """Raised for configuration or provider errors (missing key, bad provider)."""


# --------------------------------------------------------------------------- #
# Config loading
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def _load_config() -> Dict[str, Any]:
    if not _CONFIG_PATH.exists():
        raise ModelError(f"config.yaml not found at {_CONFIG_PATH}")
    with open(_CONFIG_PATH, "r") as f:
        cfg = yaml.safe_load(f) or {}
    cfg.setdefault("default_provider", "anthropic")
    cfg.setdefault("providers", {})
    cfg.setdefault("agents", {})
    return cfg


def reload_config() -> None:
    """Drop the cached config so an edit to config.yaml is picked up."""
    _load_config.cache_clear()


def get_config() -> Dict[str, Any]:
    """Public read-only access to the parsed config (routing, confidence,
    scoring, editorial, data_sandbox). Used by ledger/scoring/editorial."""
    return _load_config()


# --------------------------------------------------------------------------- #
# Model-call counter — the editorial cost ceiling counts calls this run.
# Thread-safe because Phase-2 specialists run concurrently.
# --------------------------------------------------------------------------- #
_call_lock = threading.Lock()
_call_count = 0


def reset_calls() -> None:
    global _call_count
    with _call_lock:
        _call_count = 0


def calls() -> int:
    with _call_lock:
        return _call_count


def _increment_calls() -> None:
    global _call_count
    with _call_lock:
        _call_count += 1


def route_for(agent_name: str) -> ModelRoute:
    """Resolve the provider+model assigned to `agent_name` from config.yaml."""
    cfg = _load_config()
    agent_cfg = cfg["agents"].get(agent_name, {}) or {}
    provider = agent_cfg.get("provider", cfg["default_provider"])
    if provider not in VALID_PROVIDERS:
        raise ModelError(
            f"Agent '{agent_name}' is routed to unknown provider '{provider}'. "
            f"Valid providers: {', '.join(VALID_PROVIDERS)}."
        )
    provider_cfg = cfg["providers"].get(provider, {}) or {}
    model = agent_cfg.get("model") or provider_cfg.get("model")
    if not model:
        raise ModelError(
            f"No model configured for provider '{provider}'. "
            f"Set providers.{provider}.model in config.yaml."
        )
    return ModelRoute(provider=provider, model=model)


def describe_routing() -> Dict[str, ModelRoute]:
    """Return the resolved route for every agent listed in config (for the UI)."""
    cfg = _load_config()
    return {name: route_for(name) for name in cfg["agents"]}


def _provider_setting(provider: str, key: str, default: Any = None) -> Any:
    return (_load_config()["providers"].get(provider, {}) or {}).get(key, default)


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def complete(agent_name: str, system: str, prompt: str, *, json_mode: bool = False) -> str:
    """Look up the model assigned to `agent_name` and return its text response.

    Dispatches to the right provider (anthropic | openrouter | ollama). Raises
    ModelError on configuration problems; provider/network errors propagate as
    the underlying exception so the orchestrator can record a clean failure.
    """
    route = route_for(agent_name)
    _increment_calls()
    if json_mode:
        system = (
            system
            + "\n\nIMPORTANT: Respond with a single valid JSON object only. "
            "No prose, no markdown fences."
        )

    if route.provider == "anthropic":
        return _complete_anthropic(route.model, system, prompt)
    if route.provider == "openrouter":
        return _complete_openrouter(route.model, system, prompt, json_mode)
    if route.provider == "ollama":
        return _complete_ollama(route.model, system, prompt, json_mode)
    raise ModelError(f"Unhandled provider '{route.provider}'.")  # pragma: no cover


# --------------------------------------------------------------------------- #
# Backend adapters
# --------------------------------------------------------------------------- #
def _complete_anthropic(model: str, system: str, prompt: str) -> str:
    """Standard Anthropic API call using the lab service-account key."""
    from anthropic import Anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise ModelError(
            "ANTHROPIC_API_KEY is not set. Add the lab Claude service-account "
            "key to .env (see .env.example)."
        )
    max_tokens = int(_provider_setting("anthropic", "max_tokens", 4096))
    client = Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in msg.content if getattr(block, "type", "") == "text")


def _complete_openrouter(model: str, system: str, prompt: str, json_mode: bool) -> str:
    """OpenAI-compatible call to OpenRouter (cheap open models). Optional path."""
    from openai import OpenAI

    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise ModelError(
            "OPENROUTER_API_KEY is not set, but an agent is routed to openrouter "
            "in config.yaml. Add the key to .env or reroute the agent."
        )
    max_tokens = int(_provider_setting("openrouter", "max_tokens", 4096))
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
    kwargs: Dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""


def _complete_ollama(model: str, system: str, prompt: str, json_mode: bool) -> str:
    """POST to a local Ollama server. No key. Optional local path."""
    import requests

    base_url = _provider_setting("ollama", "base_url", "http://localhost:11434")
    payload: Dict[str, Any] = {
        "model": model,
        "system": system,
        "prompt": prompt,
        "stream": False,
    }
    if json_mode:
        payload["format"] = "json"
    resp = requests.post(f"{base_url}/api/generate", json=payload, timeout=600)
    resp.raise_for_status()
    return resp.json().get("response", "")
