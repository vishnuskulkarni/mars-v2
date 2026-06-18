"""MARS v2 agents — structured, ledger-writing specialists (build spec v2 §4)."""

from mars.agents.checks import ChecksAgent
from mars.agents.critique import CritiqueAgent
from mars.agents.data import DataAgent
from mars.agents.hypothesis import HypothesisAgent
from mars.agents.literature import LiteratureAgent
from mars.agents.methods import MethodsAgent
from mars.agents.red_team import RedTeamAgent
from mars.agents.scout import ScoutAgent

__all__ = [
    "LiteratureAgent", "ScoutAgent", "DataAgent", "HypothesisAgent",
    "MethodsAgent", "CritiqueAgent", "RedTeamAgent", "ChecksAgent",
]
