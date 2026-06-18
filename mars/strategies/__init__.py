"""Decomposition strategies (build spec v2 §9). ARIA is the default; dynamic is
a pluggable stub behind the same interface."""

from mars.strategies.aria import ARIAStrategy
from mars.strategies.base import DecompositionStrategy, PipelineContext
from mars.strategies.dynamic import DynamicStrategy

_REGISTRY = {"aria": ARIAStrategy, "dynamic": DynamicStrategy}


def get_strategy(name: str) -> DecompositionStrategy:
    return _REGISTRY.get((name or "aria").lower(), ARIAStrategy)()


def strategy_names():
    return list(_REGISTRY)


__all__ = ["DecompositionStrategy", "PipelineContext", "get_strategy", "strategy_names"]
